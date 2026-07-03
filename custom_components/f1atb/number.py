"""Numbers F1ATB par action :
- Ouverture max (ForceOuvre, %) — réglage direct de l'ouverture forcée.
- Puissance max de l'appareil (W) — calibration côté HA (100 % d'ouverture = cette puissance).
- Marche forcée (W) — entrer une puissance → l'ouverture est calculée automatiquement
  (= puissance / puissance_max × 100), réglée, et la marche est forcée. 0 → retour Auto.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_FORCE_MINUTES, DEFAULT_FORCE_MINUTES, DOMAIN
from .entity import F1atbActionEntity
from .helpers import async_setup_action_platform

DEFAULT_MAX_POWER = 3000.0  # W à 100 % d'ouverture (valeur de départ, modifiable)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    def factory(index: int) -> list:
        items = [
            OuvertureMaxNumber(coordinator, index),
            PuissanceMaxNumber(coordinator, index),
            MarcheForceePuissanceNumber(coordinator, index, entry),
        ]
        # Ouverture max en routage AUTO (Vmax %) — créée pour toute action pilotée
        # (pertinent pour le triac/SSR en mode proportionnel : Demi-sinus, PWM, etc.).
        items.append(AutoOuvertureMaxNumber(coordinator, index))
        return items

    async_setup_action_platform(entry, coordinator, async_add_entities, factory)


class AutoOuvertureMaxNumber(F1atbActionEntity, NumberEntity):
    """Ouverture MAX en routage AUTO (triac) = Vmax des périodes. Écrit via /ParaNew.

    À distinguer de « Ouverture (marche forcée) » (ForceOuvre) : ici c'est le plafond
    d'ouverture que l'algorithme normal ne dépassera pas. Appliqué à TOUTES les périodes.
    """

    _attr_icon = "mdi:arrow-collapse-vertical"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _kind = "auto_ouverture_max"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_auto_ouverture_max_{index}"

    @property
    def name(self) -> str:
        return f"{self._action_name} ouverture max (Auto)"

    @property
    def native_value(self) -> float | None:
        a = self._action
        return None if a is None else float(a.get("auto_ouvre_max", 100) or 0)

    async def async_set_native_value(self, value: float) -> None:
        idx = self._index
        v = int(max(0, min(100, value)))

        def _mutate(config: dict) -> None:
            actions = config.get("Actions") or []
            if 0 <= idx < len(actions):
                periodes = actions[idx].get("Periodes")
                if periodes is None:
                    periodes = actions[idx].get("Périodes")
                for p in (periodes or []):
                    p["Vmax"] = v  # même plafond sur toutes les périodes

        await self.coordinator.client.async_patch_config(_mutate)
        await self._write_and_refresh(config_change=True)


class OuvertureMaxNumber(F1atbActionEntity, NumberEntity):
    """Ouverture appliquée en MARCHE FORCÉE (champ ForceOuvre). Écrit via /ParaNew (persistant).

    À distinguer de « Ouverture max (Auto) » : ici c'est l'ouverture utilisée quand le
    routage est forcé en marche (pas le plafond du routage automatique).
    """

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
        return f"{self._action_name} ouverture (marche forcée)"

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


class PuissanceMaxNumber(F1atbActionEntity, RestoreNumber):
    """Calibration : puissance consommée par l'appareil à 100 % d'ouverture (W).

    Stockée côté Home Assistant (le firmware n'a pas ce réglage). Sert au calcul de
    l'ouverture pour la « Marche forcée (W) ». Valeur mémorisée entre redémarrages.
    """

    _attr_icon = "mdi:flash-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_step = 50
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _kind = "puissance_max"

    def __init__(self, coordinator, index: int) -> None:
        super().__init__(coordinator, index)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_puissance_max_{index}"
        coordinator.appliance_max_power.setdefault(index, DEFAULT_MAX_POWER)

    @property
    def name(self) -> str:
        return f"{self._action_name} puissance max"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restaure la valeur mémorisée (sinon on garde celle déjà en mémoire côté coordinator,
        # qui survit à un cycle inactif→actif pendant la même session HA).
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.appliance_max_power[self._index] = float(last.native_value)

    @property
    def native_value(self) -> float | None:
        # Source unique de vérité = le coordinator, pour que la calibration auto
        # (qui écrit dans ce dict) mette l'affichage à jour toute seule.
        return float(self.coordinator.appliance_max_power.get(self._index, DEFAULT_MAX_POWER))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            **super().extra_state_attributes,
            "calibrating": self.coordinator.is_calibrating(self._index),
        }

    async def async_set_native_value(self, value: float) -> None:
        # Saisie MANUELLE : toujours possible (surcharge la calibration auto).
        self.coordinator.appliance_max_power[self._index] = float(max(0, value))
        self.async_write_ha_state()


class MarcheForceePuissanceNumber(F1atbActionEntity, RestoreNumber):
    """« Marche forcée (W) » : entrer une puissance à router.

    L'ouverture = puissance / puissance_max × 100 est calculée automatiquement, écrite
    dans ForceOuvre (/ParaNew) et la marche est forcée (/ForceAction). 0 → retour Auto.
    """

    _attr_icon = "mdi:flash"
    _attr_native_min_value = 0
    # Plafond FIXE et large : ne PAS le fixer à pmax, sinon HA rejette (ServiceValidationError)
    # toute saisie > pmax avant même d'appeler async_set_native_value. Le vrai plafond (router au
    # plus 100 %) est appliqué par le clamp de l'ouverture ci-dessous ; la carte borne à pmax.
    _attr_native_max_value = 10000
    _attr_native_step = 50
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX
    _kind = "marche_forcee_w"

    def __init__(self, coordinator, index: int, entry: ConfigEntry) -> None:
        super().__init__(coordinator, index)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.entry.unique_id}_marche_forcee_w_{index}"
        self._value = 0.0

    @property
    def name(self) -> str:
        return f"{self._action_name} marche forcée (W)"

    def _max_power(self) -> float:
        return float(self.coordinator.appliance_max_power.get(self._index, DEFAULT_MAX_POWER)) or DEFAULT_MAX_POWER

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._value = float(last.native_value)

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict:
        pmax = self._max_power()
        opening = int(max(0, min(100, round(self._value / pmax * 100)))) if pmax else 0
        return {
            **super().extra_state_attributes,
            "puissance_max": pmax,
            "ouverture_calculee": opening,
        }

    async def async_set_native_value(self, value: float) -> None:
        idx = self._index
        value = float(max(0, value))
        self._value = value
        minutes = int(self._entry.options.get(CONF_FORCE_MINUTES, DEFAULT_FORCE_MINUTES))

        if value <= 0:
            # Retour en Auto (fin du forçage)
            await self.coordinator.client.async_force_action(idx, 0)
            await self._write_and_refresh(config_change=False)
            self.async_write_ha_state()
            return

        pmax = self._max_power()
        opening = int(max(0, min(100, round(value / pmax * 100))))

        def _mutate(config: dict) -> None:
            actions = config.get("Actions") or []
            if 0 <= idx < len(actions):
                actions[idx]["ForceOuvre"] = opening

        await self.coordinator.client.async_patch_config(_mutate)
        await self.coordinator.client.async_force_action(idx, minutes)  # Marche forcée
        await self._write_and_refresh(config_change=True)
        self.async_write_ha_state()
