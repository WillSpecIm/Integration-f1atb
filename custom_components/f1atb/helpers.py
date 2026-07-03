"""Helpers partagés : mapping des modes (forme d'onde) et actions actives + setup dynamique."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import F1atbCoordinator

# --- Modes (champ "Actif" de la config F1ATB) ---
# Valeur Actif -> libellé. L'ordre de la liste = ordre affiché.
# Actif=1 : "Découpe sinus" (Triac, action 0) / "On/Off" (relais).
MODE_ORDER = [0, 1, 5, 2, 3, 4]
_MODE_COMMON = {0: "Inactif", 5: "Demi-sinus", 2: "Multi-sinus", 3: "Train de sinus", 4: "PWM"}


def _labels(is_triac: bool) -> dict[int, str]:
    labels = dict(_MODE_COMMON)
    labels[1] = "Découpe sinus" if is_triac else "On/Off"
    return labels


def mode_options(is_triac: bool) -> list[str]:
    labels = _labels(is_triac)
    return [labels[v] for v in MODE_ORDER]


def mode_value_to_label(value: int | None, is_triac: bool) -> str | None:
    return _labels(is_triac).get(int(value or 0))


def mode_label_to_value(label: str, is_triac: bool) -> int | None:
    for v, l in _labels(is_triac).items():
        if l == label:
            return v
    return None


def active_action_indices(data: dict | None) -> set[int]:
    """Index des actions ACTIVES.

    /ajax_etatActions ne renvoie QUE les actions actives : leur présence dans
    data["actions"] suffit → l'intégration est dynamique (aucune entité pour une action inactive).
    """
    if not data:
        return set()
    return set((data.get("actions") or {}).keys())


def temp_channel_indices(data: dict | None) -> set[int]:
    """Canaux de température configurés (0..3)."""
    if not data:
        return set()
    return set((data.get("temp_channels") or {}).keys())


@callback
def async_setup_action_platform(
    entry: ConfigEntry,
    coordinator: F1atbCoordinator,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[int], Iterable],
    keys_fn: Callable[[dict | None], set[int]] = active_action_indices,
) -> None:
    """Crée dynamiquement des entités par clé (action active ou canal temp), et ré-ajoute au retour.

    `factory(index)` renvoie la liste d'entités à créer. `keys_fn(data)` fournit l'ensemble des
    clés courantes. Le RETRAIT est géré par chaque entité (self-removal).
    """
    known: set[int] = set()

    @callback
    def _sync() -> None:
        current = keys_fn(coordinator.data)
        new: list = []
        for idx in current:
            if idx not in known:
                known.add(idx)
                new.extend(factory(idx))
        known.intersection_update(current)  # oublier les disparues pour permettre une ré-apparition
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))
