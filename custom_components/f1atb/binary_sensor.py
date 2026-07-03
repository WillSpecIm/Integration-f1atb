"""Binary sensor F1ATB : connectivité du routeur (toujours présent)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import F1atbBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([F1atbConnectedBinarySensor(coordinator)])


class F1atbConnectedBinarySensor(F1atbBaseEntity, BinarySensorEntity):
    """« Connecté » : ON tant que le routeur répond, OFF sinon.

    Reste TOUJOURS disponible (contrairement aux autres entités) pour pouvoir rapporter
    l'état déconnecté → permet de suivre quand le routeur est en marche (historique).
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Connecté"
    _attr_icon = "mdi:router-wireless"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_connected"

    @property
    def available(self) -> bool:
        # Toujours dispo : doit pouvoir afficher "Déconnecté" quand le routeur est coupé.
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    def extra_state_attributes(self) -> dict:
        return {"f1atb_kind": "connected"}
