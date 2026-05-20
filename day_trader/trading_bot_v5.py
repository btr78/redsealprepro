import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import json
import os
import re
import logging
from datetime import datetime, time as dtime, timedelta
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import pytz

load_dotenv()
ET = pytz.timezone('America/New_York')

# CONFIGURATION
BOT_TITLE          = "Day Trader B🤖T v5.0"
ACCOUNT_BALANCE    = 10000.0
RISK_PER_TRADE     = 0.01
MAX_TRADES_PER_DAY = 5
SCAN_INTERVAL_SEC  = 300           # 5-minute scan matches 5m candles

# Opening Range Breakout
ORB_RANGE_MINUTES  = 15            # 9:30–9:45 AM ET
ORB_VALID_START    = dtime(9, 45)  # Can only trade after range closes
ORB_VALID_UNTIL    = dtime(15, 0)
ORB_VOL_MULT       = 1.5           # Min volume for breakout
ORB_VOL_STRONG     = 2.0           # Strong volume bonus
ORB_MIN_SCORE      = 65
ORB_RR_MIN         = 1.5           # Min risk:reward

# VWAP Institutional Reversion
VWAP_START         = dtime(10, 30)
VWAP_END           = dtime(14, 30)
VWAP_BAND_STD      = 2.0
VWAP_RSI_BUY       = 40            # RSI must be <= this for BUY
VWAP_RSI_SELL      = 60            # RSI must be >= this for SELL
VWAP_VOL_MULT      = 1.3
VWAP_MIN_SCORE     = 70

# Relative strength filter
RS_MIN_OUTPERFORM  = 0.2

# Market regime / VIX
VIX_CRASH          = 35
VIX_HIGH           = 25
VIX_NORMAL         = 20

# Indicators
RSI_PERIOD = 14
ATR_PERIOD = 14
EMA_FAST   = 9
EMA_SLOW   = 21
EMA_200    = 200
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIG   = 9
BB_PERIOD  = 20
BB_STD     = 2.0

# Cooldowns
SIGNAL_COOLDOWN    = 1800   # 30 min per ticker
GLOBAL_GAP         = 60     # Min 60 sec between any two alerts

# Circuit breakers
CONSEC_LOSS_LIMIT  = 3      # Pause ticker after 3 consecutive losses
DAILY_LOSS_LIMIT   = 4      # Raise min score after 4 losses in a day
DAILY_LOSS_TIGHTEN = 10     # How much to raise min score

# Earnings guard
EARNINGS_BLOCK_DAYS = 2

# Blacklisted tickers — permanently removed for poor performance
# GRAB: 0% WR, SNAP: 4% WR, GME: 13% WR, BB: 6% WR, PLTR: 14% WR
BLOCKED_TICKERS = {'GRAB', 'SNAP', 'GME', 'BB', 'PLTR'}

# Blocked hours ET (hour 14 = 2 PM historically worst — 13% WR)
BLOCKED_HOURS = {14}

# Dynamic suspend thresholds
DYNA_MIN_TRADES  = 20
DYNA_SUSPEND_WR  = 0.15

# Files
TRADES_FILE    = "trade_history.json"
COOLDOWN_FILE  = "cooldown_state.json"
WATCHLIST_FILE = "watchlist.txt"
SETTINGS_FILE  = "bot_settings.json"
LOG_FILE       = "daytrader_v5.log"

WEEKLY_REPORT_DAY  = 6   # Sunday
WEEKLY_REPORT_HOUR = 18  # 6 PM ET

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# LOGGING
_fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_fh, _ch])
log = logging.getLogger(__name__)

# UTILITIES
def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def download_with_retry(ticker, period, interval, retries=3):
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period=period, interval=interval,
                             progress=False, auto_adjust=True)
            if not df.empty:
                return flatten_columns(df)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                log.error(f"Download failed {ticker} {interval}: {e}")
    return pd.DataFrame()

def is_market_hours():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 30) <= t < dtime(16, 0)

def market_time():
    return datetime.now(ET).time()

def is_blocked_hour():
    return datetime.now(ET).hour in BLOCKED_HOURS

def get_today_str():
    return datetime.now(ET).strftime('%Y-%m-%d')

def idx_to_et(df):
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize('UTC').tz_convert(ET)
    else:
        df.index = df.index.tz_convert(ET)
    return df

# SETTINGS & WATCHLIST
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram_ids": [], "email": ""}

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE) as f:
                tickers = [ln.strip().upper() for ln in f if ln.strip()]
            return [t for t in tickers if t not in BLOCKED_TICKERS]
        except Exception:
            pass
    return []

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, 'w') as f:
        f.write('\n'.join(watchlist))

# TELEGRAM
def send_telegram(message, telegram_ids):
    if not TELEGRAM_TOKEN or not telegram_ids:
        return
    for chat_id in telegram_ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": chat_id,
                "text": message[:4096],
                "parse_mode": "Markdown"
            }, timeout=10)
        except Exception as e:
            log.error(f"Telegram error {chat_id}: {e}")

# TRADE TRACKING
def load_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"trades": [], "stats": {"total": 0, "wins": 0, "losses": 0, "pending": 0}}

def save_trades(data):
    with open(TRADES_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def log_trade_record(ticker, action, entry, target, stop, score, strategy, rr):
    data = load_trades()
    trade = {
        "id": len(data["trades"]) + 1,
        "ticker": ticker,
        "action": action,
        "entry": round(entry, 4),
        "target": round(target, 4),
        "stop": round(stop, 4),
        "score": score,
        "strategy": strategy,
        "rr": round(rr, 2),
        "timestamp": datetime.now(ET).isoformat(),
        "status": "PENDING",
        "outcome": None,
        "exit_price": None,
        "pnl_pct": None
    }
    data["trades"].append(trade)
    data["stats"]["total"] += 1
    data["stats"]["pending"] += 1
    save_trades(data)
    log.info(f"Trade logged: {ticker} {action} @ ${entry:.2f} score={score} [{strategy}]")

def check_trade_outcomes():
    data = load_trades()
    updated = False
    for trade in data["trades"]:
        if trade["status"] != "PENDING":
            continue
        try:
            ts_str = trade["timestamp"]
            trade_time = datetime.fromisoformat(ts_str)
            if trade_time.tzinfo is None:
                trade_time = ET.localize(trade_time)
            age_hours = (datetime.now(ET) - trade_time).total_seconds() / 3600
            if age_hours < 1:
                continue
            df = download_with_retry(trade["ticker"], "10d", "1h")
            if df.empty:
                continue
            df = idx_to_et(df)
            df_after = df[df.index > trade_time]
            if df_after.empty:
                continue
            action = trade["action"]
            entry  = trade["entry"]
            target = trade["target"]
            stop   = trade["stop"]
            result = None
            exit_price = None
            for _, row in df_after.iterrows():
                if action == "BUY":
                    if row['High'] >= target:
                        result, exit_price = "WIN", target; break
                    elif row['Low'] <= stop:
                        result, exit_price = "LOSS", stop; break
                else:
                    if row['Low'] <= target:
                        result, exit_price = "WIN", target; break
                    elif row['High'] >= stop:
                        result, exit_price = "LOSS", stop; break
            if result is None and age_hours >= 48:
                exit_price = float(df_after.iloc[-1]['Close'])
                if action == "BUY":
                    result = "WIN" if exit_price > entry else "LOSS"
                else:
                    result = "WIN" if exit_price < entry else "LOSS"
            if result and exit_price is not None:
                pnl = (exit_price - entry) / entry * 100 if action == "BUY" else (entry - exit_price) / entry * 100
                trade["status"]     = result
                trade["outcome"]    = "TARGET HIT" if result == "WIN" else "STOP HIT"
                trade["exit_price"] = round(exit_price, 4)
                trade["pnl_pct"]    = round(pnl, 2)
                data["stats"]["pending"] -= 1
                if result == "WIN":
                    data["stats"]["wins"] += 1
                else:
                    data["stats"]["losses"] += 1
                updated = True
                log.info(f"Trade closed: {trade['ticker']} {result} {pnl:+.2f}%")
        except Exception as e:
            log.error(f"check_trade_outcomes {trade.get('ticker','?')}: {e}")
    if updated:
        save_trades(data)

def get_overall_stats():
    data = load_trades()
    completed = [t for t in data["trades"] if t["status"] in ["WIN", "LOSS"]]
    if not completed:
        return {
            "total": data["stats"]["total"], "wins": 0, "losses": 0,
            "win_rate": 0, "avg_pnl": 0, "total_pnl": 0,
            "pending": data["stats"]["pending"], "best": None, "worst": None
        }
    wins = [t for t in completed if t["status"] == "WIN"]
    pnls = [t["pnl_pct"] for t in completed if t.get("pnl_pct") is not None]
    return {
        "total": data["stats"]["total"],
        "wins": len(wins),
        "losses": len(completed) - len(wins),
        "win_rate": len(wins) / len(completed) * 100,
        "avg_pnl": sum(pnls) / len(pnls) if pnls else 0,
        "total_pnl": sum(pnls),
        "pending": data["stats"]["pending"],
        "best": max(completed, key=lambda x: x.get("pnl_pct") or 0),
        "worst": min(completed, key=lambda x: x.get("pnl_pct") or 0)
    }

def get_ticker_stats():
    data = load_trades()
    stats = {}
    for t in data["trades"]:
        if t["status"] not in ["WIN", "LOSS"]:
            continue
        tk = t["ticker"]
        if tk not in stats:
            stats[tk] = {"wins": 0, "losses": 0}
        if t["status"] == "WIN":
            stats[tk]["wins"] += 1
        else:
            stats[tk]["losses"] += 1
    return stats

def get_daily_counts():
    data = load_trades()
    today = get_today_str()
    today_trades = [t for t in data["trades"] if t.get("timestamp", "").startswith(today)]
    losses = len([t for t in today_trades if t["status"] == "LOSS"])
    return len(today_trades), losses

def get_consecutive_losses(ticker):
    data = load_trades()
    ticker_trades = [t for t in data["trades"]
                     if t["ticker"] == ticker and t["status"] in ["WIN", "LOSS"]]
    count = 0
    for t in reversed(ticker_trades):
        if t["status"] == "LOSS":
            count += 1
        else:
            break
    return count

# COOLDOWNS
def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE) as f:
                d = json.load(f)
            return d.get("signals", {}), d.get("last_any", 0)
        except Exception:
            pass
    return {}, 0

def save_cooldowns(signals, last_any):
    with open(COOLDOWN_FILE, 'w') as f:
        json.dump({"signals": signals, "last_any": last_any,
                   "saved": datetime.now().isoformat()}, f)

# INDICATORS
def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def compute_atr(df, period=14):
    h, l, c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_macd(series):
    fast = compute_ema(series, MACD_FAST)
    slow = compute_ema(series, MACD_SLOW)
    macd = fast - slow
    sig  = compute_ema(macd, MACD_SIG)
    return macd, sig

def compute_bollinger(series, period=20, std_dev=2.0):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + std * std_dev, sma, sma - std * std_dev

def compute_vwap_today(df_5m):
    today        = datetime.now(ET).date()
    session_open = ET.localize(datetime.combine(today, dtime(9, 30)))
    df_et = idx_to_et(df_5m.copy())
    df_today = df_et[df_et.index >= session_open].copy()
    if len(df_today) < 5:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
    typical  = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
    cum_vol  = df_today['Volume'].cumsum()
    cum_tpv  = (typical * df_today['Volume']).cumsum()
    vwap     = cum_tpv / cum_vol.replace(0, np.nan)
    roll_std = typical.rolling(min(20, len(df_today))).std().fillna(method='bfill').fillna(typical.std())
    return vwap, vwap + roll_std * VWAP_BAND_STD, vwap - roll_std * VWAP_BAND_STD

def add_indicators(df):
    if len(df) < 20:
        return df
    df = df.copy()
    df['RSI']    = compute_rsi(df['Close'])
    df['ATR']    = compute_atr(df)
    df['EMA9']   = compute_ema(df['Close'], EMA_FAST)
    df['EMA21']  = compute_ema(df['Close'], EMA_SLOW)
    df['EMA200'] = compute_ema(df['Close'], EMA_200)
    macd, sig    = compute_macd(df['Close'])
    df['MACD'], df['MACDSig'] = macd, sig
    df['BBU'], df['BBM'], df['BBL'] = compute_bollinger(df['Close'])
    vol_sma       = df['Volume'].rolling(20).mean()
    df['VolSMA']  = vol_sma
    df['VolMult'] = df['Volume'] / vol_sma.replace(0, np.nan)
    return df

# MARKET REGIME
def get_vix():
    try:
        df = download_with_retry("^VIX", "2d", "1d")
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except Exception:
        pass
    return 20.0

def get_market_regime(spy_1h):
    if spy_1h.empty or len(spy_1h) < 25:
        return "neutral", 0.5
    spy  = add_indicators(spy_1h)
    last = spy.iloc[-1]
    close  = float(last['Close'])
    ema9   = float(last.get('EMA9')   or close)
    ema21  = float(last.get('EMA21')  or close)
    ema200 = float(last.get('EMA200') or close)
    rsi    = float(last.get('RSI')    or 50)
    macd   = float(last.get('MACD')   or 0)
    sig    = float(last.get('MACDSig')or 0)
    vix    = get_vix()

    if vix >= VIX_CRASH:
        return "crash", 0.95

    bull, bear = 0, 0
    # EMA stack
    if close > ema9 > ema21:    bull += 2
    elif close < ema9 < ema21:  bear += 2
    # EMA 200
    if close > ema200:          bull += 2
    else:                       bear += 2
    # MACD
    if macd > sig:              bull += 1
    else:                       bear += 1
    # RSI
    if rsi > 55:                bull += 1
    elif rsi < 45:              bear += 1
    # VIX
    if vix < VIX_NORMAL:        bull += 1
    elif vix > VIX_HIGH:        bear += 2
    # Recent 5-bar price action
    if len(spy) >= 5:
        if float(spy['Close'].iloc[-1]) > float(spy['Close'].iloc[-5]):
            bull += 1
        else:
            bear += 1

    total = bull + bear
    if total == 0:
        return "neutral", 0.5
    bull_c = bull / total
    bear_c = bear / total
    if bull_c >= 0.65: return "bull",    round(bull_c, 2)
    if bear_c >= 0.65: return "bear",    round(bear_c, 2)
    return "neutral", round(max(bull_c, bear_c), 2)

# EARNINGS GUARD
def get_earnings_info(ticker):
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return False, None, None
        earn_date = None
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            if 'Earnings Date' in cal.index:
                earn_date = pd.to_datetime(cal.loc['Earnings Date'].iloc[0])
            elif 'Earnings Date' in cal.columns:
                earn_date = pd.to_datetime(cal['Earnings Date'].iloc[0])
        elif isinstance(cal, dict):
            dates = cal.get('Earnings Date', [])
            if dates:
                earn_date = pd.to_datetime(dates[0])
        if earn_date is None:
            return False, None, None
        days_away = (earn_date.date() - datetime.now().date()).days
        return 0 <= days_away <= EARNINGS_BLOCK_DAYS, days_away, earn_date.strftime('%b %d')
    except Exception:
        return False, None, None

# STRATEGY A — OPENING RANGE BREAKOUT (ORB)
def get_opening_range(df_5m):
    today        = datetime.now(ET).date()
    mkt_open     = ET.localize(datetime.combine(today, dtime(9, 30)))
    orb_end      = ET.localize(datetime.combine(today, dtime(9, 30) if False else
                               dtime(9, 30 + ORB_RANGE_MINUTES if 30 + ORB_RANGE_MINUTES < 60
                                     else 45)))
    orb_end      = ET.localize(datetime.combine(today, dtime(9, 45)))
    df_et        = idx_to_et(df_5m.copy())
    orb_candles  = df_et[(df_et.index >= mkt_open) & (df_et.index < orb_end)]
    if len(orb_candles) < 2:
        return None, None
    return float(orb_candles['High'].max()), float(orb_candles['Low'].min())

def strategy_orb(ticker, df_5m, df_1h, regime, regime_conf):
    mt = market_time()
    if mt < ORB_VALID_START or mt >= ORB_VALID_UNTIL:
        return None, 0, {}
    if df_5m.empty or len(df_5m) < 8:
        return None, 0, {}

    df_5m_ind = add_indicators(df_5m)
    orb_high, orb_low = get_opening_range(df_5m_ind)
    if orb_high is None:
        return None, 0, {}

    orb_range = orb_high - orb_low
    if orb_range <= 0:
        return None, 0, {}

    curr     = df_5m_ind.iloc[-1]
    close    = float(curr['Close'])
    vol_mult = float(curr['VolMult']) if pd.notna(curr.get('VolMult')) else 1.0
    rsi      = float(curr['RSI']) if pd.notna(curr.get('RSI')) else 50

    # Detect breakout: close beyond ORB boundary
    if close > orb_high:
        action = "BUY"
    elif close < orb_low:
        action = "SELL"
    else:
        return None, 0, {}

    # Hard regime gates
    if action == "BUY" and regime in ("bear", "crash"):
        log.info(f"{ticker} ORB BUY blocked — {regime} regime")
        return None, 0, {}
    if action == "SELL" and regime == "bull" and regime_conf >= 0.75:
        log.info(f"{ticker} ORB SELL blocked — strong bull {regime_conf:.0%}")
        return None, 0, {}

    # Target / stop
    if action == "BUY":
        entry, stop = close, orb_low
        target = entry + orb_range * 2.0
    else:
        entry, stop = close, orb_high
        target = entry - orb_range * 2.0

    risk = abs(entry - stop)
    rr   = abs(target - entry) / risk if risk > 0 else 0
    if rr < ORB_RR_MIN:
        log.info(f"{ticker} ORB R:R {rr:.1f} too low")
        return None, 0, {}

    score = 40  # Base: breakout confirmed

    # Volume (most important for ORB)
    if vol_mult >= ORB_VOL_STRONG:
        score += 20; vol_signal = "STRONG 🔥"
    elif vol_mult >= ORB_VOL_MULT:
        score += 10; vol_signal = "ADEQUATE"
    else:
        score -= 20; vol_signal = "WEAK ⚠️"  # Fake breakout likely

    # 1h trend alignment
    trend_1h = "NEUTRAL"
    if not df_1h.empty and len(df_1h) >= 25:
        df_1h_ind = add_indicators(df_1h)
        last_1h   = df_1h_ind.iloc[-1]
        c1h  = float(last_1h['Close'])
        e9   = float(last_1h.get('EMA9')  or c1h)
        e21  = float(last_1h.get('EMA21') or c1h)
        macd_1h = float(last_1h.get('MACD')    or 0)
        sig_1h  = float(last_1h.get('MACDSig') or 0)
        if action == "BUY":
            if c1h > e9 > e21:
                score += 15; trend_1h = "BULLISH ✅"
                if macd_1h > sig_1h > 0: score += 5
            elif c1h < e21:
                score -= 10; trend_1h = "COUNTER ⚠️"
        else:
            if c1h < e9 < e21:
                score += 15; trend_1h = "BEARISH ✅"
                if macd_1h < sig_1h < 0: score += 5
            elif c1h > e21:
                score -= 10; trend_1h = "COUNTER ⚠️"

    # RSI check — avoid overextended entries
    if action == "BUY":
        if rsi > 80:   score -= 10; rsi_signal = "OVERBOUGHT ⚠️"
        elif 45 <= rsi <= 70: score += 5; rsi_signal = "ROOM TO RUN"
        else:          rsi_signal = "NEUTRAL"
    else:
        if rsi < 20:   score -= 10; rsi_signal = "OVERSOLD ⚠️"
        elif 30 <= rsi <= 55: score += 5; rsi_signal = "ROOM TO DROP"
        else:          rsi_signal = "NEUTRAL"

    # Regime bonus
    regime_adj = ""
    if action == "BUY" and regime == "bull":
        score += 10; regime_adj = "+10 bull"
    elif action == "SELL" and regime == "bear":
        score += 10; regime_adj = "+10 bear"

    # Morning bonus — best ORB signals are before noon
    if mt < dtime(12, 0):
        score += 5

    score = max(0, min(100, score))
    details = {
        "strategy": "ORB", "action": action,
        "orb_high": orb_high, "orb_low": orb_low, "orb_range": orb_range,
        "entry": entry, "stop": stop, "target": target, "rr": rr,
        "vol_mult": vol_mult, "vol_signal": vol_signal,
        "rsi": rsi, "rsi_signal": rsi_signal,
        "trend_1h": trend_1h, "regime_adj": regime_adj
    }
    log.info(f"{ticker} ORB {action} score={score}/100 vol={vol_mult:.1f}x rsi={rsi:.0f}")
    return action, score, details

# STRATEGY B — VWAP INSTITUTIONAL REVERSION
def strategy_vwap_reversion(ticker, df_5m, df_1h, regime, regime_conf):
    mt = market_time()
    if mt < VWAP_START or mt > VWAP_END:
        return None, 0, {}
    if df_5m.empty or len(df_5m) < 25:
        return None, 0, {}

    df_5m_ind = add_indicators(df_5m)
    vwap, upper, lower = compute_vwap_today(df_5m_ind)
    if vwap.empty:
        return None, 0, {}

    curr     = df_5m_ind.iloc[-1]
    close    = float(curr['Close'])
    vwap_val = float(vwap.iloc[-1])  if pd.notna(vwap.iloc[-1])  else 0
    upper_v  = float(upper.iloc[-1]) if pd.notna(upper.iloc[-1]) else 0
    lower_v  = float(lower.iloc[-1]) if pd.notna(lower.iloc[-1]) else 0
    vol_mult = float(curr['VolMult']) if pd.notna(curr.get('VolMult')) else 1.0
    rsi      = float(curr['RSI'])     if pd.notna(curr.get('RSI'))     else 50

    if vwap_val <= 0 or upper_v <= lower_v:
        return None, 0, {}

    # Criterion 1 (REQUIRED): Price at VWAP band
    if close <= lower_v:
        action = "BUY"
    elif close >= upper_v:
        action = "SELL"
    else:
        return None, 0, {}

    # Hard regime gates
    if action == "BUY" and regime in ("bear", "crash"):
        log.info(f"{ticker} VWAP BUY blocked — {regime}")
        return None, 0, {}
    if action == "SELL" and regime == "bull" and regime_conf >= 0.80:
        log.info(f"{ticker} VWAP SELL blocked — strong bull {regime_conf:.0%}")
        return None, 0, {}

    # Criterion 2 (REQUIRED): RSI extreme
    if action == "BUY" and rsi > VWAP_RSI_BUY:
        log.info(f"{ticker} VWAP BUY RSI gate failed rsi={rsi:.0f}")
        return None, 0, {}
    if action == "SELL" and rsi < VWAP_RSI_SELL:
        log.info(f"{ticker} VWAP SELL RSI gate failed rsi={rsi:.0f}")
        return None, 0, {}

    # Criterion 3 (REQUIRED): Volume
    if vol_mult < VWAP_VOL_MULT:
        log.info(f"{ticker} VWAP volume gate failed vol={vol_mult:.1f}x")
        return None, 0, {}

    # Target / stop
    atr = float(curr['ATR']) if pd.notna(curr.get('ATR')) else close * 0.01
    if action == "BUY":
        entry, stop = close, close - atr * 1.5
        target = vwap_val
    else:
        entry, stop = close, close + atr * 1.5
        target = vwap_val

    risk = abs(entry - stop)
    rr   = abs(target - entry) / risk if risk > 0 else 0
    if rr < 1.2:
        log.info(f"{ticker} VWAP R:R {rr:.1f} too low")
        return None, 0, {}

    score = 35  # Base: all 3 required criteria met

    # RSI depth bonus
    if action == "BUY":
        if rsi < 20:   score += 20; rsi_signal = "DEEPLY OVERSOLD 🔥"
        elif rsi < 30: score += 15; rsi_signal = "OVERSOLD"
        else:          score += 8;  rsi_signal = "MODERATE"
    else:
        if rsi > 80:   score += 20; rsi_signal = "DEEPLY OVERBOUGHT 🔥"
        elif rsi > 70: score += 15; rsi_signal = "OVERBOUGHT"
        else:          score += 8;  rsi_signal = "MODERATE"

    # Volume strength
    if vol_mult >= 2.5:   score += 15; vol_signal = "SURGE 🔥"
    elif vol_mult >= 1.8: score += 10; vol_signal = "STRONG"
    else:                 score += 5;  vol_signal = "ADEQUATE"

    # 1h MACD alignment
    trend_1h = "NEUTRAL"
    if not df_1h.empty and len(df_1h) >= 25:
        df_1h_ind = add_indicators(df_1h)
        last_1h   = df_1h_ind.iloc[-1]
        macd_1h   = float(last_1h.get('MACD')    or 0)
        sig_1h    = float(last_1h.get('MACDSig') or 0)
        if action == "BUY" and macd_1h > sig_1h:
            score += 10; trend_1h = "MACD BULLISH ✅"
        elif action == "SELL" and macd_1h < sig_1h:
            score += 10; trend_1h = "MACD BEARISH ✅"

    # Bollinger Band confluence
    bb_signal = ""
    bbl = float(curr.get('BBL') or 0) if pd.notna(curr.get('BBL')) else 0
    bbu = float(curr.get('BBU') or 0) if pd.notna(curr.get('BBU')) else 0
    if action == "BUY" and bbl > 0 and close <= bbl:
        score += 10; bb_signal = "AT BB LOWER ✅"
    elif action == "SELL" and bbu > 0 and close >= bbu:
        score += 10; bb_signal = "AT BB UPPER ✅"

    score = max(0, min(100, score))
    details = {
        "strategy": "VWAP", "action": action,
        "vwap": vwap_val, "upper": upper_v, "lower": lower_v,
        "entry": entry, "stop": stop, "target": target, "rr": rr,
        "vol_mult": vol_mult, "vol_signal": vol_signal,
        "rsi": rsi, "rsi_signal": rsi_signal,
        "trend_1h": trend_1h, "bb_signal": bb_signal
    }
    log.info(f"{ticker} VWAP {action} score={score}/100 rsi={rsi:.0f} vol={vol_mult:.1f}x")
    return action, score, details

# RELATIVE STRENGTH FILTER
def get_relative_strength(ticker, df_5m_ticker, df_5m_spy):
    today        = datetime.now(ET).date()
    session_open = ET.localize(datetime.combine(today, dtime(9, 30)))

    def today_pct(df):
        if df.empty:
            return 0.0
        df_et = idx_to_et(df.copy())
        today_df = df_et[df_et.index >= session_open]
        if today_df.empty or len(today_df) < 2:
            return 0.0
        open_p = float(today_df.iloc[0]['Open'])
        curr_p = float(today_df.iloc[-1]['Close'])
        return (curr_p - open_p) / open_p * 100 if open_p > 0 else 0.0

    ticker_chg = today_pct(df_5m_ticker)
    spy_chg    = today_pct(df_5m_spy)
    rs = ticker_chg - spy_chg

    if abs(spy_chg) < 0.15:   spy_dir = "flat"
    elif spy_chg > 0:          spy_dir = "up"
    else:                      spy_dir = "down"

    return rs, spy_dir, spy_chg

def rs_filter_passes(action, rs, spy_dir):
    if spy_dir == "flat":
        return True
    if action == "BUY":
        if spy_dir == "up":
            return rs >= RS_MIN_OUTPERFORM   # Must outperform on green day
        else:
            return rs <= -3.0               # Only deeply oversold relative movers on red day
    else:
        if spy_dir == "down":
            return rs <= -RS_MIN_OUTPERFORM  # Must underperform on red day
        else:
            return rs >= 3.0               # Only heavily lagging on green day

# ALERT FORMATTING
def get_grade(score):
    if score >= 90: return "A+ 🌟"
    if score >= 80: return "A 🟢"
    if score >= 70: return "B+ 🟡"
    if score >= 60: return "B 🟠"
    return "C ⚠️"

def format_signal_alert(ticker, action, score, details, regime, regime_conf,
                         rs, spy_dir, spy_chg, vix):
    grade    = get_grade(score)
    strategy = details.get("strategy", "")
    entry    = details.get("entry", 0)
    stop     = details.get("stop",  0)
    target   = details.get("target",0)
    rr       = details.get("rr",    0)

    action_line  = "✅ STRONG BUY" if action == "BUY" else "🛑 STRONG SELL"
    regime_emoji = {"bull": "🟢", "neutral": "🟡", "bear": "🔴", "crash": "🆘"}.get(regime, "🟡")
    spy_emoji    = "📈" if spy_dir == "up" else "📉" if spy_dir == "down" else "➡️"

    risk_pct = abs(entry - stop) / entry * 100 if entry > 0 else 0
    gain_pct = abs(target - entry) / entry * 100 if entry > 0 else 0

    if strategy == "ORB":
        strat_line = (
            f"*STRATEGY:* Opening Range Breakout\n"
            f"*ORB RANGE:* ${details.get('orb_low',0):.2f} — ${details.get('orb_high',0):.2f}"
            f" (${details.get('orb_range',0):.2f} wide)"
        )
    else:
        strat_line = (
            f"*STRATEGY:* VWAP Institutional Reversion\n"
            f"*VWAP:* ${details.get('vwap',0):.2f} | "
            f"Band: ${details.get('lower',0):.2f} — ${details.get('upper',0):.2f}"
        )

    vol_line   = f"*VOLUME:* {details.get('vol_signal','')} ({details.get('vol_mult',0):.1f}x avg)"
    rsi_line   = f"*RSI:* {details.get('rsi',0):.0f} — {details.get('rsi_signal','')}"
    trend_line = f"*1H TREND:* {details.get('trend_1h','NEUTRAL')}"
    bb_line    = f"\n*BB:* {details['bb_signal']}" if details.get('bb_signal') else ""
    vix_warn   = f"\n*VIX:* ⚠️ {vix:.1f} ELEVATED — Tighten Stops" if vix >= VIX_HIGH else ""

    msg = (
        f"*Day Trader B🤖T v5.0*\n"
        f"*TICKER:* {ticker}\n"
        f"*SIGNAL:* {action_line}\n"
        f"*PRICE:* ${entry:.2f}\n"
        f"{strat_line}\n"
        f"*SCORE:* {score}/100 — {grade}\n"
        f"*ENTRY:* ${entry:.2f}\n"
        f"*STOP:* ${stop:.2f}  (−{risk_pct:.1f}%)\n"
        f"*TARGET:* ${target:.2f}  (+{gain_pct:.1f}%)\n"
        f"*R:R RATIO:* 1:{rr:.1f}\n"
        f"{vol_line}\n"
        f"{rsi_line}\n"
        f"{trend_line}"
        f"{bb_line}\n"
        f"*MARKET:* {spy_emoji} SPY {spy_chg:+.2f}% | RS: {rs:+.2f}%\n"
        f"*REGIME:* {regime_emoji} {regime.upper()} ({regime_conf:.0%})"
        f"{vix_warn}\n"
        f"_Risk 1% of account. Not financial advice._"
    )
    return msg[:4096]

# REPORTS
last_weekly_report_time = None

def should_send_weekly_report():
    global last_weekly_report_time
    now = datetime.now(ET)
    if now.weekday() != WEEKLY_REPORT_DAY or now.hour != WEEKLY_REPORT_HOUR:
        return False
    if last_weekly_report_time and (now - last_weekly_report_time).total_seconds() < 82800:
        return False
    return True

def generate_weekly_report():
    global last_weekly_report_time
    stats    = get_overall_stats()
    data     = load_trades()
    week_ago = datetime.now(ET) - timedelta(days=7)

    weekly = []
    for t in data["trades"]:
        try:
            ts = datetime.fromisoformat(t["timestamp"])
            if ts.replace(tzinfo=None) > week_ago.replace(tzinfo=None):
                weekly.append(t)
        except Exception:
            pass

    weekly_done  = [t for t in weekly if t["status"] in ["WIN", "LOSS"]]
    weekly_wins  = len([t for t in weekly_done if t["status"] == "WIN"])
    weekly_pnl   = sum(t.get("pnl_pct") or 0 for t in weekly_done)
    weekly_wr    = weekly_wins / len(weekly_done) * 100 if weekly_done else 0

    orb_trades   = [t for t in data["trades"] if t.get("strategy") == "ORB"  and t["status"] in ["WIN","LOSS"]]
    vwap_trades  = [t for t in data["trades"] if t.get("strategy") == "VWAP" and t["status"] in ["WIN","LOSS"]]
    orb_wr  = len([t for t in orb_trades  if t["status"] == "WIN"]) / len(orb_trades)  * 100 if orb_trades  else 0
    vwap_wr = len([t for t in vwap_trades if t["status"] == "WIN"]) / len(vwap_trades) * 100 if vwap_trades else 0

    tk_stats = get_ticker_stats()
    best_tks = sorted(
        [(tk, s["wins"] / (s["wins"] + s["losses"]) * 100, s["wins"] + s["losses"])
         for tk, s in tk_stats.items() if s["wins"] + s["losses"] >= 3],
        key=lambda x: -x[1]
    )[:5]

    wr_emoji   = "📈" if stats["win_rate"] >= 55 else "📉"
    week_emoji = "🟢" if weekly_pnl >= 0 else "🔴"

    report = (
        f"*Day Trader B🤖T v5.0 — WEEKLY REPORT*\n"
        f"*📅 THIS WEEK*\n"
        f"Signals: {len(weekly)} | Done: {len(weekly_done)}\n"
        f"Wins: {weekly_wins} | Losses: {len(weekly_done) - weekly_wins}\n"
        f"Win Rate: {weekly_wr:.1f}%\n"
        f"P&L: {week_emoji} {weekly_pnl:+.2f}%\n"
        f"*{wr_emoji} ALL TIME*\n"
        f"Total: {stats['total']} | Pending: {stats['pending']}\n"
        f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        f"Win Rate: {stats['win_rate']:.1f}%\n"
        f"Avg P&L: {stats['avg_pnl']:+.2f}%\n"
        f"Total P&L: {stats['total_pnl']:+.2f}%\n"
        f"*📊 BY STRATEGY*\n"
        f"ORB: {orb_wr:.1f}% WR ({len(orb_trades)} trades)\n"
        f"VWAP: {vwap_wr:.1f}% WR ({len(vwap_trades)} trades)\n"
    )

    if best_tks:
        for tk, wr, n in best_tks:
            s = tk_stats[tk]
            report += f"{tk}: {wr:.0f}% WR ({s['wins']}W/{s['losses']}L)\n"

    if stats.get("best") and stats["best"].get("pnl_pct"):
        b = stats["best"]
    if stats.get("worst") and stats["worst"].get("pnl_pct"):
        w = stats["worst"]
        report += f"*💔 WORST:* {w['ticker']} {w['action']} {w['pnl_pct']:.2f}%\n"

    last_weekly_report_time = datetime.now(ET)
    return report[:4096]

# TELEGRAM COMMAND LISTENER
last_update_id = 0
scanning_paused = False
_watchlist_ref = []
_tg_ids_ref = []

def _cmd_listener_thread():
    import time as _t
    while True:
        try:
            listen_commands(_watchlist_ref, _tg_ids_ref)
        except Exception:
            pass
        _t.sleep(3)

def listen_commands(watchlist, telegram_ids):
    global last_update_id, scanning_paused
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 3}, timeout=8)
        if not resp.ok:
            return watchlist
        updates = resp.json().get("result", [])
        for upd in updates:
            last_update_id = upd["update_id"]
            msg_obj = upd.get("message", {})
            text    = msg_obj.get("text", "").strip()
            chat_id = str(msg_obj.get("chat", {}).get("id", ""))
            log.info(f"CMD recv: chat_id={chat_id} text={repr(text)}")
            if chat_id not in [str(t) for t in telegram_ids]:
                continue
            cmd = text.lower()
            if cmd == "/status":
                stats = get_overall_stats()
                total_today, losses_today = get_daily_counts()
                reply = (
                    f"*Day Trader B🤖T v5.0 STATUS*\n"
                    f"Win Rate: {stats['win_rate']:.1f}%\n"
                    f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
                    f"Avg P&L: {stats['avg_pnl']:+.2f}%\n"
                    f"Pending: {stats['pending']}\n"
                    f"Today: {total_today} signals ({losses_today} losses)\n"
                    f"Market: {'OPEN' if is_market_hours() else 'CLOSED'}"
                )
                send_telegram(reply, [chat_id])
            elif cmd == "/watchlist":
                send_telegram(f"*WATCHLIST ({len(watchlist)})*\n" + ", ".join(watchlist), [chat_id])
            elif cmd == "/report":
                send_telegram(generate_weekly_report(), [chat_id])
            elif cmd.startswith("/add "):
                new_tks = [t.strip().upper() for t in text[5:].split(",") if t.strip()]
                added = [t for t in new_tks if t not in watchlist and t not in BLOCKED_TICKERS]
                watchlist.extend(added)
                if added:
                    save_watchlist(watchlist)
                    send_telegram(f"Added: {', '.join(added)}", [chat_id])
                else:
                    send_telegram("No valid tickers to add.", [chat_id])
            elif cmd.startswith("/remove "):
                rem = [t.strip().upper() for t in text[8:].split(",") if t.strip()]
                removed = [t for t in rem if t in watchlist]
                for t in removed:
                    watchlist.remove(t)
                if removed:
                    save_watchlist(watchlist)
                    send_telegram(f"Removed: {', '.join(removed)}", [chat_id])
            elif cmd == "/pause":
                scanning_paused = True
                send_telegram("\u23f8 Scanning *PAUSED*. Send /resume to restart.", [chat_id])
            elif cmd == "/resume":
                scanning_paused = False
                send_telegram("\u25b6 Scanning *RESUMED*.", [chat_id])
            elif cmd == "/vix":
                try:
                    import yfinance as _yf
                    _vdf = _yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=True)
                    if hasattr(_vdf.columns, "levels"):
                        _vdf.columns = [c[0] if isinstance(c, tuple) else c for c in _vdf.columns]
                    _cv = float(_vdf["Close"].iloc[-1])
                    _pv = float(_vdf["Close"].iloc[-2])
                    _chg = _cv - _pv
                    if _cv < 15:   _gauge = "\U0001f7e2 COMPLACENT — markets very calm"
                    elif _cv < 20: _gauge = "\U0001f7e1 NORMAL — healthy volatility"
                    elif _cv < 25: _gauge = "\U0001f7e0 CAUTION — watch your stops"
                    elif _cv < 35: _gauge = "\U0001f534 FEAR — reduce size"
                    else:          _gauge = "\u26a0 EXTREME FEAR / CRASH MODE"
                    _arrow = "\U0001f4c8" if _chg > 0 else "\U0001f4c9"
                    send_telegram(
                        f"*\U0001f4ca VIX Fear Gauge*\n"
                        f"Current: *{_cv:.2f}* {_arrow} ({_chg:+.2f} vs yesterday)\n"
                        f"Signal: {_gauge}\n"
                        f"Levels: <15 Calm | 15-20 Normal | 20-25 Caution | 25-35 Fear | 35+ Crash",
                        [chat_id]
                    )
                except Exception as _e:
                    send_telegram(f"VIX error: {_e}", [chat_id])
            elif cmd == "/sectors":
                try:
                    import yfinance as _yf
                    _SECTORS = {
                        "XLK": "Tech", "XLF": "Financials", "XLE": "Energy",
                        "XLV": "Healthcare", "XLI": "Industrials", "XLC": "Comms",
                        "XLY": "Cons Disc", "XLP": "Cons Staples", "XLU": "Utilities",
                        "XLRE": "Real Estate", "XLB": "Materials"
                    }
                    _sdf = _yf.download(" ".join(_SECTORS.keys()), period="2d", interval="1d",
                                        progress=False, auto_adjust=True, group_by="ticker")
                    _rows = []
                    for _etf, _name in _SECTORS.items():
                        try:
                            _c = _sdf[_etf]["Close"] if isinstance(_sdf.columns, pd.MultiIndex) else _sdf["Close"]
                            _pct = (float(_c.iloc[-1]) - float(_c.iloc[-2])) / float(_c.iloc[-2]) * 100
                            _rows.append((_name, _etf, _pct))
                        except Exception:
                            pass
                    _rows.sort(key=lambda x: x[2], reverse=True)
                    _smsg = "*\U0001f4ca Sector Rotation (1d %)*\n"
                    for _sname, _setf, _spct in _rows:
                        _bar = "\U0001f7e2" if _spct > 0.5 else "\U0001f534" if _spct < -0.5 else "\U0001f7e1"
                        _smsg += f"{_bar} {_sname} ({_setf}): {_spct:+.2f}%\n"
                    send_telegram(_smsg, [chat_id])
                except Exception as _e:
                    send_telegram(f"Sectors error: {_e}", [chat_id])
            elif cmd.startswith("/check "):
                _tk = text[7:].strip().upper()
                if not _tk:
                    send_telegram("Usage: /check TICKER", [chat_id])
                else:
                    try:
                        import yfinance as _yf
                        _info = _yf.Ticker(_tk).info
                        _eps  = _info.get("trailingEps") or _info.get("forwardEps") or 0
                        _feps = _info.get("forwardEps") or _eps
                        _pe_t = _info.get("trailingPE") or 0
                        _pe_f = _info.get("forwardPE") or 0
                        _cname = _info.get("shortName", _tk)
                        _price = float(_info.get("currentPrice") or _info.get("regularMarketPrice") or 0)
                        _tech_line = ""
                        _df_d = download_with_retry(_tk, "6mo", "1d")
                        if not _df_d.empty and len(_df_d) >= 50:
                            _df_d = add_indicators(_df_d)
                            _last = _df_d.iloc[-1]
                            _rsi  = float(_last.get("RSI") or 50)
                            _adx  = float(_last.get("ADX") or 0)
                            _macd = float(_last.get("MACD") or 0)
                            _msig = float(_last.get("MACDSig") or 0)
                            _e9   = float(_last.get("EMA9") or _price)
                            _e21  = float(_last.get("EMA21") or _price)
                            _e200 = float(_last.get("EMA200") or _price)
                            if _e9 > _e21 > _e200:   _trend = "\U0001f7e2 BULLISH stack"
                            elif _e9 < _e21 < _e200: _trend = "\U0001f534 BEARISH stack"
                            else:                    _trend = "\U0001f7e1 MIXED"
                            _macd_str = "Bull" if _macd > _msig else "Bear"
                            _rsi_str = "Oversold" if _rsi < 30 else "Overbought" if _rsi > 70 else f"{_rsi:.0f}"
                            _tech_line = (
                                f"*Technical:* {_trend}\n"
                                f"RSI: {_rsi_str} | ADX: {_adx:.0f} | MACD: {_macd_str}\n"
                                f"EMA 9/21/200: ${_e9:.2f} / ${_e21:.2f} / ${_e200:.2f}\n\n"
                            )
                        _fv_lines = ""
                        if _eps and _eps > 0:
                            _bfv = round(_eps * 12, 2)
                            _nfv = round(_eps * 18, 2)
                            _ufv = round(_eps * 25, 2)
                            def _ud(_fv):
                                return "undervalued" if _price < _fv else "overvalued"
                            _fv_lines = (
                                f"*Fair Value (P/E based):*\n"
                                f"\U0001f7e2 Bear (12x EPS ${_eps:.2f}): ${_bfv} — {_ud(_bfv)}\n"
                                f"\U0001f7e1 Base (18x EPS): ${_nfv} — {_ud(_nfv)}\n"
                                f"\U0001f4b9 Bull (25x EPS): ${_ufv} — {_ud(_ufv)}\n"
                            )
                            if _feps and _feps > 0 and _feps != _eps:
                                _ffv = round(_feps * 18, 2)
                                _fv_lines += f"Forward (18x fEPS ${_feps:.2f}): ${_ffv} — {_ud(_ffv)}\n"
                        _pe_line = ""
                        if _pe_t: _pe_line += f"Trailing P/E: {_pe_t:.1f}"
                        if _pe_f: _pe_line += f" | Forward P/E: {_pe_f:.1f}"
                        send_telegram(
                            f"*\U0001f50d {_cname} ({_tk}) @ ${_price:.2f}*\n"
                            f"{_pe_line}\n\n"
                            f"{_tech_line}"
                            f"{_fv_lines}",
                            [chat_id]
                        )
                    except Exception as _e:
                        send_telegram(f"/check error for {_tk}: {_e}", [chat_id])
            elif cmd == "/help":
                send_telegram(
                    "\U0001f4d6 *BOT COMMANDS*\n"
                    "/status \u2014 bot health & today's stats\n"
                    "/check TICKER \u2014 technical analysis + DCF & P/E fair value (bear/base/bull)\n"
                    "/report \u2014 performance report\n"
                    "/pause \u2014 pause all scanning\n"
                    "/resume \u2014 resume scanning\n"
                    "/vix \u2014 VIX fear gauge\n"
                    "/sectors \u2014 sector rotation\n"
                    "/watchlist \u2014 see all tickers",
                    [chat_id]
                )
    except Exception as e:
        log.error(f"listen_commands error: {e}")
    return watchlist

# MAIN SCAN
def scan(watchlist, telegram_ids, regime, regime_conf, spy_5m, vix, cooldowns, last_any):
    total_today, losses_today = get_daily_counts()
    if total_today >= MAX_TRADES_PER_DAY:
        log.info(f"Max trades/day reached ({MAX_TRADES_PER_DAY})")
        return cooldowns, last_any

    eff_orb_min  = ORB_MIN_SCORE  + (DAILY_LOSS_TIGHTEN if losses_today >= DAILY_LOSS_LIMIT else 0)
    eff_vwap_min = VWAP_MIN_SCORE + (DAILY_LOSS_TIGHTEN if losses_today >= DAILY_LOSS_LIMIT else 0)
    tk_stats     = get_ticker_stats()

    for ticker in watchlist:
        if ticker == "SPY":
            continue
        try:
            # Auto-suspend: poor win rate after enough trades
            ts = tk_stats.get(ticker, {"wins": 0, "losses": 0})
            total_tk = ts["wins"] + ts["losses"]
            if total_tk >= DYNA_MIN_TRADES:
                wr_tk = ts["wins"] / total_tk
                if wr_tk < DYNA_SUSPEND_WR:
                    log.info(f"{ticker} auto-suspended WR={wr_tk:.0%} ({total_tk} trades)")
                    continue

            # Consecutive loss circuit breaker
            if get_consecutive_losses(ticker) >= CONSEC_LOSS_LIMIT:
                log.info(f"{ticker} paused — {CONSEC_LOSS_LIMIT} consecutive losses")
                continue

            # Cooldown
            now_ts = time.time()
            if ticker in cooldowns and now_ts - cooldowns[ticker] < SIGNAL_COOLDOWN:
                continue

            # Earnings guard
            has_earn, earn_days, earn_str = get_earnings_info(ticker)
            if has_earn:
                log.info(f"{ticker} blocked — earnings {earn_str} in {earn_days}d")
                continue

            # Download data
            df_5m = download_with_retry(ticker, "5d",  "5m")
            df_1h = download_with_retry(ticker, "60d", "1h")
            if df_5m.empty or df_1h.empty:
                continue

            # Relative strength vs SPY
            rs, spy_dir, spy_chg = get_relative_strength(ticker, df_5m, spy_5m)

            # Try both strategies — take the higher-scoring one
            best_action, best_score, best_details = None, 0, {}

            # Strategy A: ORB
            orb_act, orb_score, orb_det = strategy_orb(ticker, df_5m, df_1h, regime, regime_conf)
            if orb_act and orb_score >= eff_orb_min:
                if rs_filter_passes(orb_act, rs, spy_dir):
                    if orb_score > best_score:
                        best_action, best_score, best_details = orb_act, orb_score, orb_det
                else:
                    log.info(f"{ticker} ORB {orb_act} RS filter failed rs={rs:+.2f}% spy={spy_dir}")

            # Strategy B: VWAP Reversion
            vwap_act, vwap_score, vwap_det = strategy_vwap_reversion(
                ticker, df_5m, df_1h, regime, regime_conf)
            if vwap_act and vwap_score >= eff_vwap_min:
                if rs_filter_passes(vwap_act, rs, spy_dir):
                    if vwap_score > best_score:
                        best_action, best_score, best_details = vwap_act, vwap_score, vwap_det
                else:
                    log.info(f"{ticker} VWAP {vwap_act} RS filter failed rs={rs:+.2f}% spy={spy_dir}")

            if not best_action:
                continue

            # Global gap cooldown
            if now_ts - last_any < GLOBAL_GAP:
                log.info(f"{ticker} global gap cooldown {int(now_ts-last_any)}s")
                continue

            # Send alert
            msg = format_signal_alert(
                ticker, best_action, best_score, best_details,
                regime, regime_conf, rs, spy_dir, spy_chg, vix
            )
            send_telegram(msg, telegram_ids)

            # Log trade
            log_trade_record(
                ticker=ticker, action=best_action,
                entry=best_details["entry"], target=best_details["target"],
                stop=best_details["stop"],   score=best_score,
                strategy=best_details["strategy"], rr=best_details["rr"]
            )

            cooldowns[ticker] = now_ts
            last_any = now_ts
            save_cooldowns(cooldowns, last_any)
            log.info(f"ALERT SENT: {ticker} {best_action} {best_score}/100 [{best_details['strategy']}]")

        except Exception as e:
            log.error(f"Scan error {ticker}: {e}")

    return cooldowns, last_any

# MAIN
def main():
    log.info("=" * 60)
    log.info("Day Trader B🤖T v5.0 — Starting")
    log.info("Strategies: Opening Range Breakout + VWAP Reversion")
    log.info("=" * 60)

    settings     = load_settings()
    telegram_ids = settings.get("telegram_ids", [])

    watchlist = load_watchlist()
    if not watchlist:
        watchlist = [
            "HOOD", "TTWO", "LULU", "SOFI", "TSLA", "AMD", "CELH",
            "AMZN", "GOOGL", "META", "NVDA", "SHOP", "PYPL"
        ]
        save_watchlist(watchlist)
    watchlist = [t for t in watchlist if t not in BLOCKED_TICKERS]

    import threading as _threading
    _tg_ids_ref.extend(telegram_ids)
    _watchlist_ref.extend(watchlist)
    _threading.Thread(target=_cmd_listener_thread, daemon=True).start()
    log.info("Command listener thread started (polling every 3s)")

    log.info(f"Watchlist ({len(watchlist)}): {', '.join(watchlist)}")
    log.info(f"Telegram IDs: {len(telegram_ids)}")

    cooldowns, last_any = load_cooldowns()

    send_telegram(
        f"*Day Trader B🤖T v5.0 — ONLINE* 🟢\n"
        f"*Strategies:* ORB + VWAP Reversion\n"
        f"*RS Filter:* Active (outperform SPY required)\n"
        f"*Watchlist:* {len(watchlist)} tickers\n"
        f"*Min Score:* ORB={ORB_MIN_SCORE} | VWAP={VWAP_MIN_SCORE}\n"
        f"*Scan:* Every 5 min\n"
        f"*Blocked Tickers:* {', '.join(sorted(BLOCKED_TICKERS))}",
        telegram_ids
    )

    regime          = "neutral"
    regime_conf     = 0.5
    vix             = 20.0
    regime_last_upd = 0
    REGIME_INTERVAL = 1800  # Update regime every 30 min

    while True:
        try:
            # Telegram commands handled by background thread

            # Check trade outcomes periodically
            try:
                check_trade_outcomes()
            except Exception as e:
                log.error(f"check_trade_outcomes: {e}")

            # Weekly report
            if should_send_weekly_report():
                try:
                    send_telegram(generate_weekly_report(), telegram_ids)
                    log.info("Weekly report sent")
                except Exception as e:
                    log.error(f"Weekly report: {e}")

            if not is_market_hours():
                log.info("Market closed — sleeping 5 min")
                time.sleep(300)
                continue

            if is_blocked_hour():
                log.info(f"Blocked hour {datetime.now(ET).hour}:00 ET — skipping scan")
                time.sleep(300)
                continue

            # Update regime every 30 min
            now_ts = time.time()
            if now_ts - regime_last_upd > REGIME_INTERVAL:
                try:
                    spy_1h = download_with_retry("SPY", "60d", "1h")
                    regime, regime_conf = get_market_regime(spy_1h)
                    vix = get_vix()
                    regime_last_upd = now_ts
                    log.info(f"Regime: {regime.upper()} ({regime_conf:.0%}) | VIX: {vix:.1f}")
                except Exception as e:
                    log.error(f"Regime update: {e}")

            # Download SPY 5m once per scan cycle for RS calculations
            try:
                spy_5m = download_with_retry("SPY", "5d", "5m")
            except Exception:
                spy_5m = pd.DataFrame()

            if scanning_paused:
                time.sleep(10)
                continue
            log.info(f"--- Scanning {len(watchlist)} tickers | {regime.upper()} | VIX {vix:.1f} ---")
            cooldowns, last_any = scan(
                watchlist, telegram_ids,
                regime, regime_conf,
                spy_5m, vix,
                cooldowns, last_any
            )

        except Exception as e:
            log.error(f"Main loop error: {e}")

        time.sleep(SCAN_INTERVAL_SEC)

if __name__ == "__main__":
    main()
