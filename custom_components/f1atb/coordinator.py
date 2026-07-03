"""Coordinateur de mise à jour des données F1ATB.

- Données LIVE (puissances, énergies, état des actions actives, système) : chaque cycle.
- CONFIG (/ParaFixe : mode/forme d'onde `Actif`, `ForceOuvre`) : rafraîchie périodiquement
  (capte aussi les changements faits depuis l'interface web du routeur) et juste après une écriture.
Le mode + ForceOuvre sont fusionnés dans chaque action live pour simplifier les entités.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import F1atbApiError, F1atbClient

_LOGGER = logging.getLogger(__name__)

CONFIG_EVERY = 6  # rafraîchir la config tous les N cycles (~30 s à 5 s d'intervalle)


class F1atbCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: F1atbClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="F1ATB Solar Router",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry
        self.config: dict = {}
        self.force_minutes: dict[int, int] = {}  # durée de forçage choisie dans HA, par action
        self._config_countdown = 0

    async def async_refresh_config(self) -> None:
        """Relit la config complète (après une écriture, pour refléter le changement)."""
        try:
            self.config = await self.client.async_get_config()
            self._config_countdown = CONFIG_EVERY
        except F1atbApiError as err:
            _LOGGER.warning("Relecture config échouée: %s", err)

    async def _async_update_data(self) -> dict:
        try:
            data = await self.client.async_get_data()
        except F1atbApiError as err:
            raise UpdateFailed(str(err)) from err

        if self._config_countdown <= 0:
            try:
                self.config = await self.client.async_get_config()
            except F1atbApiError as err:
                _LOGGER.debug("Config non rafraîchie: %s", err)
            self._config_countdown = CONFIG_EVERY
        self._config_countdown -= 1

        # Fusion mode (Actif) + ForceOuvre depuis la config, dans chaque action active
        cfg_actions = self.config.get("Actions") or []
        for idx, a in (data.get("actions") or {}).items():
            cfg = cfg_actions[idx] if 0 <= idx < len(cfg_actions) else {}
            a["mode"] = int(cfg.get("Actif", 0) or 0)
            a["force_ouvre"] = int(cfg.get("ForceOuvre", 0) or 0)
            a["is_triac"] = idx == 0
        return data
