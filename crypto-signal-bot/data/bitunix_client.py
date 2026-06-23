"""
Bitunix API Client - دریافت داده کندل از صرافی Bitunix
Base URL: https://fapi.bitunix.com
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Optional


BASE_URL = "https://fapi.bitunix.com"

# بازه‌های زمانی مجاز
VALID_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]


def get_klines(
    symbol: str,
    interval: str = "15m",
    limit: int = 200,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """
    دریافت داده کندل از Bitunix

    Args:
        symbol:     جفت ارز مثلاً BTCUSDT
        interval:   بازه زمانی: 1m 5m 15m 30m 1h 4h 1d ...
        limit:      تعداد کندل (max 200)
        start_time: تایم‌استمپ شروع (میلی‌ثانیه)
        end_time:   تایم‌استمپ پایان (میلی‌ثانیه)

    Returns:
        DataFrame با ستون‌های: time, open, high, low, close, quoteVol, baseVol
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"interval باید یکی از اینا باشه: {VALID_INTERVALS}")

    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": min(limit, 200),
    }
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time

    try:
        headers = {"User-Agent": "Mozilla/5.0 (crypto-signal-bot/1.0)"}
        resp = requests.get(
            f"{BASE_URL}/api/v1/futures/market/kline",
            params=params,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Bitunix API خطا داد: {data.get('msg')}")

        candles = data["data"]
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms")
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
        df[["quoteVol", "baseVol"]] = df[["quoteVol", "baseVol"]].astype(float)
        df = df.sort_values("time").reset_index(drop=True)

        return df

    except requests.RequestException as e:
        raise ConnectionError(f"خطا در اتصال به Bitunix: {e}")


def get_ticker(symbol: str) -> dict:
    """
    دریافت قیمت لحظه‌ای یک جفت ارز
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/futures/market/tickers",
        params={"symbol": symbol.upper()},
        headers={"User-Agent": "Mozilla/5.0 (crypto-signal-bot/1.0)"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"خطا: {data.get('msg')}")

    tickers = data.get("data", [])
    if not tickers:
        return {}

    # اول دقیقاً symbol رو پیدا کن
    for t in tickers:
        if t.get("symbol", "").upper() == symbol.upper():
            return t

    # اگه فقط یه نتیجه برگشت
    if len(tickers) == 1:
        return tickers[0]

    return {}


def get_trading_pairs() -> list:
    """
    دریافت لیست تمام جفت ارزهای موجود در Bitunix
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/futures/market/trading_pairs",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return [p["symbol"] for p in data.get("data", [])]


# ───── تست سریع ─────
if __name__ == "__main__":
    print("📡 دریافت کندل‌های BTCUSDT (15 دقیقه‌ای)...")
    df = get_klines("BTCUSDT", interval="15m", limit=10)
    print(df[["time", "open", "high", "low", "close", "baseVol"]])
    print(f"\n✅ {len(df)} کندل دریافت شد")
