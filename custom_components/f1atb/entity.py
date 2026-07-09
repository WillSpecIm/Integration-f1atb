"""Base commune des entités F1ATB."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import F1atbCoordinator


class F1atbBaseEntity(CoordinatorEntity[F1atbCoordinator]):
    """Entité rattachée au device routeur."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator)
        cfg = coordinator.config or {}
        uid = coordinator.entry.unique_id or coordinator.entry.entry_id
        # Routeur hors tension : la config est vide → on retombe sur le titre de l'entrée
        # (le nom du routeur, posé par le config_flow) pour ne pas renommer l'appareil.
        name = (
            cfg.get("Routeur")
            or cfg.get("hostname")
            or coordinator.entry.title
            or "Routeur F1ATB"
        )
        info = DeviceInfo(
            identifiers={(DOMAIN, str(uid))},
            name=name,
            manufacturer="F1ATB",
            model="Solar Router (RMS ESP32)",
            configuration_url=coordinator.client.base_url,
        )
        version = cfg.get("VersionStocke")
        if version:  # ne pas effacer la version connue quand le routeur est éteint
            info["sw_version"] = str(version)
        self._attr_device_info = info


class F1atbActionEntity(F1atbBaseEntity):
    """Entité liée à UNE action (index). Se retire toute seule si l'action devient inactive."""

    _kind: str = ""  # identifie le rôle pour la carte Lovelace (forme_onde, ouverture_max…)

    def __init__(self, coordinator: F1atbCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self._index = index

    @property
    def _action(self) -> dict | None:
        return (self.coordinator.data or {}).get("actions", {}).get(self._index)

    @property
    def extra_state_attributes(self) -> dict:
        # Permet à la carte de grouper de façon fiable (par action + rôle).
        return {
            "f1atb_kind": self._kind,
            "action_index": self._index,
            "action_name": self._action_name,
        }

    @property
    def _action_name(self) -> str:
        a = self._action
        return (a.get("name") if a else None) or f"Action {self._index}"

    @property
    def _config_ok(self) -> bool:
        """La config (/ParaFixe) de cette action est-elle connue ? (sinon mode/ForceOuvre = 0)."""
        a = self._action
        return bool(a and a.get("config_ok"))

    @property
    def available(self) -> bool:
        return super().available and self._action is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Se retire de HA si l'action n'est plus active (dynamique).
        self.async_on_remove(
            self.coordinator.async_add_listener(self._remove_if_inactive)
        )

    @callback
    def _remove_if_inactive(self) -> None:
        if self._index not in (self.coordinator.data or {}).get("actions", {}):
            self.hass.async_create_task(self.async_remove(force_remove=True))

    async def _write_and_refresh(self, config_change: bool) -> None:
        """Après une écriture : relit (config si besoin) et met à jour l'état HA."""
        if config_change:
            await self.coordinator.async_refresh_config()
        await self.coordinator.async_request_refresh()
