"""
Cerebro IA del bot. Usa la API de DeepSeek (compatible con OpenAI) para analizar
cada par y decidir si entrar en una posición, con SL y TP propios.
"""
import json
import logging

import pandas as pd

logger = logging.getLogger(__name__)

_ai_client = None


def init(api_key: str) -> None:
    """Inicializa el cliente DeepSeek. Llamar una vez al arrancar el bot."""
    global _ai_client
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY no configurada — bot usará solo reglas técnicas.")
        return
    try:
        from openai import OpenAI
        _ai_client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        logger.info("DeepSeek AI inicializado correctamente.")
    except ImportError:
        logger.error("Librería 'openai' no instalada. Ejecuta: pip install openai")


def is_available() -> bool:
    return _ai_client is not None


def analyze(pair: str, df: pd.DataFrame, indicators: dict) -> dict | None:
    """
    Envía datos de mercado a DeepSeek y recibe una decisión de trading.

    Devuelve dict con keys: action, sl, tp, confidence, reason
    o None si hubo un error.
    """
    if not is_available():
        return None

    price    = indicators["price"]
    ema_fast = indicators["ema_fast"]
    ema_slow = indicators["ema_slow"]
    rsi_val  = indicators["rsi"]
    atr_val  = indicators["atr"]

    # Últimas 30 velas en formato compacto
    recent = df.tail(30)[["Open", "High", "Low", "Close", "Volume"]].round(6)
    candles_text = recent.to_string(index=False)

    system_prompt = (
        "You are a disciplined quantitative crypto trader. "
        "Your job is to find high-probability momentum entries with strict risk management. "
        "You ONLY output valid JSON — no markdown, no explanation outside the JSON."
    )

    user_prompt = f"""Analyze {pair} (15-minute candles) and decide whether to BUY now.

Last 30 candles (OHLCV):
{candles_text}

Current technical indicators:
- Price:  {price:.6f}
- EMA9:   {ema_fast:.6f}
- EMA21:  {ema_slow:.6f}
- RSI14:  {rsi_val:.2f}
- ATR14:  {atr_val:.6f}

Respond with ONLY this JSON (numbers, not strings for sl/tp/confidence):
{{"action": "BUY" or "HOLD", "sl": <stop_loss_price>, "tp": <take_profit_price>, "confidence": <0.0-1.0>, "reason": "<max 15 words>"}}

Strict rules:
- action=BUY only when trend is clear and risk/reward ratio >= 2.0
- sl MUST be strictly below current price
- tp MUST be strictly above current price
- If uncertain, return HOLD"""

    try:
        response = _ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()

        # Eliminar bloques markdown si el modelo los añade
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)

        # Validación básica
        required = {"action", "sl", "tp", "confidence", "reason"}
        if not required.issubset(result):
            logger.warning("%s: respuesta DeepSeek incompleta: %s", pair, result)
            return None

        result["sl"]         = float(result["sl"])
        result["tp"]         = float(result["tp"])
        result["confidence"] = float(result["confidence"])

        logger.debug("%s → DeepSeek: %s", pair, result)
        return result

    except json.JSONDecodeError as exc:
        logger.warning("%s: DeepSeek devolvió JSON inválido: %s", pair, exc)
        return None
    except Exception as exc:
        logger.warning("%s: error llamando a DeepSeek: %s", pair, exc)
        return None
