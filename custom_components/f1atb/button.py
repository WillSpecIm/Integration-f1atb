"""Button F1ATB : calibration auto de la puissance max (par action active)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import F1atbActionEntity
from .helpers import async_setup_action_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    def factory(index: int) -> list:
        return [CalibrationButton(coordinator, index)]

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)


class CalibrationButton(F1atbActionEntity, ButtonEntity):
    """Lance la calibration : ouvre à 100 %, mesure la puissance routée, l'enregistre.

    N'empêche pas la saisie manuelle de « Puissance max de l'appareil » (les deux
    écrivent la même valeur ; la dernière action gagne).
    """

    _attr_icon = "mdi:ruler"
    _attr_entity_category = EntityCategory.CONFIG
    _kind = "calibrer"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_calibrer_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} calibrer puissance max"

    async def async_press(self) -> None:
        # Tâche de fond : la procédure dure ~15 s (délai d'adaptation + moyenne sur 10 s).
        self.hass.async_create_task(self.coordinator.async_calibrate(self._index))
