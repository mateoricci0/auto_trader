"""
Cerebro IA del bot — DeepSeek.

Analiza TODOS los pares en UNA sola llamada API, forzando selectividad real.
DeepSeek compara pares entre sí y elige máximo 2 con alta convicción.
"""
import json
import logging

import pandas as pd

from .config import TIMEFRAME

logger = logging.getLogger(__name__)

_ai_client = None


def init(api_key: str) -> None:
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


def analyze_all(pairs_data: list[dict]) -> list[dict]:
    """
    Envía datos de TODOS los pares en una sola llamada a DeepSeek.
    Devuelve lista de trades recomendados [{pair, sl, tp, confidence, reason}, ...]
    o lista vacía si no hay oportunidades claras.

    pairs_data: lista de dicts con keys: pair, price, ema_fast, ema_slow, rsi, atr, candles_text
    """
    if not is_available():
        return []

    # Construir sección de datos de mercado
    market_sections = []
    for p in pairs_data:
        section = (
            f"=== {p['pair']} ===\n"
            f"Price: {p['price']:.6f} | EMA9: {p['ema_fast']:.6f} | EMA21: {p['ema_slow']:.6f} "
            f"| RSI: {p['rsi']:.1f} | ATR: {p['atr']:.6f}\n"
            f"Last 30 candles (Open High Low Close Volume):\n{p['candles_text']}"
        )
        market_sections.append(section)

    market_block = "\n\n".join(market_sections)

    system_prompt = (
        "You are a disciplined professional crypto trader with 10+ years of experience. "
        "You are known for being VERY selective — you only take high-conviction trades. "
        "Capital preservation is your top priority. "
        "You ONLY output valid JSON, no markdown, no explanation."
    )

    user_prompt = f"""Analyze these {len(pairs_data)} crypto pairs ({TIMEFRAME} timeframe) and select AT MOST 2 for a BUY entry.

Be selective but active — look for 1-3 good setups. Not every cycle will have trades, but don't be overly conservative.

GOAL: Find 1-3 momentum trades with strong direction. Target 0.5-2% profit per trade. Set ambitious TPs at real resistance levels, not minimal ones.

BUY criteria:
1. Price above EMA9 and EMA21 (uptrend confirmed)
2. RSI between 40 and 70 (has momentum, not extreme)
3. Stop Loss below recent support, at least 0.2% below entry
4. Take Profit at the NEXT MAJOR resistance, minimum 0.5% above entry — prefer 1-2% when the chart supports it
5. Risk/Reward at least 2.0:1 (aim for 3:1 when possible)
6. Strong volume confirming the move

SKIP when:
- Price clearly ranging with no direction
- RSI above 72 (very overbought) or below 35 (downtrend)
- No identifiable support/resistance for SL/TP placement
- Risk/reward below 2.0:1
- TP would be less than 0.5% above entry

Market data:
{market_block}

Respond ONLY with this JSON (no markdown, numbers not strings):
{{"trades": [{{"pair": "XXXUSDT", "sl": 0.0, "tp": 0.0, "confidence": 0.0, "reason": "<max 12 words>"}}]}}

If no good setups exist: {{"trades": []}}"""

    try:
        response = _ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()

        # Quitar bloques markdown si el modelo los añade
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        trades = result.get("trades", [])

        validated = []
        for t in trades:
            if not {"pair", "sl", "tp", "confidence"}.issubset(t):
                continue
            t["sl"]         = float(t["sl"])
            t["tp"]         = float(t["tp"])
            t["confidence"] = float(t["confidence"])
            validated.append(t)

        logger.info("DeepSeek recomienda %d trade(s): %s",
                    len(validated), [t["pair"] for t in validated])
        return validated

    except json.JSONDecodeError as exc:
        logger.warning("DeepSeek devolvió JSON inválido: %s", exc)
        return []
    except Exception as exc:
        logger.warning("Error llamando a DeepSeek: %s", exc)
        return []
