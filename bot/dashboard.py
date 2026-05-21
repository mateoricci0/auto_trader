"""
Flask dashboard for AUTO_TRADER BOT.
Serves a live web UI at http://localhost:5000 that reads bot_state.json.
"""
import json
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request

logger = logging.getLogger(__name__)

# Silenciar logs de acceso HTTP de werkzeug (GET /api/data cada 3s)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

_STATE_FILE = Path("bot_state.json")

app = Flask(__name__, template_folder="templates")


def _load_state() -> dict:
    """Load bot_state.json, returning safe defaults if the file doesn't exist yet."""
    defaults: dict = {
        "positions": {},
        "daily": {},
        "session": {
            "start_balance": 0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "gross_pnl": 0.0,
        },
        "history": [],
        "live": {
            "balance": 0.0,
            "capital": 0.0,
            "open_positions": {},
            "last_signal_count": 0,
            "last_update": None,
        },
    }
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            # Deep-merge so any missing sub-keys still get defaults
            for key, val in defaults.items():
                if key not in data:
                    data[key] = val
                elif isinstance(val, dict):
                    for subkey, subval in val.items():
                        if subkey not in data[key]:
                            data[key][subkey] = subval
            return data
        except Exception as exc:
            logger.warning("Could not read bot_state.json: %s", exc)
    return defaults


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    state = _load_state()

    # Merge in config values (imported lazily to avoid circular imports)
    try:
        import bot.config as cfg  # noqa: PLC0415
        state["config"] = {
            "trading_capital": cfg.TRADING_CAPITAL,
            "timeframe": cfg.TIMEFRAME,
            "pairs_count": len(cfg.PAIRS),
        }
    except Exception:
        state["config"] = {
            "trading_capital": 0,
            "timeframe": "?",
            "pairs_count": 0,
        }

    return jsonify(state)


@app.route("/api/command", methods=["POST"])
def api_command():
    cmd = request.json.get("cmd", "")
    if cmd in ("close_all",):
        from bot import state as _state
        _state.set_command(cmd)
        return jsonify({"ok": True, "msg": f"Comando '{cmd}' enviado al bot."})
    return jsonify({"ok": False, "msg": "Comando desconocido."}), 400


def start_dashboard(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Start Flask in a daemon thread so it doesn't block the bot loop."""
    import threading

    thread = threading.Thread(
        target=lambda: app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        ),
        daemon=True,
        name="dashboard",
    )
    thread.start()
    logger.info("Dashboard started at http://localhost:%d", port)
