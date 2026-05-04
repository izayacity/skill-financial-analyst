"""
Technical Tool - Daily technical metrics with local parquet caching.

Workflow:
1. Read ticker history from local parquet (if present).
2. Fetch recent daily OHLCV via existing API fallback flow.
3. Merge local + fetched price rows and recompute MA/RSI metrics.
4. Persist merged results back to parquet.
5. Return latest-row technical snapshot by default.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import pandas as pd

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from persist.persist_factory import PersistFactory
from scripts.api_caller import call_api, call_with_fallback
from scripts.api_config import get_api_key
from scripts.data_fetchers import (
    alpha_vantage_price_history,
    fmp_price_history,
    polygon_price_history,
    yfinance_price_history,
)


DEFAULT_LOOKBACK_DAYS = 90
PARQUET_DIR = os.path.join(_project_root, "data", "parquet")
EASTERN_TZ = ZoneInfo("America/New_York")


def technical_parquet_path(ticker: str) -> str:
    """Return per-ticker parquet path."""
    symbol = ticker.strip().upper()
    return os.path.join(PARQUET_DIR, f"{symbol}_technical_daily.parquet")


def load_local_technical_history(ticker: str) -> pd.DataFrame:
    """Load local technical parquet if available; else return empty DataFrame."""
    path = technical_parquet_path(ticker)
    if not os.path.exists(path):
        return pd.DataFrame()

    try:
        factory = PersistFactory("parquet", path)
        df = factory.read(as_dataframe=True)
    except FileNotFoundError:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    if "trade_date" in df.columns:
        df["trade_date"] = _normalize_trade_date(df["trade_date"])
        df = df[df["trade_date"].notna()]
        expected_text = _format_trade_date_int(df["trade_date"])
        if "trade_date_text" not in df.columns:
            df["trade_date_text"] = expected_text
        else:
            existing_text = pd.to_numeric(df["trade_date_text"], errors="coerce").astype("Int64")
            repair_mask = existing_text.isna() | (existing_text != expected_text)
            df["trade_date_text"] = existing_text
            if repair_mask.any():
                df.loc[repair_mask, "trade_date_text"] = expected_text[repair_mask]
            df["trade_date_text"] = df["trade_date_text"].astype("Int64")
    return df


def build_price_fetchers(ticker: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> Dict[str, callable]:
    """Create fallback-compatible fetchers using existing API fetch functions."""
    period_days = max(30, int(lookback_days))
    return {
        "yfinance": lambda: yfinance_price_history(ticker, period=f"{period_days}d", interval="1d"),
        "polygon": lambda: polygon_price_history(ticker, days=period_days),
        "alpha_vantage": lambda: alpha_vantage_price_history(ticker),
        "fmp": lambda: fmp_price_history(ticker),
    }


def fetch_recent_price_history(ticker: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> Dict:
    """
    Fetch recent price history through the shared fallback pipeline.

    Returns:
        dict with call_with_fallback response shape.
    """
    fetchers = build_price_fetchers(ticker, lookback_days=lookback_days)
    return call_with_fallback("price_history", fetchers)


def _normalize_from_yfinance(payload: Dict) -> pd.DataFrame:
    raw = payload.get("data")
    if raw is None or getattr(raw, "empty", True):
        return pd.DataFrame()

    df = raw.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    normalized = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df[date_col], errors="coerce"),
            "open": pd.to_numeric(df.get("Open"), errors="coerce"),
            "high": pd.to_numeric(df.get("High"), errors="coerce"),
            "low": pd.to_numeric(df.get("Low"), errors="coerce"),
            "close": pd.to_numeric(df.get("Close"), errors="coerce"),
            "volume": pd.to_numeric(df.get("Volume"), errors="coerce"),
        }
    )
    return _finalize_price_frame(normalized)


def _normalize_from_polygon(payload: Dict) -> pd.DataFrame:
    rows = payload.get("results") or []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    normalized = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df.get("t"), unit="ms", errors="coerce"),
            "open": pd.to_numeric(df.get("o"), errors="coerce"),
            "high": pd.to_numeric(df.get("h"), errors="coerce"),
            "low": pd.to_numeric(df.get("l"), errors="coerce"),
            "close": pd.to_numeric(df.get("c"), errors="coerce"),
            "volume": pd.to_numeric(df.get("v"), errors="coerce"),
        }
    )
    return _finalize_price_frame(normalized)


def _normalize_from_alpha_vantage(payload: Dict) -> pd.DataFrame:
    ts = payload.get("time_series") or {}
    if not isinstance(ts, dict) or not ts:
        return pd.DataFrame()

    rows = []
    for day, values in ts.items():
        rows.append(
            {
                "trade_date": pd.to_datetime(day, errors="coerce"),
                "open": pd.to_numeric(values.get("1. open"), errors="coerce"),
                "high": pd.to_numeric(values.get("2. high"), errors="coerce"),
                "low": pd.to_numeric(values.get("3. low"), errors="coerce"),
                "close": pd.to_numeric(values.get("4. close"), errors="coerce"),
                "volume": pd.to_numeric(values.get("5. volume"), errors="coerce"),
            }
        )
    return _finalize_price_frame(pd.DataFrame(rows))


def _normalize_from_fmp(payload: Dict) -> pd.DataFrame:
    raw = payload.get("data")
    if isinstance(raw, dict) and isinstance(raw.get("historical"), list):
        rows = raw.get("historical")
    elif isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = [raw]
    else:
        rows = []

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "close" in df.columns:
        close_series = pd.to_numeric(df["close"], errors="coerce")
        if "adjClose" in df.columns:
            close_series = close_series.fillna(pd.to_numeric(df["adjClose"], errors="coerce"))
    else:
        close_series = pd.to_numeric(df.get("adjClose"), errors="coerce")

    normalized = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df.get("date"), errors="coerce"),
            "open": pd.to_numeric(df.get("open"), errors="coerce"),
            "high": pd.to_numeric(df.get("high"), errors="coerce"),
            "low": pd.to_numeric(df.get("low"), errors="coerce"),
            "close": close_series,
            "volume": pd.to_numeric(df.get("volume"), errors="coerce"),
        }
    )
    return _finalize_price_frame(normalized)


def normalize_price_history(api_id: str, payload: Dict) -> pd.DataFrame:
    """Normalize any price-history source into trade_date/open/high/low/close/volume."""
    normalizers = {
        "yfinance": _normalize_from_yfinance,
        "polygon": _normalize_from_polygon,
        "alpha_vantage": _normalize_from_alpha_vantage,
        "fmp": _normalize_from_fmp,
    }
    normalizer = normalizers.get(api_id)
    if normalizer is None:
        raise ValueError(f"Unsupported price-history source: {api_id}")
    return normalizer(payload)


def _finalize_price_frame(df: pd.DataFrame, keep_missing_close: bool = False) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume"])

    out = df.copy()
    out["trade_date"] = _normalize_trade_date(out["trade_date"])
    out = out[out["trade_date"].notna()]
    if not keep_missing_close:
        out = out[out["close"].notna()]

    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.sort_values("trade_date")
    out = out.drop_duplicates(subset=["trade_date"], keep="last")
    return out.reset_index(drop=True)


def _normalize_trade_date(series: pd.Series) -> pd.Series:
    """Normalize timestamps to day granularity with tz removed."""
    ts = pd.to_datetime(series, errors="coerce")
    if getattr(ts.dtype, "tz", None) is not None:
        ts = ts.dt.tz_convert(None)
    return ts.dt.normalize()


def _format_trade_date_int(series: pd.Series) -> pd.Series:
    """Return YYYYMMDD integer from a date series."""
    normalized = _normalize_trade_date(series)
    text = normalized.dt.strftime("%Y%m%d")
    return pd.to_numeric(text, errors="coerce").astype("Int64")


def _extract_local_price_columns(local_df: pd.DataFrame) -> pd.DataFrame:
    required = ["trade_date", "open", "high", "low", "close", "volume"]
    if local_df is None or local_df.empty or not all(col in local_df.columns for col in required):
        return pd.DataFrame(columns=required)

    out = local_df[required].copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.normalize()
    return _finalize_price_frame(out, keep_missing_close=True)


def merge_price_history(local_price: pd.DataFrame, remote_price: pd.DataFrame) -> pd.DataFrame:
    """Merge local and remote OHLCV by trade_date (remote wins on overlap)."""
    if (local_price is None or local_price.empty) and (remote_price is None or remote_price.empty):
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume"])
    if local_price is None or local_price.empty:
        return _finalize_price_frame(remote_price, keep_missing_close=True)
    if remote_price is None or remote_price.empty:
        return _finalize_price_frame(local_price, keep_missing_close=True)

    local = local_price.copy()
    remote = remote_price.copy()
    local["_source_priority"] = 0
    remote["_source_priority"] = 1

    combined = pd.concat([local, remote], ignore_index=True)
    combined["_has_close"] = combined["close"].notna().astype(int)
    # Resolution order per date:
    # 1) rows with close beat rows without close
    # 2) if both have close, remote beats local
    combined = combined.sort_values(["trade_date", "_has_close", "_source_priority"])
    combined = combined.drop_duplicates(subset=["trade_date"], keep="last")
    combined = combined.drop(columns=["_source_priority", "_has_close"], errors="ignore")
    return _finalize_price_frame(combined, keep_missing_close=True)


def append_today_placeholder(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure current-date row exists.
    If today's finalized close is unavailable, keep a temporary row with close=None.
    """
    out = _finalize_price_frame(price_df, keep_missing_close=True)
    # Always align "today" to US Eastern market date.
    today = pd.Timestamp(datetime.now(EASTERN_TZ).date())

    # Clean stale future placeholder rows caused by non-Eastern local clocks.
    if not out.empty:
        out = out[~((out["trade_date"] > today) & out["close"].isna())].copy()

    if out.empty:
        out = pd.DataFrame(
            [{"trade_date": today, "open": pd.NA, "high": pd.NA, "low": pd.NA, "close": pd.NA, "volume": pd.NA}]
        )
        return _finalize_price_frame(out, keep_missing_close=True)

    today_mask = out["trade_date"] == today
    if not today_mask.any():
        out = pd.concat(
            [
                out,
                pd.DataFrame(
                    [{"trade_date": today, "open": pd.NA, "high": pd.NA, "low": pd.NA, "close": pd.NA, "volume": pd.NA}]
                ),
            ],
            ignore_index=True,
        )

    out = out.sort_values("trade_date")
    out = out.drop_duplicates(subset=["trade_date"], keep="last")
    return _finalize_price_frame(out, keep_missing_close=True)


def _fetch_fmp_intraday_snapshot(ticker: str) -> Dict:
    """Fetch current session quote fields from FMP."""
    import requests

    key = get_api_key("fmp")
    if not key:
        raise ValueError("FMP API key not configured")

    r = requests.get(
        "https://financialmodelingprep.com/stable/quote",
        params={"symbol": ticker, "apikey": key},
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json()
    row = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(row, dict):
        raise ValueError("FMP quote response malformed")

    return {
        "open": row.get("open"),
        "high": row.get("dayHigh"),
        "low": row.get("dayLow"),
        "volume": row.get("volume"),
        "price": row.get("price"),
        "timestamp": row.get("timestamp"),
    }


def _fetch_finnhub_intraday_snapshot(ticker: str) -> Dict:
    """Fetch current session quote fields from Finnhub."""
    import requests

    key = get_api_key("finnhub")
    if not key:
        raise ValueError("Finnhub API key not configured")

    r = requests.get(
        "https://finnhub.io/api/v1/quote",
        params={"symbol": ticker, "token": key},
        timeout=15,
    )
    r.raise_for_status()
    row = r.json()
    if not isinstance(row, dict):
        raise ValueError("Finnhub quote response malformed")

    return {
        "open": row.get("o"),
        "high": row.get("h"),
        "low": row.get("l"),
        "volume": None,  # Finnhub quote endpoint does not provide volume.
        "price": row.get("c"),
        "timestamp": row.get("t"),
    }


def _fetch_yfinance_intraday_snapshot(ticker: str) -> Dict:
    """Fetch current session quote fields from yfinance 1m intraday bars."""
    payload = yfinance_price_history(ticker, period="1d", interval="1m")
    df = payload.get("data")
    if df is None or df.empty:
        raise ValueError(f"No yfinance intraday data for {ticker}")

    open_price = pd.to_numeric(df["Open"], errors="coerce").dropna()
    high_price = pd.to_numeric(df["High"], errors="coerce").dropna()
    low_price = pd.to_numeric(df["Low"], errors="coerce").dropna()
    close_price = pd.to_numeric(df["Close"], errors="coerce").dropna()
    volume_series = pd.to_numeric(df["Volume"], errors="coerce").dropna()

    return {
        "open": float(open_price.iloc[0]) if not open_price.empty else None,
        "high": float(high_price.max()) if not high_price.empty else None,
        "low": float(low_price.min()) if not low_price.empty else None,
        "volume": int(volume_series.sum()) if not volume_series.empty else None,
        "price": float(close_price.iloc[-1]) if not close_price.empty else None,
        "timestamp": None,
    }


def _fetch_intraday_snapshot(ticker: str) -> Dict:
    """
    Fetch current-session intraday fields from available quote APIs.

    Order:
      1) FMP (includes open/high/low/volume)
      2) Finnhub (includes open/high/low/current)
      3) yfinance intraday bars
    """
    attempts = [
        ("fmp", lambda: _fetch_fmp_intraday_snapshot(ticker)),
        ("finnhub", lambda: _fetch_finnhub_intraday_snapshot(ticker)),
        ("yfinance", lambda: _fetch_yfinance_intraday_snapshot(ticker)),
    ]

    for api_id, fn in attempts:
        result = call_api(api_id, "intraday_snapshot", fn)
        if not result.get("success"):
            continue
        data = result.get("data") or {}
        if any(data.get(k) is not None for k in ("open", "high", "low", "volume", "price")):
            return {"api_id": api_id, "data": data}

    return {"api_id": None, "data": {}}


def apply_intraday_snapshot_to_today(ticker: str, price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill today's temporary row with available intraday fields.
    Keep close empty until finalized day-close data is available.
    """
    out = append_today_placeholder(price_df)
    if out.empty:
        return out

    today = pd.Timestamp(datetime.now(EASTERN_TZ).date())
    today_mask = out["trade_date"] == today
    if not today_mask.any():
        return out

    # If today already has finalized close, do not override.
    if out.loc[today_mask, "close"].notna().any():
        return out

    snap = _fetch_intraday_snapshot(ticker)
    data = snap.get("data") or {}
    if not data:
        return out

    field_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "volume": "volume",
    }
    for snap_key, col in field_map.items():
        val = data.get(snap_key)
        if val is None:
            continue
        out.loc[today_mask, col] = pd.to_numeric(val, errors="coerce")

    # Keep close empty on temporary intraday row by design.
    out.loc[today_mask, "close"] = pd.NA
    return _finalize_price_frame(out, keep_missing_close=True)


def _compute_rsi_series(close: pd.Series, period: int) -> pd.Series:
    """Simple rolling RSI (SMA-based)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    # Keep output numeric (float) to avoid pandas extension-dtype assignment issues.
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_required_technicals(price_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Compute required daily fields only:
    - MA: 5, 10, 20, 50
    - RSI: 6, 12, 24
    - OHLCV + trade_date + ticker
    """
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    df = _finalize_price_frame(price_df, keep_missing_close=True).copy()
    df["ticker"] = ticker.strip().upper()
    df["trade_date_text"] = _format_trade_date_int(df["trade_date"])
    if "volume" in df.columns:
        df["volume"] = df["volume"].round().astype("Int64")

    close = pd.to_numeric(df["close"], errors="coerce")
    df["ma_5"] = close.rolling(window=5, min_periods=5).mean()
    df["ma_10"] = close.rolling(window=10, min_periods=10).mean()
    df["ma_20"] = close.rolling(window=20, min_periods=20).mean()
    df["ma_50"] = close.rolling(window=50, min_periods=50).mean()
    df["rsi_6"] = _compute_rsi_series(close, 6)
    df["rsi_12"] = _compute_rsi_series(close, 12)
    df["rsi_24"] = _compute_rsi_series(close, 24)

    # Keep schema stable for downstream range queries.
    ordered_cols = [
        "ticker",
        "trade_date",
        "trade_date_text",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ma_5",
        "ma_10",
        "ma_20",
        "ma_50",
        "rsi_6",
        "rsi_12",
        "rsi_24",
    ]
    return df[ordered_cols].reset_index(drop=True)


def save_technical_history(ticker: str, technical_df: pd.DataFrame) -> str:
    """Overwrite per-ticker parquet with merged/recalculated technical history."""
    os.makedirs(PARQUET_DIR, exist_ok=True)
    path = technical_parquet_path(ticker)
    factory = PersistFactory("parquet", path)
    to_write = technical_df.copy()
    if "trade_date" in to_write.columns:
        to_write["trade_date"] = _normalize_trade_date(to_write["trade_date"])
        to_write = to_write[to_write["trade_date"].notna()]
        to_write["trade_date_text"] = _format_trade_date_int(to_write["trade_date"])
        to_write = to_write.sort_values("trade_date")
    factory.write(to_write, append=False)
    return path


def _row_to_python_dict(row: pd.Series) -> Dict:
    out = row.to_dict()
    if pd.notna(out.get("trade_date")):
        out["trade_date"] = pd.to_datetime(out["trade_date"]).strftime("%Y-%m-%d")
    for key, value in list(out.items()):
        if isinstance(value, pd.Timestamp):
            out[key] = value.strftime("%Y-%m-%d")
        elif pd.isna(value):
            out[key] = None
    return out


def query_technical_metrics(
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    refresh_remote: bool = True,
) -> Dict:
    """
    Query a ticker's technical metrics with local-first + incremental refresh flow.

    Default return is latest row.
    """
    symbol = ticker.strip().upper()
    local_df = load_local_technical_history(symbol)
    local_price = _extract_local_price_columns(local_df)

    api_used = None
    remote_price = pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume"])
    remote_error = None

    if refresh_remote:
        fetch_result = fetch_recent_price_history(symbol, lookback_days=lookback_days)
        if fetch_result.get("success"):
            api_used = fetch_result.get("api_id")
            remote_price = normalize_price_history(api_used, fetch_result.get("data") or {})
        else:
            remote_error = fetch_result.get("error")

    merged_price = merge_price_history(local_price, remote_price)
    merged_price = apply_intraday_snapshot_to_today(symbol, merged_price)
    if merged_price.empty:
        raise ValueError(f"No price history available for {symbol}. Last remote error: {remote_error}")

    technical_df = compute_required_technicals(merged_price, symbol)
    parquet_path = save_technical_history(symbol, technical_df)
    latest = _row_to_python_dict(technical_df.iloc[-1])

    return {
        "ticker": symbol,
        "latest": latest,
        "rows": int(len(technical_df)),
        "api_used": api_used,
        "remote_error": remote_error,
        "parquet_path": parquet_path,
    }


def get_cached_technical_history(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Read cached history with optional date-range filtering.
    Reserved for future date-range queries.
    """
    df = load_local_technical_history(ticker)
    if df.empty or "trade_date" not in df.columns:
        return df

    filtered = df.copy()
    filtered["trade_date"] = pd.to_datetime(filtered["trade_date"], errors="coerce").dt.normalize()
    if start_date:
        start_ts = pd.to_datetime(start_date, errors="coerce")
        if pd.notna(start_ts):
            filtered = filtered[filtered["trade_date"] >= start_ts.normalize()]
    if end_date:
        end_ts = pd.to_datetime(end_date, errors="coerce")
        if pd.notna(end_ts):
            filtered = filtered[filtered["trade_date"] <= end_ts.normalize()]
    return filtered.sort_values("trade_date").reset_index(drop=True)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Daily technical metrics tool with local parquet cache.")
    parser.add_argument("ticker", help="Ticker, e.g. AAPL")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="Remote refresh lookback window.")
    parser.add_argument("--no-refresh", action="store_true", help="Skip remote call and use local parquet only.")
    args = parser.parse_args()

    result = query_technical_metrics(
        ticker=args.ticker,
        lookback_days=args.lookback_days,
        refresh_remote=not args.no_refresh,
    )

    latest = result["latest"]
    print(f"Ticker: {result['ticker']}")
    print(f"Date: {latest.get('trade_date')}")
    print(f"Close: {latest.get('close')}")
    print(f"MA5/10/20/50: {latest.get('ma_5')}, {latest.get('ma_10')}, {latest.get('ma_20')}, {latest.get('ma_50')}")
    print(f"RSI6/12/24: {latest.get('rsi_6')}, {latest.get('rsi_12')}, {latest.get('rsi_24')}")
    print(f"Volume: {latest.get('volume')}")
    print(f"Rows: {result['rows']}")
    print(f"API used: {result.get('api_used')}")
    print(f"Parquet: {result['parquet_path']}")


if __name__ == "__main__":
    _main()
