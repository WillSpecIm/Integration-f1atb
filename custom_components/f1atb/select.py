"""Selects F1ATB : forme d'onde (mode) et forçage (marche/arrêt)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_FORCE_MINUTES,
    DEFAULT_FORCE_MINUTES,
    DOMAIN,
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    FORCE_MODES,
)
from .entity import F1atbActionEntity
from .helpers import (
    async_setup_action_platform,
    mode_label_to_value,
    mode_options,
    mode_value_to_label,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    def factory(index: int) -> list:
        return [
            FormeOndeSelect(coordinator, index),
            ForcageSelect(coordinator, index, entry),
        ]

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)


class FormeOndeSelect(F1atbActionEntity, SelectEntity):
    """Forme d'onde (mode) de l'action. Écrit via /ParaNew (persistant)."""

    _attr_icon = "mdi:sine-wave"
    _kind = "forme_onde"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_forme_onde_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} forme d'onde"

    @property
    def available(self) -> bool:
        # Le mode vient de /ParaFixe : pas de config = pas d'affichage « Inactif » trompeur.
        return super().available and self._config_ok

    @property
    def _is_triac(self) -> bool:
        a = self._action
        return bool(a.get("is_triac")) if a else self._index == 0

    @property
    def options(self) -> list[str]:
        return mode_options(self._is_triac)

    @property
    def current_option(self) -> str | None:
        a = self._action
        if not a:
            return None
        return mode_value_to_label(a.get("mode", 0), self._is_triac)

    async def async_select_option(self, option: str) -> None:
        value = mode_label_to_value(option, self._is_triac)
        if value is None:
            return
        idx = self._index

        def _mutate(config: dict) -> None:
            actions = config.get("Actions") or []
            if 0 <= idx < len(actions):
                actions[idx]["Actif"] = value

        await self.coordinator.client.async_patch_config(_mutate)
        await self._write_and_refresh(config_change=True)


class ForcageSelect(F1atbActionEntity, SelectEntity):
    """Forçage du routage : Auto / Marche forcée / Arrêt forcé. Écrit via /ForceAction."""

    _attr_icon = "mdi:gesture-tap-button"
    _attr_options = FORCE_MODES
    _kind = "forcage"

    def __init__(self, coordinator, index: int, entry: ConfigEntry) -> None:
        super().__init__(coordinator, index)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.entry.unique_id}_forcage_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} forçage"

    @property
    def current_option(self) -> str | None:
        a = self._action
        if not a:
            return None
        force = a.get("force", 0) or 0
        if force > 0:
            return MODE_ON
        if force < 0:
            return MODE_OFF
        return MODE_AUTO

    @property
    def extra_state_attributes(self) -> dict:
        a = self._action
        force = (a.get("force", 0) or 0) if a else 0
        return {**super().extra_state_attributes, "minutes_restantes": abs(force)}

    async def async_select_option(self, option: str) -> None:
        minutes = int(
            self._entry.options.get(CONF_FORCE_MINUTES, DEFAULT_FORCE_MINUTES)
        )
        if option == MODE_ON:
            force = minutes
        elif option == MODE_OFF:
            force = -minutes
        else:
            force = 0
        await self.coordinator.client.async_force_action(self._index, force)
        await self._write_and_refresh(config_change=False)
