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
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import F1atbActionEntity, F1atbBaseEntity
from .helpers import async_setup_action_platform


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
        key="routed_energy_today",
        name="Énergie routée aujourd'hui",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda d: (
            None if d.get("routed_energy_today") is None
            else round(d["routed_energy_today"] / 1000, 3)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Capteurs globaux (toujours présents)
    async_add_entities(F1atbGlobalSensor(coordinator, desc) for desc in GLOBAL_SENSORS)

    # Capteur ouverture % par action active (dynamique)
    def factory(index: int) -> list:
        return [OuvertureSensor(coordinator, index)]

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)


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
