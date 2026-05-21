"""
Rastrea posiciones abiertas, P&L y estado diario del bot en bot_state.json.
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
    return {"positions": {}, "daily": {}, "session": {}, "history": []}


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


# ── Sesión y P&L ─────────────────────────────────────────────────────────────

def init_session(balance_usdt: float) -> None:
    """Registra el saldo al inicio de la sesión si no existe."""
    state = _load()
    if not state.get("session"):
        state["session"] = {
            "start_balance": balance_usdt,
            "trades":        0,
            "wins":          0,
            "losses":        0,
            "gross_pnl":     0.0,
        }
        _save(state)
        logger.info("Sesión iniciada. Saldo de referencia: %.2f USDT", balance_usdt)


def record_closed_trade(pair: str, entry: float, exit_price: float,
                        qty: float, pnl_usdt: float) -> None:
    """Registra el resultado de una trade cerrada."""
    state = _load()
    result = "WIN" if pnl_usdt > 0 else "LOSS"

    # Actualizar sesión
    sess = state.setdefault("session", {})
    sess["trades"]    = sess.get("trades", 0) + 1
    sess["wins"]      = sess.get("wins", 0) + (1 if pnl_usdt > 0 else 0)
    sess["losses"]    = sess.get("losses", 0) + (1 if pnl_usdt <= 0 else 0)
    sess["gross_pnl"] = sess.get("gross_pnl", 0.0) + pnl_usdt

    # Actualizar diario
    daily = state.setdefault("daily", {})
    daily["pnl_usdt"] = daily.get("pnl_usdt", 0.0) + pnl_usdt

    # Historial
    state.setdefault("history", []).append({
        "pair": pair, "entry": entry, "exit": exit_price,
        "qty": qty, "pnl": round(pnl_usdt, 4), "result": result,
    })

    _save(state)

    sign = "+" if pnl_usdt >= 0 else ""
    pct  = (exit_price - entry) / entry * 100
    logger.info("%-8s %-10s | entrada=%.4f salida=%.4f | %s%.2f USDT (%s%.2f%%)",
                result, pair, entry, exit_price, sign, pnl_usdt, sign, pct)


def get_session_stats() -> dict:
    return _load().get("session", {})


def get_daily_pnl() -> float:
    return _load().get("daily", {}).get("pnl_usdt", 0.0)


# ── Control de pérdida diaria ─────────────────────────────────────────────────

def init_daily(balance_usdt: float) -> None:
    today = str(date.today())
    state = _load()
    daily = state.setdefault("daily", {})
    if daily.get("date") != today:
        daily["date"]          = today
        daily["start_balance"] = balance_usdt
        daily["pnl_usdt"]      = 0.0
        daily["halted"]        = False
        _save(state)
        logger.info("Nuevo día. Saldo inicial del día: %.2f USDT", balance_usdt)


def record_trade() -> None:
    state = _load()
    state.setdefault("daily", {})["trades_today"] = \
        state["daily"].get("trades_today", 0) + 1
    _save(state)


# ── Live state (for dashboard) ────────────────────────────────────────────────

def update_live(
    balance: float,
    capital: float,
    open_positions: dict,
    last_signal_count: int,
) -> None:
    """Write live runtime data so the dashboard can read it without Binance access."""
    from datetime import datetime  # local import to avoid top-level cost

    state = _load()
    state["live"] = {
        "balance":           balance,
        "capital":           capital,
        "open_positions":    open_positions,
        "last_signal_count": last_signal_count,
        "last_update":       datetime.now().isoformat(timespec="seconds"),
    }
    _save(state)


def check_daily_limit(current_balance: float, limit_pct: float) -> bool:
    state = _load()
    daily = state.get("daily", {})
    if daily.get("halted"):
        return True

    start    = daily.get("start_balance", current_balance)
    loss_pct = (start - current_balance) / start if start > 0 else 0

    if loss_pct >= limit_pct:
        daily["halted"] = True
        _save(state)
        logger.warning(
            "LÍMITE DIARIO: pérdida %.1f%% (inicio=%.2f actual=%.2f). Bot pausado hasta mañana.",
            loss_pct * 100, start, current_balance,
        )
        return True

    return False
