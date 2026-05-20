"""
Rastrea posiciones abiertas por el bot en un archivo JSON local.
Solo cuenta las trades que el bot abrió — ignora balances iniciales del testnet.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILE = Path("bot_state.json")


def _load() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"positions": {}}


def _save(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_positions() -> dict:
    """Devuelve {pair: {qty, entry_price, sl, tp}} de las posiciones activas."""
    return _load()["positions"]


def add_position(pair: str, qty: float, entry_price: float, sl: float, tp: float) -> None:
    state = _load()
    state["positions"][pair] = {
        "qty": qty,
        "entry_price": entry_price,
        "sl": sl,
        "tp": tp,
    }
    _save(state)
    logger.info("Estado guardado: posición abierta en %s", pair)


def remove_position(pair: str) -> None:
    state = _load()
    if pair in state["positions"]:
        del state["positions"][pair]
        _save(state)
        logger.info("Estado actualizado: posición cerrada en %s", pair)
