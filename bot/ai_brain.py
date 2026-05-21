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

IMPORTANT: The most common correct answer is 0 trades. Only enter when the setup is exceptional.

GOAL: Find trades with 0.5% to 2% profit potential on short timeframe candles.

BUY criteria — ALL must be met:
1. Price clearly above EMA9 AND EMA21 (confirmed uptrend on hourly chart)
2. RSI between 45 and 65 (momentum building, not overbought)
3. Stop Loss below clear support, minimum 0.5% below entry price
4. Take Profit at clear resistance, MINIMUM 0.5% above entry (target 1-2%)
5. Risk/Reward ratio MINIMUM 3:1 (TP distance ÷ SL distance ≥ 3)
6. Volume confirming the move (not a fake breakout)
7. Clear setup: breakout from consolidation, EMA bounce, or strong momentum candle

DO NOT trade when:
- Target would be less than 0.5% from entry (too small to matter)
- Market is ranging/sideways with no clear direction
- RSI above 65 (overbought, late entry) or below 45 (no momentum)
- The move already happened — never chase a candle that ran
- Risk/reward worse than 3:1
- You are uncertain — 0 trades is better than a bad trade

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
            max_tokens=400,
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
