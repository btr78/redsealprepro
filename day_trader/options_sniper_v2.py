"""
OPTIONS SNIPER B🤖T v2.0 — Professional Grade
================================================
Core strategy:
  - Buy directional calls or puts on high-conviction setups
  - IV Rank filter: only buy when ATM IV / HV30 < 1.3 (cheap premium)
  - Pre-earnings vol expansion: enter 7-10 days before, exit 2 days before
  - Technical direction: Daily + 4h momentum alignment required
  - Exit: 50% profit | -30% loss | 21 DTE | max 5 trading days
  - Options chain intelligence: PCR + max pain + sweep detection
  - Scan 4x per day: 10 AM, 12 PM, 2 PM, 3:40 PM ET
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
import json, os, re, time, logging, requests
from datetime import datetime, timedelta, time as dtime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import pytz
import atexit

load_dotenv()
ET = pytz.timezone('America/New_York')

# LOCK — prevent duplicate instances
_LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniper.lock")

def _acquire_lock():
    if os.path.exists(_LOCK):
        try:
            with open(_LOCK) as f:
                pid = int(f.read().strip())
            if pid != os.getpid():
                try:
                    os.kill(pid, 0)
                    print(f"[LOCK] Sniper already running (PID {pid}). Exiting.")
                    sys.exit(0)
                except (ProcessLookupError, PermissionError):
                    pass
        except Exception:
            pass
    with open(_LOCK, 'w') as f:
        f.write(str(os.getpid()))

def _release_lock():
    try:
        if os.path.exists(_LOCK):
            os.remove(_LOCK)
    except Exception:
        pass

_acquire_lock()
atexit.register(_release_lock)

# CONFIGURATION
BOT_TITLE         = "Options Sniper B🤖T v2.0"
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
ACCOUNT_BALANCE   = 10000.0

# Watchlist — liquid options stocks only
WATCHLIST = [
    "SPY", "QQQ",                                   # ETFs — always liquid
    "AAPL", "MSFT", "NVDA", "META", "AMZN", "GOOGL", # Mega caps
    "TSLA", "AMD", "SOFI", "CELH", "HOOD",           # Volatile movers
    "COIN", "PLTR", "UBER", "SHOP",                  # High-beta
]

# IV filter — only buy when options are reasonably priced
IV_RATIO_MAX      = 1.30   # Block if ATM IV > 1.3x HV30 (expensive premium)
IV_RATIO_IDEAL    = 0.85   # Below this = very cheap options (best buying conditions)

# Options parameters
DTE_MIN           = 21     # Minimum DTE at entry
DTE_MAX           = 45     # Maximum DTE at entry
DTE_EXIT_MIN      = 21     # Exit when DTE drops to this (time decay accelerates)
DELTA_TARGET      = 0.40   # Target delta — slightly OTM for leverage
DELTA_MIN         = 0.25   # Minimum delta (too OTM = lottery ticket)
DELTA_MAX         = 0.60   # Maximum delta (too deep ITM = expensive)

# Liquidity requirements
MIN_VOLUME        = 50     # Min option contract volume
MIN_OI            = 200    # Min open interest
MIN_SPREAD_PCT    = 0.20   # Max bid-ask spread as % of mid (20% max)

# Exit rules
TAKE_PROFIT_PCT   = 50.0   # Exit at 50% profit (Tastytrade rule)
STOP_LOSS_PCT     = 30.0   # Exit at -30% loss
MAX_HOLD_DAYS     = 5      # Max 5 trading days regardless

# Technical scoring
MIN_SCORE         = 45     # Minimum technical score (0-100)
MIN_SCORE_EARNINGS = 35    # Lower bar for pre-earnings plays (vol expansion)

# Pre-earnings vol expansion play
EARN_ENTRY_DAYS   = 10     # Enter at most 10 days before earnings
EARN_EXIT_DAYS    = 2      # Exit at least 2 days before earnings (avoid IV crush)
EARN_IV_RATIO_MAX = 1.20   # Don't enter if IV already elevated (>1.2x HV)

# Scan windows (ET)
SCAN_WINDOWS = [
    (dtime(10,  0), dtime(10, 15)),
    (dtime(12,  0), dtime(12, 15)),
    (dtime(14,  0), dtime(14, 15)),
    (dtime(15, 40), dtime(15, 52)),
]

# Files
TRADES_FILE   = "sniper_trades.json"
SETTINGS_FILE = "sniper_settings.json"
LOG_FILE      = "sniper_activity.log"

WEEKLY_REPORT_DAY  = 6   # Sunday
WEEKLY_REPORT_HOUR = 18

# Indicator params
RSI_PERIOD = 14
ATR_PERIOD = 14
EMA_FAST   = 9
EMA_SLOW   = 21
EMA_200    = 200
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIG   = 9
ADX_PERIOD = 14
BB_PERIOD  = 20

# LOGGING
def _strip(t): return re.sub(r'[^\x00-\x7F]+', '', t)

class _SafeFmt(logging.Formatter):
    def format(self, r): return _strip(super().format(r))

_fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
_fh.setFormatter(_SafeFmt('%(asctime)s [%(levelname)s] %(message)s'))
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_SafeFmt('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_fh, _ch])
log = logging.getLogger(__name__)

# UTILITIES
def flatten(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def download(ticker, period, interval, retries=3):
    for i in range(retries):
        try:
            df = yf.download(ticker, period=period, interval=interval,
                             progress=False, auto_adjust=True)
            if not df.empty:
                return flatten(df)
        except Exception as e:
            if i < retries - 1: time.sleep(2 ** i)
            else: log.error(f"Download failed {ticker}: {e}")
    return pd.DataFrame()

def is_market_hours():
    now = datetime.now(ET)
    return now.weekday() < 5 and dtime(9, 30) <= now.time() < dtime(16, 0)

def market_time():
    return datetime.now(ET).time()

def get_today():
    return datetime.now(ET).date()

def in_scan_window():
    mt = market_time()
    return any(start <= mt <= end for start, end in SCAN_WINDOWS)

# SETTINGS & TELEGRAM
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram_ids": []}

def send_telegram(message, ids):
    if not TELEGRAM_TOKEN or not ids:
        return
    for chat_id in ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": message[:4096], "parse_mode": "Markdown"},
                timeout=10
            )
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

def has_active_trade():
    data = load_trades()
    return any(t["status"] == "ACTIVE" for t in data["trades"])

def log_trade_entry(ticker, direction, score, strategy, entry_stock_px,
                    stop_px, target_px, contract, strike, expiration, dte,
                    entry_option_px, iv_ratio, earn_play=False):
    data = load_trades()
    trade = {
        "id": len(data["trades"]) + 1,
        "ticker": ticker,
        "direction": direction,         # CALL or PUT
        "score": score,
        "strategy": strategy,           # TECHNICAL or EARNINGS_VOL
        "entry_stock_px": round(entry_stock_px, 4),
        "stop_px": round(stop_px, 4),
        "target_px": round(target_px, 4),
        "contract": contract,
        "strike": strike,
        "expiration": expiration,
        "dte_at_entry": dte,
        "entry_option_px": round(entry_option_px, 4),
        "entry_cost": round(entry_option_px * 100, 2),  # 1 contract = 100 shares
        "iv_ratio": round(iv_ratio, 2),
        "earn_play": earn_play,
        "timestamp": datetime.now(ET).isoformat(),
        "status": "ACTIVE",
        "exit_price": None,
        "exit_reason": None,
        "pnl_pct": None,
        "pnl_dollar": None,
        "days_held": 0
    }
    data["trades"].append(trade)
    data["stats"]["total"] += 1
    data["stats"]["pending"] += 1
    save_trades(data)
    log.info(f"Trade opened: {ticker} {direction} {contract} @ ${entry_option_px:.2f}")
    return trade

def close_trade(trade_id, exit_px, reason):
    data = load_trades()
    for t in data["trades"]:
        if t["id"] == trade_id and t["status"] == "ACTIVE":
            entry_px = t["entry_option_px"]
            pnl_pct  = (exit_px - entry_px) / entry_px * 100 if entry_px > 0 else 0
            pnl_dol  = (exit_px - entry_px) * 100  # 1 contract
            t["status"]     = "WIN" if pnl_pct > 0 else "LOSS"
            t["exit_price"] = round(exit_px, 4)
            t["exit_reason"] = reason
            t["pnl_pct"]    = round(pnl_pct, 2)
            t["pnl_dollar"] = round(pnl_dol, 2)
            entry_ts = datetime.fromisoformat(t["timestamp"]).replace(tzinfo=None)
            t["days_held"] = (datetime.now() - entry_ts).days
            data["stats"]["pending"] -= 1
            if t["status"] == "WIN":
                data["stats"]["wins"] += 1
            else:
                data["stats"]["losses"] += 1
            save_trades(data)
            log.info(f"Trade closed: {t['ticker']} {reason} {pnl_pct:+.1f}% (${pnl_dol:+.0f})")
            return t
    return None

def get_overall_stats():
    data = load_trades()
    done = [t for t in data["trades"] if t["status"] in ("WIN", "LOSS")]
    if not done:
        return {"total": data["stats"]["total"], "wins": 0, "losses": 0,
                "win_rate": 0, "avg_pnl_pct": 0, "total_pnl_dol": 0,
                "pending": data["stats"]["pending"]}
    wins = [t for t in done if t["status"] == "WIN"]
    pnl_pcts = [t.get("pnl_pct") or 0 for t in done]
    pnl_dols = [t.get("pnl_dollar") or 0 for t in done]
    return {
        "total": data["stats"]["total"],
        "wins": len(wins), "losses": len(done) - len(wins),
        "win_rate": len(wins) / len(done) * 100,
        "avg_pnl_pct": sum(pnl_pcts) / len(pnl_pcts),
        "total_pnl_dol": sum(pnl_dols),
        "pending": data["stats"]["pending"]
    }

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
    f = compute_ema(series, MACD_FAST)
    s = compute_ema(series, MACD_SLOW)
    m = f - s
    return m, compute_ema(m, MACD_SIG)

def compute_adx(df, period=14):
    h, l, c = df['High'], df['Low'], df['Close']
    plus_dm  = h.diff().clip(lower=0)
    minus_dm = (-l.diff()).clip(lower=0)
    # Zero out where the other direction is larger
    plus_dm  = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    atr = compute_atr(df, period)
    pdi = 100 * plus_dm.rolling(period).mean()  / atr.replace(0, np.nan)
    mdi = 100 * minus_dm.rolling(period).mean() / atr.replace(0, np.nan)
    dx  = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan))
    return dx.rolling(period).mean(), pdi, mdi

def compute_bb(series, period=20, std=2.0):
    sma = series.rolling(period).mean()
    s   = series.rolling(period).std()
    return sma + s * std, sma, sma - s * std

def add_indicators(df):
    if len(df) < 30:
        return df
    df = df.copy()
    df['RSI']    = compute_rsi(df['Close'])
    df['ATR']    = compute_atr(df)
    df['EMA9']   = compute_ema(df['Close'], EMA_FAST)
    df['EMA21']  = compute_ema(df['Close'], EMA_SLOW)
    df['EMA200'] = compute_ema(df['Close'], EMA_200)
    df['MACD'], df['MACDSig'] = compute_macd(df['Close'])
    df['MACDHist'] = df['MACD'] - df['MACDSig']
    df['ADX'], df['PlusDI'], df['MinusDI'] = compute_adx(df)
    df['BBU'], df['BBM'], df['BBL'] = compute_bb(df['Close'])
    df['VolSMA']  = df['Volume'].rolling(20).mean()
    df['VolMult'] = df['Volume'] / df['VolSMA'].replace(0, np.nan)
    return df

# IV RANK — compare ATM implied vol to 30-day historical vol
def get_iv_rank(ticker):
    """
    Returns (iv_ratio, label) where iv_ratio = ATM_IV / HV30.
    < 0.85 = LOW (great for buying)
    0.85-1.30 = NORMAL
    > 1.30 = HIGH (IV crush risk)
    """
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="2d")
        if hist.empty:
            return 1.0, "UNKNOWN"
        current_price = float(hist['Close'].iloc[-1])

        expirations = stock.options
        if not expirations:
            return 1.0, "UNKNOWN"

        # Find expiration closest to 30-45 DTE
        today  = get_today()
        target_exp = None
        min_dist   = 999
        for exp_str in expirations:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if DTE_MIN <= dte <= DTE_MAX + 10:
                    dist = abs(dte - 35)
                    if dist < min_dist:
                        min_dist = dist
                        target_exp = exp_str
            except Exception:
                continue

        if not target_exp:
            target_exp = expirations[0]

        chain = stock.option_chain(target_exp)
        calls = chain.calls.copy()
        if calls.empty:
            return 1.0, "UNKNOWN"

        calls['distance'] = (calls['strike'] - current_price).abs()
        atm_row = calls.loc[calls['distance'].idxmin()]
        atm_iv  = float(atm_row['impliedVolatility']) if pd.notna(atm_row.get('impliedVolatility')) else 0
        if atm_iv <= 0:
            return 1.0, "UNKNOWN"

        # 30-day historical volatility
        df_d = download(ticker, "90d", "1d")
        if df_d.empty or len(df_d) < 30:
            return 1.0, "UNKNOWN"
        rets = df_d['Close'].pct_change().dropna()
        hv30 = float(rets.tail(30).std() * np.sqrt(252))
        if hv30 <= 0:
            return 1.0, "UNKNOWN"

        ratio = round(atm_iv / hv30, 2)
        if ratio < 0.85:    label = "LOW"
        elif ratio < 1.30:  label = "NORMAL"
        elif ratio < 1.70:  label = "HIGH"
        else:               label = "EXTREME"

        log.info(f"{ticker} IV Rank: ATM_IV={atm_iv:.1%} HV30={hv30:.1%} ratio={ratio:.2f} [{label}]")
        return ratio, label

    except Exception as e:
        log.debug(f"IV rank error {ticker}: {e}")
        return 1.0, "UNKNOWN"

# VIX REGIME
def get_vix():
    try:
        df = download("^VIX", "2d", "1d")
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except Exception:
        pass
    return 20.0

def vix_regime(vix):
    if vix < 15:   return "LOW",     +5
    elif vix < 25: return "NORMAL",   0
    elif vix < 35: return "HIGH",    -8
    else:          return "EXTREME", -20

# EARNINGS CALENDAR
def get_earnings_days_away(ticker):
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return None
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
            return None
        return (earn_date.date() - get_today()).days
    except Exception:
        return None

# PUT/CALL RATIO — institutional sentiment
def get_pcr(ticker):
    try:
        stock = yf.Ticker(ticker)
        exps  = stock.options
        if not exps:
            return 1.0, "NEUTRAL", 0

        call_oi, put_oi = 0, 0
        for exp in exps[:3]:
            chain = stock.option_chain(exp)
            call_oi += chain.calls['openInterest'].fillna(0).sum()
            put_oi  += chain.puts['openInterest'].fillna(0).sum()

        if call_oi == 0:
            return 1.0, "NEUTRAL", 0

        pcr = round(put_oi / call_oi, 2)
        if pcr < 0.50:   return pcr, "EXTREME_GREED", -5
        elif pcr < 0.70: return pcr, "BULLISH",       +6
        elif pcr <= 1.00: return pcr, "NEUTRAL",        0
        elif pcr <= 1.30: return pcr, "BEARISH",       +6
        else:            return pcr, "EXTREME_FEAR",   -5
    except Exception as e:
        log.debug(f"PCR error {ticker}: {e}")
    return 1.0, "NEUTRAL", 0

# MAX PAIN
def get_max_pain(ticker):
    try:
        stock = yf.Ticker(ticker)
        exps  = stock.options
        if not exps:
            return None, None

        today = get_today()
        target_exp = None
        for exp_str in exps:
            dte = (datetime.strptime(exp_str, "%Y-%m-%d").date() - today).days
            if DTE_MIN <= dte <= DTE_MAX:
                target_exp = exp_str
                break
        if not target_exp:
            return None, None

        chain  = stock.option_chain(target_exp)
        calls  = chain.calls[['strike', 'openInterest']].rename(columns={'openInterest': 'c_oi'})
        puts   = chain.puts[['strike', 'openInterest']].rename(columns={'openInterest': 'p_oi'})
        merged = pd.merge(calls, puts, on='strike', how='outer').fillna(0)
        strikes = merged['strike'].values

        min_pain, max_pain_strike = float('inf'), None
        for s in strikes:
            c_pain = sum(max(0, s - k) * merged.loc[merged['strike'] == k, 'c_oi'].values[0] for k in strikes)
            p_pain = sum(max(0, k - s) * merged.loc[merged['strike'] == k, 'p_oi'].values[0] for k in strikes)
            total  = c_pain + p_pain
            if total < min_pain:
                min_pain = total
                max_pain_strike = s

        hist = stock.history(period="1d")
        curr_px = float(hist['Close'].iloc[-1]) if not hist.empty else None
        return max_pain_strike, curr_px
    except Exception as e:
        log.debug(f"Max pain error {ticker}: {e}")
    return None, None

# SWEEP DETECTION — unusual options activity
def detect_sweeps(ticker, direction):
    try:
        stock = yf.Ticker(ticker)
        exps  = stock.options
        if not exps:
            return False, 0

        today = get_today()
        score = 0
        for exp_str in exps[:2]:
            dte = (datetime.strptime(exp_str, "%Y-%m-%d").date() - today).days
            if not (DTE_MIN - 5 <= dte <= DTE_MAX + 10):
                continue
            chain   = stock.option_chain(exp_str)
            options = chain.calls if direction == "CALL" else chain.puts
            for _, row in options.iterrows():
                bid  = float(row.get('bid', 0) or 0)
                ask  = float(row.get('ask', 0) or 0)
                last = float(row.get('lastPrice', 0) or 0)
                vol  = int(row.get('volume', 0) or 0)
                oi   = int(row.get('openInterest', 1) or 1)
                if ask > 0 and last >= ask * 0.97 and vol >= 50:
                    score += 3  # Buying at ask = urgency
                vol_oi = vol / max(oi, 1)
                if vol_oi >= 3.0 and vol >= 100:
                    score += 4  # Vol/OI spike
                elif vol_oi >= 2.0 and vol >= 50:
                    score += 2

        return score >= 5, score
    except Exception as e:
        log.debug(f"Sweep error {ticker}: {e}")
    return False, 0

# NEWS SENTIMENT
BULL_WORDS = ['upgrade','beat','beats','growth','record','bullish','buy','strong',
              'profit','raises','outperform','surge','soar','rally','boost','partnership']
BEAR_WORDS = ['downgrade','miss','misses','layoff','sec','lawsuit','bearish','sell',
              'weak','loss','cuts','underperform','drop','fall','decline','warning']

def get_news_sentiment(ticker):
    try:
        news = yf.Ticker(ticker).news
        if not news:
            return 0, "NEUTRAL"
        score = 0
        for article in news[:10]:
            title = (article.get('title') or '').lower()
            score += sum(1 for w in BULL_WORDS if w in title)
            score -= sum(1 for w in BEAR_WORDS if w in title)
        score = max(-10, min(10, score))
        if score >= 3:   return score, "BULLISH"
        elif score <= -3: return score, "BEARISH"
        return score, "NEUTRAL"
    except Exception:
        return 0, "NEUTRAL"

# TECHNICAL SCORING — daily + 4h alignment
def technical_score(ticker):
    """
    Returns (direction, score, details) or (None, 0, {})
    direction = "CALL" (bullish) or "PUT" (bearish)
    score = 0-100
    """
    try:
        df_d = download(ticker, "6mo", "1d")
        if df_d.empty or len(df_d) < 50:
            return None, 0, {}
        df_d = add_indicators(df_d)
        curr = df_d.iloc[-1]
        prev = df_d.iloc[-2]
    except Exception as e:
        log.error(f"Daily data error {ticker}: {e}")
        return None, 0, {}

    # 4-hour data for confirmation
    curr_4h = None
    try:
        df_4h = download(ticker, "60d", "1h")
        if not df_4h.empty and len(df_4h) >= 50:
            df_4h = add_indicators(df_4h)
            curr_4h = df_4h.iloc[-1]
    except Exception as e:
        log.debug(f"4h data error {ticker}: {e}")

    bull, bear = 0, 0
    details = []

    close  = float(curr['Close'])
    ema9   = float(curr.get('EMA9')    or close)
    ema21  = float(curr.get('EMA21')   or close)
    ema200 = float(curr.get('EMA200')  or close)
    rsi    = float(curr.get('RSI')     or 50)
    macd   = float(curr.get('MACD')    or 0)
    sig    = float(curr.get('MACDSig') or 0)
    hist_v = float(curr.get('MACDHist') or 0)
    prev_hist = float(prev.get('MACDHist') or 0)
    adx    = float(curr.get('ADX')     or 0)
    pdi    = float(curr.get('PlusDI')  or 0)
    mdi    = float(curr.get('MinusDI') or 0)
    vol_m  = float(curr.get('VolMult') or 1)
    bbu    = float(curr.get('BBU')     or 0)
    bbl    = float(curr.get('BBL')     or 0)

    # 1. EMA stack (primary trend — most important)
    if ema9 > ema21 > ema200 and close > ema200:
        bull += 20; details.append("EMA stack bullish")
    elif ema9 < ema21 < ema200 and close < ema200:
        bear += 20; details.append("EMA stack bearish")
    elif close > ema200:
        bull += 10; details.append("Above EMA200")
    else:
        bear += 10; details.append("Below EMA200")

    # 2. ADX trend strength
    if adx > 30:
        if pdi > mdi:
            bull += 10; details.append(f"Strong bull ADX={adx:.0f}")
        else:
            bear += 10; details.append(f"Strong bear ADX={adx:.0f}")
    elif adx > 20:
        if pdi > mdi:
            bull += 5
        else:
            bear += 5

    # 3. MACD crossover
    prev_macd = float(prev.get('MACD', 0) or 0)
    prev_sig  = float(prev.get('MACDSig', 0) or 0)
    if macd > sig and prev_macd <= prev_sig:
        bull += 12; details.append("MACD bullish cross")
    elif macd < sig and prev_macd >= prev_sig:
        bear += 12; details.append("MACD bearish cross")
    elif macd > sig:
        bull += 5
    else:
        bear += 5

    # MACD histogram expanding
    if hist_v > 0 and hist_v > prev_hist:
        bull += 5; details.append("MACD hist expanding bull")
    elif hist_v < 0 and hist_v < prev_hist:
        bear += 5; details.append("MACD hist expanding bear")

    # 4. RSI
    if rsi < 30:
        bull += 10; details.append(f"RSI oversold {rsi:.0f}")
    elif rsi > 70:
        bear += 10; details.append(f"RSI overbought {rsi:.0f}")
    elif 50 < rsi < 70:
        bull += 5
    elif 30 < rsi < 50:
        bear += 5

    # 5. Bollinger Band position
    if close > bbu and bbu > 0:
        bear += 5; details.append("Above BB upper — overextended")
    elif close < bbl and bbl > 0:
        bull += 5; details.append("At BB lower — potential bounce")

    # 6. Volume confirmation
    if vol_m >= 1.5:
        if close > float(prev['Close']):
            bull += 5; details.append(f"Bull vol surge {vol_m:.1f}x")
        else:
            bear += 5; details.append(f"Bear vol surge {vol_m:.1f}x")

    # 7. 4h confirmation (alignment bonus)
    if curr_4h is not None:
        c4h_ema9  = float(curr_4h.get('EMA9')  or 0)
        c4h_ema21 = float(curr_4h.get('EMA21') or 0)
        c4h_close = float(curr_4h['Close'])
        c4h_macd  = float(curr_4h.get('MACD')    or 0)
        c4h_sig   = float(curr_4h.get('MACDSig') or 0)
        if bull > bear:  # Looking for CALL
            if c4h_close > c4h_ema9 > c4h_ema21:
                bull += 10; details.append("4h bullish aligned")
            elif c4h_macd > c4h_sig:
                bull += 5
        else:  # Looking for PUT
            if c4h_close < c4h_ema9 < c4h_ema21:
                bear += 10; details.append("4h bearish aligned")
            elif c4h_macd < c4h_sig:
                bear += 5

    total = bull + bear
    if total == 0:
        return None, 0, {}

    if bull > bear:
        direction = "CALL"
        raw = bull
        dom_pct = bull / total
    else:
        direction = "PUT"
        raw = bear
        dom_pct = bear / total

    # Need at least 60% dominance
    if dom_pct < 0.60:
        log.info(f"{ticker} no dominant direction bull={bull} bear={bear}")
        return None, 0, {}

    # Normalize to 0-100
    score = min(100, int(raw * 100 / 85))

    return direction, score, {
        "bull": bull, "bear": bear, "details": details,
        "rsi": rsi, "adx": adx, "vol_mult": vol_m
    }

# OPTION CONTRACT SELECTOR
def find_best_contract(ticker, direction):
    """
    Find the best contract: target delta ~0.40, DTE 21-45.
    Returns contract dict or None.
    """
    try:
        stock = yf.Ticker(ticker)
        exps  = stock.options
        if not exps:
            return None

        hist = stock.history(period="1d")
        if hist.empty:
            return None
        current_price = float(hist['Close'].iloc[-1])

        today  = get_today()
        best   = None
        best_score = 999

        for exp_str in exps:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if not (DTE_MIN <= dte <= DTE_MAX):
                    continue

                chain   = stock.option_chain(exp_str)
                options = chain.calls if direction == "CALL" else chain.puts

                for _, row in options.iterrows():
                    delta = float(row.get('delta', 0) or 0)
                    if delta == 0:
                        # Estimate delta from strike distance if not provided
                        strike  = float(row['strike'])
                        distance = (strike - current_price) / current_price
                        delta = max(0.05, 0.50 - distance * 3) if direction == "CALL" else \
                                max(0.05, 0.50 + distance * 3)

                    if not (DELTA_MIN <= abs(delta) <= DELTA_MAX):
                        continue

                    vol = int(row.get('volume', 0) or 0)
                    oi  = int(row.get('openInterest', 0) or 0)
                    if vol < MIN_VOLUME or oi < MIN_OI:
                        continue

                    bid  = float(row.get('bid', 0) or 0)
                    ask  = float(row.get('ask', 0) or 0)
                    mid  = (bid + ask) / 2 if ask > 0 else 0
                    if mid <= 0:
                        continue
                    spread_pct = (ask - bid) / mid if mid > 0 else 1.0
                    if spread_pct > MIN_SPREAD_PCT:
                        continue

                    # Score: closeness to target delta + DTE closeness to 35
                    delta_dist = abs(abs(delta) - DELTA_TARGET)
                    dte_dist   = abs(dte - 35) / 35
                    total_dist = delta_dist + dte_dist * 0.5

                    if total_dist < best_score:
                        best_score = total_dist
                        best = {
                            "contract":   str(row.get('contractSymbol', '')),
                            "strike":     float(row['strike']),
                            "expiration": exp_str,
                            "dte":        dte,
                            "delta":      round(abs(delta), 2),
                            "bid":        bid,
                            "ask":        ask,
                            "mid":        round(mid, 2),
                            "last":       float(row.get('lastPrice', mid) or mid),
                            "volume":     vol,
                            "oi":         oi,
                            "spread_pct": round(spread_pct * 100, 1),
                            "iv":         float(row.get('impliedVolatility', 0) or 0)
                        }
            except Exception as e:
                log.debug(f"Chain error {ticker} {exp_str}: {e}")
                continue

        if best:
            log.info(f"{ticker} best contract: {best['contract']} "
                     f"strike={best['strike']} DTE={best['dte']} delta={best['delta']:.2f}")
        return best
    except Exception as e:
        log.error(f"find_best_contract error {ticker}: {e}")
    return None

# ACTIVE TRADE MONITOR — check TP / SL / DTE / days held
def monitor_active_trades(telegram_ids):
    data = load_trades()
    active = [t for t in data["trades"] if t["status"] == "ACTIVE"]
    if not active:
        return

    for trade in active:
        ticker    = trade["ticker"]
        direction = trade["direction"]
        entry_px  = trade["entry_option_px"]
        contract  = trade["contract"]
        expiration= trade["expiration"]

        try:
            # Check DTE
            exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
            dte_now  = (exp_date - get_today()).days

            # Days held
            ts = datetime.fromisoformat(trade["timestamp"]).replace(tzinfo=None)
            days_held = (datetime.now() - ts).days

            # Force exit conditions (before trying to get current price)
            force_exit_reason = None
            if dte_now <= DTE_EXIT_MIN:
                force_exit_reason = f"DTE={dte_now} — TIME EXIT"
            elif days_held >= MAX_HOLD_DAYS:
                force_exit_reason = f"Max hold days ({MAX_HOLD_DAYS}d) reached"

            # Check if it's a pre-earnings play and earnings approaching
            if trade.get("earn_play"):
                earn_days = get_earnings_days_away(ticker)
                if earn_days is not None and earn_days <= EARN_EXIT_DAYS:
                    force_exit_reason = f"EARNINGS in {earn_days}d — Exit before IV crush"

            # Get current option price from chain
            curr_option_px = None
            try:
                stock = yf.Ticker(ticker)
                chain = stock.option_chain(expiration)
                opts  = chain.calls if direction == "CALL" else chain.puts
                row   = opts[opts['contractSymbol'] == contract]
                if not row.empty:
                    bid  = float(row.iloc[0].get('bid', 0) or 0)
                    ask  = float(row.iloc[0].get('ask', 0) or 0)
                    curr_option_px = (bid + ask) / 2 if ask > 0 else float(row.iloc[0].get('lastPrice', 0) or 0)
            except Exception:
                pass

            if curr_option_px is None or curr_option_px <= 0:
                # Can't get price, check by underlying stock price vs stop/target
                try:
                    stock_hist = yf.Ticker(ticker).history(period="1d")
                    if not stock_hist.empty:
                        curr_stock = float(stock_hist['Close'].iloc[-1])
                        entry_stock = trade["entry_stock_px"]
                        if direction == "CALL":
                            if curr_stock >= trade["target_px"]:
                                curr_option_px = entry_px * 1.5  # Assume ~50% profit
                            elif curr_stock <= trade["stop_px"]:
                                curr_option_px = entry_px * 0.7  # Assume ~30% loss
                        else:
                            if curr_stock <= trade["target_px"]:
                                curr_option_px = entry_px * 1.5
                            elif curr_stock >= trade["stop_px"]:
                                curr_option_px = entry_px * 0.7
                except Exception:
                    pass

            if curr_option_px is None:
                if force_exit_reason:
                    closed = close_trade(trade["id"], entry_px, force_exit_reason)
                    if closed:
                        _send_exit_alert(closed, telegram_ids, force_exit_reason, entry_px)
                continue

            pnl_pct = (curr_option_px - entry_px) / entry_px * 100

            # Exit conditions
            exit_reason = None
            if force_exit_reason:
                exit_reason = force_exit_reason
            elif pnl_pct >= TAKE_PROFIT_PCT:
                exit_reason = f"TAKE PROFIT +{pnl_pct:.1f}%"
            elif pnl_pct <= -STOP_LOSS_PCT:
                exit_reason = f"STOP LOSS {pnl_pct:.1f}%"

            # Heartbeat log
            log.info(f"ACTIVE {ticker} {direction} {contract}: "
                     f"P&L={pnl_pct:+.1f}% DTE={dte_now} days={days_held}")

            if exit_reason:
                closed = close_trade(trade["id"], curr_option_px, exit_reason)
                if closed:
                    _send_exit_alert(closed, telegram_ids, exit_reason, curr_option_px)

        except Exception as e:
            log.error(f"Monitor error {ticker}: {e}")

def _send_exit_alert(trade, telegram_ids, reason, exit_px):
    pnl_pct = trade.get("pnl_pct", 0)
    pnl_dol = trade.get("pnl_dollar", 0)
    status  = "WIN 🟢" if pnl_pct > 0 else "LOSS 🔴"
    msg = (
        f"*Options Sniper B🤖T v2.0 — EXIT*\n"
        f"*TICKER:* {trade['ticker']}\n"
        f"*DIRECTION:* {trade['direction']}\n"
        f"*CONTRACT:* {trade.get('contract','?')}\n"
        f"*RESULT:* {status}\n"
        f"*EXIT REASON:* {reason}\n"
        f"*ENTRY:* ${trade['entry_option_px']:.2f}\n"
        f"*EXIT:* ${exit_px:.2f}\n"
        f"*P&L:* {pnl_pct:+.1f}% (${pnl_dol:+.0f})\n"
        f"*DAYS HELD:* {trade.get('days_held',0)}"
    )
    send_telegram(msg, telegram_ids)

# SIGNAL ALERT FORMATTER
def format_entry_alert(ticker, direction, score, tech_details, contract, iv_ratio, iv_label,
                        vix, vix_label, pcr, pcr_signal, max_pain, curr_px,
                        sweep, news_score, news_signal, earn_days, strategy):
    grade = "A+ 🌟" if score >= 85 else "A 🟢" if score >= 75 else "B+ 🟡" if score >= 65 else "B 🟠"
    dir_emoji = "📈 CALL" if direction == "CALL" else "📉 PUT"
    iv_emoji  = "🟢" if iv_label == "LOW" else "🟡" if iv_label == "NORMAL" else "🔴"
    earn_line = ""
    if earn_days is not None and earn_days > 0:
        earn_line = f"\n*EARNINGS:* {earn_days}d away"
        if strategy == "EARNINGS_VOL":
            earn_line += " — VOL EXPANSION PLAY"

    sweep_line = "\n*SWEEPS:* 🔥 UNUSUAL ACTIVITY DETECTED" if sweep else ""
    news_emoji = "📗" if news_signal == "BULLISH" else "📕" if news_signal == "BEARISH" else ""
    news_line  = f"\n*NEWS:* {news_emoji} {news_signal} (score {news_score:+d})" if news_score != 0 else ""

    mp_line = ""
    if max_pain and curr_px:
        mp_dist = (max_pain - curr_px) / curr_px * 100
        mp_line = f"\n*MAX PAIN:* ${max_pain:.2f} ({mp_dist:+.1f}% from current)"

    pcr_emoji = "🟢" if pcr_signal in ("BULLISH","EXTREME_FEAR") else "🔴" if pcr_signal in ("BEARISH","EXTREME_GREED") else "⚪"

    # Stop and target from stock price
    atr_est = curr_px * 0.02  # rough ATR estimate
    if direction == "CALL":
        stop_px   = curr_px - atr_est * 2
        target_px = curr_px + atr_est * 3
    else:
        stop_px   = curr_px + atr_est * 2
        target_px = curr_px - atr_est * 3

    msg = (
        f"*Options Sniper B🤖T v2.0*\n"
        f"*TICKER:* {ticker}\n"
        f"*SIGNAL:* {dir_emoji}\n"
        f"*STRATEGY:* {strategy.replace('_',' ')}\n"
        f"*SCORE:* {score}/100 — {grade}\n"
        f"*STOCK PRICE:* ${curr_px:.2f}\n"
        f"*STOCK STOP:* ${stop_px:.2f}\n"
        f"*STOCK TARGET:* ${target_px:.2f}\n"
        f"*CONTRACT:* {contract['contract']}\n"
        f"*STRIKE:* ${contract['strike']:.2f}\n"
        f"*EXPIRY:* {contract['expiration']} ({contract['dte']}d)\n"
        f"*DELTA:* {contract['delta']:.2f}\n"
        f"*BID/ASK:* ${contract['bid']:.2f} / ${contract['ask']:.2f}\n"
        f"*MID PRICE:* ${contract['mid']:.2f} (cost: ${contract['mid']*100:.0f})\n"
        f"*SPREAD:* {contract['spread_pct']:.1f}%\n"
        f"*IV RATIO:* {iv_emoji} {iv_ratio:.2f}x HV30 [{iv_label}]\n"
        f"*VIX:* {vix:.1f} [{vix_label}]\n"
        f"*PUT/CALL:* {pcr_emoji} {pcr:.2f} [{pcr_signal}]"
        f"{mp_line}"
        f"{sweep_line}"
        f"{news_line}"
        f"{earn_line}\n"
        f"*EXIT RULES:* +50% TP | -30% SL | 21 DTE | 5 days max\n"
        f"_1 contract = ${contract['mid']*100:.0f} cost. Not financial advice._"
    )
    return msg[:4096]

# WEEKLY REPORT
last_weekly = None

def should_weekly():
    global last_weekly
    now = datetime.now(ET)
    if now.weekday() != WEEKLY_REPORT_DAY or now.hour != WEEKLY_REPORT_HOUR:
        return False
    if last_weekly and (now - last_weekly).total_seconds() < 82800:
        return False
    return True

def weekly_report():
    global last_weekly
    data  = load_trades()
    stats = get_overall_stats()
    week_ago = datetime.now(ET) - timedelta(days=7)

    weekly_done = [t for t in data["trades"]
                   if t["status"] in ("WIN","LOSS") and
                   datetime.fromisoformat(t["timestamp"]).replace(tzinfo=None) > week_ago.replace(tzinfo=None)]
    w_wins = len([t for t in weekly_done if t["status"] == "WIN"])
    w_pnl  = sum(t.get("pnl_dollar") or 0 for t in weekly_done)
    w_wr   = w_wins / len(weekly_done) * 100 if weekly_done else 0

    earn_trades = [t for t in data["trades"] if t.get("earn_play") and t["status"] in ("WIN","LOSS")]
    tech_trades = [t for t in data["trades"] if not t.get("earn_play") and t["status"] in ("WIN","LOSS")]
    earn_wr = len([t for t in earn_trades if t["status"]=="WIN"]) / len(earn_trades)*100 if earn_trades else 0
    tech_wr = len([t for t in tech_trades if t["status"]=="WIN"]) / len(tech_trades)*100 if tech_trades else 0

    wr_emoji = "📈" if stats["win_rate"] >= 55 else "📉"
    w_emoji  = "🟢" if w_pnl >= 0 else "🔴"

    active = [t for t in data["trades"] if t["status"] == "ACTIVE"]
    active_str = ""
    for t in active:
        active_str += f"\n  {t['ticker']} {t['direction']} {t['contract']}"

    report = (
        f"*Options Sniper B🤖T v2.0 — WEEKLY REPORT*\n"
        f"*📅 THIS WEEK*\n"
        f"Trades: {len(weekly_done)} | Wins: {w_wins} | Losses: {len(weekly_done)-w_wins}\n"
        f"Win Rate: {w_wr:.1f}%\n"
        f"P&L: {w_emoji} ${w_pnl:+.0f}\n"
        f"*{wr_emoji} ALL TIME*\n"
        f"Total: {stats['total']} | Pending: {stats['pending']}\n"
        f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        f"Win Rate: {stats['win_rate']:.1f}%\n"
        f"Avg P&L: {stats['avg_pnl_pct']:+.1f}%\n"
        f"Total P&L: ${stats['total_pnl_dol']:+.0f}\n"
        f"*📊 BY STRATEGY*\n"
        f"Technical: {tech_wr:.1f}% WR ({len(tech_trades)} trades)\n"
        f"Earnings Vol: {earn_wr:.1f}% WR ({len(earn_trades)} trades)\n"
    )
    if active:
        report += f"\n*ACTIVE TRADES:*{active_str}\n"
    last_weekly = datetime.now(ET)
    return report[:4096]

# MAIN SCAN
def run_scan(telegram_ids, vix):
    log.info("=" * 50)
    log.info(f"Running scan — {datetime.now(ET).strftime('%H:%M ET')} | VIX={vix:.1f}")
    log.info("=" * 50)

    # Only 1 active trade at a time
    if has_active_trade():
        log.info("Active trade in progress — skipping new entries")
        return

    vix_label, vix_mod = vix_regime(vix)

    for ticker in WATCHLIST:
        try:
            log.info(f"--- Analyzing {ticker} ---")

            # Get IV rank first — primary gate
            iv_ratio, iv_label = get_iv_rank(ticker)

            # Earnings check
            earn_days = get_earnings_days_away(ticker)
            is_earn_play = False
            min_score    = MIN_SCORE

            if earn_days is not None:
                if earn_days <= 0:
                    log.info(f"{ticker} earnings today/past — skip")
                    continue
                if earn_days <= EARN_EXIT_DAYS:
                    log.info(f"{ticker} earnings in {earn_days}d — too close, skip")
                    continue
                if earn_days <= EARN_ENTRY_DAYS:
                    # Pre-earnings vol expansion play
                    if iv_ratio <= EARN_IV_RATIO_MAX:
                        is_earn_play = True
                        min_score = MIN_SCORE_EARNINGS
                        log.info(f"{ticker} EARNINGS PLAY candidate — {earn_days}d away iv_ratio={iv_ratio:.2f}")
                    else:
                        log.info(f"{ticker} earnings {earn_days}d but IV already elevated ({iv_ratio:.2f}) — skip")
                        continue

            # IV filter for regular technical trades
            if not is_earn_play:
                if iv_ratio > IV_RATIO_MAX:
                    log.info(f"{ticker} IV too high ({iv_ratio:.2f}) — skip")
                    continue

            # Technical direction scoring
            direction, score, tech_det = technical_score(ticker)
            if direction is None or score < min_score:
                log.info(f"{ticker} score={score} direction={direction} — below threshold")
                continue

            score += vix_mod  # VIX regime adjustment
            score = max(0, min(100, score))

            # Options chain intelligence
            pcr, pcr_signal, pcr_mod = get_pcr(ticker)
            max_pain_strike, curr_px = get_max_pain(ticker)
            sweep, sweep_score = detect_sweeps(ticker, direction)
            news_score, news_signal = get_news_sentiment(ticker)

            # Max pain confirmation — if max pain is in our direction, bonus
            mp_confirms = False
            if max_pain_strike and curr_px:
                if direction == "CALL" and max_pain_strike > curr_px:
                    score += 5; mp_confirms = True
                elif direction == "PUT" and max_pain_strike < curr_px:
                    score += 5; mp_confirms = True

            # PCR score adjustment
            if (direction == "CALL" and pcr_signal in ("BULLISH", "EXTREME_FEAR")) or \
               (direction == "PUT"  and pcr_signal in ("BEARISH", "EXTREME_GREED")):
                score += abs(pcr_mod)

            # Sweep detected — strong signal
            if sweep:
                score += 8
                log.info(f"{ticker} SWEEP DETECTED score={sweep_score}")

            # News alignment
            if (direction == "CALL" and news_signal == "BULLISH") or \
               (direction == "PUT"  and news_signal == "BEARISH"):
                score += 3

            score = max(0, min(100, score))
            log.info(f"{ticker} final score={score}/100 direction={direction} iv={iv_ratio:.2f}")

            if score < min_score:
                log.info(f"{ticker} score {score} still below {min_score} after adjustments — skip")
                continue

            # Find best contract
            contract = find_best_contract(ticker, direction)
            if contract is None:
                log.info(f"{ticker} no suitable contract found — skip")
                continue

            entry_option_px = contract['mid']
            if entry_option_px <= 0:
                continue

            # Stock price for stop/target
            if curr_px is None:
                try:
                    h = yf.Ticker(ticker).history(period="1d")
                    curr_px = float(h['Close'].iloc[-1]) if not h.empty else 0
                except Exception:
                    curr_px = 0

            atr_est = curr_px * 0.02
            if direction == "CALL":
                stop_px   = curr_px - atr_est * 2
                target_px = curr_px + atr_est * 3
            else:
                stop_px   = curr_px + atr_est * 2
                target_px = curr_px - atr_est * 3

            strategy_name = "EARNINGS_VOL" if is_earn_play else "TECHNICAL"

            # Send alert
            msg = format_entry_alert(
                ticker, direction, score, tech_det, contract,
                iv_ratio, iv_label, vix, vix_label,
                pcr, pcr_signal, max_pain_strike, curr_px,
                sweep, news_score, news_signal, earn_days, strategy_name
            )
            send_telegram(msg, telegram_ids)

            # Log trade
            log_trade_entry(
                ticker=ticker, direction=direction, score=score,
                strategy=strategy_name,
                entry_stock_px=curr_px, stop_px=stop_px, target_px=target_px,
                contract=contract["contract"], strike=contract["strike"],
                expiration=contract["expiration"], dte=contract["dte"],
                entry_option_px=entry_option_px,
                iv_ratio=iv_ratio, earn_play=is_earn_play
            )

            log.info(f"ALERT SENT: {ticker} {direction} {contract['contract']} score={score}")
            break  # One trade at a time

        except Exception as e:
            log.error(f"Scan error {ticker}: {e}")

# MAIN
def main():
    log.info("=" * 60)
    log.info("Options Sniper B🤖T v2.0 — Starting")
    log.info("Strategy: IV-filtered directional options + pre-earnings vol expansion")
    log.info("=" * 60)

    settings     = load_settings()
    telegram_ids = settings.get("telegram_ids", [])

    log.info(f"Watchlist: {', '.join(WATCHLIST)}")
    log.info(f"Telegram IDs: {len(telegram_ids)}")

    send_telegram(
        f"*Options Sniper B🤖T v2.0 — ONLINE* 🟢\n"
        f"*Strategy:* IV-filtered directional + pre-earnings vol expansion\n"
        f"*Exit Rules:* +50% TP | -30% SL | 21 DTE | 5 day max\n"
        f"*IV Gate:* Max {IV_RATIO_MAX}x HV30\n"
        f"*DTE Range:* {DTE_MIN}–{DTE_MAX} days\n"
        f"*Watchlist:* {len(WATCHLIST)} tickers\n"
        f"*Scans:* 10 AM, 12 PM, 2 PM, 3:40 PM ET",
        telegram_ids
    )

    vix              = 20.0
    vix_last_upd     = 0
    last_scan_window = None

    while True:
        try:
            now_ts = time.time()
            if now_ts - vix_last_upd > 1800:
                try:
                    vix = get_vix()
                    vix_last_upd = now_ts
                    log.info(f"VIX updated: {vix:.1f}")
                except Exception as e:
                    log.error(f"VIX update: {e}")

            # Weekly report
            if should_weekly():
                try:
                    send_telegram(weekly_report(), telegram_ids)
                    log.info("Weekly report sent")
                except Exception as e:
                    log.error(f"Weekly report: {e}")

            if not is_market_hours():
                time.sleep(60)
                continue

            # Monitor active trades every cycle
            try:
                monitor_active_trades(telegram_ids)
            except Exception as e:
                log.error(f"Monitor error: {e}")

            # Run scan only during scan windows, once per window
            mt = market_time()
            current_window = None
            for i, (start, end) in enumerate(SCAN_WINDOWS):
                if start <= mt <= end:
                    current_window = i
                    break

            if current_window is not None and current_window != last_scan_window:
                last_scan_window = current_window
                run_scan(telegram_ids, vix)
            elif current_window is None:
                # Reset between windows
                last_scan_window = None

        except Exception as e:
            log.error(f"Main loop error: {e}")

        time.sleep(30)  # Check every 30 seconds for precise window detection

if __name__ == "__main__":
    main()
