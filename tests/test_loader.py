"""Tests unitarios del módulo data/loader.py."""
import shutil
from pathlib import Path

import pandas as pd
import pytest

from data.loader import download, load_split, CACHE_DIR, TRAIN_START, TRAIN_END, OOS_START

TICKER = "SPY"
TF     = "1d"


@pytest.fixture(autouse=True)
def _clear_spy_cache():
    """Limpia el caché de SPY 1d antes/después de cada test."""
    path = CACHE_DIR / f"{TICKER}_{TF}.parquet"
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


class TestDownload:
    def test_columnas_correctas(self):
        df = download(TICKER, TF)
        assert set(df.columns) >= {"Open", "High", "Low", "Close", "Volume"}, \
            f"Columnas inesperadas: {df.columns.tolist()}"

    def test_index_datetime_utc(self):
        df = download(TICKER, TF)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.tz is not None and str(df.index.tz) == "UTC"

    def test_no_filas_vacias(self):
        df = download(TICKER, TF)
        assert len(df) > 0, "DataFrame vacío"

    def test_timeframe_invalido(self):
        with pytest.raises(ValueError, match="timeframe debe ser"):
            download(TICKER, "15m")


class TestCache:
    def test_segunda_llamada_no_descarga(self, monkeypatch):
        """La segunda llamada debe leer del parquet, no de yfinance."""
        download(TICKER, TF)  # primera vez — crea caché

        llamadas = {"n": 0}
        original_download = __import__("data.loader", fromlist=["_download_1d"])._download_1d

        def mock_download_1d(*args, **kwargs):
            llamadas["n"] += 1
            return original_download(*args, **kwargs)

        monkeypatch.setattr("data.loader._download_1d", mock_download_1d)
        download(TICKER, TF)  # segunda vez — debe usar caché

        assert llamadas["n"] == 0, "Se llamó a _download_1d a pesar de que el caché existía"

    def test_force_redescarga(self, monkeypatch):
        """force=True debe ignorar el caché."""
        download(TICKER, TF)  # crea caché

        llamadas = {"n": 0}
        original = __import__("data.loader", fromlist=["_download_1d"])._download_1d

        def mock_1d(*args, **kwargs):
            llamadas["n"] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr("data.loader._download_1d", mock_1d)
        download(TICKER, TF, force=True)

        assert llamadas["n"] == 1, "force=True no llamó a _download_1d"


class TestLoadSplit:
    @pytest.fixture(autouse=True)
    def _setup(self):
        """Descarga datos una sola vez para todos los tests de este bloque."""
        download(TICKER, TF)  # llena caché

    def test_no_solapamiento(self):
        train, test = load_split(TICKER, TF)
        if len(train) > 0 and len(test) > 0:
            assert train.index.max() < test.index.min(), \
                "train y test se solapan"

    def test_fechas_train(self):
        train, _ = load_split(TICKER, TF)
        assert train.index.min() >= pd.Timestamp(TRAIN_START, tz="UTC")
        assert train.index.max() <= pd.Timestamp(TRAIN_END,   tz="UTC")

    def test_fechas_test(self):
        _, test = load_split(TICKER, TF)
        if len(test) > 0:
            assert test.index.min() >= pd.Timestamp(OOS_START, tz="UTC")

    def test_sin_nans_close(self):
        train, test = load_split(TICKER, TF)
        assert train["Close"].isna().sum() == 0, "NaNs en Close de train"
        if len(test) > 0:
            assert test["Close"].isna().sum() == 0, "NaNs en Close de test"

    def test_sin_nans_volume(self):
        train, test = load_split(TICKER, TF)
        assert train["Volume"].isna().sum() == 0, "NaNs en Volume de train"
