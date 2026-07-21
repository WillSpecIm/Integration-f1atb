"""Capteurs F1ATB : puissances de routage (global) + ouverture % (par action active)."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import F1atbActionEntity, F1atbBaseEntity
from .helpers import async_setup_action_platform, temp_channel_indices

# Au-delà de cet écart entre deux mesures (redémarrage HA, routeur coupé), on n'intègre
# pas l'intervalle : on ignore la période au lieu d'inventer de l'énergie.
INTEGRATION_MAX_DT = 600  # secondes


@dataclass(frozen=True, kw_only=True)
class F1atbSensorDesc(SensorEntityDescription):
    value: Callable[[dict], float | None]


GLOBAL_SENSORS: tuple[F1atbSensorDesc, ...] = (
    F1atbSensorDesc(
        key="grid_import_power",
        name="Soutirée réseau",
        icon="mdi:transmission-tower-export",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("grid_import_power"),
    ),
    F1atbSensorDesc(
        key="grid_export_power",
        name="Injectée réseau",
        icon="mdi:transmission-tower-import",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("grid_export_power"),
    ),
    F1atbSensorDesc(
        key="routed_power",
        name="Puissance routée",
        icon="mdi:sine-wave",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("routed_power"),
    ),
    F1atbSensorDesc(
        key="routed_energy_total",
        name="Énergie routée totale",
        icon="mdi:lightning-bolt-outline",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        # Compteur à vie : ne se remet JAMAIS à zéro → parfait pour le tableau de bord Énergie.
        value=lambda d: (
            None if d.get("routed_energy_total") is None
            else round(d["routed_energy_total"] / 1000, 3)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Capteurs globaux + "routé aujourd'hui" calculé par intégration de la puissance
    entities: list = [F1atbGlobalSensor(coordinator, desc) for desc in GLOBAL_SENSORS]
    entities.append(F1atbRoutedTodaySensor(coordinator))
    async_add_entities(entities)

    # Capteur ouverture % par action active (dynamique)
    def factory(index: int) -> list:
        return [OuvertureSensor(coordinator, index)]

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)

    # Capteurs de température des canaux configurés 0..3 (dynamique)
    def temp_factory(channel: int) -> list:
        return [TemperatureSensor(coordinator, channel)]

    async_setup_action_platform(
        entry, coordinator, async_add_entities, temp_factory, keys_fn=temp_channel_indices
    )


class F1atbGlobalSensor(F1atbBaseEntity, SensorEntity):
    entity_description: F1atbSensorDesc

    def __init__(self, coordinator, description: F1atbSensorDesc) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict:
        return {"f1atb_kind": self.entity_description.key}


@dataclass
class _RoutedTodayExtra(ExtraStoredData):
    """État persisté du cumul journalier (survit à un redémarrage de HA)."""

    accum_wh: float | None
    day: str | None

    def as_dict(self) -> dict:
        return {"accum_wh": self.accum_wh, "day": self.day}


class F1atbRoutedTodaySensor(F1atbBaseEntity, SensorEntity, RestoreEntity):
    """Énergie routée aujourd'hui, calculée par INTÉGRATION de la puissance routée.

    Le compteur d'énergie « du jour » du firmware est sur-compté (surtout quand l'alimentation
    du routeur est coupée : sauts d'horloge au reboot → intégration faussée). On intègre donc
    la puissance routée (physiquement bornée, elle, correcte) côté HA, en trapèzes, et on remet
    à zéro à minuit local. Résultat fiable et cohérent, indépendant des reboots du routeur.
    """

    _attr_name = "Énergie routée aujourd'hui"
    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_routed_energy_today"
        self._accum: float = 0.0          # Wh accumulés aujourd'hui
        self._day: str | None = None      # date locale du cumul courant
        self._last_ts = None              # datetime UTC de la dernière mesure intégrée
        self._last_power: float = 0.0     # dernière puissance routée (W)
        self._value: float = 0.0          # kWh du jour

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        if extra is not None:
            d = extra.as_dict()
            self._accum = float(d.get("accum_wh") or 0.0)
            self._day = d.get("day")
        # Si HA reprend un autre jour, on repartira de zéro au 1er échantillon.
        self._value = round(self._accum / 1000.0, 3)

    @property
    def extra_restore_state_data(self) -> _RoutedTodayExtra:
        return _RoutedTodayExtra(self._accum, self._day)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._integrate()
        super()._handle_coordinator_update()

    def _integrate(self) -> None:
        # Pas d'intégration si le routeur est injoignable (données périmées).
        if not self.coordinator.last_update_success:
            return
        power = (self.coordinator.data or {}).get("routed_power")
        if power is None:
            return
        try:
            power = max(0.0, float(power))
        except (TypeError, ValueError):
            return

        now = dt_util.utcnow()
        today = dt_util.now().date().isoformat()

        if self._day != today:  # nouveau jour (ou 1re fois) → remise à zéro
            self._day = today
            self._accum = 0.0
            self._last_ts = now
            self._last_power = power
            self._value = 0.0
            return

        if self._last_ts is not None:
            dt = (now - self._last_ts).total_seconds()
            if 0 < dt <= INTEGRATION_MAX_DT:
                # Trapèze : énergie (Wh) = puissance moyenne × durée / 3600
                self._accum += (self._last_power + power) / 2.0 * dt / 3600.0
        self._last_ts = now
        self._last_power = power
        self._value = round(self._accum / 1000.0, 3)

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict:
        return {"f1atb_kind": "routed_energy_today", "methode": "intégration de la puissance (HA)"}


class TemperatureSensor(F1atbBaseEntity, SensorEntity):
    """Température d'un canal configuré (DS18B20 interne / externe / MQTT).

    Un canal (0..3) est exposé s'il est configuré côté routeur (Source_Temp ≠ « tempNo »).
    L'entité se retire d'elle-même si le canal disparaît de la config.
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator, channel: int) -> None:
        super().__init__(coordinator)
        self._channel = channel
        self._attr_unique_id = f"{coordinator.entry.unique_id}_temperature_{channel}"

    @property
    def _chan(self) -> dict | None:
        return (self.coordinator.data or {}).get("temp_channels", {}).get(self._channel)

    @property
    def name(self) -> str:
        c = self._chan
        return (c.get("name") if c else None) or f"Température {self._channel}"

    @property
    def available(self) -> bool:
        c = self._chan
        return super().available and c is not None and c.get("value") is not None

    @property
    def native_value(self) -> float | None:
        c = self._chan
        if not c or c.get("value") is None:
            return None
        return round(float(c["value"]), 1)

    @property
    def extra_state_attributes(self) -> dict:
        c = self._chan or {}
        return {
            "f1atb_kind": "temperature",
            "temp_channel": self._channel,
            "source": c.get("source"),
            "nom": c.get("name"),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._remove_if_gone))

    @callback
    def _remove_if_gone(self) -> None:
        if self._channel not in (self.coordinator.data or {}).get("temp_channels", {}):
            self.hass.async_create_task(self.async_remove(force_remove=True))


class OuvertureSensor(F1atbActionEntity, SensorEntity):
    """Ouverture instantanée du routage (%) pour une action active."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _kind = "ouverture"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_ouverture_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} ouverture"

    @property
    def native_value(self) -> float | None:
        a = self._action
        return None if a is None else a.get("opening")
