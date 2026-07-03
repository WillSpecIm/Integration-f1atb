"""Client HTTP asynchrone pour le routeur solaire F1ATB (firmware officiel).

Ne nécessite AUCUNE modification du firmware : on utilise l'API web existante
(/ajax_data, /ajax_etatActions, /ajax_dataESP32, /ParaFixe, /ForceAction).
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

# Séparateurs utilisés par le firmware F1ATB
GS = chr(29)  # Group Separator
RS = chr(30)  # Record Separator
US = chr(31)  # Unit Separator

TIMEOUT = 10


class F1atbApiError(Exception):
    """Erreur de communication avec le routeur F1ATB."""


def _f(lst: list[str], i: int) -> float | None:
    try:
        return float(lst[i])
    except (IndexError, ValueError, TypeError):
        return None


def _i(val: str) -> int | None:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


class F1atbClient:
    """Dialogue avec un routeur F1ATB via son API HTTP locale."""

    def __init__(self, session: ClientSession, host: str) -> None:
        host = host.strip().rstrip("/")
        if not host.startswith("http://") and not host.startswith("https://"):
            host = "http://" + host
        self._base = host
        self._session = session

    @property
    def base_url(self) -> str:
        return self._base

    async def _get(self, path: str) -> str:
        url = self._base + path
        try:
            async with asyncio.timeout(TIMEOUT):
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.text()
        except (ClientError, asyncio.TimeoutError) as err:
            raise F1atbApiError(f"Échec requête {url}: {err}") from err

    async def _post_plain(self, path: str, body: str) -> str:
        url = self._base + path
        # IMPORTANT : Content-Type text/plain → le firmware récupère le corps brut via
        # server.arg("plain"). Avec application/x-www-form-urlencoded il le parserait comme
        # un formulaire et le JSON serait ignoré (POST accepté mais SANS effet).
        headers = {"Content-Type": "text/plain"}
        try:
            async with asyncio.timeout(TIMEOUT):
                async with self._session.post(
                    url, data=body.encode("utf-8"), headers=headers
                ) as resp:
                    resp.raise_for_status()
                    return await resp.text()
        except (ClientError, asyncio.TimeoutError) as err:
            raise F1atbApiError(f"Échec POST {url}: {err}") from err

    # ---------------------------------------------------------------- lecture
    async def async_get_config(self) -> dict:
        """/ParaFixe : configuration (JSON). Sert à identifier l'appareil + les actions."""
        import json

        txt = await self._get("/ParaFixe")
        try:
            return json.loads(txt)
        except ValueError as err:
            raise F1atbApiError(f"/ParaFixe JSON invalide: {err}") from err

    async def async_get_data(self) -> dict:
        """Agrège /ajax_data + /ajax_etatActions + /ajax_dataESP32 en un dict."""
        data: dict = {"actions": {}}

        # ---- /ajax_data : puissances & énergies maison + sonde routée ----
        txt = await self._get("/ajax_data")
        groups = txt.split(GS)
        g0 = groups[0].split(RS) if groups else []
        house = groups[1].split(RS) if len(groups) > 1 else []
        probe = groups[2].split(RS) if len(groups) > 2 else []

        data["date"] = g0[1].strip() if len(g0) > 1 else None
        data["source"] = g0[2].strip() if len(g0) > 2 else None
        data["grid_import_power"] = _f(house, 0)          # PwS_M (soutirée réseau)
        data["grid_export_power"] = _f(house, 1)          # PwI_M (injectée réseau)
        data["house_energy_import_today"] = _f(house, 4)  # EAJS_M (Wh)
        data["house_energy_export_today"] = _f(house, 5)  # EAJI_M (Wh)
        data["routed_power"] = _f(probe, 0)               # PwS_T (routée vers charge)
        data["routed_energy_today"] = _f(probe, 4)        # EAJS_T (Wh)

        # températures (pipe-separated dans g0[5])
        temps = []
        if len(g0) > 5:
            for t in g0[5].split("|"):
                v = None
                try:
                    v = float(t)
                except ValueError:
                    v = None
                if v is not None and v > -100:  # -127 = sonde absente
                    temps.append(v)
                else:
                    temps.append(None)
        data["temperatures"] = temps

        # ---- /ajax_etatActions : état de chaque action pilotée ----
        try:
            txt2 = await self._get("/ajax_etatActions")
            g = txt2.split(GS)
            # g = [temps, source, RMSextIP, NbActifs, rec1, rec2, ...]
            for rec in g[4:]:
                f = rec.split(RS)
                if len(f) < 4 or not f[0].strip():
                    continue
                idx = _i(f[0])
                if idx is None:
                    continue
                opening_raw = f[2].strip()
                if opening_raw in ("On", "on"):
                    opening = 100
                elif opening_raw in ("Off", "off"):
                    opening = 0
                else:
                    opening = _i(opening_raw)
                data["actions"][idx] = {
                    "index": idx,
                    "name": f[1].strip(),
                    "opening": opening,          # 0-100 %
                    "force": _i(f[3]) or 0,      # tOnOff : >0 forcé Marche (min), <0 forcé Arrêt
                }
        except F1atbApiError as err:
            _LOGGER.debug("etatActions indisponible: %s", err)

        # ---- /ajax_dataESP32 : infos système ----
        try:
            txt3 = await self._get("/ajax_dataESP32")
            m = txt3.split(GS)[0].split(RS)
            data["uptime_hours"] = _f(m, 0)
            data["rssi"] = _f(m, 2)
            data["heap_free"] = _f(m, 13)
            data["heap_min"] = _f(m, 14)
            ips = m[7].split(US) if len(m) > 7 else []
            data["ip"] = ips[0] if ips else None
        except (F1atbApiError, IndexError) as err:
            _LOGGER.debug("dataESP32 indisponible: %s", err)

        return data

    # ---------------------------------------------------------------- écriture
    async def async_force_action(self, num_action: int, force_minutes: int) -> None:
        """Force une action : +N = Marche N min, -N = Arrêt N min, 0 = Auto.

        (handler officiel /ForceAction : LesActions[NumAction].tOnOff = Force)
        """
        await self._get(f"/ForceAction?NumAction={int(num_action)}&Force={int(force_minutes)}")

    async def async_update_pid(self, i_act: int, kp: int, ki: int, kd: int) -> None:
        """Coefficients PID en temps réel (/UpdateK). Non persisté au reboot."""
        await self._get(
            f"/UpdateK?iAct={int(i_act)}&Kp={int(kp)}&Ki={int(ki)}&Kd={int(kd)}"
        )

    async def async_patch_config(self, mutate) -> None:
        """Lit la config complète (/ParaFixe), applique `mutate(config)`, la reposte (/ParaNew).

        Permet de changer N'IMPORTE QUEL réglage persistant (mode/type d'onde, seuils,
        PID persisté, GPIOs…) exactement comme le bouton « Sauvegarder » de l'UI web.
        `mutate` reçoit le dict config et le modifie en place.
        """
        import json

        config = await self.async_get_config()
        mutate(config)
        body = json.dumps(config, separators=(",", ":"))
        await self._post_plain("/ParaNew", body)
