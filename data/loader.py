import time
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
TRAIN_START = "2023-01-01"
TRAIN_END   = "2025-06-30"
OOS_START   = "2025-07-01"
OOS_END     = "2025-12-31"

# yfinance limita datos 1h a los últimos ~730 días desde hoy.
# Para cubrir 2023-01-01 usamos descarga incremental por bloques de 6 meses.
_1H_BLOCK_MONTHS = 6


def _cache_path(ticker: str, timeframe: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker}_{timeframe}.parquet"


def _download_with_retry(ticker: str, start: str, end: str, interval: str, retries: int = 3) -> pd.DataFrame:
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                ticker,
                start=start,
                end=end,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )
            if df is not None and not df.empty:
                return df
            logger.warning("%s %s [%s-%s] devolvió vacío (intento %d)", ticker, interval, start, end, attempt)
        except Exception as exc:
            logger.warning("%s %s intento %d falló: %s", ticker, interval, attempt, exc)
        if attempt < retries:
            time.sleep(2)
    return pd.DataFrame()


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas y tz a UTC para compatibilidad con backtesting.py."""
    if df.empty:
        return df

    # yfinance puede devolver MultiIndex cuando se descarga 1 ticker — aplanar
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Renombrar a capitalizadas
    rename = {c: c.capitalize() for c in df.columns}
    rename.update({"Adj close": "Close", "Adj Close": "Close"})
    df = df.rename(columns=rename)

    needed = {"Open", "High", "Low", "Close", "Volume"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes tras normalización: {missing}")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()

    # Asegurar DatetimeIndex con timezone UTC
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    return df


def _download_1d(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = _download_with_retry(ticker, start, end, "1d")
    return _normalize(df)


def _download_1h(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga 1h en bloques para sortear el limite de 730 dias de yfinance.

    LIMITACION CONOCIDA: yfinance solo provee datos 1h para los ultimos
    ~730 dias desde hoy. Bloques anteriores a esa ventana se omiten
    silenciosamente en lugar de reintentar 3 veces con error esperable.
    En la practica (hoy=2026-05-19) la cobertura 1h arranca ~2024-05-19.
    """
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=728)
    starts = pd.date_range(start=start, end=end, freq=f"{_1H_BLOCK_MONTHS}MS")
    ends   = starts.shift(_1H_BLOCK_MONTHS, freq="MS")

    frames = []
    for s, e in zip(starts, ends):
        # Saltar bloques claramente fuera del rango disponible
        if e < cutoff:
            logger.debug("1h bloque [%s-%s] fuera de ventana 730d, omitido",
                         s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"))
            continue
        s_str = max(s, cutoff).strftime("%Y-%m-%d")
        e_str = min(e, pd.Timestamp(end)).strftime("%Y-%m-%d")
        chunk = _download_with_retry(ticker, s_str, e_str, "1h")
        if not chunk.empty:
            frames.append(chunk)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames)
    return _normalize(df)


def download(
    ticker: str,
    timeframe: str,
    start: str = TRAIN_START,
    end: str   = OOS_END,
    force: bool = False,
) -> pd.DataFrame:
    """
    Descarga datos OHLCV y los cachea en parquet.

    Args:
        ticker:    símbolo (SPY, AAPL, …)
        timeframe: '1h' o '1d'
        start:     fecha inicio YYYY-MM-DD
        end:       fecha fin   YYYY-MM-DD
        force:     si True, ignora caché y descarga de nuevo
    """
    if timeframe not in ("1h", "1d"):
        raise ValueError(f"timeframe debe ser '1h' o '1d', recibido: {timeframe!r}")

    path = _cache_path(ticker, timeframe)
    if path.exists() and not force:
        logger.info("Caché hit: %s", path)
        return pd.read_parquet(path)

    logger.info("Descargando %s %s [%s → %s]", ticker, timeframe, start, end)
    if timeframe == "1d":
        df = _download_1d(ticker, start, end)
    else:
        df = _download_1h(ticker, start, end)

    if df.empty:
        raise RuntimeError(f"No se obtuvieron datos para {ticker} {timeframe}")

    df.to_parquet(path)
    logger.info("Guardado: %s (%d filas)", path, len(df))
    return df


def load_split(ticker: str, timeframe: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga datos del caché y los divide en train / test (OOS).

    Returns:
        (df_train, df_test) — fechas no solapadas garantizadas.
        train: 2023-01-01 a 2025-06-30
        test:  2025-07-01 a 2025-12-31
    """
    df = download(ticker, timeframe)

    train_mask = (df.index >= pd.Timestamp(TRAIN_START, tz="UTC")) & \
                 (df.index <= pd.Timestamp(TRAIN_END,   tz="UTC"))
    test_mask  = (df.index >= pd.Timestamp(OOS_START,   tz="UTC")) & \
                 (df.index <= pd.Timestamp(OOS_END,     tz="UTC"))

    return df[train_mask].copy(), df[test_mask].copy()
