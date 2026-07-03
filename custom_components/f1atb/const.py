"""Constantes de l'intégration F1ATB Solar Router."""
from __future__ import annotations

DOMAIN = "f1atb"

CONF_HOST = "host"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_FORCE_MINUTES = "force_minutes"

DEFAULT_SCAN_INTERVAL = 5  # secondes
DEFAULT_FORCE_MINUTES = 720  # durée d'un forçage (Marche/Arrêt) en minutes = 12 h

# Modes de forçage exposés (select)
MODE_AUTO = "Auto"
MODE_ON = "Forcé Marche"
MODE_OFF = "Forcé Arrêt"
FORCE_MODES = [MODE_AUTO, MODE_ON, MODE_OFF]
