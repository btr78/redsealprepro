"""
EARNINGS SCREENER ALERT v2.0 — PEAD Edition  🤖
================================================
Two-mode earnings intelligence system:

MODE 1 — PRE-EARNINGS SCAN (3:45 PM ET daily):
  Scans upcoming earnings (next 5 days) for high implied-move setups.
  Requires >= 7% implied move. Sends directional pick + lotto option.
  Enhanced directional model: RSI, momentum (5d/20d/60d), volume trend,
  52w-high proximity, historical EPS beat rate (last 4 quarters).
  Max 2 picks per week.

MODE 2 — PEAD MORNING SCAN (7:30 AM ET daily):
  Post-Earnings Announcement Drift: stocks that gap 4%+ on earnings day
  with 1.5x+ volume tend to continue drifting in that direction for 3-5 days.
  Scans watchlist for yesterday-evening reporters, detects gap + vol.
  No weekly limit — fires whenever a qualifying PEAD setup exists.
  Option: slightly ITM, 2-3 week DTE (time for drift to develop).

POST-EARNINGS AUDIT:
  Both pick types are audited the next morning for actual vs predicted move.
  Accuracy tracked over time with win rate displayed in alerts.
"""

import sys, os, json, time, logging, traceback
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    ET = pytz.timezone("America/New_York")

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
BOT_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_settings.json")
STATE_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earnings_screener_state.json")

BOT_TITLE         = "Earnings Screener 🤖 v2.0"

# Pre-earnings scan
MIN_IMPLIED_MOVE  = 7.0   # % implied move to qualify for pre-earnings pick
MAX_PICKS_WEEK    = 2     # max pre-earnings alerts per week
PRE_SCAN_HOUR     = 15
PRE_SCAN_MIN      = 45    # 3:45 PM ET

# PEAD scan
PEAD_GAP_MIN      = 4.0   # % gap (open vs prev close) to qualify
PEAD_RVOL_MIN     = 1.5   # relative volume on earnings day
PEAD_SCAN_HOUR    = 7
PEAD_SCAN_MIN     = 30    # 7:30 AM ET

# Lotto option (pre-earnings): cheap OTM, captures the vol event
LOTTO_DELTA_MIN   = 0.15
LOTTO_DELTA_MAX   = 0.35
LOTTO_MIN_OI      = 50
LOTTO_MAX_PREMIUM = 3.00

# PEAD option: slightly ITM/ATM with more DTE for drift
PEAD_DELTA_MIN    = 0.40
PEAD_DELTA_MAX    = 0.65
PEAD_DTE_MIN      = 10    # days to expiry minimum
PEAD_DTE_MAX      = 25    # days to expiry maximum

SCAN_INTERVAL_S   = 60
LOOK_AHEAD_DAYS   = 5     # earnings within next N days

# ─── WATCHLIST ───────────────────────────────────────────────────────────────
WATCHLIST = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # Semis
    "AMD", "AMAT", "AVGO", "MU", "QCOM", "LRCX", "KLAC", "SMCI", "ARM",
    # Cloud / SaaS
    "CRM", "SNOW", "DDOG", "NET", "PANW", "ZS", "MDB", "CSCO",
    # Retail
    "WMT", "TGT", "COST", "HD",
    # Financials
    "JPM", "GS", "MS", "BAC", "V", "MA", "HOOD", "COIN",
    # Biotech / Pharma
    "HIMS", "MRNA", "LLY", "ABBV", "GILD",
    # China ADRs
    "BABA", "JD",
    # High-beta momentum
    "PLTR", "SOFI", "CELH", "MSTR", "APP", "UBER", "SHOP",
    "MELI", "AFRM", "UPST", "DKNG", "ABNB", "DASH", "RIVN",
    "RBLX", "ONON", "LYFT",
]
WATCHLIST = list(dict.fromkeys(WATCHLIST))

# ─── LOGGING ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("earnings_screener.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("EarningsScreener")

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
def load_telegram_ids() -> list:
    for fname in (BOT_SETTINGS_FILE, "sniper_settings.json", "dt_reversal_settings.json"):
        try:
            with open(fname) as f:
                ids = json.load(f).get("telegram_ids", [])
            if ids:
                return ids
        except Exception:
            continue
    return []

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN:
        return
    ids = load_telegram_ids()
    for cid in ids:
        try:
            for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    data={"chat_id": cid, "text": chunk, "parse_mode": "HTML"},
                    timeout=10,
                )
        except Exception as e:
            log.warning(f"Telegram error {cid}: {e}")

# ─── STATE ───────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(s: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, default=str)

def week_key() -> str:
    d = date.today()
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"

def picks_sent_this_week(state: dict) -> int:
    return state.get("weekly_picks", {}).get(week_key(), 0)

def mark_pre_pick_sent(state: dict):
    wk = state.setdefault("weekly_picks", {})
    wk[week_key()] = wk.get(week_key(), 0) + 1
    state["last_pre_scan_date"] = str(date.today())
    save_state(state)

def pre_scan_done_today(state: dict) -> bool:
    return state.get("last_pre_scan_date", "") == str(date.today())

def pead_scan_done_today(state: dict) -> bool:
    return state.get("last_pead_scan_date", "") == str(date.today())

def mark_pead_scan_done(state: dict):
    state["last_pead_scan_date"] = str(date.today())
    save_state(state)

# ─── EARNINGS DATE ───────────────────────────────────────────────────────────
def get_earnings_date(ticker: str) -> date | None:
    try:
        tk  = yf.Ticker(ticker)
        cal = tk.calendar
        if cal is None:
            return None

        # calendar can be a dict or DataFrame
        if hasattr(cal, "columns"):
            # DataFrame — try "Earnings Date" column
            if "Earnings Date" in cal.columns:
                val = cal["Earnings Date"].iloc[0]
                return pd.Timestamp(val).date() if hasattr(val, "date") else None
        elif isinstance(cal, dict):
            for key in ("Earnings Date", "earningsDate"):
                val = cal.get(key)
                if val is not None:
                    if isinstance(val, (list, tuple)):
                        val = val[0]
                    if hasattr(val, "date"):
                        return val.date()
                    return date.fromisoformat(str(val)[:10])
        return None
    except Exception as e:
        log.debug(f"Earnings date error {ticker}: {e}")
        return None

# ─── IMPLIED MOVE ─────────────────────────────────────────────────────────────
def get_implied_move(ticker: str) -> tuple[float | None, str | None, float | None]:
    """Return (implied_move_pct, expiry_used, spot_price)."""
    try:
        tk   = yf.Ticker(ticker)
        spot = tk.fast_info.get("lastPrice") or tk.fast_info.get("regularMarketPrice")
        if not spot or spot <= 0:
            return None, None, None

        exps = tk.options
        if not exps:
            return None, None, None

        # Use front-month expiry (closest, within 7 days)
        target = None
        for exp in exps:
            ed = date.fromisoformat(exp)
            if (ed - date.today()).days <= 14:
                target = exp
        if not target:
            target = exps[0]

        chain  = tk.option_chain(target)
        atm_c  = chain.calls[chain.calls["strike"].sub(spot).abs() < spot * 0.05]
        atm_p  = chain.puts [chain.puts ["strike"].sub(spot).abs() < spot * 0.05]

        if atm_c.empty or atm_p.empty:
            return None, None, None

        straddle = float(atm_c["ask"].min()) + float(atm_p["ask"].min())
        implied  = round((straddle / spot) * 100, 1)
        return implied, target, round(spot, 2)
    except Exception as e:
        log.debug(f"Implied move error {ticker}: {e}")
        return None, None, None

# ─── EPS BEAT HISTORY ────────────────────────────────────────────────────────
def get_eps_beat_rate(ticker: str) -> float | None:
    """
    Returns fraction of last 4 quarters where EPS beat estimate (0.0-1.0).
    Uses yfinance earnings history. Returns None if insufficient data.
    """
    try:
        tk = yf.Ticker(ticker)
        eh = tk.earnings_dates
        if eh is None or eh.empty:
            return None

        # earnings_dates has 'EPS Estimate' and 'Reported EPS' columns
        recent = eh.dropna(subset=["EPS Estimate", "Reported EPS"]).head(4)
        if len(recent) < 2:
            return None

        beats = (recent["Reported EPS"] > recent["EPS Estimate"]).sum()
        return round(beats / len(recent), 2)
    except Exception as e:
        log.debug(f"EPS beat rate error {ticker}: {e}")
        return None

# ─── HISTORICAL AVG MOVE ─────────────────────────────────────────────────────
def get_hist_avg_move(ticker: str) -> float | None:
    try:
        tk = yf.Ticker(ticker)
        eh = tk.earnings_dates
        if eh is None or eh.empty:
            return None
        surprises = eh["Surprise(%)"].dropna().abs().head(4)
        if len(surprises) < 2:
            return None
        return round(float(surprises.mean()), 1)
    except Exception:
        return None

# ─── ENHANCED DIRECTION PREDICTION ───────────────────────────────────────────
def predict_direction(ticker: str, eps_beat_rate: float | None = None) -> tuple[str, list[str]]:
    """
    Enhanced directional model — score -5 to +5.
    UP if score >= 2, DOWN if score <= -2, else NEUTRAL.
    """
    try:
        import pandas as pd
        hist = yf.Ticker(ticker).history(period="6mo")
        if hist.empty or len(hist) < 20:
            return "NEUTRAL", ["insufficient data"]

        close  = hist["Close"]
        volume = hist["Volume"]
        price  = float(close.iloc[-1])

        # RSI(14)
        delta  = close.diff()
        gain   = delta.clip(lower=0).rolling(14).mean()
        loss   = (-delta.clip(upper=0)).rolling(14).mean()
        rsi    = float((100 - (100 / (1 + gain / loss.replace(0, np.nan)))).iloc[-1])

        # Momentum
        mom5d  = (price / float(close.iloc[-5])  - 1) * 100 if len(close) > 5  else 0
        mom20d = (price / float(close.iloc[-20]) - 1) * 100 if len(close) > 20 else 0
        mom60d = (price / float(close.iloc[-60]) - 1) * 100 if len(close) > 60 else 0

        # Trend
        sma50  = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price

        # Volume trend: compare last 5 avg to 20 avg
        v5  = float(volume.tail(5).mean())
        v20 = float(volume.tail(20).mean())
        vol_rising = v5 > v20 * 1.1

        # 52-week high proximity
        high52 = float(close.tail(252).max())
        pct_off_high = (price - high52) / high52 * 100

        score   = 0
        signals = []

        # RSI
        if rsi > 60:
            score += 1; signals.append(f"RSI {rsi:.0f}↑")
        elif rsi < 40:
            score -= 1; signals.append(f"RSI {rsi:.0f}↓")
        else:
            signals.append(f"RSI {rsi:.0f}=")

        # 5d momentum
        if mom5d > 3:
            score += 1; signals.append(f"5d +{mom5d:.1f}%")
        elif mom5d < -3:
            score -= 1; signals.append(f"5d {mom5d:.1f}%")

        # 20d momentum
        if mom20d > 6:
            score += 1; signals.append(f"20d +{mom20d:.1f}%")
        elif mom20d < -6:
            score -= 1; signals.append(f"20d {mom20d:.1f}%")

        # 60d momentum (institutional trend)
        if mom60d > 10:
            score += 1; signals.append(f"60d +{mom60d:.1f}%")
        elif mom60d < -10:
            score -= 1; signals.append(f"60d {mom60d:.1f}%")

        # Trend alignment
        if price > sma50 > sma200:
            score += 1; signals.append("50>200 SMA✓")
        elif price < sma50 < sma200:
            score -= 1; signals.append("50<200 SMA✗")

        # Volume accumulation
        if vol_rising:
            score += 1; signals.append("vol rising")
        else:
            signals.append("vol flat")

        # 52w high proximity: near high = momentum
        if pct_off_high > -10:
            score += 1; signals.append(f"{pct_off_high:+.0f}% from 52wH")
        elif pct_off_high < -30:
            score -= 1; signals.append(f"{pct_off_high:+.0f}% from 52wH")

        # EPS beat history
        if eps_beat_rate is not None:
            if eps_beat_rate >= 0.75:
                score += 1; signals.append(f"EPS beat {eps_beat_rate*100:.0f}%")
            elif eps_beat_rate <= 0.25:
                score -= 1; signals.append(f"EPS miss {(1-eps_beat_rate)*100:.0f}%")

        direction = "UP" if score >= 2 else ("DOWN" if score <= -2 else "NEUTRAL")
        return direction, signals[:5]

    except Exception as e:
        log.debug(f"Direction error {ticker}: {e}")
        return "NEUTRAL", ["error"]

# ─── PEAD GAP DETECTION ───────────────────────────────────────────────────────
def detect_pead_gap(ticker: str) -> dict | None:
    """
    Check if ticker reported earnings yesterday/after-hours and gapped today.
    Returns gap data dict or None.
    Requirements:
      - Earnings date was yesterday (or 2 days ago if weekend/holiday)
      - Today's open vs yesterday's close: |gap| >= PEAD_GAP_MIN %
      - Today's volume so far >= PEAD_RVOL_MIN × 20-day avg volume
    """
    try:
        import pandas as pd
        tk  = yf.Ticker(ticker)

        # Check if earnings was recent (yesterday or up to 2 trading days ago)
        ed = get_earnings_date(ticker)
        today = date.today()
        if ed is None:
            return None
        days_since = (today - ed).days
        if days_since < 0 or days_since > 3:
            return None

        # Get recent daily bars
        hist = tk.history(period="10d")
        if hist is None or len(hist) < 3:
            return None

        yesterday_close = float(hist["Close"].iloc[-2])
        today_open      = float(hist["Open"].iloc[-1])
        today_vol       = float(hist["Volume"].iloc[-1])
        avg_vol_20      = float(hist["Volume"].tail(20).mean())

        if yesterday_close <= 0:
            return None

        gap_pct  = (today_open - yesterday_close) / yesterday_close * 100
        rvol     = round(today_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0.0
        spot     = float(hist["Close"].iloc[-1])

        if abs(gap_pct) < PEAD_GAP_MIN:
            return None
        if rvol < PEAD_RVOL_MIN:
            return None

        direction = "UP" if gap_pct > 0 else "DOWN"

        return {
            "ticker":           ticker,
            "earnings_date":    str(ed),
            "gap_pct":          round(gap_pct, 2),
            "rvol":             rvol,
            "direction":        direction,
            "yesterday_close":  round(yesterday_close, 2),
            "today_open":       round(today_open, 2),
            "spot":             round(spot, 2),
            "avg_vol":          int(avg_vol_20),
        }
    except Exception as e:
        log.debug(f"PEAD gap detection error {ticker}: {e}")
        return None

# ─── OPTION PICKERS ──────────────────────────────────────────────────────────
def _find_option(ticker: str, want_calls: bool, spot: float,
                 delta_min: float, delta_max: float,
                 dte_min: int, dte_max: int,
                 max_premium: float, min_oi: int) -> dict | None:
    """Generic option finder. Used by both lotto and PEAD pickers."""
    try:
        tk   = yf.Ticker(ticker)
        exps = tk.options
        if not exps:
            return None

        # Filter expiries by DTE range
        valid_exps = []
        for exp in exps:
            dte = (date.fromisoformat(exp) - date.today()).days
            if dte_min <= dte <= dte_max:
                valid_exps.append(exp)

        if not valid_exps:
            # Fallback: pick closest within 3× max DTE
            for exp in exps:
                dte = (date.fromisoformat(exp) - date.today()).days
                if 0 < dte <= dte_max * 3:
                    valid_exps.append(exp)
                    break

        if not valid_exps:
            return None

        # Use the nearest valid expiry
        target = valid_exps[0]
        dte    = (date.fromisoformat(target) - date.today()).days

        chain     = tk.option_chain(target)
        contracts = (chain.calls if want_calls else chain.puts).copy()

        for col in ["bid", "ask", "openInterest", "delta", "impliedVolatility"]:
            if col not in contracts.columns:
                contracts[col] = np.nan

        # Strike filter
        if want_calls:
            contracts = contracts[(contracts["strike"] >= spot * 0.90) &
                                  (contracts["strike"] <= spot * 1.25)]
        else:
            contracts = contracts[(contracts["strike"] >= spot * 0.75) &
                                  (contracts["strike"] <= spot * 1.10)]

        # Premium and OI filters
        mask = ((contracts["ask"] > 0) &
                (contracts["ask"] <= max_premium) &
                (contracts["openInterest"].fillna(0) >= min_oi))
        filtered = contracts[mask].copy()

        if filtered.empty:
            mask2 = (contracts["ask"] > 0) & (contracts["ask"] <= max_premium)
            filtered = contracts[mask2].copy()

        if filtered.empty:
            return None

        # Delta filter if available
        if filtered["delta"].notna().any():
            abs_d   = filtered["delta"].abs()
            in_range = filtered[(abs_d >= delta_min) & (abs_d <= delta_max)]
            if not in_range.empty:
                filtered = in_range

        best = filtered.sort_values("ask").iloc[0]

        delta_val = best.get("delta", np.nan)
        delta_str = f"{abs(float(delta_val)):.2f}" if (isinstance(delta_val, float) and not np.isnan(delta_val)) else "n/a"
        iv_val    = best.get("impliedVolatility", np.nan)
        iv_str    = f"{float(iv_val)*100:.0f}%" if (isinstance(iv_val, float) and not np.isnan(iv_val)) else "n/a"
        oi_val    = best.get("openInterest", 0)
        oi_str    = f"{int(oi_val):,}" if (oi_val and not np.isnan(float(oi_val))) else "n/a"

        ask   = float(best["ask"])
        bid   = float(best["bid"]) if best.get("bid", 0) > 0 else ask * 0.85
        mid   = round((bid + ask) / 2, 2)

        return {
            "type":       "CALL" if want_calls else "PUT",
            "strike":     float(best["strike"]),
            "expiry":     target,
            "dte":        dte,
            "bid":        round(bid, 2),
            "ask":        round(ask, 2),
            "mid":        mid,
            "cost_1cont": round(mid * 100, 2),
            "delta":      delta_str,
            "iv":         iv_str,
            "open_int":   oi_str,
        }
    except Exception as e:
        log.debug(f"Option finder error {ticker}: {e}")
        return None


def pick_lotto_option(ticker: str, direction: str, spot: float) -> dict | None:
    """Cheap OTM option for pre-earnings vol capture. DTE 1-14."""
    if direction == "NEUTRAL" or spot <= 0:
        return None
    return _find_option(ticker, want_calls=(direction == "UP"), spot=spot,
                        delta_min=LOTTO_DELTA_MIN, delta_max=LOTTO_DELTA_MAX,
                        dte_min=1, dte_max=14,
                        max_premium=LOTTO_MAX_PREMIUM, min_oi=LOTTO_MIN_OI)


def pick_pead_option(ticker: str, direction: str, spot: float) -> dict | None:
    """ATM/slightly-ITM option for PEAD drift trade. DTE 10-25 for multi-day hold."""
    if direction == "NEUTRAL" or spot <= 0:
        return None
    return _find_option(ticker, want_calls=(direction == "UP"), spot=spot,
                        delta_min=PEAD_DELTA_MIN, delta_max=PEAD_DELTA_MAX,
                        dte_min=PEAD_DTE_MIN, dte_max=PEAD_DTE_MAX,
                        max_premium=10.00, min_oi=25)

# ─── PRE-EARNINGS SCAN ───────────────────────────────────────────────────────
def scan_for_pre_picks() -> list[dict]:
    today = date.today()
    end   = today + timedelta(days=LOOK_AHEAD_DAYS)
    log.info(f"[PRE-EARNINGS] Scanning {today} → {end} | min implied {MIN_IMPLIED_MOVE}%")

    qualified = []
    for ticker in WATCHLIST:
        try:
            ed = get_earnings_date(ticker)
            if not ed or not (today <= ed <= end):
                continue

            log.info(f"  {ticker}: earnings {ed} — checking options...")
            implied, exp_used, spot = get_implied_move(ticker)

            if implied is None:
                log.info(f"  {ticker}: no options data"); continue
            if implied < MIN_IMPLIED_MOVE:
                log.info(f"  {ticker}: implied {implied}% < {MIN_IMPLIED_MOVE}%"); continue

            eps_beat     = get_eps_beat_rate(ticker)
            hist_avg     = get_hist_avg_move(ticker)
            direction, signals = predict_direction(ticker, eps_beat)
            option       = pick_lotto_option(ticker, direction, spot or 0)

            qualified.append({
                "type":          "PRE",
                "ticker":        ticker,
                "earnings_date": str(ed),
                "implied_move":  implied,
                "hist_avg":      hist_avg,
                "eps_beat_rate": eps_beat,
                "direction":     direction,
                "dir_signals":   signals,
                "spot":          round(spot, 2) if spot else None,
                "option":        option,
            })
            log.info(f"  PASS {ticker}: {implied}% implied | {direction} | beat_rate={eps_beat}")
        except Exception as e:
            log.warning(f"  Error {ticker}: {e}")

    qualified.sort(key=lambda x: x["implied_move"], reverse=True)
    return qualified

# ─── PEAD SCAN ───────────────────────────────────────────────────────────────
def scan_for_pead_picks() -> list[dict]:
    log.info(f"[PEAD] Scanning {len(WATCHLIST)} tickers for post-earnings gap drift...")
    picks = []
    for ticker in WATCHLIST:
        try:
            gap = detect_pead_gap(ticker)
            if not gap:
                continue
            spot      = gap["spot"]
            direction = gap["direction"]
            option    = pick_pead_option(ticker, direction, spot)
            _, signals = predict_direction(ticker)
            gap["dir_signals"] = signals
            gap["option"]      = option
            gap["type"]        = "PEAD"
            picks.append(gap)
            log.info(f"  PEAD {ticker}: gap {gap['gap_pct']:+.1f}% | rvol {gap['rvol']}x | {direction}")
        except Exception as e:
            log.warning(f"  Error {ticker}: {e}")
        time.sleep(0.3)

    picks.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return picks

# ─── POST-EARNINGS AUDIT ─────────────────────────────────────────────────────
def check_audits(state: dict):
    """Check pending picks for actual move and log accuracy."""
    pending = state.get("pending_audit", [])
    if not pending:
        return

    today = date.today()
    still_pending = []
    results       = state.setdefault("audit_history", [])

    for pick in pending:
        try:
            audit_date = date.fromisoformat(pick.get("audit_date", str(today)))
            if today < audit_date:
                still_pending.append(pick)
                continue

            tk   = yf.Ticker(pick["ticker"])
            hist = tk.history(period="5d")
            if hist is None or len(hist) < 2:
                still_pending.append(pick); continue

            pre_close  = float(hist["Close"].iloc[-2])
            today_open = float(hist["Open"].iloc[-1])
            actual_pct = (today_open - pre_close) / pre_close * 100
            predicted  = pick.get("direction", "NEUTRAL")
            success    = ((predicted == "UP" and actual_pct > 1) or
                          (predicted == "DOWN" and actual_pct < -1))

            result = {
                "ticker":     pick["ticker"],
                "pick_type":  pick.get("type", "PRE"),
                "direction":  predicted,
                "actual_pct": round(actual_pct, 2),
                "success":    success,
                "date":       str(today),
            }
            results.append(result)
            emoji = "✅" if success else "❌"
            send_telegram(
                f"<b>{BOT_TITLE} — Earnings Audit</b>\n"
                f"{emoji} <b>{pick['ticker']}</b> | {pick.get('type','PRE')} pick\n"
                f"Predicted: {predicted} | Actual gap: {actual_pct:+.1f}%\n"
                f"Result: {'WIN' if success else 'MISS'}"
            )
            log.info(f"[AUDIT] {pick['ticker']}: predicted {predicted}, actual {actual_pct:+.1f}% → {'WIN' if success else 'MISS'}")
        except Exception as e:
            log.warning(f"Audit error {pick.get('ticker','?')}: {e}")
            still_pending.append(pick)

    state["pending_audit"] = still_pending
    save_state(state)

def model_accuracy(state: dict) -> tuple[float | None, int]:
    history = state.get("audit_history", [])
    if len(history) < 3:
        return None, len(history)
    wins  = sum(1 for r in history if r.get("success"))
    return round(wins / len(history) * 100, 1), len(history)

def accuracy_bar(win_rate: float | None) -> str:
    if win_rate is None:
        return "📊 Accuracy: insufficient data"
    filled = round(win_rate / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"📊 Model accuracy: {win_rate:.0f}%  [{bar}]"

# ─── ALERT FORMATTERS ────────────────────────────────────────────────────────
def format_pre_alert(picks: list[dict], state: dict) -> str:
    wk_after = picks_sent_this_week(state) + len(picks)
    wr, n    = model_accuracy(state)

    lines = [
        f"📅 <b>{BOT_TITLE} — PRE-EARNINGS PICKS</b>",
        f"<i>Upcoming earnings · min {MIN_IMPLIED_MOVE}% implied move · 3:45 PM ET</i>",
        accuracy_bar(wr) + (f" ({n} audited)" if n >= 3 else ""),
        "",
    ]
    for i, p in enumerate(picks, 1):
        arrow    = "🟢 ▲ UP" if p["direction"] == "UP" else ("🔴 ▼ DOWN" if p["direction"] == "DOWN" else "⚪ NEUTRAL")
        hist_str = f"±{p['hist_avg']}%" if p["hist_avg"] else "n/a"
        beat_str = f"{p['eps_beat_rate']*100:.0f}% beat rate" if p.get("eps_beat_rate") else "beat rate n/a"
        sigs     = " · ".join(p["dir_signals"][:4])
        spot_str = f"${p['spot']}" if p["spot"] else "n/a"

        lines += [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>#{i} {p['ticker']}</b>  ({spot_str})",
            f"📆 Earnings:  {p['earnings_date']}",
            f"⚡ Direction: {arrow}",
            f"📊 Implied:  ±{p['implied_move']}%  (hist avg {hist_str})",
            f"🧠 {beat_str}  |  {sigs}",
        ]
        opt = p.get("option")
        if opt:
            lines += [
                "",
                f"🎰 <b>Lotto Option</b> (OTM, defined risk)",
                f"   {opt['type']} ${opt['strike']:.2f} exp {opt['expiry']} ({opt['dte']}d)",
                f"   Bid ${opt['bid']} / Ask ${opt['ask']}  →  Mid ${opt['mid']}",
                f"   Cost (1 contract): <b>${opt['cost_1cont']:.2f}</b>",
                f"   Δ {opt['delta']}  |  IV {opt['iv']}  |  OI {opt['open_int']}",
            ]
        else:
            lines.append("   🎰 Option: check chain manually (low liquidity)")
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Picks this week: {wk_after}/{MAX_PICKS_WEEK}",
        "<i>Lotto = high risk. Size small. Not financial advice.</i>",
    ]
    return "\n".join(lines)


def format_pead_alert(picks: list[dict], state: dict) -> str:
    wr, n = model_accuracy(state)
    lines = [
        f"📈 <b>{BOT_TITLE} — PEAD DRIFT ALERT</b>",
        f"<i>Post-Earnings Announcement Drift — gap {PEAD_GAP_MIN}%+ with {PEAD_RVOL_MIN}x+ volume</i>",
        f"<i>Strategy: ride the drift in gap direction for 3-5 trading days</i>",
        accuracy_bar(wr) + (f" ({n} audited)" if n >= 3 else ""),
        "",
    ]
    for i, p in enumerate(picks, 1):
        dir_emoji = "🚀" if p["direction"] == "UP" else "💥"
        gap_arrow = "▲" if p["direction"] == "UP" else "▼"
        sigs      = " · ".join(p.get("dir_signals", [])[:3])
        lines += [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>#{i} {p['ticker']}</b>  {dir_emoji} PEAD {p['direction']}",
            f"📆 Reported:    {p['earnings_date']}",
            f"📉 Gap:         {gap_arrow} {abs(p['gap_pct']):.1f}%  "
            f"(prev close ${p['yesterday_close']} → open ${p['today_open']})",
            f"📊 Volume:      {p['rvol']:.1f}x avg  (vol confirmation ✅)",
            f"💰 Spot:        ${p['spot']}",
            f"🔍 Signals:     {sigs}",
        ]
        opt = p.get("option")
        if opt:
            lines += [
                "",
                f"📌 <b>PEAD Option</b> (ATM, {PEAD_DTE_MIN}-{PEAD_DTE_MAX}d DTE for drift)",
                f"   {opt['type']} ${opt['strike']:.2f} exp {opt['expiry']} ({opt['dte']}d)",
                f"   Bid ${opt['bid']} / Ask ${opt['ask']}  →  Mid ${opt['mid']}",
                f"   Cost (1 contract): <b>${opt['cost_1cont']:.2f}</b>",
                f"   Δ {opt['delta']}  |  IV {opt['iv']}  |  OI {opt['open_int']}",
            ]
            lines += [
                "",
                f"📐 <b>Drift Trade Plan</b>",
                f"   Entry: near open (first 30 min)",
                f"   Target: 3-5 trading days, trail stop after +5%",
                f"   Stop: if gap fills (price returns to pre-earnings close)",
            ]
        else:
            lines.append("   📌 Option: check chain manually")
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<i>PEAD = statistical drift after earnings gap. Not guaranteed.</i>",
        "<i>Exit if gap fills or after 5 trading days. Size conservatively.</i>",
    ]
    return "\n".join(lines)

# ─── MAIN LOOP ───────────────────────────────────────────────────────────────
def now_et() -> datetime:
    return datetime.now(ET)

def is_weekday() -> bool:
    return now_et().weekday() < 5

def main():
    log.info("=" * 60)
    log.info(f"{BOT_TITLE} — Starting")
    log.info(f"PRE-EARNINGS scan: {PRE_SCAN_HOUR}:{PRE_SCAN_MIN:02d} ET | PEAD scan: {PEAD_SCAN_HOUR}:{PEAD_SCAN_MIN:02d} ET")
    log.info(f"Watchlist: {len(WATCHLIST)} tickers")
    log.info("=" * 60)

    send_telegram(
        f"<b>{BOT_TITLE} Online</b>\n\n"
        f"MODE 1 — Pre-Earnings scan at {PRE_SCAN_HOUR}:{PRE_SCAN_MIN:02d} PM ET\n"
        f"  • Min {MIN_IMPLIED_MOVE}% implied move · max {MAX_PICKS_WEEK} picks/week\n"
        f"  • Enhanced direction: RSI + momentum + EPS beat history\n\n"
        f"MODE 2 — PEAD drift scan at {PEAD_SCAN_HOUR}:{PEAD_SCAN_MIN:02d} AM ET\n"
        f"  • {PEAD_GAP_MIN}%+ gap + {PEAD_RVOL_MIN}x volume on earnings day\n"
        f"  • ATM option, 3-5 day drift trade\n\n"
        f"Watchlist: {len(WATCHLIST)} tickers"
    )

    # Handle --now flag for immediate test run
    if "--now" in sys.argv:
        state = load_state()
        check_audits(state)
        pead_picks = scan_for_pead_picks()
        if pead_picks:
            send_telegram(format_pead_alert(pead_picks, state))
            for p in pead_picks:
                state.setdefault("pending_audit", []).append({
                    "ticker":     p["ticker"],
                    "type":       "PEAD",
                    "direction":  p["direction"],
                    "spot":       p["spot"],
                    "audit_date": str(date.today() + timedelta(days=3)),
                })
            save_state(state)
        pre_picks = scan_for_pre_picks()
        if pre_picks:
            top = pre_picks[:MAX_PICKS_WEEK]
            send_telegram(format_pre_alert(top, state))
            for p in top:
                state.setdefault("pending_audit", []).append({
                    "ticker":     p["ticker"],
                    "type":       "PRE",
                    "direction":  p["direction"],
                    "spot":       p["spot"],
                    "earnings_date": p["earnings_date"],
                    "audit_date": str(date.fromisoformat(p["earnings_date"]) + timedelta(days=1)),
                })
            mark_pre_pick_sent(state)
        return

    while True:
        try:
            now  = now_et()
            hhmm = (now.hour, now.minute)

            if is_weekday():
                state = load_state()

                # Post-earnings audit (runs at PEAD scan time too)
                check_audits(state)

                # PEAD scan window: 7:30-7:35 AM ET
                if (PEAD_SCAN_HOUR, PEAD_SCAN_MIN) <= hhmm < (PEAD_SCAN_HOUR, PEAD_SCAN_MIN + 5):
                    if not pead_scan_done_today(state):
                        log.info("[PEAD] Running morning gap scan...")
                        pead_picks = scan_for_pead_picks()
                        if pead_picks:
                            send_telegram(format_pead_alert(pead_picks, state))
                            for p in pead_picks:
                                state.setdefault("pending_audit", []).append({
                                    "ticker":     p["ticker"],
                                    "type":       "PEAD",
                                    "direction":  p["direction"],
                                    "spot":       p["spot"],
                                    "audit_date": str(date.today() + timedelta(days=3)),
                                })
                        else:
                            log.info("[PEAD] No qualifying gaps today.")
                        mark_pead_scan_done(state)

                # Pre-earnings scan window: 3:45-3:50 PM ET
                elif (PRE_SCAN_HOUR, PRE_SCAN_MIN) <= hhmm < (PRE_SCAN_HOUR, PRE_SCAN_MIN + 5):
                    if not pre_scan_done_today(state):
                        remaining = MAX_PICKS_WEEK - picks_sent_this_week(state)
                        if remaining > 0:
                            log.info(f"[PRE-EARNINGS] Running scan ({remaining} picks remaining this week)...")
                            pre_picks = scan_for_pre_picks()
                            if pre_picks:
                                top = pre_picks[:remaining]
                                send_telegram(format_pre_alert(top, state))
                                for p in top:
                                    state.setdefault("pending_audit", []).append({
                                        "ticker":       p["ticker"],
                                        "type":         "PRE",
                                        "direction":    p["direction"],
                                        "spot":         p["spot"],
                                        "earnings_date": p["earnings_date"],
                                        "audit_date":   str(date.fromisoformat(p["earnings_date"]) + timedelta(days=1)),
                                    })
                                mark_pre_pick_sent(state)
                            else:
                                log.info("[PRE-EARNINGS] No qualifying setups today.")
                                state["last_pre_scan_date"] = str(date.today())
                                save_state(state)
                        else:
                            log.info("[PRE-EARNINGS] Weekly pick limit reached.")
                            state["last_pre_scan_date"] = str(date.today())
                            save_state(state)

            time.sleep(SCAN_INTERVAL_S)

        except KeyboardInterrupt:
            log.info("Shutting down.")
            break
        except Exception as e:
            log.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(60)

if __name__ == "__main__":
    main()
