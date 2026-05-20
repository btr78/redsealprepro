#!/usr/bin/env python3
"""
CBOT PRO v4.0 - Advanced Cryptocurrency Trading Signal Bot
===========================================================
A robust, production-grade crypto signal bot with:
- Advanced technical indicators (ADX, Bollinger, SuperTrend, etc.)
- Crypto-specific metrics (funding rate sentiment, whale detection)
- Multi-timeframe analysis
- Signal confidence scoring
- Proper error handling and logging
- State persistence and recovery
v3.0 Upgrades:
- Self-learning brain: per-ticker weight/threshold adjustment from outcomes
- BTC regime gate: suppresses buy signals in BTC downtrend
- Candlestick pattern recognition: hammer, engulfing, doji, morning/evening star
- Fear & Greed Index + funding rate filter
- Smart stop loss: nearest pivot support vs fixed ATR
- Real signal outcome tracking: T1/T2/T3 hit vs stop hit
v4.0 Upgrades:
- Fixed funding rate URL (was always returning None)
- Fixed Ichimoku chikou lookahead bias
- Choppiness Index hard gate: suppresses signals in ranging/sideways markets
- Heikin Ashi candles for EMA + SuperTrend (cleaner trend signals, less noise)
- Consecutive candle confirmation: signal must persist 2 candles (kills whipsaws)
- Liquidation cascade scoring from Gate.io free public API
- Long/Short ratio + funding rate contrarian scoring
"""

import requests
import pandas as pd
import numpy as np
import time
import datetime
import sys
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import signal as sig
import hashlib

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Centralized configuration with validation"""
    # Telegram Settings
    telegram_token: str = ""
    chat_ids: List[str] = field(default_factory=list)

    # Watchlist
    watchlist: List[str] = field(default_factory=lambda: [
        'XRP_USDT', 'XLM_USDT', 'XDC_USDT', 'HBAR_USDT',
        'ZBCN_USDT', 'HNT_USDT', 'UNI_USDT', 'BTC_USDT', 'ETH_USDT',
        'LTC_USDT', 'NEAR_USDT', 'LINK_USDT', 'SOL_USDT', 'ADA_USDT',
    ])

    # Timeframes for multi-timeframe analysis
    primary_timeframe: str = '5m'
    secondary_timeframe: str = '15m'
    tertiary_timeframe: str = '1h'

    # Thresholds
    vol_threshold: float = 2.0
    atr_threshold: float = 2.5
    min_confluence: int = 12
    min_signal_score: float = 72.0  # Minimum score out of 100
    min_price_move_pct: float = 3.0  # Minimum predicted price movement percentage
    fib_tolerance_pct: float = 1.0
    lookback_swing: int = 100

    # Operational
    scan_interval: int = 60  # seconds
    alert_cooldown: int = 3600  # seconds per ticker
    heartbeat_time: str = "06:30"  # Daily heartbeat at 6:30 AM
    max_retries: int = 3
    retry_delay: float = 2.0

    # State persistence
    state_file: str = "cbot_state.json"
    brain_file: str = "cbot_brain.json"

    @classmethod
    def from_env(cls) -> 'Config':
        """Load config from environment variables with fallbacks"""
        config = cls()

        # Try environment variables first, then fallback to defaults
        config.telegram_token = os.environ.get(
            "TELEGRAM_BOT_TOKEN",
            "8104100309:AAGe4OJMAHD6U87k_eFCbhHd9Ib8oq0WR70"  # Fallback
        )

        chat_ids_env = os.environ.get("TELEGRAM_CHAT_IDS", "")
        if chat_ids_env:
            config.chat_ids = [cid.strip() for cid in chat_ids_env.split(",")]
        else:
            config.chat_ids = ["7202311083", "8204374456", "5958228425", "8113872093", "8269621251", "8446633516", "8725728527", "8635897069", "8792071860"]

        return config

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        if not self.telegram_token:
            errors.append("Telegram token is required")
        if not self.chat_ids:
            errors.append("At least one chat ID is required")
        if not self.watchlist:
            errors.append("Watchlist cannot be empty")
        if self.min_signal_score < 0 or self.min_signal_score > 100:
            errors.append("Signal score must be between 0 and 100")
        return errors


class SignalType(Enum):
    """Signal types with associated properties"""
    STRONG_BUY = ("🟢🟢", "STRONG BUY", 1.0)
    BUY = ("🟢", "BUY", 0.7)
    WEAK_BUY = ("🟡", "WEAK BUY", 0.4)
    NEUTRAL = ("⚪", "NEUTRAL", 0.0)
    WEAK_SELL = ("🟠", "WEAK SELL", -0.4)
    SELL = ("🔴", "SELL", -0.7)
    STRONG_SELL = ("🔴🔴", "STRONG SELL", -1.0)

    def __init__(self, emoji: str, label: str, weight: float):
        self.emoji = emoji
        self.label = label
        self.weight = weight


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure logging with console and file handlers"""
    logger = logging.getLogger("CBOT_PRO")
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler('cbot_pro.log')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================================================
# API LAYER WITH RETRY LOGIC
# ============================================================================

class APIClient:
    """Robust API client with retry logic and rate limiting"""

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json"
        })
        self._last_request_time = 0
        self._min_request_interval = 0.2  # 200ms between requests

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request_with_retry(self, url: str, params: dict = None,
                            timeout: int = 10) -> Optional[requests.Response]:
        """Make request with exponential backoff retry"""
        for attempt in range(self.config.max_retries):
            try:
                self._rate_limit()
                response = self.session.get(url, params=params, timeout=timeout)

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 200:
                    return response

                logger.warning(f"API returned {response.status_code}")

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Request error: {e}")

            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay * (2 ** attempt)
                time.sleep(delay)

        return None

    def fetch_ohlcv(self, ticker: str, interval: str = '5m',
                    limit: int = 300) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Gate.io"""
        url = "https://api.gateio.ws/api/v4/spot/candlesticks"
        params = {'currency_pair': ticker, 'interval': interval, 'limit': limit}

        response = self._request_with_retry(url, params)
        if response is None:
            return None

        try:
            data = response.json()
            if not data:
                return None

            df = pd.DataFrame(data)
            df = df.iloc[:, :8]
            df.columns = ['timestamp', 'volume_quote', 'close', 'high',
                         'low', 'open', 'volume_base', 'closed']

            numeric_cols = ['open', 'high', 'low', 'close', 'volume_quote', 'volume_base']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)

            return df
        except Exception as e:
            logger.error(f"Error parsing OHLCV data: {e}")
            return None

    def send_telegram(self, message: str, parse_mode: str = None) -> bool:
        """Send Telegram message with retry logic"""
        success_count = 0

        for chat_id in self.config.chat_ids:
            for attempt in range(2):  # 2 attempts per chat
                try:
                    url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
                    payload = {"chat_id": chat_id, "text": message}
                    if parse_mode:
                        payload["parse_mode"] = parse_mode

                    response = self.session.post(url, data=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                        break
                    else:
                        logger.warning(f"Telegram send failed for {chat_id}: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Telegram error for {chat_id}: {e}")

                if attempt == 0:
                    time.sleep(1)

        return success_count > 0

    def fetch_fear_greed(self) -> Optional[int]:
        """Fetch Crypto Fear & Greed Index (0=extreme fear, 100=extreme greed)"""
        try:
            response = self._request_with_retry("https://api.alternative.me/fng/?limit=1")
            if response:
                data = response.json()
                return int(data['data'][0]['value'])
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")
        return None

    def fetch_funding_rate(self, ticker: str) -> Optional[float]:
        """Fetch funding rate for a perpetual contract on Gate.io (positive=longs pay, negative=shorts pay).
        v4.0: Fixed URL — was broken and always returning None."""
        try:
            url = f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{ticker}"
            response = self._request_with_retry(url)
            if response:
                data = response.json()
                if isinstance(data, dict) and 'funding_rate' in data:
                    return float(data['funding_rate'])
        except Exception as e:
            logger.debug(f"Funding rate fetch failed for {ticker}: {e}")
        return None

    def fetch_contract_data(self, ticker: str) -> Optional[dict]:
        """Fetch full futures contract data: funding rate, long/short sizes, liq data.
        Returns dict with funding_rate, long_size, short_size or None."""
        try:
            url = f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{ticker}"
            response = self._request_with_retry(url)
            if response:
                data = response.json()
                if isinstance(data, dict):
                    long_size = float(data.get('long_size', 0) or 0)
                    short_size = float(data.get('short_size', 0) or 0)
                    funding_rate = float(data.get('funding_rate', 0) or 0)
                    return {
                        'funding_rate': funding_rate,
                        'long_size': long_size,
                        'short_size': short_size,
                    }
        except Exception as e:
            logger.debug(f"Contract data fetch failed for {ticker}: {e}")
        return None

    def fetch_liquidations(self, ticker: str, limit: int = 50) -> Optional[list]:
        """Fetch recent liquidation orders from Gate.io (free public API).
        Returns list of liq events with size and side."""
        try:
            url = "https://api.gateio.ws/api/v4/futures/usdt/liq_orders"
            params = {'contract': ticker, 'limit': limit}
            response = self._request_with_retry(url, params)
            if response:
                return response.json()
        except Exception as e:
            logger.debug(f"Liquidations fetch failed for {ticker}: {e}")
        return None


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

class Indicators:
    """Advanced technical indicators for crypto trading"""

    @staticmethod
    def safe_divide(a, b, default: float = 0.0):
        """Safe division handling zeros and NaN - returns pandas Series"""
        result = np.where(b != 0, a / b, default)
        if isinstance(a, pd.Series):
            return pd.Series(result, index=a.index)
        elif isinstance(b, pd.Series):
            return pd.Series(result, index=b.index)
        return result

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(period).mean()

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = Indicators.safe_divide(gain, loss, 1.0)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26,
             signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD with Signal and Histogram"""
        ema_fast = Indicators.ema(close, fast)
        ema_slow = Indicators.ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = Indicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                   k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()

        denom = highest_high - lowest_low
        k = pd.Series(
            np.where(denom != 0, 100 * (close - lowest_low) / denom, 50),
            index=close.index
        )
        d = k.rolling(d_period).mean()
        return k, d

    @staticmethod
    def bollinger_bands(close: pd.Series, period: int = 20,
                        std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands"""
        middle = Indicators.sma(close, period)
        std = close.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Average Directional Index with +DI and -DI"""
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low

        # Create pandas Series for plus_dm and minus_dm
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0),
            index=high.index
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0),
            index=high.index
        )

        # Smoothed values
        atr_smooth = tr.rolling(period).mean()
        plus_di = 100 * plus_dm.rolling(period).mean() / atr_smooth
        minus_di = 100 * minus_dm.rolling(period).mean() / atr_smooth

        # Replace inf and handle division issues
        plus_di = plus_di.replace([np.inf, -np.inf], 0).fillna(0)
        minus_di = minus_di.replace([np.inf, -np.inf], 0).fillna(0)

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(period).mean()

        return adx, plus_di, minus_di

    @staticmethod
    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """SuperTrend Indicator"""
        atr = Indicators.atr(high, low, close, period)
        hl2 = (high + low) / 2

        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)

        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)

        supertrend.iloc[0] = upper_band.iloc[0]
        direction.iloc[0] = 1

        for i in range(1, len(close)):
            if close.iloc[i] > supertrend.iloc[i-1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1  # Bullish
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1  # Bearish

        return supertrend, direction

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series,
             volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        cum_vol = volume.cumsum()
        cum_tp_vol = (typical_price * volume).cumsum()
        return Indicators.safe_divide(cum_tp_vol, cum_vol, close)

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume"""
        direction = np.sign(close.diff())
        return (direction * volume).fillna(0).cumsum()

    @staticmethod
    def mfi(high: pd.Series, low: pd.Series, close: pd.Series,
            volume: pd.Series, period: int = 14) -> pd.Series:
        """Money Flow Index - Volume-weighted RSI"""
        typical_price = (high + low + close) / 3
        raw_money_flow = typical_price * volume

        flow_direction = np.sign(typical_price.diff())
        positive_flow = np.where(flow_direction > 0, raw_money_flow, 0)
        negative_flow = np.where(flow_direction < 0, raw_money_flow, 0)

        positive_mf = pd.Series(positive_flow).rolling(period).sum()
        negative_mf = pd.Series(negative_flow).rolling(period).sum()

        mfi = 100 - (100 / (1 + Indicators.safe_divide(positive_mf, negative_mf, 1)))
        return mfi

    @staticmethod
    def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, pd.Series]:
        """Ichimoku Cloud Components"""
        # Tenkan-sen (Conversion Line)
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2

        # Kijun-sen (Base Line)
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2

        # Senkou Span A (Leading Span A)
        senkou_a = ((tenkan + kijun) / 2).shift(26)

        # Senkou Span B (Leading Span B)
        senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)

        # Chikou Span — v4.0 fix: compare current close vs price 26 bars ago (no lookahead)
        # Old code used close.shift(-26) which reads future bars (invalid in live trading)
        chikou_current = close.iloc[-1] if len(close) > 26 else None
        chikou_past_price = close.iloc[-27] if len(close) > 26 else None
        chikou_above = (chikou_current > chikou_past_price) if (chikou_current and chikou_past_price) else None

        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
            'chikou_above': chikou_above,  # True=bullish, False=bearish, None=unknown
        }

    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = 14) -> pd.Series:
        """Williams %R"""
        highest_high = high.rolling(period).max()
        lowest_low = low.rolling(period).min()
        wr = -100 * Indicators.safe_divide(highest_high - close,
                                           highest_high - lowest_low, 50)
        return wr

    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 20) -> pd.Series:
        """Commodity Channel Index"""
        typical_price = (high + low + close) / 3
        sma_tp = typical_price.rolling(period).mean()
        mean_deviation = typical_price.rolling(period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        cci = Indicators.safe_divide(typical_price - sma_tp, 0.015 * mean_deviation, 0)
        return cci

    @staticmethod
    def detect_divergence(price: pd.Series, indicator: pd.Series,
                          lookback: int = 20) -> Tuple[bool, bool]:
        """
        Detect bullish and bearish divergences
        Returns: (bullish_divergence, bearish_divergence)
        """
        if len(price) < lookback:
            return False, False

        recent_price = price.iloc[-lookback:]
        recent_ind = indicator.iloc[-lookback:]

        # Find local minima and maxima
        price_min_idx = recent_price.idxmin()
        price_max_idx = recent_price.idxmax()
        ind_min_idx = recent_ind.idxmin()
        ind_max_idx = recent_ind.idxmax()

        # Bullish divergence: price makes lower low, indicator makes higher low
        current_price_low = recent_price.iloc[-5:].min()
        prev_price_low = recent_price.iloc[:10].min()
        current_ind_low = recent_ind.iloc[-5:].min()
        prev_ind_low = recent_ind.iloc[:10].min()

        bullish_div = (current_price_low < prev_price_low and
                      current_ind_low > prev_ind_low)

        # Bearish divergence: price makes higher high, indicator makes lower high
        current_price_high = recent_price.iloc[-5:].max()
        prev_price_high = recent_price.iloc[:10].max()
        current_ind_high = recent_ind.iloc[-5:].max()
        prev_ind_high = recent_ind.iloc[:10].max()

        bearish_div = (current_price_high > prev_price_high and
                      current_ind_high < prev_ind_high)

        return bullish_div, bearish_div

    @staticmethod
    def pivot_points(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, float]:
        """Calculate Pivot Points (Standard)"""
        h = high.iloc[-1]
        l = low.iloc[-1]
        c = close.iloc[-1]

        pivot = (h + l + c) / 3
        r1 = (2 * pivot) - l
        r2 = pivot + (h - l)
        r3 = h + 2 * (pivot - l)
        s1 = (2 * pivot) - h
        s2 = pivot - (h - l)
        s3 = l - 2 * (h - pivot)

        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }

    @staticmethod
    def fibonacci_levels(high: pd.Series, low: pd.Series, close: pd.Series,
                        lookback: int = 100) -> Dict[str, Any]:
        """Calculate Fibonacci retracement and extension levels"""
        if len(high) < lookback:
            return {}

        recent_high = high.iloc[-lookback:]
        recent_low = low.iloc[-lookback:]

        swing_high = recent_high.max()
        swing_low = recent_low.min()
        diff = swing_high - swing_low

        # Determine trend direction
        ema20 = Indicators.ema(close, 20).iloc[-1]
        is_uptrend = close.iloc[-1] > ema20

        if is_uptrend:
            # Retracement levels in uptrend
            levels = {
                '0.0': swing_high,
                '23.6': swing_high - 0.236 * diff,
                '38.2': swing_high - 0.382 * diff,
                '50.0': swing_high - 0.500 * diff,
                '61.8': swing_high - 0.618 * diff,
                '78.6': swing_high - 0.786 * diff,
                '100.0': swing_low,
                # Extensions
                'ext_127.2': swing_high + 0.272 * diff,
                'ext_161.8': swing_high + 0.618 * diff,
                'ext_261.8': swing_high + 1.618 * diff,
            }
            direction = "uptrend"
        else:
            # Retracement levels in downtrend
            levels = {
                '0.0': swing_low,
                '23.6': swing_low + 0.236 * diff,
                '38.2': swing_low + 0.382 * diff,
                '50.0': swing_low + 0.500 * diff,
                '61.8': swing_low + 0.618 * diff,
                '78.6': swing_low + 0.786 * diff,
                '100.0': swing_high,
                # Extensions
                'ext_127.2': swing_low - 0.272 * diff,
                'ext_161.8': swing_low - 0.618 * diff,
                'ext_261.8': swing_low - 1.618 * diff,
            }
            direction = "downtrend"

        return {
            'levels': levels,
            'direction': direction,
            'swing_high': swing_high,
            'swing_low': swing_low
        }

    @staticmethod
    def volume_profile(close: pd.Series, volume: pd.Series,
                       bins: int = 20) -> Dict[str, float]:
        """Calculate Volume Profile POC and Value Area"""
        if len(close) < 50:
            return {}

        price_range = close.max() - close.min()
        if price_range == 0:
            return {}

        bin_size = price_range / bins
        volume_at_price = {}

        for i in range(len(close)):
            price_bin = int((close.iloc[i] - close.min()) / bin_size)
            price_bin = min(price_bin, bins - 1)
            bin_price = close.min() + (price_bin + 0.5) * bin_size
            volume_at_price[bin_price] = volume_at_price.get(bin_price, 0) + volume.iloc[i]

        # Point of Control (POC) - price level with highest volume
        poc = max(volume_at_price, key=volume_at_price.get)

        # Value Area (70% of volume)
        total_vol = sum(volume_at_price.values())
        sorted_prices = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)

        va_vol = 0
        va_prices = []
        for price, vol in sorted_prices:
            va_prices.append(price)
            va_vol += vol
            if va_vol >= total_vol * 0.7:
                break

        return {
            'poc': poc,
            'vah': max(va_prices) if va_prices else poc,
            'val': min(va_prices) if va_prices else poc
        }

    @staticmethod
    def whale_detection(volume: pd.Series, lookback: int = 20,
                       threshold: float = 3.0) -> Tuple[bool, float]:
        """
        Detect unusual volume spikes that may indicate whale activity
        Returns: (is_whale_activity, volume_ratio)
        """
        if len(volume) < lookback:
            return False, 0.0

        avg_volume = volume.iloc[-lookback:-1].mean()
        current_volume = volume.iloc[-1]

        if avg_volume == 0:
            return False, 0.0

        ratio = current_volume / avg_volume
        is_whale = ratio >= threshold

        return is_whale, ratio

    @staticmethod
    def awesome_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
        """Awesome Oscillator (AO) — median price SMA5 minus SMA34"""
        median = (high + low) / 2
        return Indicators.sma(median, 5) - Indicators.sma(median, 34)

    @staticmethod
    def accelerator_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
        """Accelerator Oscillator (AC) — AO minus SMA5 of AO"""
        ao = Indicators.awesome_oscillator(high, low)
        return ao - Indicators.sma(ao, 5)

    @staticmethod
    def candlestick_patterns(open_: pd.Series, high: pd.Series,
                              low: pd.Series, close: pd.Series) -> Dict[str, bool]:
        """Detect common candlestick reversal patterns. Returns dict of pattern name → bool."""
        if len(close) < 3:
            return {}

        o,  h,  l,  c  = open_.iloc[-1], high.iloc[-1], low.iloc[-1], close.iloc[-1]
        po, ph, pl, pc = open_.iloc[-2], high.iloc[-2], low.iloc[-2], close.iloc[-2]
        ppo, _,  _,  ppc = open_.iloc[-3], high.iloc[-3], low.iloc[-3], close.iloc[-3]

        body       = abs(c - o)
        full_range = h - l if h > l else 1e-10
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        prev_body  = abs(pc - po)
        prev_range = ph - pl if ph > pl else 1e-10

        patterns: Dict[str, bool] = {}

        # Hammer (bullish reversal): small body at top, lower wick >= 2× body
        patterns['hammer'] = (
            lower_wick >= 2 * body and
            upper_wick <= body * 0.5 and
            body / full_range >= 0.1 and
            c >= o  # prefer green
        )

        # Shooting Star (bearish reversal): small body at bottom, upper wick >= 2× body
        patterns['shooting_star'] = (
            upper_wick >= 2 * body and
            lower_wick <= body * 0.5 and
            body / full_range >= 0.1 and
            c <= o  # prefer red
        )

        # Bullish Engulfing: current green fully engulfs prior red candle
        patterns['bull_engulfing'] = (
            c > o and pc < po and   # current green, prior red
            c > po and o < pc       # current body wraps prior body
        )

        # Bearish Engulfing: current red fully engulfs prior green candle
        patterns['bear_engulfing'] = (
            c < o and pc > po and   # current red, prior green
            o > pc and c < po       # current body wraps prior body
        )

        # Doji: body <= 10% of range (indecision / potential reversal)
        patterns['doji'] = body <= full_range * 0.1

        # Morning Star (3-candle bullish): red → small-body → green closing above midpoint
        ppbody = abs(ppc - ppo)
        patterns['morning_star'] = (
            ppc < ppo and                          # candle-3: red
            prev_body <= prev_range * 0.3 and      # candle-2: small/doji
            c > o and                              # candle-1: green
            c > (ppo + ppc) / 2                    # closes above midpoint of red candle
        )

        # Evening Star (3-candle bearish): green → small-body → red closing below midpoint
        patterns['evening_star'] = (
            ppc > ppo and                          # candle-3: green
            prev_body <= prev_range * 0.3 and      # candle-2: small/doji
            c < o and                              # candle-1: red
            c < (ppo + ppc) / 2                    # closes below midpoint of green candle
        )

        return patterns

    @staticmethod
    def choppiness_index(high: pd.Series, low: pd.Series, close: pd.Series,
                         period: int = 14) -> pd.Series:
        """Choppiness Index — measures trending vs ranging market.
        > 61.8 = choppy/ranging (suppress signals), < 38.2 = strongly trending (ideal for signals).
        v4.0: Hard regime gate."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_sum = tr.rolling(period).sum()
        highest = high.rolling(period).max()
        lowest = low.rolling(period).min()
        price_range = (highest - lowest).replace(0, np.nan)
        chop = 100 * np.log10(atr_sum / price_range) / np.log10(period)
        return chop.fillna(50.0)

    @staticmethod
    def heikin_ashi(open_: pd.Series, high: pd.Series, low: pd.Series,
                    close: pd.Series) -> tuple:
        """Convert OHLC to Heikin Ashi candles for cleaner trend signals.
        v4.0: EMA and SuperTrend run on HA candles to reduce whipsaw noise."""
        ha_close = (open_ + high + low + close) / 4
        ha_open = pd.Series(index=open_.index, dtype=float)
        ha_open.iloc[0] = (open_.iloc[0] + close.iloc[0]) / 2
        for i in range(1, len(open_)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
        ha_high = pd.concat([high, ha_open, ha_close], axis=1).max(axis=1)
        ha_low = pd.concat([low, ha_open, ha_close], axis=1).min(axis=1)
        return ha_open, ha_high, ha_low, ha_close

    @staticmethod
    def detect_bos_choch(high: pd.Series, low: pd.Series, close: pd.Series,
                          lookback: int = 20) -> dict:
        """v5.0: Detect ICT Break of Structure (BOS) and Change of Character (CHoCH).
        BOS  = price breaks above recent swing high (bull) or below swing low (bear).
        CHoCH = BOS that runs counter to the prior dominant structure (reversal signal)."""
        result = {'bos_bull': False, 'bos_bear': False, 'choch_bull': False, 'choch_bear': False}
        if len(close) < lookback + 5:
            return result
        try:
            # Swing high/low of the lookback window (excluding last bar)
            window_high = high.iloc[-(lookback+1):-1]
            window_low  = low.iloc[-(lookback+1):-1]
            swing_high = float(window_high.max())
            swing_low  = float(window_low.min())
            cur_close  = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])

            # --- BOS detection ---
            bos_bull = cur_close > swing_high and prev_close <= swing_high
            bos_bear = cur_close < swing_low  and prev_close >= swing_low
            result['bos_bull'] = bos_bull
            result['bos_bear'] = bos_bear

            # --- Structure bias over lookback (is market making HH or LL?) ---
            # Compare first-half vs second-half of the lookback window
            mid = lookback // 2
            first_half_high = float(high.iloc[-(lookback+1):-mid-1].max())
            second_half_high = float(high.iloc[-mid-1:-1].max())
            first_half_low  = float(low.iloc[-(lookback+1):-mid-1].min())
            second_half_low  = float(low.iloc[-mid-1:-1].min())

            prior_structure_bull = second_half_high > first_half_high  # market making HH
            prior_structure_bear = second_half_low  < first_half_low   # market making LL

            # CHoCH = BOS that goes against the dominant prior structure
            if bos_bull and prior_structure_bear:
                result['choch_bull'] = True  # was bearish, now breaks up = bullish flip
            if bos_bear and prior_structure_bull:
                result['choch_bear'] = True  # was bullish, now breaks down = bearish flip
        except Exception:
            pass
        return result

    @staticmethod
    def detect_fvg(high: pd.Series, low: pd.Series, lookback: int = 10) -> dict:
        """v5.0: Detect Fair Value Gap (FVG) — 3-candle imbalance zones.
        Bullish FVG: candle[-3].high < candle[-1].low  (gap above old high, unvisited supply).
        Bearish FVG: candle[-3].low  > candle[-1].high (gap below old low,  unvisited demand).
        Also check if price is currently inside a recent FVG (returning-to-fill = confluence)."""
        result = {'fvg_bull': False, 'fvg_bear': False, 'fvg_gap_pct': 0.0}
        if len(high) < lookback + 3:
            return result
        try:
            cur_high  = float(high.iloc[-1])
            cur_low   = float(low.iloc[-1])
            # Check last `lookback` sets of 3-bar patterns for recent FVGs
            for i in range(3, lookback + 3):
                h3 = float(high.iloc[-i])     # oldest of the 3 bars
                l3 = float(low.iloc[-i])
                h1 = float(high.iloc[-i+2])   # newest of the 3 bars
                l1 = float(low.iloc[-i+2])
                mid_val = (h1 + l1) / 2
                if mid_val == 0:
                    continue
                # Bullish FVG: gap between high[-3] and low[-1]
                if l1 > h3:  # gap exists above old high
                    gap_pct = (l1 - h3) / mid_val * 100
                    # Price currently in or touching the FVG = extra confluence
                    if cur_low <= l1 and cur_high >= h3:
                        result['fvg_bull'] = True
                        result['fvg_gap_pct'] = round(gap_pct, 3)
                        break
                # Bearish FVG: gap between low[-3] and high[-1]
                if h1 < l3:  # gap exists below old low
                    gap_pct = (l3 - h1) / mid_val * 100
                    if cur_high >= h1 and cur_low <= l3:
                        result['fvg_bear'] = True
                        result['fvg_gap_pct'] = round(gap_pct, 3)
                        break
        except Exception:
            pass
        return result


# ============================================================================
# SIGNAL ANALYSIS ENGINE
# ============================================================================

@dataclass
class SignalResult:
    """Container for signal analysis results"""
    ticker: str
    timestamp: datetime.datetime
    price: float
    signal_type: SignalType
    score: float  # 0-100
    confidence: str  # Low, Medium, High
    signals: List[str]
    reasons: List[str]
    metrics: Dict[str, Any]
    targets: Dict[str, float]
    stop_loss: float
    risk_reward: float
    timeframe_alignment: bool


class SignalEngine:
    """Advanced signal generation and scoring engine"""

    # Signal weights for scoring (sum should enable max 100)
    SIGNAL_WEIGHTS = {
        'trend_ema': 8,
        'trend_supertrend': 7,
        'trend_ichimoku': 7,
        'trend_adx': 6,
        'momentum_rsi': 6,
        'momentum_macd': 7,
        'momentum_stoch': 5,
        'momentum_mfi': 5,
        'momentum_williams': 4,
        'momentum_cci': 4,
        'volume_spike': 6,
        'volume_obv': 5,
        'volume_whale': 5,
        'volatility_bb': 5,
        'volatility_atr': 4,
        'support_resistance_fib': 6,
        'support_resistance_pivot': 5,
        'support_resistance_vwap': 5,
        'momentum_ac': 5,
        'divergence_rsi': 8,
        'divergence_macd': 7,
        'timeframe_alignment': 10,
        # v3.0 additions
        'candle_pattern_strong': 8,   # engulfing / morning/evening star
        'candle_pattern_weak': 4,     # hammer / shooting star / doji
        # v4.0 additions
        'funding_rate_contrarian': 6,  # extreme funding rate = contrarian signal
        'liquidation_cascade': 7,      # liquidation cluster = directional confirmation
        'long_short_ratio': 5,         # crowded positioning = contrarian signal
        'consecutive_candle': 5,       # signal confirmed on previous candle too
        # v5.0 ICT/SMC additions
        'ict_bos': 8,                  # Break of Structure — price breaks swing high/low
        'ict_choch': 9,                # Change of Character — BOS counter to current structure
        'ict_fvg': 7,                  # Fair Value Gap — 3-candle price imbalance zone
    }

    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def analyze(self, ticker: str, df_primary: pd.DataFrame,
                df_secondary: pd.DataFrame = None,
                df_tertiary: pd.DataFrame = None,
                btc_df: pd.DataFrame = None,
                fear_greed: Optional[int] = None,
                brain_multiplier: float = 1.0,
                contract_data: Optional[dict] = None,
                liquidations: Optional[list] = None) -> Optional[SignalResult]:
        """
        Perform comprehensive signal analysis
        """
        if df_primary is None or len(df_primary) < 100:
            return None

        close = df_primary['close']
        high = df_primary['high']
        low = df_primary['low']
        volume = df_primary['volume_base']
        open_ = df_primary.get('open', close)
        price = close.iloc[-1]

        signals = []
        reasons = []
        bull_score = 0
        bear_score = 0

        # ===== v4.0: CHOPPINESS INDEX HARD GATE =====
        # If market is ranging (CHOP > 61.8), suppress signals — most false signals come from choppy markets
        chop = Indicators.choppiness_index(high, low, close)
        chop_val = chop.iloc[-1] if pd.notna(chop.iloc[-1]) else 50.0
        chop_penalty = 1.0
        if chop_val > 61.8:
            chop_penalty = 0.35  # Strong suppression — market is choppy
            reasons.append(f"⚠️ CHOP {chop_val:.1f} (>61.8 = ranging) — signal suppressed 65%")
        elif chop_val > 55:
            chop_penalty = 0.65  # Moderate suppression
            reasons.append(f"⚠️ CHOP {chop_val:.1f} (mildly choppy) — signal reduced 35%")
        elif chop_val < 38.2:
            chop_penalty = 1.15  # Boost in strongly trending markets
            reasons.append(f"✅ CHOP {chop_val:.1f} (<38.2 = strong trend) — signal boosted 15%")

        # ===== v4.0: HEIKIN ASHI CANDLES for trend indicators =====
        # Run EMA and SuperTrend on HA candles — far less whipsaw noise
        ha_open, ha_high, ha_low, ha_close = Indicators.heikin_ashi(open_, high, low, close)

        # ===== TREND INDICATORS =====

        # EMA Trend — v4.0: use Heikin Ashi close for cleaner signals
        ema20 = Indicators.ema(ha_close, 20).iloc[-1]
        ema50 = Indicators.ema(ha_close, 50).iloc[-1]
        ema200 = Indicators.ema(ha_close, 200).iloc[-1]

        if price > ema20 > ema50 > ema200:
            bull_score += self.SIGNAL_WEIGHTS['trend_ema']
            signals.append("EMA Bullish Stack (20>50>200)")
            reasons.append(f"Strong uptrend: Price ${price:.6f} > EMA20 > EMA50 > EMA200")
        elif price < ema20 < ema50 < ema200:
            bear_score += self.SIGNAL_WEIGHTS['trend_ema']
            signals.append("EMA Bearish Stack (20<50<200)")
            reasons.append(f"Strong downtrend: Price ${price:.6f} < EMA20 < EMA50 < EMA200")

        # SuperTrend — v4.0: use Heikin Ashi candles for cleaner trend
        supertrend, st_direction = Indicators.supertrend(ha_high, ha_low, ha_close)
        if pd.notna(st_direction.iloc[-1]):
            if st_direction.iloc[-1] == 1:
                bull_score += self.SIGNAL_WEIGHTS['trend_supertrend']
                signals.append("SuperTrend Bullish")
                reasons.append(f"SuperTrend support at ${supertrend.iloc[-1]:.6f}")
            else:
                bear_score += self.SIGNAL_WEIGHTS['trend_supertrend']
                signals.append("SuperTrend Bearish")
                reasons.append(f"SuperTrend resistance at ${supertrend.iloc[-1]:.6f}")

        # Ichimoku
        ichi = Indicators.ichimoku(high, low, close)
        cloud_top = max(ichi['senkou_a'].iloc[-1], ichi['senkou_b'].iloc[-1]) if pd.notna(ichi['senkou_a'].iloc[-1]) else np.nan
        cloud_bottom = min(ichi['senkou_a'].iloc[-1], ichi['senkou_b'].iloc[-1]) if pd.notna(ichi['senkou_a'].iloc[-1]) else np.nan

        if pd.notna(cloud_top):
            if price > cloud_top:
                bull_score += self.SIGNAL_WEIGHTS['trend_ichimoku']
                signals.append("Above Ichimoku Cloud")
                reasons.append(f"Price above cloud (top: ${cloud_top:.6f})")
            elif price < cloud_bottom:
                bear_score += self.SIGNAL_WEIGHTS['trend_ichimoku']
                signals.append("Below Ichimoku Cloud")
                reasons.append(f"Price below cloud (bottom: ${cloud_bottom:.6f})")

        # ADX Trend Strength
        adx, plus_di, minus_di = Indicators.adx(high, low, close)
        adx_value = adx.iloc[-1] if pd.notna(adx.iloc[-1]) else 0

        if adx_value > 25:
            if plus_di.iloc[-1] > minus_di.iloc[-1]:
                bull_score += self.SIGNAL_WEIGHTS['trend_adx']
                signals.append(f"ADX Strong Uptrend ({adx_value:.1f})")
                reasons.append(f"ADX {adx_value:.1f} with +DI > -DI (strong bullish)")
            else:
                bear_score += self.SIGNAL_WEIGHTS['trend_adx']
                signals.append(f"ADX Strong Downtrend ({adx_value:.1f})")
                reasons.append(f"ADX {adx_value:.1f} with -DI > +DI (strong bearish)")

        # ===== MOMENTUM INDICATORS =====

        # RSI
        rsi = Indicators.rsi(close).iloc[-1]
        if rsi < 30:
            bull_score += self.SIGNAL_WEIGHTS['momentum_rsi']
            signals.append(f"RSI Oversold ({rsi:.1f})")
            reasons.append(f"RSI at {rsi:.1f} - potential reversal zone")
        elif rsi > 70:
            bear_score += self.SIGNAL_WEIGHTS['momentum_rsi']
            signals.append(f"RSI Overbought ({rsi:.1f})")
            reasons.append(f"RSI at {rsi:.1f} - potential reversal zone")
        elif 50 < rsi < 70:
            bull_score += self.SIGNAL_WEIGHTS['momentum_rsi'] * 0.3
        elif 30 < rsi < 50:
            bear_score += self.SIGNAL_WEIGHTS['momentum_rsi'] * 0.3

        # MACD
        macd_line, macd_signal, macd_hist = Indicators.macd(close)
        macd_bull = macd_line.iloc[-1] > macd_signal.iloc[-1] and macd_hist.iloc[-1] > 0
        macd_bear = macd_line.iloc[-1] < macd_signal.iloc[-1] and macd_hist.iloc[-1] < 0

        # MACD crossover detection
        macd_cross_up = (macd_line.iloc[-1] > macd_signal.iloc[-1] and
                        macd_line.iloc[-2] <= macd_signal.iloc[-2])
        macd_cross_down = (macd_line.iloc[-1] < macd_signal.iloc[-1] and
                          macd_line.iloc[-2] >= macd_signal.iloc[-2])

        if macd_cross_up:
            bull_score += self.SIGNAL_WEIGHTS['momentum_macd']
            signals.append("MACD Bullish Crossover")
            reasons.append("MACD line crossed above signal line")
        elif macd_cross_down:
            bear_score += self.SIGNAL_WEIGHTS['momentum_macd']
            signals.append("MACD Bearish Crossover")
            reasons.append("MACD line crossed below signal line")
        elif macd_bull:
            bull_score += self.SIGNAL_WEIGHTS['momentum_macd'] * 0.5
            signals.append("MACD Bullish")
        elif macd_bear:
            bear_score += self.SIGNAL_WEIGHTS['momentum_macd'] * 0.5
            signals.append("MACD Bearish")

        # Stochastic
        stoch_k, stoch_d = Indicators.stochastic(high, low, close)
        stoch_k_val = stoch_k.iloc[-1]
        stoch_d_val = stoch_d.iloc[-1]

        if stoch_k_val < 20 and stoch_k_val > stoch_d_val:
            bull_score += self.SIGNAL_WEIGHTS['momentum_stoch']
            signals.append(f"Stoch Oversold Reversal (K:{stoch_k_val:.1f})")
            reasons.append(f"Stochastic %K {stoch_k_val:.1f} crossing above %D from oversold")
        elif stoch_k_val > 80 and stoch_k_val < stoch_d_val:
            bear_score += self.SIGNAL_WEIGHTS['momentum_stoch']
            signals.append(f"Stoch Overbought Reversal (K:{stoch_k_val:.1f})")
            reasons.append(f"Stochastic %K {stoch_k_val:.1f} crossing below %D from overbought")

        # MFI (Money Flow Index)
        mfi = Indicators.mfi(high, low, close, volume).iloc[-1]
        if pd.notna(mfi):
            if mfi < 20:
                bull_score += self.SIGNAL_WEIGHTS['momentum_mfi']
                signals.append(f"MFI Oversold ({mfi:.1f})")
                reasons.append(f"Money Flow Index at {mfi:.1f} - oversold with volume")
            elif mfi > 80:
                bear_score += self.SIGNAL_WEIGHTS['momentum_mfi']
                signals.append(f"MFI Overbought ({mfi:.1f})")
                reasons.append(f"Money Flow Index at {mfi:.1f} - overbought with volume")

        # Williams %R
        williams = Indicators.williams_r(high, low, close).iloc[-1]
        if pd.notna(williams):
            if williams < -80:
                bull_score += self.SIGNAL_WEIGHTS['momentum_williams']
                signals.append(f"Williams %R Oversold ({williams:.1f})")
            elif williams > -20:
                bear_score += self.SIGNAL_WEIGHTS['momentum_williams']
                signals.append(f"Williams %R Overbought ({williams:.1f})")

        # CCI
        cci = Indicators.cci(high, low, close).iloc[-1]
        if pd.notna(cci):
            if cci < -100:
                bull_score += self.SIGNAL_WEIGHTS['momentum_cci']
                signals.append(f"CCI Oversold ({cci:.1f})")
            elif cci > 100:
                bear_score += self.SIGNAL_WEIGHTS['momentum_cci']
                signals.append(f"CCI Overbought ({cci:.1f})")

        # Accelerator Oscillator
        ac = Indicators.accelerator_oscillator(high, low)
        if len(ac) >= 3 and pd.notna(ac.iloc[-1]):
            ac_val = ac.iloc[-1]
            ac_prev = ac.iloc[-2]
            # Bullish: AC positive and rising (or crossing from negative to positive)
            if ac_val > 0 and ac_val > ac_prev:
                bull_score += self.SIGNAL_WEIGHTS['momentum_ac']
                signals.append(f"AC Bullish ({ac_val:.6f})")
                reasons.append("Accelerator Oscillator positive and rising — momentum accelerating up")
            # Bearish: AC negative and falling
            elif ac_val < 0 and ac_val < ac_prev:
                bear_score += self.SIGNAL_WEIGHTS['momentum_ac']
                signals.append(f"AC Bearish ({ac_val:.6f})")
                reasons.append("Accelerator Oscillator negative and falling — momentum accelerating down")

        # ===== CANDLESTICK PATTERNS (v3.0) =====

        if 'open' in df_primary.columns:
            candle_open = df_primary['open']
        else:
            candle_open = close  # fallback if open not present
        candle_patterns = Indicators.candlestick_patterns(candle_open, high, low, close)

        bull_candle = candle_patterns.get('hammer') or candle_patterns.get('bull_engulfing') or candle_patterns.get('morning_star')
        bear_candle = candle_patterns.get('shooting_star') or candle_patterns.get('bear_engulfing') or candle_patterns.get('evening_star')
        strong_candle = candle_patterns.get('bull_engulfing') or candle_patterns.get('bear_engulfing') or candle_patterns.get('morning_star') or candle_patterns.get('evening_star')

        if bull_candle:
            pts = self.SIGNAL_WEIGHTS['candle_pattern_strong'] if strong_candle else self.SIGNAL_WEIGHTS['candle_pattern_weak']
            pattern_name = "Bullish Engulfing" if candle_patterns.get('bull_engulfing') else \
                           "Morning Star" if candle_patterns.get('morning_star') else \
                           "Hammer" if candle_patterns.get('hammer') else "Doji"
            bull_score += pts
            signals.append(f"🕯 {pattern_name}")
            reasons.append(f"Candlestick pattern: {pattern_name} — bullish reversal signal")
        elif bear_candle:
            pts = self.SIGNAL_WEIGHTS['candle_pattern_strong'] if strong_candle else self.SIGNAL_WEIGHTS['candle_pattern_weak']
            pattern_name = "Bearish Engulfing" if candle_patterns.get('bear_engulfing') else \
                           "Evening Star" if candle_patterns.get('evening_star') else \
                           "Shooting Star" if candle_patterns.get('shooting_star') else "Doji"
            bear_score += pts
            signals.append(f"🕯 {pattern_name}")
            reasons.append(f"Candlestick pattern: {pattern_name} — bearish reversal signal")
        elif candle_patterns.get('doji'):
            signals.append("🕯 Doji (indecision)")

        # ===== VOLUME INDICATORS =====

        # Volume Spike
        vol_ma = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / vol_ma if vol_ma > 0 else 0

        if vol_ratio > self.config.vol_threshold:
            price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
            if price_change > 0:
                bull_score += self.SIGNAL_WEIGHTS['volume_spike']
                signals.append(f"Volume Spike Bullish ({vol_ratio:.1f}x)")
                reasons.append(f"Volume {vol_ratio:.1f}x average on up move")
            else:
                bear_score += self.SIGNAL_WEIGHTS['volume_spike']
                signals.append(f"Volume Spike Bearish ({vol_ratio:.1f}x)")
                reasons.append(f"Volume {vol_ratio:.1f}x average on down move")

        # OBV Trend
        obv = Indicators.obv(close, volume)
        obv_ema = Indicators.ema(obv, 20)
        if obv.iloc[-1] > obv_ema.iloc[-1] and obv.iloc[-1] > obv.iloc[-5]:
            bull_score += self.SIGNAL_WEIGHTS['volume_obv']
            signals.append("OBV Rising")
            reasons.append("On-Balance Volume trending up (accumulation)")
        elif obv.iloc[-1] < obv_ema.iloc[-1] and obv.iloc[-1] < obv.iloc[-5]:
            bear_score += self.SIGNAL_WEIGHTS['volume_obv']
            signals.append("OBV Falling")
            reasons.append("On-Balance Volume trending down (distribution)")

        # Volume RSI — RSI applied to volume to detect volume momentum
        vol_rsi = Indicators.rsi(volume).iloc[-1]
        vol_rsi = vol_rsi if pd.notna(vol_rsi) else 50.0

        # Whale Detection
        is_whale, whale_ratio = Indicators.whale_detection(volume)
        if is_whale:
            signals.append(f"🐋 Whale Activity ({whale_ratio:.1f}x)")
            reasons.append(f"Unusual volume spike {whale_ratio:.1f}x - possible whale activity")
            # Add to appropriate direction based on price action
            if close.iloc[-1] > close.iloc[-2]:
                bull_score += self.SIGNAL_WEIGHTS['volume_whale']
            else:
                bear_score += self.SIGNAL_WEIGHTS['volume_whale']

        # ===== VOLATILITY INDICATORS =====

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = Indicators.bollinger_bands(close)
        bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1] * 100

        if price <= bb_lower.iloc[-1]:
            bull_score += self.SIGNAL_WEIGHTS['volatility_bb']
            signals.append("BB Lower Band Touch")
            reasons.append(f"Price at lower Bollinger Band (${bb_lower.iloc[-1]:.6f})")
        elif price >= bb_upper.iloc[-1]:
            bear_score += self.SIGNAL_WEIGHTS['volatility_bb']
            signals.append("BB Upper Band Touch")
            reasons.append(f"Price at upper Bollinger Band (${bb_upper.iloc[-1]:.6f})")

        # ATR for volatility assessment
        atr = Indicators.atr(high, low, close).iloc[-1]
        atr_pct = (atr / price) * 100

        # ===== SUPPORT/RESISTANCE =====

        # Fibonacci Levels
        fib_data = Indicators.fibonacci_levels(high, low, close, self.config.lookback_swing)
        near_fib = None
        fib_level_name = None

        if fib_data and 'levels' in fib_data:
            for level_name, level_price in fib_data['levels'].items():
                if not level_name.startswith('ext_'):
                    pct_diff = abs(price - level_price) / price * 100
                    if pct_diff <= self.config.fib_tolerance_pct:
                        near_fib = level_price
                        fib_level_name = level_name
                        if fib_data['direction'] == 'uptrend' and level_name in ['38.2', '50.0', '61.8']:
                            bull_score += self.SIGNAL_WEIGHTS['support_resistance_fib']
                            signals.append(f"Fib {level_name}% Support")
                            reasons.append(f"Price near {level_name}% Fib retracement (${level_price:.6f})")
                        elif fib_data['direction'] == 'downtrend' and level_name in ['38.2', '50.0', '61.8']:
                            bear_score += self.SIGNAL_WEIGHTS['support_resistance_fib']
                            signals.append(f"Fib {level_name}% Resistance")
                            reasons.append(f"Price near {level_name}% Fib retracement (${level_price:.6f})")
                        break

        # Pivot Points
        pivots = Indicators.pivot_points(high, low, close)
        for level_name, level_price in pivots.items():
            pct_diff = abs(price - level_price) / price * 100
            if pct_diff <= 0.5:  # Within 0.5% of pivot level
                if level_name.startswith('s'):
                    bull_score += self.SIGNAL_WEIGHTS['support_resistance_pivot']
                    signals.append(f"Near Pivot {level_name.upper()}")
                    reasons.append(f"Price near support {level_name.upper()} (${level_price:.6f})")
                elif level_name.startswith('r'):
                    bear_score += self.SIGNAL_WEIGHTS['support_resistance_pivot']
                    signals.append(f"Near Pivot {level_name.upper()}")
                    reasons.append(f"Price near resistance {level_name.upper()} (${level_price:.6f})")
                break

        # VWAP
        vwap = Indicators.vwap(high, low, close, volume).iloc[-1]
        vwap_pct_diff = (price - vwap) / vwap * 100

        if abs(vwap_pct_diff) < 0.5:
            signals.append("At VWAP")
        elif vwap_pct_diff > 1:
            bull_score += self.SIGNAL_WEIGHTS['support_resistance_vwap'] * 0.5
            signals.append("Above VWAP")
        elif vwap_pct_diff < -1:
            bear_score += self.SIGNAL_WEIGHTS['support_resistance_vwap'] * 0.5
            signals.append("Below VWAP")

        # ===== DIVERGENCES =====

        # RSI Divergence
        rsi_series = Indicators.rsi(close)
        rsi_bull_div, rsi_bear_div = Indicators.detect_divergence(close, rsi_series)

        if rsi_bull_div:
            bull_score += self.SIGNAL_WEIGHTS['divergence_rsi']
            signals.append("🔄 RSI Bullish Divergence")
            reasons.append("Price making lower lows while RSI making higher lows")
        elif rsi_bear_div:
            bear_score += self.SIGNAL_WEIGHTS['divergence_rsi']
            signals.append("🔄 RSI Bearish Divergence")
            reasons.append("Price making higher highs while RSI making lower highs")

        # MACD Divergence
        macd_bull_div, macd_bear_div = Indicators.detect_divergence(close, macd_hist)

        if macd_bull_div:
            bull_score += self.SIGNAL_WEIGHTS['divergence_macd']
            signals.append("🔄 MACD Bullish Divergence")
            reasons.append("Price making lower lows while MACD histogram making higher lows")
        elif macd_bear_div:
            bear_score += self.SIGNAL_WEIGHTS['divergence_macd']
            signals.append("🔄 MACD Bearish Divergence")
            reasons.append("Price making higher highs while MACD histogram making lower highs")

        # ===== MULTI-TIMEFRAME ANALYSIS =====

        timeframe_alignment = False
        if df_secondary is not None and len(df_secondary) >= 50:
            sec_close = df_secondary['close']
            sec_ema20 = Indicators.ema(sec_close, 20).iloc[-1]
            sec_ema50 = Indicators.ema(sec_close, 50).iloc[-1]
            sec_rsi = Indicators.rsi(sec_close).iloc[-1]

            # Check alignment
            primary_bullish = bull_score > bear_score
            secondary_bullish = sec_close.iloc[-1] > sec_ema20 and sec_rsi > 50

            if primary_bullish and secondary_bullish:
                timeframe_alignment = True
                bull_score += self.SIGNAL_WEIGHTS['timeframe_alignment']
                signals.append(f"✅ {self.config.secondary_timeframe} Aligned Bullish")
                reasons.append(f"Higher timeframe ({self.config.secondary_timeframe}) confirms bullish bias")
            elif not primary_bullish and not secondary_bullish:
                timeframe_alignment = True
                bear_score += self.SIGNAL_WEIGHTS['timeframe_alignment']
                signals.append(f"✅ {self.config.secondary_timeframe} Aligned Bearish")
                reasons.append(f"Higher timeframe ({self.config.secondary_timeframe}) confirms bearish bias")

        # ===== BTC DOMINANCE CONTEXT =====

        btc_context = "neutral"
        if btc_df is not None and len(btc_df) >= 20 and ticker != 'BTC_USDT':
            btc_change = (btc_df['close'].iloc[-1] / btc_df['close'].iloc[-20] - 1) * 100
            alt_change = (close.iloc[-1] / close.iloc[-20] - 1) * 100

            if btc_change > alt_change + 2:
                btc_context = "btc_dominant"
                reasons.append("BTC outperforming - caution on alt longs")
            elif alt_change > btc_change + 2:
                btc_context = "alt_season"
                if bull_score > bear_score:
                    bull_score += 3
                reasons.append("Alt outperforming BTC - favorable for alt longs")

        # ===== BTC REGIME GATE (v3.0) =====
        # Suppress buy signals when BTC is in a confirmed downtrend

        btc_regime = "neutral"
        if btc_df is not None and len(btc_df) >= 50 and ticker != 'BTC_USDT':
            btc_close_series = btc_df['close']
            btc_ema20 = Indicators.ema(btc_close_series, 20).iloc[-1]
            btc_ema50 = Indicators.ema(btc_close_series, 50).iloc[-1]
            btc_price_now = btc_close_series.iloc[-1]

            if btc_price_now < btc_ema20 < btc_ema50:
                btc_regime = "downtrend"
                bull_score *= 0.75
                reasons.append("⚠️ BTC regime: DOWNTREND — bull score -25%")
            elif btc_price_now > btc_ema20 > btc_ema50:
                btc_regime = "uptrend"
                bull_score *= 1.10
                reasons.append("✅ BTC regime: UPTREND — bull score +10%")

        # ===== FEAR & GREED FILTER (v3.0) =====

        if fear_greed is not None:
            if fear_greed >= 80:
                bull_score *= 0.85
                reasons.append(f"⚠️ Fear & Greed {fear_greed} (Extreme Greed) — bull -15%")
            elif fear_greed <= 20 and rsi > 35:
                bull_score *= 0.90
                reasons.append(f"⚠️ Fear & Greed {fear_greed} (Extreme Fear) — bull -10%")
            elif fear_greed <= 20 and rsi <= 35:
                bull_score *= 1.05
                reasons.append(f"📊 Fear & Greed {fear_greed} (Extreme Fear + RSI oversold) — contrarian +5%")

        # ===== BRAIN MULTIPLIER (v3.0) =====
        if brain_multiplier != 1.0:
            bull_score *= brain_multiplier
            bear_score *= brain_multiplier

        # ===== v4.0: CHOPPINESS PENALTY =====
        bull_score *= chop_penalty
        bear_score *= chop_penalty

        # ===== v4.0: CONSECUTIVE CANDLE CONFIRMATION =====
        # Signal must agree with previous candle direction — kills single-candle whipsaws
        if len(close) >= 3:
            prev_rsi = Indicators.rsi(close).iloc[-2]
            prev_macd_line, prev_macd_signal, prev_macd_hist = Indicators.macd(close)
            prev_ema20 = Indicators.ema(ha_close, 20).iloc[-2]
            prev_bull = (prev_rsi < 45 or
                        (prev_macd_hist.iloc[-2] > 0 and prev_macd_hist.iloc[-3] > 0) or
                        ha_close.iloc[-2] > prev_ema20)
            prev_bear = (prev_rsi > 55 or
                        (prev_macd_hist.iloc[-2] < 0 and prev_macd_hist.iloc[-3] < 0) or
                        ha_close.iloc[-2] < prev_ema20)
            current_bullish = bull_score > bear_score
            if current_bullish and prev_bull:
                bull_score += self.SIGNAL_WEIGHTS['consecutive_candle']
                signals.append("✅ Consecutive Candle Confirmed (Bullish)")
                reasons.append("Signal aligned on both current and previous candle — not a whipsaw")
            elif not current_bullish and prev_bear:
                bear_score += self.SIGNAL_WEIGHTS['consecutive_candle']
                signals.append("✅ Consecutive Candle Confirmed (Bearish)")
                reasons.append("Signal aligned on both current and previous candle — not a whipsaw")

        # ===== v4.0: FUNDING RATE CONTRARIAN SIGNAL =====
        # Extreme funding rates mean one side is over-leveraged → contrarian opportunity
        funding_rate = contract_data.get('funding_rate') if contract_data else None
        if funding_rate is not None:
            if funding_rate > 0.0008:  # Very high positive = longs overloaded = bearish contrarian
                bear_score += self.SIGNAL_WEIGHTS['funding_rate_contrarian']
                signals.append(f"💰 Funding Rate Extreme Positive ({funding_rate*100:.4f}%)")
                reasons.append(f"Funding {funding_rate*100:.4f}% — longs overloaded, short squeeze risk low, bearish contrarian")
            elif funding_rate < -0.0003:  # Negative = shorts overloaded = bullish contrarian
                bull_score += self.SIGNAL_WEIGHTS['funding_rate_contrarian']
                signals.append(f"💰 Funding Rate Negative ({funding_rate*100:.4f}%)")
                reasons.append(f"Funding {funding_rate*100:.4f}% — shorts overloaded, potential squeeze = bullish")
            elif -0.0001 < funding_rate < 0.0001:
                reasons.append(f"📊 Funding rate neutral ({funding_rate*100:.4f}%)")

        # ===== v4.0: LONG/SHORT RATIO =====
        if contract_data:
            long_size = contract_data.get('long_size', 0)
            short_size = contract_data.get('short_size', 0)
            total_size = long_size + short_size
            if total_size > 0:
                long_ratio = long_size / total_size
                if long_ratio > 0.65:  # >65% long = crowded long = contrarian bearish
                    bear_score += self.SIGNAL_WEIGHTS['long_short_ratio'] * 0.5
                    reasons.append(f"⚠️ Long/Short ratio {long_ratio*100:.0f}% long (crowded) — slight bearish")
                elif long_ratio < 0.35:  # <35% long = crowded short = contrarian bullish
                    bull_score += self.SIGNAL_WEIGHTS['long_short_ratio'] * 0.5
                    reasons.append(f"📊 Long/Short ratio {long_ratio*100:.0f}% long (crowded short) — slight bullish")

        # ===== v4.0: LIQUIDATION CASCADE SCORING =====
        if liquidations and len(liquidations) > 0:
            try:
                import time as _time
                now = _time.time()
                recent_cutoff = now - 300  # last 5 minutes
                long_liqs = sum(float(l.get('size', 0)) for l in liquidations
                               if l.get('left', 0) == 0 and
                               float(l.get('time', 0)) > recent_cutoff and
                               l.get('type', '') == 'long')
                short_liqs = sum(float(l.get('size', 0)) for l in liquidations
                                if l.get('left', 0) == 0 and
                                float(l.get('time', 0)) > recent_cutoff and
                                l.get('type', '') == 'short')
                total_liqs = long_liqs + short_liqs
                if total_liqs > 0:
                    if short_liqs > long_liqs * 2:
                        # Lots of shorts liquidated = price moved up = bullish momentum
                        bull_score += self.SIGNAL_WEIGHTS['liquidation_cascade']
                        signals.append(f"💥 Short Liquidation Cascade")
                        reasons.append(f"Recent short liquidations dominate — upward momentum confirmed")
                    elif long_liqs > short_liqs * 2:
                        # Lots of longs liquidated = price moved down = bearish momentum
                        bear_score += self.SIGNAL_WEIGHTS['liquidation_cascade']
                        signals.append(f"💥 Long Liquidation Cascade")
                        reasons.append(f"Recent long liquidations dominate — downward momentum confirmed")
            except Exception:
                pass

        # ===== v5.0: ICT / SMC SIGNALS =====
        # Break of Structure (BOS), Change of Character (CHoCH), Fair Value Gap (FVG)
        try:
            bos_data  = Indicators.detect_bos_choch(high, low, close, lookback=20)
            fvg_data  = Indicators.detect_fvg(high, low, lookback=10)

            # CHoCH is a stronger signal than plain BOS — score both but CHoCH supersedes
            if bos_data['choch_bull']:
                bull_score += self.SIGNAL_WEIGHTS['ict_choch']
                signals.append('🔄 CHoCH Bullish (Structure Flip)')
                reasons.append('Price broke above swing high vs a prior bearish structure — trend reversal signal')
            elif bos_data['bos_bull']:
                bull_score += self.SIGNAL_WEIGHTS['ict_bos']
                signals.append('📈 BOS Bullish (Swing High Break)')
                reasons.append('Price broke above recent swing high — bullish market structure continuation')

            if bos_data['choch_bear']:
                bear_score += self.SIGNAL_WEIGHTS['ict_choch']
                signals.append('🔄 CHoCH Bearish (Structure Flip)')
                reasons.append('Price broke below swing low vs a prior bullish structure — trend reversal signal')
            elif bos_data['bos_bear']:
                bear_score += self.SIGNAL_WEIGHTS['ict_bos']
                signals.append('📉 BOS Bearish (Swing Low Break)')
                reasons.append('Price broke below recent swing low — bearish market structure continuation')

            if fvg_data['fvg_bull']:
                bull_score += self.SIGNAL_WEIGHTS['ict_fvg']
                signals.append(f'🟦 Bullish FVG ({fvg_data["fvg_gap_pct"]:.2f}% gap)')
                reasons.append('Price returning to fill a bullish fair value gap — institutional demand zone')
            elif fvg_data['fvg_bear']:
                bear_score += self.SIGNAL_WEIGHTS['ict_fvg']
                signals.append(f'🟥 Bearish FVG ({fvg_data["fvg_gap_pct"]:.2f}% gap)')
                reasons.append('Price returning to fill a bearish fair value gap — institutional supply zone')
        except Exception as _e:
            logger.debug(f'ICT signals error: {_e}')

        # ===== CALCULATE FINAL SCORE AND SIGNAL =====

        # Normalize scores to 0-100
        max_possible = sum(self.SIGNAL_WEIGHTS.values())

        if bull_score > bear_score:
            final_score = min(100, (bull_score / max_possible) * 100 * 1.5)
            is_bullish = True
        else:
            final_score = min(100, (bear_score / max_possible) * 100 * 1.5)
            is_bullish = False

        # Determine signal type based on score
        if final_score >= 75:
            signal_type = SignalType.STRONG_BUY if is_bullish else SignalType.STRONG_SELL
        elif final_score >= 65:
            signal_type = SignalType.BUY if is_bullish else SignalType.SELL
        elif final_score >= 50:
            signal_type = SignalType.WEAK_BUY if is_bullish else SignalType.WEAK_SELL
        else:
            signal_type = SignalType.NEUTRAL

        # Confidence level
        if final_score >= 75 and timeframe_alignment:
            confidence = "High"
        elif final_score >= 60:
            confidence = "Medium"
        else:
            confidence = "Low"

        # ===== CALCULATE TARGETS AND STOP LOSS (v3.0 Smart Stop) =====
        # Smart stop: use nearest pivot support/resistance instead of fixed ATR*2
        # This tightens the stop → better R:R ratio

        pivots = Indicators.pivot_points(high, low, close)

        if is_bullish:
            # Smart stop: use highest pivot support below price (S1, S2, S3)
            # Fall back to ATR*2 if no support found below price
            atr_stop = price - (atr * 2)
            support_candidates = [v for k, v in pivots.items()
                                  if k.startswith('s') and v < price]
            if support_candidates:
                # Pick the nearest support level, minus a small buffer (0.2% of price)
                nearest_support = max(support_candidates)
                smart_stop = nearest_support * (1 - 0.002)
                # Only use smart stop if it's tighter than ATR stop (better R:R)
                stop_loss = smart_stop if smart_stop > atr_stop else atr_stop
            else:
                stop_loss = atr_stop

            target1 = price + (atr * 2)
            target2 = price + (atr * 3)
            target3 = price + (atr * 4.5)

            # Use Fibonacci extensions if available
            if fib_data and 'levels' in fib_data:
                if 'ext_127.2' in fib_data['levels']:
                    target2 = fib_data['levels']['ext_127.2']
                if 'ext_161.8' in fib_data['levels']:
                    target3 = fib_data['levels']['ext_161.8']
        else:
            # Smart stop for shorts: use nearest resistance above price (R1, R2, R3)
            atr_stop = price + (atr * 2)
            resistance_candidates = [v for k, v in pivots.items()
                                     if k.startswith('r') and v > price]
            if resistance_candidates:
                nearest_resistance = min(resistance_candidates)
                smart_stop = nearest_resistance * (1 + 0.002)
                stop_loss = smart_stop if smart_stop < atr_stop else atr_stop
            else:
                stop_loss = atr_stop

            target1 = price - (atr * 2)
            target2 = price - (atr * 3)
            target3 = price - (atr * 4.5)

            if fib_data and 'levels' in fib_data:
                if 'ext_127.2' in fib_data['levels']:
                    target2 = fib_data['levels']['ext_127.2']
                if 'ext_161.8' in fib_data['levels']:
                    target3 = fib_data['levels']['ext_161.8']

        # Risk/Reward calculation
        risk = abs(price - stop_loss)
        reward = abs(target2 - price)
        risk_reward = reward / risk if risk > 0 else 0

        # ===== BUILD METRICS DICT =====

        metrics = {
            'price': price,
            'ema20': ema20,
            'ema50': ema50,
            'ema200': ema200,
            'rsi': rsi,
            'macd_line': macd_line.iloc[-1],
            'macd_signal': macd_signal.iloc[-1],
            'macd_hist': macd_hist.iloc[-1],
            'stoch_k': stoch_k_val,
            'stoch_d': stoch_d_val,
            'adx': adx_value,
            'atr': atr,
            'atr_pct': atr_pct,
            'volume': volume.iloc[-1],
            'vol_ratio': vol_ratio,
            'vwap': vwap,
            'bb_upper': bb_upper.iloc[-1],
            'bb_lower': bb_lower.iloc[-1],
            'bb_width': bb_width,
            'mfi': mfi if pd.notna(mfi) else 50,
            'williams_r': williams if pd.notna(williams) else -50,
            'cci': cci if pd.notna(cci) else 0,
            'supertrend': supertrend.iloc[-1] if pd.notna(supertrend.iloc[-1]) else price,
            'cloud_top': cloud_top if pd.notna(cloud_top) else price,
            'cloud_bottom': cloud_bottom if pd.notna(cloud_bottom) else price,
            'btc_context': btc_context,
            'btc_regime': btc_regime,
            'fear_greed': fear_greed,
            'vol_rsi': vol_rsi,
            'bull_score': bull_score,
            'bear_score': bear_score,
            'chop_index': round(chop_val, 1),
            'funding_rate': funding_rate,
        }

        targets = {
            'target1': target1,
            'target2': target2,
            'target3': target3,
        }

        return SignalResult(
            ticker=ticker,
            timestamp=datetime.datetime.now(),
            price=price,
            signal_type=signal_type,
            score=final_score,
            confidence=confidence,
            signals=signals,
            reasons=reasons,
            metrics=metrics,
            targets=targets,
            stop_loss=stop_loss,
            risk_reward=risk_reward,
            timeframe_alignment=timeframe_alignment
        )


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class StateManager:
    """Manage bot state persistence and recovery"""

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self.state = {
            'last_alerts': {},
            'signal_history': [],
            'stats': {
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'start_time': datetime.datetime.now().isoformat()
            }
        }
        self.load()

    def load(self):
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    self.state.update(saved_state)
                logger.info(f"Loaded state from {self.state_file}")
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

    def save(self):
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save state: {e}")

    def can_alert(self, ticker: str, cooldown: int) -> bool:
        """Check if enough time has passed since last alert for ticker"""
        last_time = self.state['last_alerts'].get(ticker, 0)
        return time.time() - last_time >= cooldown

    def record_alert(self, ticker: str, signal: SignalResult):
        """Record an alert and update statistics. Also open a tracked trade for outcome checking."""
        self.state['last_alerts'][ticker] = time.time()
        self.state['stats']['total_signals'] += 1

        is_buy = signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY, SignalType.WEAK_BUY]
        if is_buy:
            self.state['stats']['buy_signals'] += 1
        else:
            self.state['stats']['sell_signals'] += 1

        # Keep last 200 signals in history
        signal_record = {
            'ticker': signal.ticker,
            'timestamp': signal.timestamp.isoformat(),
            'price': signal.price,
            'signal': signal.signal_type.label,
            'score': signal.score,
            'confidence': signal.confidence
        }
        self.state['signal_history'].append(signal_record)
        self.state['signal_history'] = self.state['signal_history'][-200:]

        # Open signal tracking for real outcome monitoring (v3.0)
        trade_key = f"{ticker}_{int(time.time())}"
        open_trades = self.state.setdefault('open_trades', {})
        open_trades[trade_key] = {
            'ticker': ticker,
            'timestamp': signal.timestamp.isoformat(),
            'entry': signal.price,
            'direction': 'BUY' if is_buy else 'SELL',
            't1': signal.targets['target1'],
            't2': signal.targets['target2'],
            't3': signal.targets['target3'],
            'stop': signal.stop_loss,
            'outcome': None,   # None = open, 'T1'/'T2'/'T3'/'STOP'
            'exit_price': None,
            'pnl_pct': None,
        }

        self.save()

    def check_signal_outcomes(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Check all open trades against current prices.
        Marks outcome when T1/T2/T3 or stop is hit.
        Returns list of newly resolved trades.
        """
        resolved = []
        open_trades = self.state.get('open_trades', {})

        for key, trade in list(open_trades.items()):
            if trade.get('outcome') is not None:
                continue  # already resolved

            ticker = trade['ticker']
            price = current_prices.get(ticker)
            if price is None:
                continue

            entry = trade['entry']
            direction = trade['direction']
            outcome = None
            exit_price = None

            if direction == 'BUY':
                if price <= trade['stop']:
                    outcome = 'STOP'
                    exit_price = trade['stop']
                elif price >= trade['t3']:
                    outcome = 'T3'
                    exit_price = trade['t3']
                elif price >= trade['t2']:
                    outcome = 'T2'
                    exit_price = trade['t2']
                elif price >= trade['t1']:
                    outcome = 'T1'
                    exit_price = trade['t1']
            else:  # SELL
                if price >= trade['stop']:
                    outcome = 'STOP'
                    exit_price = trade['stop']
                elif price <= trade['t3']:
                    outcome = 'T3'
                    exit_price = trade['t3']
                elif price <= trade['t2']:
                    outcome = 'T2'
                    exit_price = trade['t2']
                elif price <= trade['t1']:
                    outcome = 'T1'
                    exit_price = trade['t1']

            if outcome:
                if direction == 'BUY':
                    pnl = (exit_price - entry) / entry * 100
                else:
                    pnl = (entry - exit_price) / entry * 100

                trade['outcome'] = outcome
                trade['exit_price'] = exit_price
                trade['pnl_pct'] = round(pnl, 3)
                resolved.append(trade)
                logger.info(f"[OUTCOME] {ticker} {direction} → {outcome} | P&L: {pnl:+.2f}%")

        # Clean up old resolved trades (keep last 200)
        all_trades = list(open_trades.values())
        resolved_trades = [t for t in all_trades if t.get('outcome')]
        open_only = [t for t in all_trades if not t.get('outcome')]

        # Auto-expire trades older than 7 days with no outcome
        week_ago = time.time() - 7 * 86400
        for key in list(open_trades.keys()):
            trade = open_trades[key]
            if not trade.get('outcome'):
                try:
                    ts = datetime.datetime.fromisoformat(trade['timestamp']).timestamp()
                    if ts < week_ago:
                        trade['outcome'] = 'EXPIRED'
                        trade['pnl_pct'] = 0.0
                except Exception:
                    pass

        if resolved:
            self.save()

        return resolved


# ============================================================================
# BRAIN MANAGER (v3.0) — self-learning per-ticker signal adjustment
# ============================================================================

class BrainManager:
    """
    Learns from signal outcomes to adjust per-ticker scoring thresholds.
    - Tracks win rate and avg P&L per ticker
    - Adjusts score threshold: tighten for weak tickers, loosen for strong ones
    - Adjusts brain_multiplier: scales scoring weight for consistent performers
    """

    def __init__(self, brain_file: str):
        self.brain_file = Path(brain_file)
        self.brain: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.brain_file.exists():
            try:
                with open(self.brain_file, 'r') as f:
                    self.brain = json.load(f)
                logger.info(f"Brain loaded: {len(self.brain)} tickers")
            except Exception as e:
                logger.warning(f"Could not load brain: {e}")

    def save(self):
        try:
            with open(self.brain_file, 'w') as f:
                json.dump(self.brain, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save brain: {e}")

    def _get_ticker(self, ticker: str) -> Dict:
        if ticker not in self.brain:
            self.brain[ticker] = {
                'wins': 0, 'losses': 0, 'signals': 0,
                'total_pnl': 0.0, 'multiplier': 1.0, 'threshold_adj': 0
            }
        return self.brain[ticker]

    def record_outcome(self, ticker: str, outcome: str, pnl_pct: float):
        """Record a resolved trade outcome and update learning."""
        t = self._get_ticker(ticker)
        t['signals'] += 1
        t['total_pnl'] += pnl_pct

        if outcome != 'STOP' and pnl_pct > 0:
            t['wins'] += 1
        else:
            t['losses'] += 1

        # Recalculate adjustments after every 5 signals
        if t['signals'] >= 5:
            win_rate = t['wins'] / t['signals']
            avg_pnl = t['total_pnl'] / t['signals']

            # threshold_adj: raise bar for bad tickers, lower for good ones
            if win_rate < 0.35:
                t['threshold_adj'] = min(10, t['threshold_adj'] + 2)   # harder to signal
            elif win_rate > 0.65 and avg_pnl > 2.0:
                t['threshold_adj'] = max(-5, t['threshold_adj'] - 1)   # easier to signal
            elif 0.45 <= win_rate <= 0.65:
                t['threshold_adj'] = max(0, t['threshold_adj'] - 1)    # drift back to normal

            # multiplier: boost strong tickers, dampen weak ones
            if win_rate > 0.60:
                t['multiplier'] = min(1.3, t['multiplier'] + 0.05)
            elif win_rate < 0.35:
                t['multiplier'] = max(0.7, t['multiplier'] - 0.05)
            else:
                # Drift back toward 1.0
                t['multiplier'] = round(t['multiplier'] * 0.98 + 1.0 * 0.02, 3)

        self.save()
        logger.info(f"[BRAIN] {ticker} updated: {t['wins']}W/{t['losses']}L | "
                    f"mult={t['multiplier']:.2f} adj={t['threshold_adj']:+d}")

    def get_multiplier(self, ticker: str) -> float:
        return self._get_ticker(ticker).get('multiplier', 1.0)

    def get_threshold_adj(self, ticker: str) -> float:
        return self._get_ticker(ticker).get('threshold_adj', 0)

    def get_summary(self) -> str:
        """Return a readable brain summary for weekly reports."""
        if not self.brain:
            return "No data yet."
        lines = []
        for ticker, data in sorted(self.brain.items()):
            if data['signals'] < 3:
                continue
            wr = data['wins'] / data['signals'] * 100 if data['signals'] > 0 else 0
            avg = data['total_pnl'] / data['signals'] if data['signals'] > 0 else 0
            emoji = "🟢" if wr >= 50 else "🔴"
            lines.append(f"  {emoji} {ticker.replace('_','/')}: {data['signals']} signals | "
                         f"WR {wr:.0f}% | Avg {avg:+.1f}% | "
                         f"mult={data['multiplier']:.2f}")
        return "\n".join(lines) if lines else "Insufficient data (need 3+ signals per ticker)."


# ============================================================================
# MESSAGE FORMATTER
# ============================================================================

class MessageFormatter:
    """Format trading signals into readable messages"""

    @staticmethod
    def format_signal(signal: SignalResult) -> str:
        """Format a signal result into a Telegram message (keep indicators secret)"""
        clean_ticker = signal.ticker.replace("_", "/")
        factors_met = len(signal.signals)

        # Estimate trade duration based on multiple factors:
        # - ATR% (volatility): higher = faster moves
        # - Price move %: larger targets = longer duration
        # - Score: higher = more conviction = hold longer
        # - Timeframe alignment: aligned = stronger trend = longer duration

        atr_pct = signal.metrics.get('atr_pct', 1.5)
        target2 = signal.targets['target2']
        price_move_pct = abs(target2 - signal.price) / signal.price * 100

        # Base duration in hours based on price move vs volatility
        # How many ATR periods needed to reach target
        if atr_pct > 0:
            atr_periods_needed = price_move_pct / atr_pct
        else:
            atr_periods_needed = 10

        # Each 5m candle = 1 ATR period, convert to hours
        base_hours = (atr_periods_needed * 5) / 60  # 5 min candles

        # Adjust based on score (higher score = stronger signal = potentially faster)
        if signal.score >= 85:
            base_hours *= 0.7
        elif signal.score >= 80:
            base_hours *= 0.8
        elif signal.score >= 75:
            base_hours *= 0.9

        # Adjust based on timeframe alignment (aligned = more sustained move)
        if signal.timeframe_alignment:
            base_hours *= 1.3

        # Create duration range
        min_hours = max(0.5, base_hours * 0.6)
        max_hours = base_hours * 1.5

        # Format the duration string
        if max_hours < 1:
            est_duration = f"{int(min_hours*60)}-{int(max_hours*60)} mins"
        elif min_hours < 1:
            est_duration = f"{int(min_hours*60)} mins - {max_hours:.1f} hrs"
        elif max_hours < 24:
            est_duration = f"{min_hours:.1f}-{max_hours:.1f} hrs"
        else:
            est_duration = f"{min_hours:.0f}-{max_hours:.0f} hrs"

        # Determine confidence rating based on multiple factors
        confidence_score = 0

        # Score contribution (max 40 points)
        if signal.score >= 85:
            confidence_score += 40
        elif signal.score >= 80:
            confidence_score += 35
        elif signal.score >= 75:
            confidence_score += 30
        elif signal.score >= 70:
            confidence_score += 25

        # Timeframe alignment (max 20 points)
        if signal.timeframe_alignment:
            confidence_score += 20

        # Risk/Reward ratio (max 20 points)
        if signal.risk_reward >= 3.0:
            confidence_score += 20
        elif signal.risk_reward >= 2.5:
            confidence_score += 15
        elif signal.risk_reward >= 2.0:
            confidence_score += 10
        elif signal.risk_reward >= 1.5:
            confidence_score += 5

        # Factors met (max 20 points)
        if factors_met >= 15:
            confidence_score += 20
        elif factors_met >= 12:
            confidence_score += 15
        elif factors_met >= 10:
            confidence_score += 10
        elif factors_met >= 8:
            confidence_score += 5

        # Determine confidence label
        if confidence_score >= 75:
            confidence = "🟢 High"
        elif confidence_score >= 50:
            confidence = "🟡 Medium"
        else:
            confidence = "🟠 Low"

        # Simple, clean message format
        lines = [
            f"{signal.signal_type.emoji} {signal.signal_type.label}: {clean_ticker}",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"💰 Price: ${signal.price:.6f}",
            f"📊 {factors_met} of 21 factors met",
            f"📈 Score: {signal.score:.0f}/100",
            f"📊 Vol RSI: {signal.metrics.get('vol_rsi', 50):.1f}",
            f"📦 Volume: {signal.metrics.get('volume', 0):,.0f} | RVOL: {signal.metrics.get('vol_ratio', 1.0):.2f}x",
            f"🎯 Confidence: {confidence}",
            f"⏱ Est. Duration: {est_duration}",
            "",
            "🎯 Targets:",
            f"  T1: ${signal.targets['target1']:.6f}",
            f"  T2: ${signal.targets['target2']:.6f}",
            f"  T3: ${signal.targets['target3']:.6f}",
            f"🛑 Stop Loss: ${signal.stop_loss:.6f}",
            f"📈 Risk/Reward: 1:{signal.risk_reward:.1f}",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"🤖 CBot | {signal.timestamp.strftime('%H:%M:%S UTC')}"
        ]

        return "\n".join(lines)

    @staticmethod
    def format_heartbeat(stats: dict, watchlist_count: int) -> str:
        """Format simple heartbeat status message"""
        return "💓 CBot is running"

    @staticmethod
    def format_weekly_report(signal_history: list, stats: dict, api, watchlist: list,
                              open_trades: dict = None, brain_summary: str = None) -> str:
        """Format weekly performance report with price checks."""
        now = datetime.datetime.now()
        week_ago = now - datetime.timedelta(days=7)

        # Filter signals from last 7 days
        week_signals = []
        for s in signal_history:
            try:
                ts = datetime.datetime.fromisoformat(s['timestamp'])
                if ts >= week_ago:
                    week_signals.append(s)
            except Exception:
                continue

        if not week_signals:
            return (
                "📊 CBOT WEEKLY REPORT\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "No signals fired this week.\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 CBot | {now.strftime('%Y-%m-%d %H:%M')}"
            )

        # Get current prices for all watchlist tickers
        current_prices = {}
        for ticker in watchlist:
            try:
                df = api.fetch_ohlcv(ticker, '5m', 5)
                if df is not None and len(df) > 0:
                    current_prices[ticker] = float(df['close'].iloc[-1])
            except Exception:
                pass

        # Analyze each signal
        wins = 0
        losses = 0
        total_pnl = 0.0
        ticker_summary = {}
        buy_count = 0
        sell_count = 0

        for s in week_signals:
            ticker = s['ticker']
            signal_price = s['price']
            signal_type = s['signal']
            current = current_prices.get(ticker)

            is_buy = signal_type in ('BUY', 'STRONG BUY', 'WEAK BUY')
            if is_buy:
                buy_count += 1
            else:
                sell_count += 1

            if current and signal_price > 0:
                if is_buy:
                    pnl = (current - signal_price) / signal_price * 100
                else:
                    pnl = (signal_price - current) / signal_price * 100

                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                if ticker not in ticker_summary:
                    ticker_summary[ticker] = {'signals': 0, 'pnl': 0.0}
                ticker_summary[ticker]['signals'] += 1
                ticker_summary[ticker]['pnl'] += pnl

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_pnl = (total_pnl / total) if total > 0 else 0

        # Build ticker breakdown
        ticker_lines = []
        for ticker, data in sorted(ticker_summary.items(), key=lambda x: x[1]['pnl'], reverse=True):
            clean = ticker.replace("_", "/")
            avg = data['pnl'] / data['signals'] if data['signals'] > 0 else 0
            emoji = "🟢" if data['pnl'] > 0 else "🔴"
            ticker_lines.append(f"  {emoji} {clean}: {data['signals']} signals | {data['pnl']:+.2f}%")

        # Best and worst
        best = max(ticker_summary.items(), key=lambda x: x[1]['pnl']) if ticker_summary else None
        worst = min(ticker_summary.items(), key=lambda x: x[1]['pnl']) if ticker_summary else None

        lines = [
            "📊 CBOT WEEKLY REPORT",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 {week_ago.strftime('%b %d')} - {now.strftime('%b %d, %Y')}",
            "",
            f"📈 Total Signals: {len(week_signals)}",
            f"  🟢 Buy: {buy_count} | 🔴 Sell: {sell_count}",
            f"  ✅ Wins: {wins} | ❌ Losses: {losses}",
            f"  🎯 Win Rate: {win_rate:.0f}%",
            f"  💰 Avg P&L: {avg_pnl:+.2f}%",
            f"  📊 Total P&L: {total_pnl:+.2f}%",
            "",
            "📋 By Ticker:",
        ]
        lines.extend(ticker_lines)

        if best:
            lines.append(f"\n🏆 Best: {best[0].replace('_','/')} ({best[1]['pnl']:+.2f}%)")
        if worst and worst != best:
            lines.append(f"💩 Worst: {worst[0].replace('_','/')} ({worst[1]['pnl']:+.2f}%)")

        # Tracked real outcomes from open_trades (v3.0)
        if open_trades:
            resolved = [t for t in open_trades.values() if t.get('outcome') and t['outcome'] != 'EXPIRED']
            week_ago_dt = now - datetime.timedelta(days=7)
            week_resolved = []
            for t in resolved:
                try:
                    ts = datetime.datetime.fromisoformat(t['timestamp'])
                    if ts >= week_ago_dt:
                        week_resolved.append(t)
                except Exception:
                    pass

            if week_resolved:
                r_wins = sum(1 for t in week_resolved if t['outcome'] != 'STOP')
                r_losses = sum(1 for t in week_resolved if t['outcome'] == 'STOP')
                r_total = len(week_resolved)
                r_wr = r_wins / r_total * 100 if r_total > 0 else 0
                r_pnl = sum(t.get('pnl_pct', 0) for t in week_resolved)

                outcome_breakdown = {}
                for t in week_resolved:
                    oc = t['outcome']
                    outcome_breakdown[oc] = outcome_breakdown.get(oc, 0) + 1

                lines.extend([
                    "",
                    "🎯 Real Tracked Outcomes (this week):",
                    f"  ✅ Wins: {r_wins} | ❌ Stops: {r_losses} | Total: {r_total}",
                    f"  🏆 Win Rate: {r_wr:.0f}% | Total P&L: {r_pnl:+.1f}%",
                ])
                for oc, cnt in sorted(outcome_breakdown.items()):
                    lines.append(f"  {oc}: {cnt}")

        # Brain summary (v3.0)
        if brain_summary:
            lines.extend([
                "",
                "🧠 Brain (per-ticker learning):",
                brain_summary,
            ])

        lines.extend([
            "",
            f"📊 All Time: {stats.get('total_signals', 0)} signals",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"🤖 CBot Pro v5.0 | {now.strftime('%Y-%m-%d %H:%M')}"
        ])

        return "\n".join(lines)


# ============================================================================
# MAIN BOT CLASS
# ============================================================================

class CBotPro:
    """Main bot orchestrator"""

    def __init__(self):
        self.config = Config.from_env()
        self.api = APIClient(self.config)
        self.engine = SignalEngine(self.config, self.api)
        self.state = StateManager(self.config.state_file)
        self.brain = BrainManager(self.config.brain_file)
        self.formatter = MessageFormatter()
        self.running = True
        self.last_heartbeat_date = None  # Track the date of last heartbeat
        self.last_weekly_report_week = None  # Track week number of last report
        self._fear_greed: Optional[int] = None
        self._fear_greed_fetched_at: float = 0.0

        # Setup graceful shutdown
        sig.signal(sig.SIGINT, self._shutdown_handler)
        sig.signal(sig.SIGTERM, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutdown signal received, cleaning up...")
        self.running = False
        self.state.save()
        self.api.send_telegram("🛑 CBot shutting down...")
        sys.exit(0)

    def _send_heartbeat(self):
        """Send daily heartbeat message at configured time (default 6:30 AM)"""
        now = datetime.datetime.now()
        today = now.date()

        # Parse heartbeat time from config (format: "HH:MM")
        hb_hour, hb_minute = map(int, self.config.heartbeat_time.split(':'))

        # Check if we should send heartbeat:
        # 1. Haven't sent one today yet
        # 2. Current time is at or past the configured heartbeat time
        if (self.last_heartbeat_date != today and
            now.hour >= hb_hour and
            (now.hour > hb_hour or now.minute >= hb_minute)):

            msg = self.formatter.format_heartbeat(
                self.state.state['stats'],
                len(self.config.watchlist)
            )
            self.api.send_telegram(msg)
            self.last_heartbeat_date = today
            logger.info(f"Daily heartbeat sent at {now.strftime('%H:%M')}")

    def _send_weekly_report(self):
        """Send weekly report every Sunday at 18:00 UTC."""
        now = datetime.datetime.now()
        current_week = now.isocalendar()[1]

        # Sunday = weekday 6, after 6 PM
        if now.weekday() == 6 and now.hour >= 18 and self.last_weekly_report_week != current_week:
            try:
                report = self.formatter.format_weekly_report(
                    self.state.state['signal_history'],
                    self.state.state['stats'],
                    self.api,
                    self.config.watchlist,
                    open_trades=self.state.state.get('open_trades', {}),
                    brain_summary=self.brain.get_summary(),
                )
                self.api.send_telegram(report)
                self.last_weekly_report_week = current_week
                logger.info("Weekly report sent")
            except Exception as e:
                logger.error(f"Error sending weekly report: {e}")

    def _validate_startup(self) -> bool:
        """Validate configuration and connectivity at startup"""
        errors = self.config.validate()
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            return False

        # Test API connectivity
        test_df = self.api.fetch_ohlcv('BTC_USDT', '5m', 10)
        if test_df is None:
            logger.error("Failed to connect to Gate.io API")
            return False

        logger.info("API connectivity verified")
        return True

    def run(self):
        """Main bot loop"""
        logger.info("=" * 60)
        logger.info("CBOT PRO v5.0 Starting...")
        logger.info("=" * 60)

        if not self._validate_startup():
            logger.error("Startup validation failed. Exiting.")
            return

        # Send simple startup message
        startup_msg = "🤖 CBot Pro v5.0 is online — ICT/SMC signals active"
        self.api.send_telegram(startup_msg)
        # Don't set heartbeat date on startup - let first heartbeat happen at 6:30 AM

        logger.info(f"Monitoring {len(self.config.watchlist)} pairs")
        logger.info(f"Minimum signal score: {self.config.min_signal_score}")

        while self.running:
            try:
                scan_start = time.time()
                logger.info(f"--- Scan {datetime.datetime.now().strftime('%H:%M:%S')} ---")

                # ---- Fear & Greed Index (refresh every 15 min) ----
                if time.time() - self._fear_greed_fetched_at > 900:
                    fg = self.api.fetch_fear_greed()
                    if fg is not None:
                        self._fear_greed = fg
                        self._fear_greed_fetched_at = time.time()
                        logger.info(f"Fear & Greed: {fg}")

                # ---- Fetch BTC data for context (used for all alts) ----
                btc_df_primary = self.api.fetch_ohlcv('BTC_USDT', self.config.primary_timeframe)

                # ---- Collect current prices for outcome checking ----
                current_prices: Dict[str, float] = {}

                for ticker in self.config.watchlist:
                    if not self.running:
                        break

                    try:
                        # Fetch multi-timeframe data
                        df_primary = self.api.fetch_ohlcv(ticker, self.config.primary_timeframe)
                        df_secondary = self.api.fetch_ohlcv(ticker, self.config.secondary_timeframe, 100)

                        if df_primary is None:
                            logger.warning(f"{ticker}: Failed to fetch data")
                            continue

                        # Store current price for outcome checking
                        if len(df_primary) > 0:
                            current_prices[ticker] = float(df_primary['close'].iloc[-1])

                        # Get brain adjustments for this ticker
                        brain_multiplier = self.brain.get_multiplier(ticker)
                        threshold_adj = self.brain.get_threshold_adj(ticker)
                        effective_threshold = self.config.min_signal_score + threshold_adj

                        # v4.0: Fetch futures contract data + liquidations (free Gate.io API)
                        contract_data = self.api.fetch_contract_data(ticker)
                        liquidations = self.api.fetch_liquidations(ticker, limit=50)

                        # Run analysis with v4.0 enhancements
                        signal = self.engine.analyze(
                            ticker, df_primary, df_secondary,
                            btc_df=btc_df_primary if ticker != 'BTC_USDT' else None,
                            fear_greed=self._fear_greed,
                            brain_multiplier=brain_multiplier,
                            contract_data=contract_data,
                            liquidations=liquidations,
                        )

                        if signal is None:
                            logger.debug(f"{ticker}: Analysis returned None")
                            continue

                        price = signal.price
                        score = signal.score
                        sig_type = signal.signal_type.label

                        # Calculate predicted price movement percentage
                        target2 = signal.targets['target2']
                        price_move_pct = abs(target2 - price) / price * 100

                        logger.info(f"{ticker}: ${price:.6f} | Score: {score:.0f} | Move: {price_move_pct:.1f}% | {sig_type}")

                        # Check if signal meets criteria for alert:
                        # 1. STRONG BUY or STRONG SELL only
                        # 2. Score >= min threshold (brain-adjusted per ticker)
                        # 3. Minimum confluence factors met
                        # 4. Predicted price movement >= 3%
                        # 5. Cooldown period passed
                        factors_met = len(signal.signals)
                        if (signal.signal_type in [SignalType.STRONG_BUY, SignalType.STRONG_SELL] and
                            score >= effective_threshold and
                            factors_met >= self.config.min_confluence and
                            price_move_pct >= self.config.min_price_move_pct and
                            self.state.can_alert(ticker, self.config.alert_cooldown)):

                            # Send alert
                            msg = self.formatter.format_signal(signal)
                            if self.api.send_telegram(msg):
                                logger.info(f">>> ALERT SENT: {ticker} - {sig_type} "
                                            f"(Score: {score:.0f} >= {effective_threshold:.0f}, "
                                            f"Move: {price_move_pct:.1f}%)")
                                self.state.record_alert(ticker, signal)
                            else:
                                logger.error(f"Failed to send alert for {ticker}")

                    except Exception as e:
                        logger.error(f"{ticker}: Error during analysis - {e}")
                        continue

                    time.sleep(0.3)  # Small delay between tickers

                # ---- Check open signal outcomes (v3.0) ----
                if current_prices:
                    resolved = self.state.check_signal_outcomes(current_prices)
                    for trade in resolved:
                        self.brain.record_outcome(trade['ticker'], trade['outcome'],
                                                  trade.get('pnl_pct', 0.0))

                # Weekly report check
                self._send_weekly_report()
                self._send_heartbeat()

                # Calculate sleep time
                elapsed = time.time() - scan_start
                sleep_time = max(1, self.config.scan_interval - elapsed)
                logger.info(f"Scan complete in {elapsed:.1f}s. Sleeping {sleep_time:.0f}s...")

                # Sleep in small increments to allow for graceful shutdown
                sleep_end = time.time() + sleep_time
                while time.time() < sleep_end and self.running:
                    time.sleep(1)

            except KeyboardInterrupt:
                self._shutdown_handler(None, None)
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(10)

        logger.info("Bot stopped")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    bot = CBotPro()
    bot.run()
