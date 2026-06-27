import pandas as pd
import numpy as np


def _find_swing_highs(highs: pd.Series, pivot_len: int) -> list:
    swings = []
    for i in range(pivot_len, len(highs) - pivot_len):
        if highs.iloc[i] == max(highs.iloc[i - pivot_len:i + pivot_len + 1]):
            swings.append((i, highs.iloc[i]))
    return swings


def _find_swing_lows(lows: pd.Series, pivot_len: int) -> list:
    swings = []
    for i in range(pivot_len, len(lows) - pivot_len):
        if lows.iloc[i] == min(lows.iloc[i - pivot_len:i + pivot_len + 1]):
            swings.append((i, lows.iloc[i]))
    return swings


def _group_levels(levels: list, tolerance: float = 0.001) -> list:
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda x: x[1])
    groups = []
    current_group = [sorted_levels[0]]

    for i in range(1, len(sorted_levels)):
        ref_price = current_group[0][1]
        if ref_price == 0:
            current_group = [sorted_levels[i]]
            continue
        if abs(sorted_levels[i][1] - ref_price) / ref_price <= tolerance:
            current_group.append(sorted_levels[i])
        else:
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [sorted_levels[i]]

    if len(current_group) >= 2:
        groups.append(current_group)

    return groups


def compute_liquidity(df: pd.DataFrame, pivot_len: int = 5) -> dict:
    result = {
        "equal_highs": [],
        "equal_lows": [],
        "buy_side_liq": None,
        "sell_side_liq": None,
        "sweep_up": False,
        "sweep_down": False,
        "sweep_signal": None,
    }

    if len(df) < pivot_len * 2 + 1:
        return result

    swing_highs = _find_swing_highs(df["high"], pivot_len)
    swing_lows = _find_swing_lows(df["low"], pivot_len)

    high_groups = _group_levels(swing_highs)
    low_groups = _group_levels(swing_lows)

    equal_highs = [np.mean([p for _, p in g]) for g in high_groups]
    equal_lows = [np.mean([p for _, p in g]) for g in low_groups]

    result["equal_highs"] = sorted(equal_highs)
    result["equal_lows"] = sorted(equal_lows)

    if not equal_highs and not equal_lows:
        return result

    if equal_highs:
        result["buy_side_liq"] = max(equal_highs)

    if equal_lows:
        result["sell_side_liq"] = min(equal_lows)

    last_high = df["high"].iloc[-1]
    last_close = df["close"].iloc[-1]
    last_low = df["low"].iloc[-1]

    if result["buy_side_liq"] is not None:
        bsl = result["buy_side_liq"]
        if last_high > bsl and last_close < bsl:
            result["sweep_up"] = True

    if result["sell_side_liq"] is not None:
        ssl = result["sell_side_liq"]
        if last_low < ssl and last_close > ssl:
            result["sweep_down"] = True

    if result["sweep_down"] and not result["sweep_up"]:
        result["sweep_signal"] = "bullish_sweep"
    elif result["sweep_up"] and not result["sweep_down"]:
        result["sweep_signal"] = "bearish_sweep"

    return result
