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
        # Compteur à vie (Shelly) : ne se remet JAMAIS à zéro → parfait pour le tableau
        # de bord Énergie (HA calcule jour/mois tout seul, insensible aux reboots).
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

    # Capteurs globaux (toujours présents) + "routé aujourd'hui" robuste (anti-reset reboot)
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
    """Référence persistée pour recalculer le journalier après un redémarrage de HA."""

    baseline: float | None
    day: str | None

    def as_dict(self) -> dict:
        return {"baseline": self.baseline, "day": self.day}


class F1atbRoutedTodaySensor(F1atbBaseEntity, SensorEntity, RestoreEntity):
    """Énergie routée aujourd'hui, calculée depuis le compteur CUMULÉ (à vie).

    valeur = cumulé − cumulé_à_minuit. Insensible aux redémarrages du routeur (le cumulé
    ne se remet pas à zéro), et la référence de minuit est persistée côté HA (survit aussi
    à un redémarrage de Home Assistant). Repart de zéro à minuit (heure locale HA).
    """

    _attr_name = "Énergie routée aujourd'hui"
    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_routed_energy_today"
        self._baseline: float | None = None   # cumulé (Wh) à minuit
        self._day: str | None = None          # date locale de la référence
        self._value: float | None = None      # kWh du jour

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        if extra is not None:
            d = extra.as_dict()
            self._baseline = d.get("baseline")
            self._day = d.get("day")
        self._recompute()

    @property
    def extra_restore_state_data(self) -> _RoutedTodayExtra:
        return _RoutedTodayExtra(self._baseline, self._day)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._recompute()
        super()._handle_coordinator_update()

    def _recompute(self) -> None:
        total = (self.coordinator.data or {}).get("routed_energy_total")  # Wh cumulés
        if total is None:
            return
        today = dt_util.now().date().isoformat()
        # Nouveau jour, 1re fois, ou compteur reculé (reset Shelly) → on re-cale la référence.
        if self._day != today or self._baseline is None or total < self._baseline:
            self._day = today
            self._baseline = total
        self._value = round(max(0.0, total - self._baseline) / 1000.0, 3)

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict:
        return {"f1atb_kind": "routed_energy_today"}


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
