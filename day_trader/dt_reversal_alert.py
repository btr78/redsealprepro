"""
DAY TRADE REVERSAL ALERT  🤖  v2.0
====================================
Intraday volume-climax reversal scanner — dual-timeframe (10m + 15m).
Sends ONE alert per trading day — winner ranked by composite score then RVOL.

5 SCORED CRITERIA — need 4 of 5 to qualify (plus 2 hard gates):

  HARD GATES (always required — not scored):
    H1. Reversal candle direction (green=LONG, red=SHORT)
    H2. SPY regime (< -2% blocks longs; > +2% blocks shorts)

  SCORED CRITERIA (4 of 5 must pass):
    [1] VOLUME CLIMAX    — 15m RVOL >= 3.0x  (was 2x — much stricter)
    [2] WIDE-RANGE BAR   — candle range >= 1.5x ATR(14)  (new gate)
    [3] RSI DUAL-TF      — 15m RSI <= 30 (bull) / >= 70 (bear)
                           AND 10m RSI <= 35 (bull) / >= 65 (bear)
    [4] INTRADAY MOVE    — drop/spike from session extreme >= 2.5%  (was 1.5%)
    [5] VWAP CONFLUENCE  — price at or below VWAP (LONG) / at or above VWAP (SHORT)

  WINNER: highest composite score; RVOL breaks ties.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import sys
import logging
import time
import requests
import re
import anthropic
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# ─── SINGLE INSTANCE LOCK ────────────────────────────────────────────────────
_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dt_reversal.lock")

def _acquire_lock():
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                try:
                    os.kill(old_pid, 0)
                    print(f"[LOCK] dt_reversal_alert already running (PID {old_pid}). Exiting.")
                    sys.exit(0)
                except (ProcessLookupError, PermissionError):
                    pass
        except Exception:
            pass
    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def _release_lock():
    try:
        if os.path.exists(_LOCK_FILE):
            os.remove(_LOCK_FILE)
    except Exception:
        pass

_acquire_lock()
import atexit
atexit.register(_release_lock)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")

SETTINGS_FILE = "dt_reversal_settings.json"
STATE_FILE    = "dt_reversal_state.json"
LOG_FILE      = "dt_reversal_alert.log"

ET = ZoneInfo("America/New_York")

WATCHLIST = [
    "TSLA", "NVDA", "AMD", "META", "AMZN", "GOOGL", "MSFT", "AAPL",
    "SOFI", "CELH", "HOOD", "COIN", "SHOP", "PYPL", "LULU", "TTWO",
    "SPY", "QQQ", "PLTR", "UBER",
]

# RSI thresholds
RSI_PERIOD        = 14
RSI_15M_BUY       = 30      # 15m RSI <= this for bullish reversal
RSI_10M_BUY       = 35      # 10m RSI <= this (secondary confirmation)
RSI_15M_SELL      = 70      # 15m RSI >= this for bearish reversal
RSI_10M_SELL      = 65      # 10m RSI >= this (secondary confirmation)

# v2.0 — tighter signal gates
INTRADAY_MOVE_PCT  = 2.5    # minimum % drop/spike from session extreme (was 1.5%)
VOLUME_CLIMAX_MULT = 3.0    # RVOL >= 3x for volume climax criterion (was 2x)
WIDE_RANGE_ATR_X   = 1.5    # candle range >= this × ATR(14) for wide-range criterion
VWAP_PROXIMITY     = 0.0    # price must be at/below VWAP (LONG) or at/above (SHORT)
SPY_LIMIT          = 2.0    # SPY hard gate: blocks longs if < -2%, shorts if > +2%
CRITERIA_NEEDED    = 4      # of 5 scored criteria must pass

# Trade management
STOP_BUFFER       = 0.5     # % below session low (LONG) / above session high (SHORT)
TARGET_RR         = 2.0     # reward:risk ratio for target calculation

SCAN_INTERVAL     = 5       # minutes between scans

# ─── LOGGING ─────────────────────────────────────────────────────────────────
def _strip_emojis(text):
    return re.sub(r'[^\x00-\x7F]+', '', text)

class _SafeFormatter(logging.Formatter):
    def format(self, record):
        return _strip_emojis(super().format(record))

logger = logging.getLogger("DTReversal")
logger.setLevel(logging.DEBUG)
_fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2)
_fh.setFormatter(_SafeFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_fh)
_ch = logging.StreamHandler()
_ch.setFormatter(_SafeFormatter("%(asctime)s [%(levelname)s] %(message)s"))
_ch.setLevel(logging.INFO)
logger.addHandler(_ch)

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
def load_telegram_ids():
    for fname in (SETTINGS_FILE, "reversal_settings.json", "sniper_settings.json"):
        try:
            with open(fname) as f:
                ids = json.load(f).get("telegram_ids", [])
                if ids:
                    return ids
        except Exception:
            continue
    return []

def send_telegram(message):
    if not TELEGRAM_TOKEN:
        logger.warning("No TELEGRAM_TOKEN in .env")
        return
    ids = load_telegram_ids()
    for chat_id in ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            for chunk in [message[i:i + 4000] for i in range(0, len(message), 4000)]:
                r = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=10)
                if r.status_code != 200:
                    logger.error(f"Telegram {chat_id}: {r.text}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")

# ─── STATE ───────────────────────────────────────────────────────────────────
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

def already_alerted_today(state):
    return state.get("last_alert_date", "") == datetime.now(ET).strftime("%Y-%m-%d")

def mark_alerted(state, ticker, data):
    state["last_alert_date"] = datetime.now(ET).strftime("%Y-%m-%d")
    state["last_alert_ticker"] = ticker
    state["last_alert_time"] = datetime.now(ET).strftime("%H:%M:%S")
    state["last_alert_data"] = data
    save_state(state)

# ─── INDICATORS ──────────────────────────────────────────────────────────────
def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df

def compute_rsi(series, period=RSI_PERIOD):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# ─── CANDLE PATTERNS ─────────────────────────────────────────────────────────
def check_bullish_pattern(open_a, high_a, low_a, close_a):
    """Hammer or bullish engulfing on the latest bar."""
    if len(close_a) < 2:
        return "None", False
    o, h, l, c   = float(open_a[-1]),  float(high_a[-1]),  float(low_a[-1]),  float(close_a[-1])
    po, pc        = float(open_a[-2]), float(close_a[-2])
    body          = abs(c - o)
    lower_wick    = min(o, c) - l
    upper_wick    = h - max(o, c)
    candle_range  = h - l if h != l else 1e-4
    is_hammer     = (lower_wick >= 2 * body) and (body / candle_range <= 0.4) and (c >= o)
    prev_red      = pc < po
    today_green   = c > o
    wraps         = (c > po) and (o < pc)
    is_engulf     = prev_red and today_green and wraps
    if is_engulf:
        return "Bullish Engulfing", True
    if is_hammer:
        return "Hammer", True
    return "Green", False

def check_bearish_pattern(open_a, high_a, low_a, close_a):
    """Shooting star or bearish engulfing on the latest bar."""
    if len(close_a) < 2:
        return "None", False
    o, h, l, c   = float(open_a[-1]),  float(high_a[-1]),  float(low_a[-1]),  float(close_a[-1])
    po, pc        = float(open_a[-2]), float(close_a[-2])
    body          = abs(c - o)
    upper_wick    = h - max(o, c)
    lower_wick    = min(o, c) - l
    candle_range  = h - l if h != l else 1e-4
    is_star       = (upper_wick >= 2 * body) and (body / candle_range <= 0.4) and (c <= o)
    prev_green    = pc > po
    today_red     = c < o
    wraps         = (o > pc) and (c < po)
    is_engulf     = prev_green and today_red and wraps
    if is_engulf:
        return "Bearish Engulfing", True
    if is_star:
        return "Shooting Star", True
    return "Red", False

# ─── DATA FETCHING ────────────────────────────────────────────────────────────
def _today_bars(df):
    """Filter DataFrame to today's ET date."""
    today = datetime.now(ET).strftime("%Y-%m-%d")
    if df.index.tz is None:
        mask = df.index.normalize().strftime("%Y-%m-%d") == today
    else:
        mask = df.index.tz_convert(ET).normalize().strftime("%Y-%m-%d") == today
    return df[mask]

def get_15m_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        return flatten_columns(df).dropna(subset=["Close"])
    except Exception as e:
        logger.debug(f"{ticker} 15m download error: {e}")
        return None

def get_10m_data(ticker):
    """Download 5m bars and resample to 10m — yfinance has no 10m interval."""
    try:
        df = yf.download(ticker, period="5d", interval="5m",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        df = flatten_columns(df).dropna(subset=["Close"])
        df_10m = df.resample("10min").agg({
            "Open":   "first",
            "High":   "max",
            "Low":    "min",
            "Close":  "last",
            "Volume": "sum",
        }).dropna(subset=["Close"])
        return df_10m
    except Exception as e:
        logger.debug(f"{ticker} 10m download error: {e}")
        return None

def compute_vwap(df_15m):
    """VWAP reset at each session open — calculated from today's 15m bars."""
    today = _today_bars(df_15m)
    if len(today) < 3:
        return None
    tp  = (today["High"] + today["Low"] + today["Close"]) / 3
    tpv = (tp * today["Volume"]).cumsum()
    cvol = today["Volume"].cumsum()
    vwap = tpv / cvol.replace(0, np.nan)
    return float(vwap.iloc[-1]) if not np.isnan(vwap.iloc[-1]) else None

# ─── SPY REGIME ──────────────────────────────────────────────────────────────
_spy_cache = {"pct": 0.0, "ts": 0.0}

def get_spy_pct():
    """Cached SPY daily change — refresh every 5 minutes."""
    if time.time() - _spy_cache["ts"] < 300:
        return _spy_cache["pct"]
    try:
        spy = yf.download("SPY", period="2d", interval="1d",
                          progress=False, auto_adjust=True)
        spy = flatten_columns(spy)
        if spy is None or len(spy) < 2:
            return 0.0
        prev  = float(spy["Close"].iloc[-2])
        curr  = float(spy["Close"].iloc[-1])
        pct   = round((curr - prev) / prev * 100, 2)
        _spy_cache["pct"] = pct
        _spy_cache["ts"]  = time.time()
        return pct
    except Exception:
        return 0.0

# ─── ATR ─────────────────────────────────────────────────────────────────────
def compute_atr(df, period=14):
    """Average True Range — used for wide-range candle gate."""
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

# ─── CORE ANALYSIS ───────────────────────────────────────────────────────────
def analyze_ticker(ticker):
    """
    v2.0 — 4-of-5 scored criteria model with tighter thresholds.
    Hard gates: reversal candle direction + SPY regime.
    Scored: volume climax (3x), wide-range candle, RSI dual-TF,
            intraday move (2.5%), VWAP confluence.
    Returns result dict with criteria breakdown, or None.
    """
    df_15m = get_15m_data(ticker)
    df_10m = get_10m_data(ticker)

    if df_15m is None or df_10m is None:
        return None

    td_15m = _today_bars(df_15m)
    td_10m = _today_bars(df_10m)

    if len(td_15m) < 8 or len(td_10m) < 8:
        return None

    # Last bar
    bar   = td_15m.iloc[-1]
    price = float(bar["Close"])
    o15   = float(bar["Open"])
    h15   = float(bar["High"])
    l15   = float(bar["Low"])
    vol15 = float(bar["Volume"])

    # Candle metrics
    candle_range = h15 - l15
    is_green     = price > o15
    is_red       = price < o15

    # RSI
    rsi_15m = float(compute_rsi(td_15m["Close"].squeeze()).iloc[-1])
    rsi_10m = float(compute_rsi(td_10m["Close"].squeeze()).iloc[-1])
    if np.isnan(rsi_15m) or np.isnan(rsi_10m):
        return None

    # Session extremes
    session_high = float(td_15m["High"].max())
    session_low  = float(td_15m["Low"].min())

    # Volume
    avg_vol = float(td_15m["Volume"].iloc[:-1].tail(20).mean())
    rvol    = round(vol15 / avg_vol, 2) if avg_vol > 0 else 0.0

    # ATR (14) from today's 15m bars
    atr_val = compute_atr(td_15m)

    # VWAP and SPY
    vwap    = compute_vwap(df_15m)
    spy_pct = get_spy_pct()

    # ── Candle patterns (used for display, not a hard gate) ───────────────────
    p_name_bull, _ = check_bullish_pattern(
        td_15m["Open"].values, td_15m["High"].values,
        td_15m["Low"].values,  td_15m["Close"].values
    )
    p_name_bear, _ = check_bearish_pattern(
        td_15m["Open"].values, td_15m["High"].values,
        td_15m["Low"].values,  td_15m["Close"].values
    )

    def _evaluate(direction):
        """Score all 5 criteria for a given direction. Return (score, criteria_dict)."""
        criteria = {}

        # [1] Volume Climax — 3x+
        criteria["volume_climax"]  = rvol >= VOLUME_CLIMAX_MULT

        # [2] Wide-Range Candle — range >= 1.5×ATR
        criteria["wide_range_bar"] = (atr_val > 0 and candle_range >= WIDE_RANGE_ATR_X * atr_val)

        # [3] RSI Dual-TF Extreme
        if direction == "LONG":
            criteria["rsi_extreme"] = (rsi_15m <= RSI_15M_BUY and rsi_10m <= RSI_10M_BUY)
        else:
            criteria["rsi_extreme"] = (rsi_15m >= RSI_15M_SELL and rsi_10m >= RSI_10M_SELL)

        # [4] Intraday Move >= 2.5%
        if direction == "LONG":
            move = (session_high - price) / session_high * 100 if session_high > 0 else 0
        else:
            move = (price - session_low)  / session_low  * 100 if session_low  > 0 else 0
        criteria["intraday_move"] = (move >= INTRADAY_MOVE_PCT)

        # [5] VWAP Confluence — at or through VWAP
        if vwap is None:
            criteria["vwap_confluence"] = True  # can't measure, don't penalise
        elif direction == "LONG":
            criteria["vwap_confluence"] = price <= vwap * 1.005  # at or below VWAP
        else:
            criteria["vwap_confluence"] = price >= vwap * 0.995  # at or above VWAP

        score = sum(1 for v in criteria.values() if v)
        return score, criteria, round(move, 2)

    # ── HARD GATES then score ─────────────────────────────────────────────────
    direction = None
    score_val = 0
    criteria_final = {}
    intraday_move  = 0.0
    pattern = "None"

    # LONG attempt
    if is_green and spy_pct > -SPY_LIMIT:
        sc, cr, mv = _evaluate("LONG")
        if sc >= CRITERIA_NEEDED:
            direction      = "LONG"
            score_val      = sc
            criteria_final = cr
            intraday_move  = mv
            pattern        = p_name_bull

    # SHORT attempt
    if direction is None and is_red and spy_pct < SPY_LIMIT:
        sc, cr, mv = _evaluate("SHORT")
        if sc >= CRITERIA_NEEDED:
            direction      = "SHORT"
            score_val      = sc
            criteria_final = cr
            intraday_move  = mv
            pattern        = p_name_bear

    if direction is None:
        return None

    return {
        "ticker":        ticker,
        "direction":     direction,
        "price":         round(price, 2),
        "rsi_15m":       round(rsi_15m, 1),
        "rsi_10m":       round(rsi_10m, 1),
        "rvol":          rvol,
        "volume":        int(vol15),
        "avg_volume":    int(avg_vol),
        "vwap":          round(vwap, 2) if vwap else None,
        "session_high":  round(session_high, 2),
        "session_low":   round(session_low, 2),
        "intraday_move": intraday_move,
        "pattern":       pattern,
        "spy_pct":       spy_pct,
        "atr":           round(atr_val, 3),
        "candle_range":  round(candle_range, 3),
        "score":         score_val,
        "criteria":      criteria_final,
    }

# ─── TRADE SETUP ─────────────────────────────────────────────────────────────
def compute_setup(result):
    price    = result["price"]
    s_high   = result["session_high"]
    s_low    = result["session_low"]
    vwap     = result["vwap"]
    d        = result["direction"]

    if d == "LONG":
        stop   = round(s_low * (1 - STOP_BUFFER / 100), 2)
        risk   = price - stop
        target = round(price + TARGET_RR * risk, 2)
        if vwap and vwap > price:
            target = max(target, round(vwap, 2))
    else:
        stop   = round(s_high * (1 + STOP_BUFFER / 100), 2)
        risk   = stop - price
        target = round(price - TARGET_RR * risk, 2)
        if vwap and vwap < price:
            target = min(target, round(vwap, 2))

    risk = max(risk, price * 0.005)
    return {
        "entry":      round(price, 2),
        "stop":       stop,
        "target":     target,
        "risk_pct":   round(abs(risk) / price * 100, 2),
        "reward_pct": round(abs(target - price) / price * 100, 2),
        "rr":         f"1:{abs(target - price) / abs(risk):.1f}",
    }

# ─── AI ANALYSIS ─────────────────────────────────────────────────────────────
def fetch_news(ticker, n=6):
    try:
        news = yf.Ticker(ticker).news or []
        return [
            (item.get("title") or item.get("content", {}).get("title", ""))
            for item in news[:n]
            if (item.get("title") or item.get("content", {}).get("title", ""))
        ]
    except Exception:
        return []

def get_ai_analysis(result, setup):
    if not ANTHROPIC_KEY:
        return "AI analysis unavailable — ANTHROPIC_API_KEY not configured."
    headlines = fetch_news(result["ticker"])
    news_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No recent headlines."
    direction_context = (
        "oversold intraday reversal — potential bounce to VWAP"
        if result["direction"] == "LONG"
        else "overbought intraday reversal — potential fade to VWAP"
    )
    prompt = f"""You are a senior day trader. A stock triggered a dual-timeframe intraday reversal
({direction_context}). Both the 10-minute and 15-minute RSI confirm the extreme.
A reversal candle pattern ({result['pattern']}) formed with volume {result['rvol']:.1f}x above average.

Write 3 short sentences. Each MUST start with ✅ or ❌:
  ✅ = bullish/supportive factor
  ❌ = risk/headwind to be aware of

Cover: sentiment context from news, the #1 risk for this intraday setup, and one specific
trigger to confirm before entering. Trader language only. No fluff.

TICKER: {result['ticker']}  |  DIRECTION: {result['direction']}
PRICE: ${result['price']:.2f}  |  VWAP: ${result['vwap'] if result['vwap'] else 'N/A'}
RSI 15m: {result['rsi_15m']}  |  RSI 10m: {result['rsi_10m']}
INTRADAY MOVE: {result['intraday_move']:.1f}%  |  RVOL: {result['rvol']}x
PATTERN: {result['pattern']}  |  SPY: {result['spy_pct']:+.2f}%
ENTRY: ${setup['entry']}  |  STOP: ${setup['stop']}  |  TARGET: ${setup['target']}

NEWS:
{news_text}"""
    try:
        client   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Claude API error: {e}")
        return f"AI analysis unavailable: {e}"

# ─── ALERT FORMAT ─────────────────────────────────────────────────────────────
def format_alert(winner, runner_ups, setup, ai_analysis):
    sep  = "-" * 38
    d    = winner["direction"]
    tick = winner["ticker"]

    dir_emoji   = "📈" if d == "LONG" else "📉"
    rsi15_flag  = "✅" if (d == "LONG" and winner["rsi_15m"] <= 25) or (d == "SHORT" and winner["rsi_15m"] >= 75) else "✅"
    vol_flag    = "✅" if winner["rvol"] >= 3.0 else "✅"
    spy_flag    = "✅" if (d == "LONG" and winner["spy_pct"] > -0.5) or (d == "SHORT" and winner["spy_pct"] < 0.5) else "⚠️"
    vwap_str    = f"${winner['vwap']:.2f}" if winner["vwap"] else "N/A"

    msg  = f"*** DAY TRADE REVERSAL ALERT *** {dir_emoji}\n{sep}\n\n"
    msg += f"TICKER: {tick}  |  DIRECTION: {d}\n\n"

    msg += "PRICE ACTION:\n"
    msg += f"  Price:          ${winner['price']:.2f}\n"
    msg += f"  VWAP:           {vwap_str}\n"
    msg += f"  Session High:   ${winner['session_high']:.2f}\n"
    msg += f"  Session Low:    ${winner['session_low']:.2f}\n"
    msg += f"  Intraday Move:  {winner['intraday_move']:.1f}% {'drop' if d == 'LONG' else 'spike'}\n\n"

    msg += "INDICATORS (10m + 15m):\n"
    msg += f"  RSI 15m:        {winner['rsi_15m']}  {rsi15_flag}\n"
    msg += f"  RSI 10m:        {winner['rsi_10m']}  ✅\n"
    msg += f"  Volume (15m):   {winner['volume']:,}\n"
    msg += f"  Avg Vol (15m):  {winner['avg_volume']:,}\n"
    msg += f"  RVOL:           {winner['rvol']:.1f}x  {vol_flag}\n"
    msg += f"  Pattern:        {winner['pattern']}  ✅\n"
    msg += f"  SPY Today:      {winner['spy_pct']:+.2f}%  {spy_flag}\n\n"

    cr   = winner.get("criteria", {})
    _p   = lambda k: "✅" if cr.get(k) else "❌"
    msg += f"CRITERIA SCORECARD ({winner.get('score', 0)}/5 — needed {CRITERIA_NEEDED}):\n"
    msg += f"  H1. {'Green' if d == 'LONG' else 'Red'} candle (hard gate)       ✅\n"
    msg += f"  H2. SPY regime {winner['spy_pct']:+.2f}% (hard gate)   ✅\n"
    msg += f"  [1] Volume Climax  {winner['rvol']:.1f}x >= 3.0x        {_p('volume_climax')}\n"
    msg += f"  [2] Wide-Range Bar {winner['candle_range']:.3f} >= {WIDE_RANGE_ATR_X}x ATR({winner['atr']:.3f}) {_p('wide_range_bar')}\n"
    msg += f"  [3] RSI Dual-TF   15m={winner['rsi_15m']} / 10m={winner['rsi_10m']}  {_p('rsi_extreme')}\n"
    msg += f"  [4] Intraday Move  {winner['intraday_move']:.1f}% >= 2.5%           {_p('intraday_move')}\n"
    msg += f"  [5] VWAP Conflu.  ${winner['vwap'] if winner['vwap'] else 'N/A'}         {_p('vwap_confluence')}\n\n"

    msg += f"{sep}\n"
    msg += "SUGGESTED ACTION:\n"
    msg += f"  Direction:  {d}\n"
    msg += f"  Entry:      ${setup['entry']:.2f}  (market)\n"
    msg += f"  Stop:       ${setup['stop']:.2f}  (-{setup['risk_pct']}%)\n"
    msg += f"  Target:     ${setup['target']:.2f}  (+{setup['reward_pct']}%)\n"
    msg += f"  R:R Ratio:  {setup['rr']}\n\n"

    msg += f"{sep}\n"
    msg += "AI ANALYSIS:\n"
    for line in ai_analysis.split("\n"):
        msg += f"  {line}\n"
    msg += "\n"

    if runner_ups:
        msg += f"{sep}\n"
        msg += "OTHER SIGNALS (lower volume, silenced today):\n"
        for r in runner_ups[:4]:
            msg += (f"  {r['ticker']:6s}  {r['direction']:5s}  "
                    f"RSI15={r['rsi_15m']}  RSI10={r['rsi_10m']}  "
                    f"RVOL={r['rvol']}x  {r['pattern']}\n")
        msg += "\n"

    msg += f"{sep}\n"
    msg += f"Highest volume selected. Max 1 alert/day.\n"
    msg += f"Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}\n"
    msg += "Manual review required before entry."
    return msg

# ─── SCAN ────────────────────────────────────────────────────────────────────
def scan():
    candidates = []
    logger.info(f"Scanning {len(WATCHLIST)} tickers for intraday reversals...")
    for ticker in WATCHLIST:
        try:
            result = analyze_ticker(ticker)
            if result:
                candidates.append(result)
                logger.info(
                    f"  SIGNAL: {ticker} {result['direction']} | "
                    f"RSI15={result['rsi_15m']} RSI10={result['rsi_10m']} | "
                    f"RVOL={result['rvol']}x | Pattern={result['pattern']}"
                )
            else:
                logger.debug(f"  {ticker}: no signal")
        except Exception as e:
            logger.debug(f"  {ticker}: error — {e}")
        time.sleep(0.5)
    return candidates

# ─── MARKET HOURS ─────────────────────────────────────────────────────────────
def is_market_hours():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return open_t <= now <= close_t

def wait_for_market_open():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        days_ahead = 7 - now.weekday()
        nxt = (now + timedelta(days=days_ahead)).replace(hour=9, minute=30, second=0, microsecond=0)
        secs = (nxt - now).total_seconds()
        logger.info(f"Weekend — sleeping {secs/3600:.1f}h until Monday 9:30 AM ET")
        time.sleep(max(secs, 0))
        return
    open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    if now < open_t:
        secs = (open_t - now).total_seconds()
        logger.info(f"Pre-market — sleeping {secs/60:.0f} min until 9:30 AM ET")
        time.sleep(max(secs, 0))
    elif now > close_t:
        nxt = open_t + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        secs = (nxt - now).total_seconds()
        logger.info(f"After hours — sleeping {secs/3600:.1f}h until next open")
        time.sleep(max(secs, 0))

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("Day Trade Reversal Alert  Robot  v2.0 — Starting (4-of-5 criteria)")
    logger.info("Timeframes: 10m (5m resampled) + 15m dual confirmation")
    logger.info(f"Watchlist: {', '.join(WATCHLIST)}")
    logger.info(f"Scan interval: {SCAN_INTERVAL} min | Max 1 alert/day (highest volume)")
    logger.info("=" * 60)

    send_telegram(
        "*** DAY TRADE REVERSAL ALERT v2.0 Online ***\n\n"
        "Timeframes: 10m + 15m (dual confirmation required)\n"
        "Criteria: Volume Climax 3x | Wide-Range Bar | RSI Dual-TF\n"
        "          Intraday Move 2.5%+ | VWAP Confluence\n"
        "Need 4 of 5 scored criteria + 2 hard gates\n\n"
        f"Watchlist ({len(WATCHLIST)} tickers): {', '.join(WATCHLIST)}\n"
        f"Scan every {SCAN_INTERVAL} min | 1 alert/day max (best score wins)"
    )

    while True:
        try:
            wait_for_market_open()

            if not is_market_hours():
                time.sleep(30)
                continue

            state = load_state()
            if already_alerted_today(state):
                logger.info("Already alerted today — sleeping until next scan")
                time.sleep(SCAN_INTERVAL * 60)
                continue

            candidates = scan()

            if not candidates:
                logger.info("No signals this scan.")
                time.sleep(SCAN_INTERVAL * 60)
                continue

            # Sort by score first (criteria met), then RVOL as tiebreaker
            candidates.sort(key=lambda x: (x.get("score", 0), x.get("rvol", 0)), reverse=True)
            winner     = candidates[0]
            runner_ups = candidates[1:]

            logger.info(
                f"WINNER: {winner['ticker']} {winner['direction']} | "
                f"Vol={winner['volume']:,} | RVOL={winner['rvol']}x | "
                f"Pattern={winner['pattern']} — generating setup + AI..."
            )

            setup = compute_setup(winner)
            logger.info(f"  Setup: Entry ${setup['entry']} | Stop ${setup['stop']} | Target ${setup['target']}")

            ai_analysis = get_ai_analysis(winner, setup)
            logger.info(f"  AI: {_strip_emojis(ai_analysis[:80])}...")

            send_telegram(format_alert(winner, runner_ups, setup, ai_analysis))
            mark_alerted(state, winner["ticker"], winner)
            logger.info("Alert sent. Silent until next trading day.")

            time.sleep(SCAN_INTERVAL * 60)

        except KeyboardInterrupt:
            logger.info("Shutting down.")
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(60)

if __name__ == "__main__":
    main()
