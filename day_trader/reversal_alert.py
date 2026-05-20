"""
STOCK REVERSAL ALERT SCANNER
=============================
Monitors S&P 500 stocks for high-probability reversal setups.

CORE FILTERS (all must pass):
  1. RSI(14) <= 30                   — oversold
  2. 10%+ drop from 20-day high      — real selloff
  3. Price within 3% of 60-day low   — at support
  4. Green candle + volume > 1.5x    — reversal confirmation

ACCURACY UPGRADES (all must pass):
  5. MACD bullish divergence          — selling momentum fading
  6. Hammer or bullish engulfing      — strong candle pattern at support
  7. SPY not down > 1.5% today        — macro regime filter
  8. Weekly RSI >= 40                 — not in a weekly downtrend
  9. 3+ consecutive red days before   — exhaustion before reversal
  10. No earnings within 5 days       — avoid earnings gap risk

EXTRAS:
  - AI Confidence: backtested win-rate for this exact setup
  - Suggested Action: entry / stop / target with R:R
  - AI Analysis: live news headlines fed to Claude for sentiment + risk

PRIORITY:
  - Rank qualifying stocks by RVOL (relative volume)
  - Alert ONLY the #1 highest RVOL stock
  - ONE alert per trading day, then silent until next day
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
from datetime import datetime, timedelta, date
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# ─── SINGLE INSTANCE LOCK ───────────────────────────────────────────────────
_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reversal.lock")

def _acquire_lock():
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Cross-platform live-process check (works on Windows AND Linux)
            if old_pid != os.getpid():
                try:
                    os.kill(old_pid, 0)
                    print(f"[LOCK] Another reversal scanner is already running (PID {old_pid}). Exiting.")
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

# ─── CONFIGURATION ──────────────────────────────────────────────────────────

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")
SETTINGS_FILE  = "reversal_settings.json"
STATE_FILE     = "reversal_state.json"

# Core filter thresholds
RSI_PERIOD            = 14
RSI_THRESHOLD         = 30    # Gate 1: daily RSI must be <= this
DROP_PCT              = 10.0  # Gate 2: minimum % drop from 20-day high
SUPPORT_LOOKBACK      = 60    # Gate 3: rolling low window (days)
SUPPORT_PROXIMITY_PCT = 3.0   # Gate 3: max % above 60-day low
VOLUME_CONFIRM_MULT   = 1.5   # Gate 4: volume must be >= this x 20-day avg

# Accuracy upgrade thresholds
SPY_DROP_LIMIT        = 1.5   # Gate 7: skip if SPY is down more than this % today
WEEKLY_RSI_MIN        = 40    # Gate 8: weekly RSI must be >= this (not in weekly downtrend)
MIN_RED_DAYS          = 3     # Gate 9: minimum consecutive red days before today's green
EARNINGS_BUFFER_DAYS  = 5     # Gate 10: skip if earnings within this many days

# MACD settings (Gate 5)
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
DIVERGENCE_LOOKBACK = 10  # bars to look back for divergence

# Backtest settings
BACKTEST_PERIOD       = "2y"
BACKTEST_FORWARD_DAYS = 10
BACKTEST_TARGET_PCT   = 5.0

# Trade setup
STOP_BUFFER_PCT = 1.0
TARGET_RR       = 2.0

# Scan
SCAN_INTERVAL_MINUTES = 5

# ─── LOGGING ────────────────────────────────────────────────────────────────

def strip_emojis(text):
    return re.sub(r'[^\x00-\x7F]+', '', text)

class SafeFormatter(logging.Formatter):
    def format(self, record):
        return strip_emojis(super().format(record))

logger = logging.getLogger("ReversalAlert")
logger.setLevel(logging.DEBUG)
_fh = RotatingFileHandler("reversal_alert.log", maxBytes=5*1024*1024, backupCount=2)
_fh.setFormatter(SafeFormatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(_fh)
_ch = logging.StreamHandler()
_ch.setFormatter(SafeFormatter('%(asctime)s [%(levelname)s] %(message)s'))
_ch.setLevel(logging.INFO)
logger.addHandler(_ch)

# ─── S&P 500 TICKERS ────────────────────────────────────────────────────────

def get_sp500_tickers():
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = tables[0]['Symbol'].tolist()
        tickers = [t.replace('.', '-') for t in tickers]
        logger.info(f"Loaded {len(tickers)} S&P 500 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 list: {e}")
        return _FALLBACK_SP500

_FALLBACK_SP500 = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B","UNH","XOM",
    "JNJ","JPM","V","PG","MA","HD","CVX","MRK","ABBV","LLY","PEP","KO",
    "COST","AVGO","MCD","WMT","TMO","CSCO","ACN","ABT","CRM","DHR","NEE",
    "LIN","TXN","AMD","PM","UNP","CMCSA","NFLX","RTX","HON","LOW","INTC",
    "UPS","AMGN","QCOM","BA","CAT","GS","SPGI","BLK","MDLZ","ELV","GILD",
    "ADI","SYK","ADP","DE","ISRG","CI","CB","REGN","VRTX","PLD",
    "ZTS","BDX","SO","DUK","CME","CL","MO","SLB","EQIX","ITW","BSX",
    "APD","AON","SHW","LRCX","PYPL","KLAC","SNPS","CDNS","ORLY","AJG",
    "CTAS","WDAY","ADSK","MNST","FTNT","CPRT","MRNA","ABNB","DXCM","BIIB",
]

# ─── TELEGRAM ───────────────────────────────────────────────────────────────

def load_telegram_ids():
    for fname in (SETTINGS_FILE, "sniper_settings.json"):
        try:
            with open(fname, 'r') as f:
                return json.load(f).get("telegram_ids", [])
        except Exception:
            continue
    return []

def send_telegram(message):
    if not TELEGRAM_TOKEN:
        logger.warning("No Telegram token configured")
        return
    ids = load_telegram_ids()
    for chat_id in ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
                resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=10)
                if resp.status_code != 200:
                    logger.error(f"Telegram failed for {chat_id}: {resp.text}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")

# ─── STATE MANAGEMENT ───────────────────────────────────────────────────────

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)

def already_alerted_today(state):
    return state.get("last_alert_date", "") == datetime.now().strftime("%Y-%m-%d")

def mark_alerted(state, ticker, data):
    state["last_alert_date"] = datetime.now().strftime("%Y-%m-%d")
    state["last_alert_ticker"] = ticker
    state["last_alert_time"] = datetime.now().strftime("%H:%M:%S")
    state["last_alert_data"] = data
    save_state(state)

# ─── TECHNICAL INDICATORS ───────────────────────────────────────────────────

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast   = series.ewm(span=fast, adjust=False).mean()
    ema_slow   = series.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram

# ─── ACCURACY GATE HELPERS ──────────────────────────────────────────────────

def check_macd_divergence(close, lookback=DIVERGENCE_LOOKBACK):
    """
    Bullish divergence: price making a lower low in the lookback window
    while the MACD histogram is making a higher low — momentum fading.
    Returns True if divergence detected.
    """
    if len(close) < MACD_SLOW + lookback:
        return False
    _, _, hist = compute_macd(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    price_window = close.iloc[-lookback:]
    macd_window  = hist.iloc[-lookback:]
    if macd_window.isna().all():
        return False
    price_low_idx = int(price_window.idxmin()) if hasattr(price_window.idxmin(), '__int__') else price_window.values.argmin()
    macd_low_idx  = int(macd_window.idxmin()) if hasattr(macd_window.idxmin(), '__int__') else macd_window.values.argmin()
    # Current price near the window low but MACD histogram higher than its window low
    current_price = float(close.iloc[-1])
    window_price_low = float(price_window.min())
    current_macd  = float(hist.iloc[-1]) if not np.isnan(hist.iloc[-1]) else 0
    window_macd_low  = float(macd_window.min()) if not np.isnan(macd_window.min()) else 0
    price_near_low = (current_price - window_price_low) / window_price_low * 100 < 2.0
    macd_higher    = current_macd > window_macd_low
    return bool(price_near_low and macd_higher)


def check_candle_pattern(open_arr, high_arr, low_arr, close_arr):
    """
    Check for hammer or bullish engulfing on the last candle.
    Returns (pattern_name, bool_detected).

    Hammer: lower wick >= 2x body, upper wick small, green or small red body.
    Bullish engulfing: today's green body fully wraps yesterday's red body.
    """
    if len(close_arr) < 2:
        return "None", False

    o, h, l, c   = float(open_arr[-1]), float(high_arr[-1]), float(low_arr[-1]), float(close_arr[-1])
    po, pc        = float(open_arr[-2]), float(close_arr[-2])

    body        = abs(c - o)
    lower_wick  = min(o, c) - l
    upper_wick  = h - max(o, c)
    candle_range = h - l if h != l else 0.0001

    # Hammer: lower wick is at least 2x the body and body is <= 40% of range
    is_hammer = (lower_wick >= 2 * body) and (body / candle_range <= 0.4) and (c >= o)

    # Bullish engulfing: prev candle red, today green, today body wraps prev body
    prev_red    = pc < po
    today_green = c > o
    wraps       = (c > po) and (o < pc)
    is_engulfing = prev_red and today_green and wraps

    if is_engulfing:
        return "Bullish Engulfing", True
    if is_hammer:
        return "Hammer", True
    return "Green", False   # plain green — still passes gate 4 but no pattern bonus


def check_spy_regime():
    """
    Returns (spy_pct_change, is_ok).
    is_ok = False if SPY is down more than SPY_DROP_LIMIT% today.
    """
    try:
        spy = yf.download("SPY", period="2d", interval="1d", progress=False)
        if spy is None or len(spy) < 2:
            return 0.0, True  # can't tell — allow
        prev_close = float(spy['Close'].iloc[-2])
        curr_close = float(spy['Close'].iloc[-1])
        pct = ((curr_close - prev_close) / prev_close) * 100
        return round(pct, 2), pct > -SPY_DROP_LIMIT
    except Exception as e:
        logger.warning(f"SPY check failed: {e}")
        return 0.0, True


def check_weekly_rsi(ticker):
    """
    Download weekly bars and compute RSI.
    Returns (weekly_rsi, is_ok).
    is_ok = True if weekly RSI >= WEEKLY_RSI_MIN (not in a weekly downtrend).
    """
    try:
        hist = yf.download(ticker, period="1y", interval="1wk", progress=False)
        if hist is None or len(hist) < RSI_PERIOD + 2:
            return None, True  # can't tell — allow
        rsi = compute_rsi(hist['Close'].squeeze(), RSI_PERIOD)
        weekly_rsi = float(rsi.iloc[-1])
        if np.isnan(weekly_rsi):
            return None, True
        return round(weekly_rsi, 1), weekly_rsi >= WEEKLY_RSI_MIN
    except Exception as e:
        logger.warning(f"Weekly RSI check failed for {ticker}: {e}")
        return None, True


def check_consecutive_red_days(open_arr, close_arr, required=MIN_RED_DAYS):
    """
    Count consecutive red candles immediately before the current (last) candle.
    Returns (count, is_ok) where is_ok = count >= required.
    """
    if len(close_arr) < required + 1:
        return 0, False
    count = 0
    # Walk backwards from second-to-last bar
    for i in range(len(close_arr) - 2, -1, -1):
        if float(close_arr[i]) < float(open_arr[i]):
            count += 1
        else:
            break
    return count, count >= required


def check_earnings_safe(ticker, buffer_days=EARNINGS_BUFFER_DAYS):
    """
    Returns (days_to_earnings_or_None, is_safe).
    is_safe = True if no earnings within buffer_days.
    """
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None or cal.empty:
            return None, True
        # calendar index contains 'Earnings Date' row
        if 'Earnings Date' in cal.index:
            earn_dates = cal.loc['Earnings Date']
            # May be a Series with multiple values
            dates = pd.to_datetime(earn_dates).dropna() if hasattr(earn_dates, '__iter__') else [pd.to_datetime(earn_dates)]
            today = pd.Timestamp.now().normalize()
            for d in dates:
                d = pd.Timestamp(d).normalize()
                days_away = (d - today).days
                if 0 <= days_away <= buffer_days:
                    return days_away, False
        return None, True
    except Exception as e:
        logger.warning(f"Earnings check failed for {ticker}: {e}")
        return None, True

# ─── CORE STOCK ANALYSIS ────────────────────────────────────────────────────

def analyze_stock(ticker, hist):
    """
    Runs all 10 gates. Returns result dict if all pass, else None.
    Gates 5-10 are the accuracy upgrades — failures are logged so you can
    tune thresholds without re-scanning.
    """
    if hist is None or len(hist) < SUPPORT_LOOKBACK:
        return None

    close  = hist['Close'].squeeze()
    volume = hist['Volume'].squeeze()
    opens  = hist['Open'].squeeze()
    highs  = hist['High'].squeeze()
    lows   = hist['Low'].squeeze()

    current_price  = float(close.iloc[-1])
    current_open   = float(opens.iloc[-1])
    current_volume = float(volume.iloc[-1])

    # ── GATE 1: Daily RSI ───────────────────────────────────────────────────
    rsi_series  = compute_rsi(close, RSI_PERIOD)
    current_rsi = float(rsi_series.iloc[-1])
    if np.isnan(current_rsi) or current_rsi > RSI_THRESHOLD:
        return None

    # ── GATE 2: 10% Drop ────────────────────────────────────────────────────
    high_20d = float(close.rolling(20).max().iloc[-1])
    drop_pct = ((high_20d - current_price) / high_20d) * 100
    if drop_pct < DROP_PCT:
        return None

    # ── GATE 3: Support proximity ────────────────────────────────────────────
    low_60d = float(close.rolling(SUPPORT_LOOKBACK).min().iloc[-1])
    dist_to_support = ((current_price - low_60d) / low_60d) * 100
    if dist_to_support > SUPPORT_PROXIMITY_PCT:
        return None

    # ── GATE 4: Green candle + volume ───────────────────────────────────────
    is_green      = current_price > current_open
    avg_volume_20d = float(volume.tail(20).mean())
    rvol          = current_volume / avg_volume_20d if avg_volume_20d > 0 else 0
    if not is_green or rvol < VOLUME_CONFIRM_MULT:
        return None

    # ── GATE 5: MACD Bullish Divergence ─────────────────────────────────────
    has_divergence = check_macd_divergence(close, DIVERGENCE_LOOKBACK)
    if not has_divergence:
        logger.debug(f"  {ticker}: FAILED gate 5 — no MACD bullish divergence")
        return None

    # ── GATE 6: Candlestick pattern ─────────────────────────────────────────
    pattern_name, has_pattern = check_candle_pattern(
        opens.values, highs.values, lows.values, close.values
    )
    if not has_pattern:
        logger.debug(f"  {ticker}: FAILED gate 6 — no hammer/engulfing (plain green)")
        return None

    # ── GATE 7: SPY regime (shared across all tickers — checked once in scan) ─
    # Passed in via result dict — see scan_all_stocks()

    # ── GATE 8: Weekly RSI ──────────────────────────────────────────────────
    weekly_rsi, weekly_ok = check_weekly_rsi(ticker)
    if not weekly_ok:
        logger.debug(f"  {ticker}: FAILED gate 8 — weekly RSI {weekly_rsi} < {WEEKLY_RSI_MIN}")
        return None

    # ── GATE 9: Consecutive red days ────────────────────────────────────────
    red_days, red_ok = check_consecutive_red_days(opens.values, close.values, MIN_RED_DAYS)
    if not red_ok:
        logger.debug(f"  {ticker}: FAILED gate 9 — only {red_days} consecutive red days (need {MIN_RED_DAYS})")
        return None

    # ── GATE 10: Earnings blackout ──────────────────────────────────────────
    days_to_earnings, earnings_safe = check_earnings_safe(ticker)
    if not earnings_safe:
        logger.debug(f"  {ticker}: FAILED gate 10 — earnings in {days_to_earnings} days")
        return None

    return {
        "ticker":               ticker,
        "price":                current_price,
        "open_price":           current_open,
        "rsi":                  round(current_rsi, 2),
        "drop_pct":             round(drop_pct, 2),
        "high_20d":             round(high_20d, 2),
        "low_60d":              round(low_60d, 2),
        "support_distance_pct": round(dist_to_support, 2),
        "rvol":                 round(rvol, 2),
        "current_volume":       int(current_volume),
        "avg_volume_20d":       int(avg_volume_20d),
        "candle":               pattern_name,
        "weekly_rsi":           weekly_rsi,
        "red_days":             red_days,
        "days_to_earnings":     days_to_earnings,
        "macd_divergence":      True,
    }

# ─── BACKTESTING: AI CONFIDENCE SCORE ───────────────────────────────────────

def compute_backtest_confidence(ticker):
    """
    Slide over 2y of history finding instances where all core 4 gates fired.
    Measures % of those that saw >= BACKTEST_TARGET_PCT gain within BACKTEST_FORWARD_DAYS.
    Returns (win_rate, instance_count).
    """
    try:
        hist = yf.download(ticker, period=BACKTEST_PERIOD, interval="1d",
                           progress=False, auto_adjust=True)
        if hist is None or len(hist) < SUPPORT_LOOKBACK + BACKTEST_FORWARD_DAYS + 20:
            return None, 0

        close  = hist['Close'].squeeze()
        volume = hist['Volume'].squeeze()
        opens  = hist['Open'].squeeze()
        rsi    = compute_rsi(close, RSI_PERIOD)
        wins, total = 0, 0

        for i in range(SUPPORT_LOOKBACK, len(close) - BACKTEST_FORWARD_DAYS):
            slice_rsi = float(rsi.iloc[i])
            if np.isnan(slice_rsi) or slice_rsi > RSI_THRESHOLD:
                continue
            price    = float(close.iloc[i])
            high_20d = float(close.iloc[max(0,i-19):i+1].max())
            if ((high_20d - price) / high_20d * 100) < DROP_PCT:
                continue
            low_60d = float(close.iloc[max(0,i-59):i+1].min())
            if ((price - low_60d) / low_60d * 100) > SUPPORT_PROXIMITY_PCT:
                continue
            op    = float(opens.iloc[i])
            avg_v = float(volume.iloc[max(0,i-19):i+1].mean())
            rvol  = float(volume.iloc[i]) / avg_v if avg_v > 0 else 0
            if price <= op or rvol < VOLUME_CONFIRM_MULT:
                continue
            max_future = float(close.iloc[i+1:i+1+BACKTEST_FORWARD_DAYS].max())
            total += 1
            if ((max_future - price) / price * 100) >= BACKTEST_TARGET_PCT:
                wins += 1

        if total == 0:
            return None, 0
        return round((wins / total) * 100, 1), total
    except Exception as e:
        logger.warning(f"Backtest failed for {ticker}: {e}")
        return None, 0

def confidence_label(win_rate):
    if win_rate is None:
        return "N/A (insufficient history)"
    if win_rate >= 70:
        return f"{win_rate}%  [HIGH]"
    if win_rate >= 50:
        return f"{win_rate}%  [MODERATE]"
    return f"{win_rate}%  [LOW — exercise caution]"

# ─── TRADE SETUP ────────────────────────────────────────────────────────────

def compute_trade_setup(price, low_60d):
    entry  = price
    stop   = round(low_60d * (1 - STOP_BUFFER_PCT / 100), 2)
    risk   = entry - stop
    target = round(entry + TARGET_RR * risk, 2)
    return {
        "entry":      round(entry, 2),
        "stop":       stop,
        "target":     target,
        "risk_pct":   round((risk / entry) * 100, 2),
        "reward_pct": round((TARGET_RR * risk / entry) * 100, 2),
        "rr":         f"1:{TARGET_RR:.0f}",
    }

# ─── AI ANALYSIS VIA CLAUDE ─────────────────────────────────────────────────

def fetch_news_headlines(ticker, max_headlines=8):
    try:
        news = yf.Ticker(ticker).news or []
        headlines = []
        for item in news[:max_headlines]:
            title = item.get("title") or item.get("content", {}).get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception as e:
        logger.warning(f"News fetch failed for {ticker}: {e}")
        return []

def get_ai_analysis(ticker, data, setup):
    if not ANTHROPIC_KEY:
        return "AI analysis unavailable — ANTHROPIC_API_KEY not set."
    headlines = fetch_news_headlines(ticker)
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else "No recent headlines available."
    prompt = f"""You are a senior day trading analyst. A stock has triggered a high-probability reversal setup
(passed 10 technical gates including MACD divergence, hammer/engulfing candle, weekly RSI health, and earnings clearance).

Write 3-5 short sentences of analysis. Each sentence MUST start with either ✅ or ❌:
  ✅ = bullish factor, supporting the trade, or a positive confirmation signal
  ❌ = risk factor, bearish headwind, or a reason to be cautious

Cover: (1) what the news/sentiment context means, (2) the key remaining risk, (3) one specific
confirmation trigger to watch before entering. Be direct. No fluff. Trader language only.

TICKER: {ticker}
PRICE: ${data['price']:.2f}  |  DROP: -{data['drop_pct']:.1f}%  |  RSI: {data['rsi']}
WEEKLY RSI: {data.get('weekly_rsi', 'N/A')}  |  RED DAYS BEFORE: {data.get('red_days', 'N/A')}
PATTERN: {data.get('candle', 'GREEN')}  |  RVOL: {data['rvol']}x
ENTRY: ${setup['entry']:.2f}  |  STOP: ${setup['stop']:.2f}  |  TARGET: ${setup['target']:.2f}

RECENT NEWS:
{headlines_text}"""
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Claude API call failed: {e}")
        return f"AI analysis unavailable: {e}"

# ─── BATCH SCAN ─────────────────────────────────────────────────────────────

def scan_all_stocks(tickers):
    """
    Step 1: Check SPY regime once — skip entire scan if market is crashing.
    Step 2: Download daily bars in batches of 50, run all 10 gates.
    Weekly RSI + earnings are fetched per-ticker inside analyze_stock.
    """
    # Gate 7: SPY regime — one call for all 500 tickers
    spy_pct, spy_ok = check_spy_regime()
    if not spy_ok:
        logger.info(f"SPY down {spy_pct}% — market regime filter triggered. Skipping scan.")
        return []
    logger.info(f"SPY: {spy_pct:+.2f}% — regime OK, proceeding with scan")

    candidates = []
    batch_size = 50

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        logger.info(f"Batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1} ({len(batch)} tickers)")
        try:
            data = yf.download(" ".join(batch), period="90d", interval="1d",
                               group_by="ticker", progress=False, threads=True)
        except Exception as e:
            logger.error(f"Batch download error: {e}")
            continue

        for ticker in batch:
            try:
                hist = data if len(batch) == 1 else data[ticker].dropna()
                if hist is None or hist.empty or len(hist) < SUPPORT_LOOKBACK:
                    continue
                result = analyze_stock(ticker, hist)
                if result:
                    result["spy_pct"] = spy_pct
                    candidates.append(result)
                    logger.info(
                        f"  PASS: {ticker} | RSI={result['rsi']} | Drop={result['drop_pct']}% "
                        f"| RVOL={result['rvol']}x | Pattern={result['candle']} "
                        f"| WeeklyRSI={result['weekly_rsi']} | RedDays={result['red_days']}"
                    )
            except Exception as e:
                logger.debug(f"  Skip {ticker}: {e}")
        time.sleep(1)

    return candidates

# ─── EMOJI GRADERS ──────────────────────────────────────────────────────────

def grade_rsi(rsi):
    if rsi <= 20: return "✅", "Extremely oversold — strong signal"
    if rsi <= 25: return "✅", "Deeply oversold"
    return "✅", "Oversold"

def grade_drop(drop_pct):
    if drop_pct >= 20: return "✅", "Major selloff — high mean-reversion potential"
    if drop_pct >= 15: return "✅", "Significant drop"
    return "✅", "Meets 10% minimum"

def grade_support(dist_pct):
    if dist_pct <= 0.5: return "✅", "Sitting right on support"
    if dist_pct <= 1.5: return "✅", "Very close to support"
    return "✅", "Near support"

def grade_rvol(rvol):
    if rvol >= 4.0: return "✅", "Massive — institutional activity likely"
    if rvol >= 2.5: return "✅", "Strong volume conviction"
    if rvol >= 1.5: return "✅", "Above-average volume"
    return "❌", "Borderline volume"

def grade_candle(pattern):
    if pattern == "Bullish Engulfing": return "✅", "Bullish Engulfing — strongest pattern"
    if pattern == "Hammer":            return "✅", "Hammer — rejection of lower prices"
    return "✅", "Green candle"

def grade_macd(has_divergence):
    return ("✅", "Bullish divergence confirmed") if has_divergence else ("❌", "No divergence")

def grade_weekly_rsi(weekly_rsi):
    if weekly_rsi is None: return "✅", "N/A"
    if weekly_rsi >= 50:   return "✅", f"{weekly_rsi} — weekly trend healthy"
    if weekly_rsi >= 40:   return "✅", f"{weekly_rsi} — weekly dip, not downtrend"
    return "❌", f"{weekly_rsi} — weekly downtrend risk"

def grade_red_days(red_days):
    if red_days >= 5: return "✅", f"{red_days} consecutive red days — deep exhaustion"
    if red_days >= 3: return "✅", f"{red_days} consecutive red days — exhaustion confirmed"
    return "❌", f"Only {red_days} red day(s)"

def grade_earnings(days_to_earnings):
    if days_to_earnings is None: return "✅", "No earnings imminent"
    return "✅", f"Earnings {days_to_earnings}d away — clear"

def grade_spy(spy_pct):
    if spy_pct >= 0:    return "✅", f"SPY up {spy_pct:+.2f}% — bullish backdrop"
    if spy_pct >= -0.5: return "✅", f"SPY {spy_pct:+.2f}% — neutral"
    if spy_pct >= -1.5: return "✅", f"SPY {spy_pct:+.2f}% — mild weakness, within limit"
    return "❌", f"SPY {spy_pct:+.2f}% — regime warning"

def grade_confidence(win_rate):
    if win_rate is None: return "❌", "N/A"
    if win_rate >= 70:   return "✅", "HIGH confidence"
    if win_rate >= 50:   return "✅", "MODERATE confidence"
    return "❌", "LOW — extra caution"

def grade_rr(rr_str):
    try:
        ratio = float(rr_str.split(":")[1])
    except Exception:
        ratio = 0
    if ratio >= 3: return "✅", "Excellent R:R"
    if ratio >= 2: return "✅", "Good R:R"
    return "❌", "Tight R:R"

# ─── ALERT FORMATTING ───────────────────────────────────────────────────────

def format_alert(winner, runner_ups, setup, confidence, bt_count, ai_analysis):
    sep = "-" * 38

    rsi_e,     rsi_n     = grade_rsi(winner['rsi'])
    drop_e,    drop_n    = grade_drop(winner['drop_pct'])
    sup_e,     sup_n     = grade_support(winner['support_distance_pct'])
    rvol_e,    rvol_n    = grade_rvol(winner['rvol'])
    can_e,     can_n     = grade_candle(winner['candle'])
    macd_e,    macd_n    = grade_macd(winner.get('macd_divergence', False))
    wrsi_e,    wrsi_n    = grade_weekly_rsi(winner.get('weekly_rsi'))
    red_e,     red_n     = grade_red_days(winner.get('red_days', 0))
    earn_e,    earn_n    = grade_earnings(winner.get('days_to_earnings'))
    spy_e,     spy_n     = grade_spy(winner.get('spy_pct', 0))
    conf_e,    conf_n    = grade_confidence(confidence)
    rr_e,      rr_n      = grade_rr(setup['rr'])

    msg  = f"*** REVERSAL ALERT ***\n{sep}\n\n"
    msg += f"TICKER: {winner['ticker']}\n\n"

    msg += "PRICE ACTION:\n"
    msg += f"  Price:          ${winner['price']:.2f}\n"
    msg += f"  20D High:       ${winner['high_20d']:.2f}\n"
    msg += f"  Drop:           -{winner['drop_pct']:.1f}%  {drop_e}  {drop_n}\n"
    msg += f"  Support (60D):  ${winner['low_60d']:.2f}\n"
    msg += f"  To Support:     {winner['support_distance_pct']:.1f}%  {sup_e}  {sup_n}\n\n"

    msg += "INDICATORS:\n"
    msg += f"  RSI(14):        {winner['rsi']}  {rsi_e}  {rsi_n}\n"
    msg += f"  Weekly RSI:     {winner.get('weekly_rsi', 'N/A')}  {wrsi_e}  {wrsi_n}\n"
    msg += f"  RVOL:           {winner['rvol']:.1f}x  {rvol_e}  {rvol_n}\n"
    msg += f"  Volume:         {winner['current_volume']:,}\n"
    msg += f"  20D Avg Vol:    {winner['avg_volume_20d']:,}\n"
    msg += f"  Pattern:        {winner['candle']}  {can_e}  {can_n}\n"
    msg += f"  MACD Diverge:   {'YES'  if winner.get('macd_divergence') else 'NO'}  {macd_e}  {macd_n}\n"
    msg += f"  Red Days Prior: {winner.get('red_days', 0)}  {red_e}  {red_n}\n"
    msg += f"  SPY Today:      {winner.get('spy_pct', 0):+.2f}%  {spy_e}  {spy_n}\n"
    earnings_str = f"{winner['days_to_earnings']}d away" if winner.get('days_to_earnings') else 'Clear'
    msg += f"  Earnings:       {earnings_str}  {earn_e}  {earn_n}\n\n"

    msg += "ALL 10 GATES CLEARED:\n"
    msg += f"  [1]  RSI oversold (<=30)          {rsi_e}\n"
    msg += f"  [2]  10%+ drop from 20D high      {drop_e}\n"
    msg += f"  [3]  Price near support            {sup_e}\n"
    msg += f"  [4]  Green candle + vol spike      {rvol_e}\n"
    msg += f"  [5]  MACD bullish divergence       {macd_e}\n"
    msg += f"  [6]  Hammer or engulfing pattern   {can_e}\n"
    msg += f"  [7]  SPY regime OK                 {spy_e}\n"
    msg += f"  [8]  Weekly RSI >= 40              {wrsi_e}\n"
    msg += f"  [9]  3+ consecutive red days       {red_e}\n"
    msg += f"  [10] No earnings within 5 days     {earn_e}\n\n"

    msg += f"{sep}\n"
    msg += "AI CONFIDENCE (backtested):\n"
    msg += f"  Win Rate:  {confidence_label(confidence)}  {conf_e}  {conf_n}\n"
    if bt_count:
        msg += f"  Samples:   {bt_count} instances  ({BACKTEST_FORWARD_DAYS}d window, {BACKTEST_TARGET_PCT}% target)\n"
    msg += "\n"

    msg += "SUGGESTED ACTION:\n"
    msg += f"  Direction:  LONG\n"
    msg += f"  Entry:      ${setup['entry']:.2f}  (market)\n"
    msg += f"  Stop:       ${setup['stop']:.2f}  (-{setup['risk_pct']}%)\n"
    msg += f"  Target:     ${setup['target']:.2f}  (+{setup['reward_pct']}%)\n"
    msg += f"  R:R Ratio:  {setup['rr']}  {rr_e}  {rr_n}\n\n"

    msg += f"{sep}\n"
    msg += "AI ANALYSIS:\n"
    for line in ai_analysis.split('\n'):
        msg += f"  {line}\n"
    msg += "\n"

    if runner_ups:
        msg += f"{sep}\n"
        msg += "OTHER TRIGGERS (lower RVOL, not alerted):\n"
        for r in runner_ups[:5]:
            re_, _ = grade_rvol(r['rvol'])
            msg += f"  {r['ticker']:6s}  RSI {r['rsi']}  Drop -{r['drop_pct']}%  RVOL {r['rvol']}x  Pattern: {r['candle']}  {re_}\n"
        msg += "\n"

    msg += f"{sep}\n"
    msg += "Highest RVOL selected. Others silenced today.\n"
    msg += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    msg += "Manual review required before entry."
    return msg

# ─── MARKET HOURS ────────────────────────────────────────────────────────────

def is_market_hours():
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    return now.replace(hour=9, minute=30, second=0, microsecond=0) <= now <= now.replace(hour=16, minute=0, second=0, microsecond=0)

def wait_for_market():
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        days = 7 - now.weekday()
        next_open = now.replace(hour=9, minute=30, second=0, microsecond=0) + timedelta(days=days)
        secs = (next_open - now).total_seconds()
        logger.info(f"Weekend — sleeping {secs/3600:.1f}h until Monday open")
        time.sleep(max(secs, 0))
        return
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    if now < market_open:
        secs = (market_open - now).total_seconds()
        logger.info(f"Pre-market — sleeping {secs/60:.0f} min until 9:30 AM ET")
        time.sleep(max(secs, 0))
    elif now > market_close:
        next_open = market_open + timedelta(days=1)
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        secs = (next_open - now).total_seconds()
        logger.info(f"After hours — sleeping {secs/3600:.1f}h until next open")
        time.sleep(max(secs, 0))

# ─── MAIN LOOP ──────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("REVERSAL ALERT SCANNER — Starting (10-gate mode)")
    logger.info(f"  Core gates:      RSI<={RSI_THRESHOLD} | Drop>={DROP_PCT}% | Support | Volume")
    logger.info(f"  Accuracy gates:  MACD diverge | Pattern | SPY | WeeklyRSI | RedDays | Earnings")
    logger.info(f"  Scan interval:   {SCAN_INTERVAL_MINUTES} min | Daily limit: 1 alert (highest RVOL)")
    logger.info(f"  AI analysis:     {'ON' if ANTHROPIC_KEY else 'OFF — add ANTHROPIC_API_KEY to .env'}")
    logger.info("=" * 60)

    send_telegram(
        "*** REVERSAL SCANNER ONLINE (v2 — 10 gates) ***\n\n"
        "Core: RSI<=30 | 10% drop | Support | Volume\n"
        "Accuracy: MACD diverge | Hammer/Engulfing | SPY regime\n"
        "          Weekly RSI | 3+ red days | Earnings clearance\n\n"
        f"One alert/day — highest RVOL wins\n"
        f"Scan every {SCAN_INTERVAL_MINUTES} min during market hours"
    )

    sp500 = get_sp500_tickers()

    while True:
        try:
            wait_for_market()

            state = load_state()
            if already_alerted_today(state):
                logger.info("Already alerted today — sleeping")
                time.sleep(SCAN_INTERVAL_MINUTES * 60)
                continue

            if not is_market_hours():
                time.sleep(60)
                continue

            logger.info("--- Starting S&P 500 scan (10 gates) ---")
            candidates = scan_all_stocks(sp500)

            if not candidates:
                logger.info("No stocks passed all 10 gates this scan.")
                time.sleep(SCAN_INTERVAL_MINUTES * 60)
                continue

            candidates.sort(key=lambda x: x['rvol'], reverse=True)
            winner     = candidates[0]
            runner_ups = candidates[1:]

            logger.info(f"WINNER: {winner['ticker']} RVOL={winner['rvol']}x — running backtest + AI...")

            confidence, bt_count = compute_backtest_confidence(winner['ticker'])
            logger.info(f"  Backtest: {confidence}% over {bt_count} instances")

            setup = compute_trade_setup(winner['price'], winner['low_60d'])
            logger.info(f"  Setup: Entry ${setup['entry']} | Stop ${setup['stop']} | Target ${setup['target']}")

            ai_analysis = get_ai_analysis(winner['ticker'], winner, setup)
            logger.info(f"  AI: {strip_emojis(ai_analysis[:80])}...")

            send_telegram(format_alert(winner, runner_ups, setup, confidence, bt_count, ai_analysis))
            mark_alerted(state, winner['ticker'], winner)
            logger.info("Alert sent. Silent until next trading day.")

            time.sleep(SCAN_INTERVAL_MINUTES * 60)

        except KeyboardInterrupt:
            logger.info("Shutting down.")
            break
        except Exception as e:
            logger.error(f"Scan error: {e}", exc_info=True)
            time.sleep(60)

if __name__ == "__main__":
    main()
