"""
Descarga los 4 tickers × 2 timeframes = 8 datasets y muestra un resumen.
Uso: python scripts/download_all.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loader import download, TRAIN_START, OOS_END

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TICKERS    = ["SPY", "AAPL", "NVDA", "TSLA"]
TIMEFRAMES = ["1d", "1h"]


def main():
    rows = []
    errors = []

    for tf in TIMEFRAMES:
        for ticker in TICKERS:
            print(f"\n>> {ticker} {tf} ...", flush=True)
            try:
                df = download(ticker, tf, start=TRAIN_START, end=OOS_END, force=False)
                nans_close  = int(df["Close"].isna().sum())
                nans_volume = int(df["Volume"].isna().sum())
                rows.append({
                    "ticker":      ticker,
                    "timeframe":   tf,
                    "filas":       len(df),
                    "desde":       df.index[0].strftime("%Y-%m-%d"),
                    "hasta":       df.index[-1].strftime("%Y-%m-%d"),
                    "NaN Close":   nans_close,
                    "NaN Volume":  nans_volume,
                })
            except Exception as exc:
                errors.append(f"{ticker} {tf}: {exc}")
                print(f"  ERROR: {exc}", flush=True)

    print("\n" + "="*65)
    print(f"{'Ticker':<6} {'TF':<4} {'Filas':>7}  {'Desde':<12} {'Hasta':<12} {'NaN C':>6} {'NaN V':>6}")
    print("-"*65)
    for r in rows:
        print(f"{r['ticker']:<6} {r['timeframe']:<4} {r['filas']:>7}  "
              f"{r['desde']:<12} {r['hasta']:<12} {r['NaN Close']:>6} {r['NaN Volume']:>6}")

    if errors:
        print("\nERRORES:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("\nTodos los datasets descargados sin errores.")


if __name__ == "__main__":
    main()
