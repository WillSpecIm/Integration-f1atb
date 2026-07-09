"""Coordinateur de mise à jour des données F1ATB.

- Données LIVE (puissances, énergies, état des actions actives, système) : chaque cycle.
- CONFIG (/ParaFixe : mode/forme d'onde `Actif`, `ForceOuvre`) : rafraîchie périodiquement
  (capte aussi les changements faits depuis l'interface web du routeur) et juste après une écriture.
Le mode + ForceOuvre sont fusionnés dans chaque action live pour simplifier les entités.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import F1atbApiError, F1atbClient

_LOGGER = logging.getLogger(__name__)

CONFIG_EVERY = 6  # rafraîchir la config tous les N cycles (~30 s à 5 s d'intervalle)

# --- Calibration auto de la puissance max ---
CALIB_FORCE_MINUTES = 2   # forçage court = sécurité si le retour Auto échoue
CALIB_SETTLE_S = 5        # délai pour que la mesure s'adapte après ouverture à 100 %
CALIB_SAMPLES = 5         # nombre d'échantillons de puissance routée…
CALIB_INTERVAL_S = 2      # …espacés de N s (≈ 10 s de moyenne)


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
        # Calibration côté HA (le firmware n'a pas ce champ) : puissance consommée par
        # l'appareil à 100 % d'ouverture, par action. Sert au mode "puissance à router".
        self.appliance_max_power: dict[int, float] = {}
        self._calibrating: set[int] = set()
        self._config_countdown = 0

    def is_calibrating(self, index: int) -> bool:
        return index in self._calibrating

    async def async_calibrate(self, index: int) -> None:
        """Calibre la puissance max : ouvre à 100 %, laisse la mesure s'adapter, moyenne
        la puissance routée sur ~10 s, enregistre le résultat, puis repasse en Auto.

        Sécurité : forçage court (CALIB_FORCE_MINUTES) et retour Auto dans un `finally`,
        pour ne jamais laisser l'appareil forcé en marche si quelque chose échoue.
        """
        if index in self._calibrating:
            return
        self._calibrating.add(index)
        self.async_update_listeners()  # rafraîchit l'UI (calibration en cours)
        try:
            def _mutate(config: dict) -> None:
                actions = config.get("Actions") or []
                if 0 <= index < len(actions):
                    actions[index]["ForceOuvre"] = 100  # ouverture 100 %

            await self.client.async_patch_config(_mutate)
            await self.client.async_force_action(index, CALIB_FORCE_MINUTES)  # marche forcée
            await self.async_refresh_config()

            await asyncio.sleep(CALIB_SETTLE_S)  # délai d'adaptation de la mesure

            samples: list[float] = []
            for _ in range(CALIB_SAMPLES):
                await self.async_request_refresh()
                p = (self.data or {}).get("routed_power")
                try:
                    p = float(p)
                except (TypeError, ValueError):
                    p = None
                if p is not None and p > 0:
                    samples.append(p)
                await asyncio.sleep(CALIB_INTERVAL_S)

            act = (self.data or {}).get("actions", {}).get(index, {})
            name = act.get("name") or f"action {index}"
            notif_id = f"f1atb_calib_{index}"
            if samples:
                avg = sum(samples) / len(samples)
                self.appliance_max_power[index] = round(avg)
                _LOGGER.info(
                    "Calibration %s : %d W (moyenne de %d mesures)",
                    name, round(avg), len(samples),
                )
                persistent_notification.async_dismiss(self.hass, notif_id)  # efface un ancien warning
            else:
                # Aucune puissance routée mesurée → appareil qui ne consomme pas pendant la mesure
                # (ex. chauffe-eau déjà chaud / thermostat coupé). On NE change PAS la puissance max.
                _LOGGER.warning(
                    "Calibration %s : aucune puissance mesurée (appareil déjà chaud ?)", name,
                )
                persistent_notification.async_create(
                    self.hass,
                    f"La calibration de **{name}** n'a mesuré **aucune puissance routée**.\n\n"
                    "L'appareil consomme-t-il réellement pendant la mesure ? "
                    "(ex. chauffe-eau déjà chaud, thermostat coupé, disjoncteur ouvert).\n\n"
                    "➡️ La puissance max **n'a pas été modifiée**. Relancez la calibration quand l'appareil "
                    "peut consommer, ou saisissez la valeur manuellement.",
                    title="F1ATB — calibration sans effet",
                    notification_id=notif_id,
                )
        finally:
            await self.client.async_force_action(index, 0)  # retour Auto, quoi qu'il arrive
            self._calibrating.discard(index)
            await self.async_request_refresh()
            self.async_update_listeners()

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

        # `not self.config` : au retour d'un démarrage hors tension, la config est vide →
        # on la relit SANS attendre. Le compteur n'est réarmé qu'en cas de SUCCÈS, sinon
        # on retenterait seulement 6 cycles plus tard (entités avec mode/ouverture à 0).
        if self._config_countdown <= 0 or not self.config:
            try:
                self.config = await self.client.async_get_config()
                self._config_countdown = CONFIG_EVERY
            except F1atbApiError as err:
                _LOGGER.debug("Config non rafraîchie: %s", err)
        self._config_countdown -= 1

        # Fusion mode (Actif) + ForceOuvre depuis la config, dans chaque action active
        cfg_actions = self.config.get("Actions") or []
        for idx, a in (data.get("actions") or {}).items():
            cfg = cfg_actions[idx] if 0 <= idx < len(cfg_actions) else {}
            a["mode"] = int(cfg.get("Actif", 0) or 0)
            a["force_ouvre"] = int(cfg.get("ForceOuvre", 0) or 0)
            a["is_triac"] = idx == 0
            # Ouverture max en routage AUTO (triac) = Vmax de la 1re période.
            periodes = cfg.get("Periodes") or cfg.get("Périodes") or []
            a["auto_ouvre_max"] = int(periodes[0].get("Vmax", 100) or 0) if periodes else 100
            # Sans config (routeur qui vient de booter, /ParaFixe pas encore lu), mode/ForceOuvre
            # valent 0 : les entités qui en dépendent doivent rester INDISPONIBLES plutôt que
            # d'afficher « Inactif / ouverture 0 » avec assurance.
            a["config_ok"] = bool(cfg)

        # Canaux de température (0..3) : configurés dans /ParaFixe (Source_Temp != "tempNo"),
        # nom = nomTemperature{c}, valeur = /ajax_data (None si sonde absente / -127).
        temps = data.get("temperatures") or []
        tchan: dict[int, dict] = {}
        if self.config:  # sans config on ignore quels canaux existent → ne rien créer (pas de clignotement)
            for c in range(4):
                src = self.config.get(f"Source_Temp{c}")
                val = temps[c] if c < len(temps) else None
                configured = src not in (None, "", "tempNo")
                # inclure si configuré, ou — config lue mais sans ces clés — si une valeur valide est là
                if configured or (src is None and val is not None):
                    name = (self.config.get(f"nomTemperature{c}") or "").strip() or f"Température {c}"
                    tchan[c] = {"name": name, "source": src or "?", "value": val}
        data["temp_channels"] = tchan
        return data
