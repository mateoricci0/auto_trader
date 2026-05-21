"""
Escanea todos los pares y devuelve señales de compra validadas.

Modo AI: una sola llamada a DeepSeek con todos los pares — DeepSeek elige los mejores.
Fallback: EMA crossover + RSI + ATR por par.

Filtros de calidad aplicados en ambos modos:
  - SL mínimo MIN_SL_DISTANCE_PCT por debajo del precio
  - R/R mínimo MIN_RR_RATIO
  - Confidence mínima MIN_CONFIDENCE (modo AI)
"""
import logging
from dataclasses import dataclass, field

import pandas as pd
from binance.client import Client

from . import ai_brain
from .config import (ATR_PERIOD, CANDLES_LIMIT, CORR_GROUPS, EMA_FAST,
                     EMA_SLOW, MAX_PER_CORR_GROUP, MIN_CONFIDENCE,
                     MIN_RR_RATIO, MIN_SL_DISTANCE_PCT, MIN_TP_DISTANCE_PCT,
                     PAIRS, RSI_PERIOD, TIMEFRAME)
from .indicators import atr, ema, rsi

logger = logging.getLogger(__name__)

RSI_MIN = 45
RSI_MAX = 65
ATR_SL_MULT = 2.0
ATR_TP_MULT = 6.0   # 6× ATR → R/R ≥ 3:1 por defecto en modo fallback


@dataclass
class Signal:
    pair:      str
    price:     float
    sl:        float
    tp:        float
    atr_val:   float
    rsi_val:   float
    score:     float
    ai_reason: str = field(default="")


def _fetch_candles(client: Client, pair: str) -> pd.DataFrame:
    raw = client.get_klines(symbol=pair, interval=TIMEFRAME, limit=CANDLES_LIMIT)
    df = pd.DataFrame(raw, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
    ])
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = df[col].astype(float)
    return df


def _validate_signal(price: float, sl: float, tp: float) -> str | None:
    """Valida SL/TP. Devuelve mensaje de error o None si es válido."""
    if not (sl < price < tp):
        return f"SL/TP fuera de rango (sl={sl:.4f} price={price:.4f} tp={tp:.4f})"

    sl_dist_pct = (price - sl) / price
    if sl_dist_pct < MIN_SL_DISTANCE_PCT:
        return f"SL demasiado ajustado ({sl_dist_pct:.3%} < {MIN_SL_DISTANCE_PCT:.3%})"

    tp_dist_pct = (tp - price) / price
    if tp_dist_pct < MIN_TP_DISTANCE_PCT:
        return f"TP demasiado pequeño ({tp_dist_pct:.3%} < {MIN_TP_DISTANCE_PCT:.3%} — ganancia insuficiente)"

    rr = tp_dist_pct / sl_dist_pct
    if rr < MIN_RR_RATIO:
        return f"R/R insuficiente ({rr:.2f} < {MIN_RR_RATIO})"

    return None


def _apply_correlation_filter(signals: list[Signal]) -> list[Signal]:
    """
    Limita a MAX_PER_CORR_GROUP señales por grupo de correlación.
    Prioriza las de mayor score.
    """
    group_count: dict[int, int] = {}
    filtered = []

    for sig in signals:
        group_id = None
        for idx, group in enumerate(CORR_GROUPS):
            if sig.pair in group:
                group_id = idx
                break

        if group_id is not None:
            count = group_count.get(group_id, 0)
            if count >= MAX_PER_CORR_GROUP:
                logger.info("Filtro correlación: %s descartado (grupo %d lleno)", sig.pair, group_id)
                continue
            group_count[group_id] = count + 1

        filtered.append(sig)

    return filtered


def scan(client: Client) -> list[Signal]:
    """
    Escanea todos los pares. Si DeepSeek está disponible, hace UNA llamada con
    todos los pares. Si no, usa reglas técnicas par a par.
    """
    # 1. Descargar velas y calcular indicadores para todos los pares
    pair_data = []
    indicators_map: dict[str, dict] = {}

    for pair in PAIRS:
        try:
            df = _fetch_candles(client, pair)
            ind = {
                "price":    df["Close"].iloc[-1],
                "ema_fast": ema(df["Close"], EMA_FAST).iloc[-1],
                "ema_slow": ema(df["Close"], EMA_SLOW).iloc[-1],
                "rsi":      rsi(df["Close"], RSI_PERIOD).iloc[-1],
                "atr":      atr(df["High"], df["Low"], df["Close"], ATR_PERIOD).iloc[-1],
            }
            indicators_map[pair] = {**ind, "df": df}

            candles_text = df.tail(30)[["Open","High","Low","Close","Volume"]].round(6).to_string(index=False)
            pair_data.append({**ind, "pair": pair, "candles_text": candles_text})

        except Exception as exc:
            logger.warning("Error cargando %s: %s", pair, exc)

    # 2. Generar señales
    signals: list[Signal] = []

    if ai_brain.is_available():
        logger.info("Consultando DeepSeek con %d pares (1 llamada)...", len(pair_data))
        trades = ai_brain.analyze_all(pair_data)

        for t in trades:
            pair  = t["pair"]
            price = indicators_map.get(pair, {}).get("price")
            if price is None:
                continue

            conf = t["confidence"]
            if conf < MIN_CONFIDENCE:
                logger.info("%s: confidence %.2f < %.2f — descartado", pair, conf, MIN_CONFIDENCE)
                continue

            err = _validate_signal(price, t["sl"], t["tp"])
            if err:
                logger.info("%s: señal inválida — %s", pair, err)
                continue

            ind = indicators_map[pair]
            signals.append(Signal(
                pair=pair, price=price, sl=t["sl"], tp=t["tp"],
                atr_val=ind["atr"], rsi_val=ind["rsi"],
                score=conf, ai_reason=t.get("reason", ""),
            ))
            logger.info("Señal AI válida: %s | precio=%.4f SL=%.4f TP=%.4f R/R=%.1f conf=%.2f | %s",
                        pair, price, t["sl"], t["tp"],
                        (t["tp"] - price) / (price - t["sl"]),
                        conf, t.get("reason", ""))

    else:
        # Modo fallback: reglas técnicas par a par
        for pair, ind in indicators_map.items():
            price    = ind["price"]
            ema_f    = ema(ind["df"]["Close"], EMA_FAST)
            ema_s    = ema(ind["df"]["Close"], EMA_SLOW)
            rsi_val  = ind["rsi"]
            atr_val  = ind["atr"]

            cross_up = ema_f.iloc[-2] <= ema_s.iloc[-2] and ema_f.iloc[-1] > ema_s.iloc[-1]
            rsi_ok   = RSI_MIN < rsi_val < RSI_MAX

            if not (cross_up and rsi_ok):
                continue

            sl = price - ATR_SL_MULT * atr_val
            tp = price + ATR_TP_MULT * atr_val

            err = _validate_signal(price, sl, tp)
            if err:
                logger.info("%s: señal técnica inválida — %s", pair, err)
                continue

            ema_gap = (ema_f.iloc[-1] - ema_s.iloc[-1]) / price * 100
            score   = ema_gap + (RSI_MAX - rsi_val) / 10

            signals.append(Signal(
                pair=pair, price=price, sl=sl, tp=tp,
                atr_val=atr_val, rsi_val=rsi_val, score=score,
            ))
            logger.info("Señal técnica: %s | precio=%.4f SL=%.4f TP=%.4f RSI=%.1f",
                        pair, price, sl, tp, rsi_val)

    # 3. Filtro de correlación y ordenar por score
    signals = _apply_correlation_filter(sorted(signals, key=lambda s: s.score, reverse=True))
    return signals
