"""Number F1ATB : ouverture max (ForceOuvre) de l'action."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
        return [OuvertureMaxNumber(coordinator, index)]

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)


class OuvertureMaxNumber(F1atbActionEntity, NumberEntity):
    """Ouverture max si forcée (champ ForceOuvre). Écrit via /ParaNew (persistant)."""

    _attr_icon = "mdi:gauge"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _kind = "ouverture_max"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_ouverture_max_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} ouverture max"

    @property
    def native_value(self) -> float | None:
        a = self._action
        return None if a is None else float(a.get("force_ouvre", 0) or 0)

    async def async_set_native_value(self, value: float) -> None:
        idx = self._index
        v = int(max(0, min(100, value)))

        def _mutate(config: dict) -> None:
            actions = config.get("Actions") or []
            if 0 <= idx < len(actions):
                actions[idx]["ForceOuvre"] = v

        await self.coordinator.client.async_patch_config(_mutate)
        await self._write_and_refresh(config_change=True)
