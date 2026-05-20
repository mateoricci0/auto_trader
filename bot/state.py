"""
Rastrea posiciones abiertas y estado diario del bot en bot_state.json.
Solo cuenta las trades que el bot abrió — ignora balances iniciales del testnet.
"""
import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILE = Path("bot_state.json")


def _load() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"positions": {}, "daily": {}}


def _save(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Posiciones ────────────────────────────────────────────────────────────────

def get_positions() -> dict:
    return _load()["positions"]


def add_position(pair: str, qty: float, entry_price: float, sl: float, tp: float) -> None:
    state = _load()
    state["positions"][pair] = {
        "qty": qty, "entry_price": entry_price, "sl": sl, "tp": tp,
    }
    _save(state)
    logger.info("Estado: posición abierta en %s", pair)


def remove_position(pair: str) -> None:
    state = _load()
    if pair in state["positions"]:
        del state["positions"][pair]
        _save(state)
        logger.info("Estado: posición cerrada en %s", pair)


# ── Control de pérdida diaria ─────────────────────────────────────────────────

def init_daily(balance_usdt: float) -> None:
    """Registra el saldo al inicio del día si no existe entrada para hoy."""
    today = str(date.today())
    state = _load()
    daily = state.setdefault("daily", {})
    if daily.get("date") != today:
        daily["date"]            = today
        daily["start_balance"]   = balance_usdt
        daily["trades_today"]    = 0
        daily["halted"]          = False
        _save(state)
        logger.info("Nuevo día de trading. Saldo inicial: %.2f USDT", balance_usdt)


def record_trade() -> None:
    state = _load()
    state.setdefault("daily", {})["trades_today"] = \
        state["daily"].get("trades_today", 0) + 1
    _save(state)


def check_daily_limit(current_balance: float, limit_pct: float) -> bool:
    """
    Devuelve True si el bot debe parar por pérdida diaria excesiva.
    limit_pct = fracción del capital (ej. 0.05 = 5%).
    """
    state = _load()
    daily = state.get("daily", {})
    if daily.get("halted"):
        return True

    start = daily.get("start_balance", current_balance)
    loss_pct = (start - current_balance) / start if start > 0 else 0

    if loss_pct >= limit_pct:
        daily["halted"] = True
        _save(state)
        logger.warning(
            "LÍMITE DIARIO ALCANZADO: pérdida %.1f%% (inicio=%.2f actual=%.2f). "
            "Bot detenido hasta mañana.", loss_pct * 100, start, current_balance
        )
        return True

    return False
