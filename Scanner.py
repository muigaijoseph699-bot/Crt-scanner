import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime

# ===== EDIT THIS LINE — your own unique ntfy topic =====
TOPIC = "josephcrt-alerts-1630"
# ======================================================

PAIRS = [
    # --- Majors ---
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X",
    "AUDUSD=X", "NZDUSD=X",
    # --- EUR crosses ---
    "EURGBP=X", "EURJPY=X", "EURCHF=X", "EURAUD=X", "EURCAD=X", "EURNZD=X",
    # --- GBP crosses ---
    "GBPJPY=X", "GBPCHF=X", "GBPAUD=X", "GBPCAD=X", "GBPNZD=X",
    # --- AUD crosses ---
    "AUDJPY=X", "AUDCHF=X", "AUDCAD=X", "AUDNZD=X",
    # --- NZD crosses ---
    "NZDJPY=X", "NZDCHF=X", "NZDCAD=X",
    # --- CAD / CHF crosses ---
    "CADJPY=X", "CADCHF=X", "CHFJPY=X",
    # --- Metals ---
    "XAUUSD=X", "XAGUSD=X",
    # --- Crypto ---
    "BTC-USD",
]

SLEEP_SECONDS = 300
NTFY_URL = f"https://ntfy.sh/{TOPIC}"

alerted = set()


def notify(title, message):
    try:
        requests.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high"},
        )
    except Exception as e:
        print("ntfy error:", e)


def clean_df(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def resample_ohlc(df, rule):
    out = df.resample(rule, label="right", closed="right").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()
    return out


def check_crt(df):
    if df is None or len(df) < 3:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    c1h, c1l = float(c1["High"]), float(c1["Low"])
    c2h, c2l, c2c = float(c2["High"]), float(c2["Low"]), float(c2["Close"])
    c3h, c3l = float(c3["High"]), float(c3["Low"])

    bullish = (c2l < c1l) and (c1l < c2c < c1h) and (c3h > c2h)
    bearish = (c2h > c1h) and (c1l < c2c < c1h) and (c3l < c2l)

    if bullish:
        return ("Bullish", c2h, c2l, c1h)
    if bearish:
        return ("Bearish", c2l, c2h, c1l)
    return None


def build_timeframes(symbol):
    tfs = {}

    try:
        raw_1h = clean_df(yf.download(
            symbol, period="60d", interval="1h",
            progress=False, auto_adjust=False
        ))
    except Exception:
        raw_1h = None

    if raw_1h is not None and not raw_1h.empty:
        tfs["1H"] = raw_1h
        tfs["4H"] = resample_ohlc(raw_1h, "4h")

    try:
        raw_1d = clean_df(yf.download(
            symbol, period="5y", interval="1d",
            progress=False, auto_adjust=False
        ))
    except Exception:
        raw_1d = None

    if raw_1d is not None and not raw_1d.empty:
        tfs["1D"] = raw_1d
        tfs["1W"] = resample_ohlc(raw_1d, "1W")
        tfs["1M"] = resample_ohlc(raw_1d, "1M")

    return tfs


print("CRT scanner started — 33 pairs × 5 timeframes")

while True:
    print(f"\n===== Scan {datetime.now()} =====")

    for symbol in PAIRS:
        try:
            tfs = build_timeframes(symbol)
            if not tfs:
                print(f"{symbol} -> no data")
                continue

            for tf_name, df in tfs.items():
                sig = check_crt(df)
                if not sig:
                    continue

                c3_time = str(df.index[-1])
                key = f"{symbol}|{tf_name}|{c3_time}"

                if key in alerted:
                    continue
                alerted.add(key)

                side, entry, sl, tp = sig
                emoji = "🟢" if side == "Bullish" else "🔴"
                title = f"{side} CRT — {symbol} {tf_name}"
                msg = (
                    f"{emoji} {side} CRT\n"
                    f"Pair: {symbol}\n"
                    f"Timeframe: {tf_name}\n"
                    f"Entry: {entry:.5f}\n"
                    f"SL: {sl:.5f}\n"
                    f"TP: {tp:.5f}"
                )
                print(msg)
                notify(title, msg)

        except Exception as e:
            print(f"{symbol} -> ERROR: {e}")

    print(f"Sleeping {SLEEP_SECONDS}s...")
    time.sleep(SLEEP_SECONDS)
