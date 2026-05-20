"""
Escanea todos los pares y devuelve señales de compra ordenadas por fuerza.
Una señal es: EMA rápida cruza por encima de EMA lenta + RSI no sobrecomprado.
"""
import logging
from dataclasses import dataclass

import pandas as pd
from binance.client import Client

from .config import (ATR_PERIOD, ATR_SL_MULT, ATR_TP_MULT, CANDLES_LIMIT,
                     EMA_FAST, EMA_SLOW, PAIRS, RSI_MAX, RSI_PERIOD, TIMEFRAME)
from .indicators import atr, ema, rsi

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    pair:       str
    price:      float
    sl:         float   # stop loss
    tp:         float   # take profit
    atr_val:    float
    rsi_val:    float
    score:      float   # fuerza de la señal (mayor = mejor)


def _fetch_candles(client: Client, pair: str) -> pd.DataFrame:
    """Descarga velas OHLCV del testnet para un par."""
    raw = client.get_klines(
        symbol=pair,
        interval=TIMEFRAME,
        limit=CANDLES_LIMIT,
    )
    df = pd.DataFrame(raw, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
    ])
    df["Close"]  = df["Close"].astype(float)
    df["High"]   = df["High"].astype(float)
    df["Low"]    = df["Low"].astype(float)
    df["Open"]   = df["Open"].astype(float)
    df["Volume"] = df["Volume"].astype(float)
    return df


def _has_cross(fast: pd.Series, slow: pd.Series) -> bool:
    """True si la última vela completa muestra cruce alcista de EMAs."""
    # [-2] = vela anterior, [-1] = vela actual (acaba de cerrar)
    return fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]


def scan(client: Client) -> list[Signal]:
    """
    Escanea todos los pares y devuelve lista de señales de compra
    ordenadas por fuerza (mayor score primero).
    """
    signals = []

    for pair in PAIRS:
        try:
            df = _fetch_candles(client, pair)

            ema_fast = ema(df["Close"], EMA_FAST)
            ema_slow = ema(df["Close"], EMA_SLOW)
            rsi_val  = rsi(df["Close"], RSI_PERIOD).iloc[-1]
            atr_val  = atr(df["High"], df["Low"], df["Close"], ATR_PERIOD).iloc[-1]
            price    = df["Close"].iloc[-1]

            # Filtros de señal
            cross_up    = _has_cross(ema_fast, ema_slow)
            not_overbought = rsi_val < RSI_MAX
            trend_up    = ema_fast.iloc[-1] > ema_slow.iloc[-1]

            if not (cross_up and not_overbought):
                continue

            sl = price - ATR_SL_MULT * atr_val
            tp = price + ATR_TP_MULT * atr_val

            # Score: distancia relativa del cruce + margen de RSI
            ema_gap = (ema_fast.iloc[-1] - ema_slow.iloc[-1]) / price * 100
            score   = ema_gap + (RSI_MAX - rsi_val) / 10

            signals.append(Signal(
                pair=pair, price=price, sl=sl, tp=tp,
                atr_val=atr_val, rsi_val=rsi_val, score=score,
            ))
            logger.info("Señal: %s | precio=%.4f SL=%.4f TP=%.4f RSI=%.1f score=%.3f",
                        pair, price, sl, tp, rsi_val, score)

        except Exception as exc:
            logger.warning("Error escaneando %s: %s", pair, exc)

    return sorted(signals, key=lambda s: s.score, reverse=True)
