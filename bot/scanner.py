"""
Escanea todos los pares y devuelve señales de compra ordenadas por fuerza.

Modo AI (DeepSeek disponible):  el modelo decide si comprar y fija SL/TP.
Modo fallback (sin API key):    EMA crossover + RSI filter + SL/TP por ATR.
"""
import logging
from dataclasses import dataclass, field

import pandas as pd
from binance.client import Client

from . import ai_brain
from .config import (ATR_PERIOD, ATR_SL_MULT, ATR_TP_MULT, CANDLES_LIMIT,
                     EMA_FAST, EMA_SLOW, PAIRS, RSI_MAX, RSI_PERIOD, TIMEFRAME)
from .indicators import atr, ema, rsi

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    pair:       str
    price:      float
    sl:         float
    tp:         float
    atr_val:    float
    rsi_val:    float
    score:      float
    ai_reason:  str = field(default="")


def _fetch_candles(client: Client, pair: str) -> pd.DataFrame:
    raw = client.get_klines(symbol=pair, interval=TIMEFRAME, limit=CANDLES_LIMIT)
    df = pd.DataFrame(raw, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
    ])
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = df[col].astype(float)
    return df


def _has_cross(fast: pd.Series, slow: pd.Series) -> bool:
    return fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]


def _scan_pair_ai(pair: str, df: pd.DataFrame, indicators: dict) -> Signal | None:
    """Usa DeepSeek para decidir si hay señal de compra."""
    result = ai_brain.analyze(pair, df, indicators)
    if result is None or result.get("action") != "BUY":
        return None

    price = indicators["price"]
    sl    = result["sl"]
    tp    = result["tp"]

    # Sanidad: sl < price < tp
    if not (sl < price < tp):
        logger.warning("%s: DeepSeek devolvió SL/TP inválidos (sl=%.4f price=%.4f tp=%.4f) — skip",
                       pair, sl, price, tp)
        return None

    # Score = confidence de la IA
    score = result["confidence"]
    reason = result.get("reason", "")

    logger.info("AI BUY %s | precio=%.4f SL=%.4f TP=%.4f conf=%.2f | %s",
                pair, price, sl, tp, score, reason)

    return Signal(
        pair=pair, price=price, sl=sl, tp=tp,
        atr_val=indicators["atr"], rsi_val=indicators["rsi"],
        score=score, ai_reason=reason,
    )


def _scan_pair_rules(pair: str, df: pd.DataFrame, indicators: dict) -> Signal | None:
    """Fallback: EMA crossover + RSI + SL/TP basados en ATR."""
    ema_fast_s = ema(df["Close"], EMA_FAST)
    ema_slow_s = ema(df["Close"], EMA_SLOW)
    price      = indicators["price"]
    rsi_val    = indicators["rsi"]
    atr_val    = indicators["atr"]

    if not (_has_cross(ema_fast_s, ema_slow_s) and rsi_val < RSI_MAX):
        return None

    sl = price - ATR_SL_MULT * atr_val
    tp = price + ATR_TP_MULT * atr_val

    ema_gap = (ema_fast_s.iloc[-1] - ema_slow_s.iloc[-1]) / price * 100
    score   = ema_gap + (RSI_MAX - rsi_val) / 10

    logger.info("Señal %s | precio=%.4f SL=%.4f TP=%.4f RSI=%.1f score=%.3f",
                pair, price, sl, tp, rsi_val, score)

    return Signal(
        pair=pair, price=price, sl=sl, tp=tp,
        atr_val=atr_val, rsi_val=rsi_val, score=score,
    )


def scan(client: Client) -> list[Signal]:
    """
    Escanea todos los pares. Usa DeepSeek si está disponible, si no usa reglas.
    Devuelve lista de Signals ordenada por score descendente.
    """
    use_ai = ai_brain.is_available()
    mode   = "AI (DeepSeek)" if use_ai else "reglas técnicas"
    logger.info("Escaneando %d pares — modo: %s", len(PAIRS), mode)

    signals = []
    for pair in PAIRS:
        try:
            df = _fetch_candles(client, pair)

            indicators = {
                "price":    df["Close"].iloc[-1],
                "ema_fast": ema(df["Close"], EMA_FAST).iloc[-1],
                "ema_slow": ema(df["Close"], EMA_SLOW).iloc[-1],
                "rsi":      rsi(df["Close"], RSI_PERIOD).iloc[-1],
                "atr":      atr(df["High"], df["Low"], df["Close"], ATR_PERIOD).iloc[-1],
            }

            signal = _scan_pair_ai(pair, df, indicators) if use_ai \
                     else _scan_pair_rules(pair, df, indicators)

            if signal:
                signals.append(signal)

        except Exception as exc:
            logger.warning("Error escaneando %s: %s", pair, exc)

    return sorted(signals, key=lambda s: s.score, reverse=True)
