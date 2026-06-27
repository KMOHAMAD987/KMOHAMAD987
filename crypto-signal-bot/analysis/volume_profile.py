import numpy as np
import pandas as pd


def compute_volume_profile(df: pd.DataFrame, bins: int = 50) -> dict:
    if df.empty or len(df) < 2:
        return {
            "poc": None,
            "hvn_zones": [],
            "lvn_zones": [],
            "price_vs_poc": None,
            "nearest_hvn": None,
            "nearest_lvn": None,
        }

    price_low = df["low"].min()
    price_high = df["high"].max()

    if price_high == price_low:
        price_high = price_low + 1

    bin_edges = np.linspace(price_low, price_high, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    vol_by_bin = np.zeros(bins)

    for _, row in df.iterrows():
        mask = (bin_centers >= row["low"]) & (bin_centers <= row["high"])
        matching = np.where(mask)[0]
        if len(matching) > 0:
            vol_by_bin[matching] += row["baseVol"] / len(matching)

    poc_idx = int(np.argmax(vol_by_bin))
    poc_price = float(bin_centers[poc_idx])

    p70 = np.percentile(vol_by_bin, 70)
    p30 = np.percentile(vol_by_bin, 30)

    hvn_zones = []
    for i in range(bins):
        if vol_by_bin[i] >= p70:
            hvn_zones.append({
                "low": float(bin_edges[i]),
                "high": float(bin_edges[i + 1]),
            })

    lvn_zones = []
    for i in range(bins):
        if vol_by_bin[i] <= p30:
            lvn_zones.append({
                "low": float(bin_edges[i]),
                "high": float(bin_edges[i + 1]),
            })

    current_price = float(df["close"].iloc[-1])

    if current_price > poc_price:
        price_vs_poc = "above"
    elif current_price < poc_price:
        price_vs_poc = "below"
    else:
        price_vs_poc = "at"

    nearest_hvn = _find_nearest_zone(hvn_zones, current_price)
    nearest_lvn = _find_nearest_zone(lvn_zones, current_price)

    return {
        "poc": poc_price,
        "hvn_zones": hvn_zones,
        "lvn_zones": lvn_zones,
        "price_vs_poc": price_vs_poc,
        "nearest_hvn": nearest_hvn,
        "nearest_lvn": nearest_lvn,
    }


def _find_nearest_zone(zones, price):
    if not zones:
        return None
    best = None
    best_dist = float("inf")
    for zone in zones:
        mid = (zone["low"] + zone["high"]) / 2
        dist = abs(mid - price)
        if dist < best_dist:
            best_dist = dist
            best = zone
    return best
