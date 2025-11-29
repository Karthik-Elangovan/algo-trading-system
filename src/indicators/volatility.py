"""
Volatility Indicators Module

This module provides volatility calculations including:
- Implied Volatility (IV) calculation using Black-Scholes
- IV Rank calculation with configurable lookback periods
- IV Percentile calculation
- Historical Volatility (HV) calculation

IV Rank Formula:
    IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) * 100

This measures where current IV falls within its historical range.
A high IV Rank (>70) suggests IV is elevated relative to its history,
making it potentially favorable for premium selling strategies.
"""

import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)


class IVRankCalculator:
    """
    Calculator for Implied Volatility Rank and related metrics.
    
    IV Rank measures the current implied volatility relative to its
    historical range over a specified lookback period.
    
    Attributes:
        lookback_30d: 30-day lookback period for short-term IV Rank
        lookback_252d: 252-day (1 year) lookback period for long-term IV Rank
        risk_free_rate: Risk-free interest rate for calculations
    """
    
    def __init__(
        self,
        lookback_30d: int = 30,
        lookback_252d: int = 252,
        risk_free_rate: float = 0.07
    ):
        """
        Initialize the IV Rank Calculator.
        
        Args:
            lookback_30d: Number of days for short-term lookback
            lookback_252d: Number of days for long-term lookback (typically 252 trading days)
            risk_free_rate: Annual risk-free interest rate (default 7% for India)
        """
        self.lookback_30d = lookback_30d
        self.lookback_252d = lookback_252d
        self.risk_free_rate = risk_free_rate
    
    def calculate_iv_rank(
        self,
        iv_history: pd.Series,
        lookback_days: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate IV Rank for a series of IV values.
        
        Formula:
            IV Rank = (Current IV - Min IV) / (Max IV - Min IV) * 100
        
        Where Min and Max are calculated over the lookback period.
        
        Args:
            iv_history: Series of historical IV values indexed by date
            lookback_days: Number of days to look back (default: 252 days)
        
        Returns:
            Series of IV Rank values (0-100 scale)
        
        Example:
            >>> iv_history = pd.Series([0.15, 0.18, 0.22, 0.20, 0.17])
            >>> calculator = IVRankCalculator()
            >>> iv_rank = calculator.calculate_iv_rank(iv_history, lookback_days=5)
        """
        if lookback_days is None:
            lookback_days = self.lookback_252d
        
        if len(iv_history) < lookback_days:
            logger.warning(
                f"IV history ({len(iv_history)} days) shorter than lookback ({lookback_days} days). "
                "Using available data."
            )
            lookback_days = len(iv_history)
        
        # Calculate rolling min and max
        rolling_min = iv_history.rolling(window=lookback_days, min_periods=1).min()
        rolling_max = iv_history.rolling(window=lookback_days, min_periods=1).max()
        
        # Calculate IV Rank
        iv_range = rolling_max - rolling_min
        
        # Avoid division by zero
        iv_rank = np.where(
            iv_range > 0,
            (iv_history - rolling_min) / iv_range * 100,
            50  # Default to 50 if no range (constant IV)
        )
        
        return pd.Series(iv_rank, index=iv_history.index, name="iv_rank")
    
    def calculate_iv_percentile(
        self,
        iv_history: pd.Series,
        lookback_days: Optional[int] = None
    ) -> pd.Series:
        """
        Calculate IV Percentile for a series of IV values.
        
        IV Percentile measures what percentage of historical readings
        were below the current IV value.
        
        Formula:
            IV Percentile = (Number of days IV was lower) / (Total days) * 100
        
        Args:
            iv_history: Series of historical IV values indexed by date
            lookback_days: Number of days to look back (default: 252 days)
        
        Returns:
            Series of IV Percentile values (0-100 scale)
        
        Note:
            IV Percentile can be more robust than IV Rank as it considers
            the distribution of historical IV values, not just the extremes.
        """
        if lookback_days is None:
            lookback_days = self.lookback_252d
        
        def percentile_calc(window):
            if len(window) < 2:
                return 50.0
            current_val = window.iloc[-1]
            historical = window.iloc[:-1]
            return (historical < current_val).sum() / len(historical) * 100
        
        iv_percentile = iv_history.rolling(
            window=lookback_days + 1,
            min_periods=2
        ).apply(percentile_calc, raw=False)
        
        return pd.Series(iv_percentile, index=iv_history.index, name="iv_percentile")
    
    def calculate_iv_from_price(
        self,
        option_price: float,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        option_type: str = "CE",
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate Implied Volatility from option price using Black-Scholes model.
        
        Uses Brent's method for root finding to solve for IV.
        
        Black-Scholes Formula:
            Call: C = S*e^(-q*T)*N(d1) - K*e^(-r*T)*N(d2)
            Put:  P = K*e^(-r*T)*N(-d2) - S*e^(-q*T)*N(-d1)
        
        Where:
            d1 = [ln(S/K) + (r - q + σ²/2)*T] / (σ*√T)
            d2 = d1 - σ*√T
        
        Args:
            option_price: Market price of the option
            spot_price: Current price of the underlying
            strike_price: Strike price of the option
            time_to_expiry: Time to expiry in years
            option_type: 'CE' for call, 'PE' for put
            dividend_yield: Continuous dividend yield
        
        Returns:
            Implied volatility (annualized)
        
        Raises:
            ValueError: If IV cannot be calculated (e.g., price out of bounds)
        """
        if time_to_expiry <= 0:
            raise ValueError("Time to expiry must be positive")
        
        if option_price <= 0:
            raise ValueError("Option price must be positive")
        
        def objective(sigma):
            """Objective function for root finding."""
            return self._black_scholes_price(
                spot_price, strike_price, time_to_expiry, sigma,
                option_type, dividend_yield
            ) - option_price
        
        try:
            # Search for IV in reasonable range (1% to 500%)
            iv = brentq(objective, 0.01, 5.0, xtol=1e-6)
            return iv
        except ValueError as e:
            logger.warning(f"Could not calculate IV: {e}")
            # Return NaN if calculation fails
            return np.nan
    
    def _black_scholes_price(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        sigma: float,
        option_type: str = "CE",
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate option price using Black-Scholes model.
        
        Args:
            spot: Spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            sigma: Volatility (annualized)
            option_type: 'CE' for call, 'PE' for put
            dividend_yield: Continuous dividend yield
        
        Returns:
            Option price
        """
        if time_to_expiry <= 0:
            # At expiry, return intrinsic value
            if option_type == "CE":
                return max(0, spot - strike)
            else:
                return max(0, strike - spot)
        
        r = self.risk_free_rate
        q = dividend_yield
        
        d1 = (np.log(spot / strike) + (r - q + 0.5 * sigma ** 2) * time_to_expiry) / \
             (sigma * np.sqrt(time_to_expiry))
        d2 = d1 - sigma * np.sqrt(time_to_expiry)
        
        if option_type == "CE":
            price = spot * np.exp(-q * time_to_expiry) * norm.cdf(d1) - \
                    strike * np.exp(-r * time_to_expiry) * norm.cdf(d2)
        else:  # PE
            price = strike * np.exp(-r * time_to_expiry) * norm.cdf(-d2) - \
                    spot * np.exp(-q * time_to_expiry) * norm.cdf(-d1)
        
        return price
    
    def calculate_atm_iv(
        self,
        options_data: pd.DataFrame,
        date: datetime,
        expiry: datetime
    ) -> float:
        """
        Calculate ATM (At-The-Money) implied volatility.
        
        ATM IV is commonly used as a proxy for the overall market's
        implied volatility level.
        
        Args:
            options_data: DataFrame with options data
            date: Trading date
            expiry: Expiry date
        
        Returns:
            ATM implied volatility
        """
        # Filter data for specific date and expiry
        mask = (
            (pd.to_datetime(options_data["date"]) == pd.to_datetime(date)) &
            (pd.to_datetime(options_data["expiry"]) == pd.to_datetime(expiry))
        )
        filtered = options_data[mask]
        
        if filtered.empty:
            return np.nan
        
        # Find ATM strike (closest to spot price)
        spot_price = filtered["spot_price"].iloc[0]
        filtered = filtered.copy()
        filtered.loc[:, "distance"] = abs(filtered["strike"] - spot_price)
        atm_options = filtered[filtered["distance"] == filtered["distance"].min()]
        
        # Average IV of ATM call and put
        if "iv" in atm_options.columns:
            return atm_options["iv"].mean()
        
        return np.nan
    
    def calculate_iv_time_series(
        self,
        options_data: pd.DataFrame,
        expiry_offset_days: int = 30
    ) -> pd.DataFrame:
        """
        Calculate IV time series from options data.
        
        Extracts ATM IV for each trading day using the nearest
        monthly expiry.
        
        Args:
            options_data: DataFrame with options data
            expiry_offset_days: Preferred days to expiry for IV extraction
        
        Returns:
            DataFrame with date and IV columns
        """
        dates = pd.to_datetime(options_data["date"]).unique()
        iv_data = []
        
        for date in sorted(dates):
            date_data = options_data[pd.to_datetime(options_data["date"]) == date]
            
            if date_data.empty:
                continue
            
            # Find expiry closest to target offset
            expiries = pd.to_datetime(date_data["expiry"]).unique()
            target_expiry = date + pd.Timedelta(days=expiry_offset_days)
            
            closest_expiry = min(expiries, key=lambda x: abs((x - target_expiry).days))
            
            atm_iv = self.calculate_atm_iv(options_data, date, closest_expiry)
            
            iv_data.append({
                "date": date,
                "iv": atm_iv,
                "expiry": closest_expiry,
                "dte": (closest_expiry - date).days
            })
        
        return pd.DataFrame(iv_data)
    
    def get_iv_rank_signal(
        self,
        iv_rank: float,
        threshold_high: float = 70,
        threshold_low: float = 30
    ) -> str:
        """
        Get trading signal based on IV Rank.
        
        Args:
            iv_rank: Current IV Rank value (0-100)
            threshold_high: Upper threshold for high IV (default: 70)
            threshold_low: Lower threshold for low IV (default: 30)
        
        Returns:
            Signal string: 'HIGH', 'LOW', or 'NEUTRAL'
        """
        if iv_rank >= threshold_high:
            return "HIGH"  # Good for premium selling
        elif iv_rank <= threshold_low:
            return "LOW"  # Good for premium buying
        else:
            return "NEUTRAL"


class VolatilityIndicators:
    """
    Class for calculating various volatility indicators.
    
    Includes:
    - Historical Volatility (HV)
    - Realized Volatility (RV)
    - Parkinson Volatility (using high-low)
    - Garman-Klass Volatility (using OHLC)
    - Volatility ratio (IV/HV)
    """
    
    def __init__(self, trading_days: int = 252):
        """
        Initialize VolatilityIndicators.
        
        Args:
            trading_days: Number of trading days per year for annualization
        """
        self.trading_days = trading_days
    
    def calculate_historical_volatility(
        self,
        prices: pd.Series,
        window: int = 20,
        annualize: bool = True
    ) -> pd.Series:
        """
        Calculate Historical Volatility (HV) using close-to-close returns.
        
        Formula:
            HV = std(log returns) * sqrt(trading_days)
        
        Args:
            prices: Series of prices (typically close prices)
            window: Rolling window for calculation (default: 20 days)
            annualize: Whether to annualize the volatility
        
        Returns:
            Series of historical volatility values
        """
        # Calculate log returns
        log_returns = np.log(prices / prices.shift(1))
        
        # Calculate rolling standard deviation
        rolling_std = log_returns.rolling(window=window).std()
        
        # Annualize if requested
        if annualize:
            rolling_std = rolling_std * np.sqrt(self.trading_days)
        
        return pd.Series(rolling_std, name="historical_volatility")
    
    def calculate_realized_volatility(
        self,
        returns: pd.Series,
        window: int = 20,
        annualize: bool = True
    ) -> pd.Series:
        """
        Calculate Realized Volatility from returns.
        
        Formula:
            RV = sqrt(sum(returns^2) / n) * sqrt(trading_days)
        
        Args:
            returns: Series of returns (log or simple)
            window: Rolling window for calculation
            annualize: Whether to annualize the volatility
        
        Returns:
            Series of realized volatility values
        """
        squared_returns = returns ** 2
        rv = np.sqrt(squared_returns.rolling(window=window).mean())
        
        if annualize:
            rv = rv * np.sqrt(self.trading_days)
        
        return pd.Series(rv, name="realized_volatility")
    
    def calculate_parkinson_volatility(
        self,
        high: pd.Series,
        low: pd.Series,
        window: int = 20,
        annualize: bool = True
    ) -> pd.Series:
        """
        Calculate Parkinson Volatility using high-low range.
        
        More efficient than close-to-close as it uses intraday range.
        
        Formula:
            σ² = (1/4*ln(2)) * E[(ln(H/L))²]
        
        Args:
            high: Series of high prices
            low: Series of low prices
            window: Rolling window for calculation
            annualize: Whether to annualize the volatility
        
        Returns:
            Series of Parkinson volatility values
        """
        log_hl = np.log(high / low) ** 2
        factor = 1.0 / (4.0 * np.log(2))
        
        pv = np.sqrt(factor * log_hl.rolling(window=window).mean())
        
        if annualize:
            pv = pv * np.sqrt(self.trading_days)
        
        return pd.Series(pv, name="parkinson_volatility")
    
    def calculate_garman_klass_volatility(
        self,
        open_price: pd.Series,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 20,
        annualize: bool = True
    ) -> pd.Series:
        """
        Calculate Garman-Klass Volatility using OHLC data.
        
        Most efficient estimator for volatility using OHLC prices.
        
        Formula:
            σ² = 0.5*(ln(H/L))² - (2*ln(2)-1)*(ln(C/O))²
        
        Args:
            open_price: Series of open prices
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            window: Rolling window for calculation
            annualize: Whether to annualize the volatility
        
        Returns:
            Series of Garman-Klass volatility values
        """
        log_hl = np.log(high / low) ** 2
        log_co = np.log(close / open_price) ** 2
        
        gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
        gkv = np.sqrt(gk.rolling(window=window).mean())
        
        if annualize:
            gkv = gkv * np.sqrt(self.trading_days)
        
        return pd.Series(gkv, name="garman_klass_volatility")
    
    def calculate_volatility_ratio(
        self,
        iv: pd.Series,
        hv: pd.Series
    ) -> pd.Series:
        """
        Calculate IV/HV ratio (Volatility Risk Premium indicator).
        
        Ratio > 1: IV is higher than HV (premium selling favorable)
        Ratio < 1: HV is higher than IV (premium buying favorable)
        
        Args:
            iv: Series of implied volatility values
            hv: Series of historical volatility values
        
        Returns:
            Series of IV/HV ratio values
        """
        ratio = iv / hv
        return pd.Series(ratio, name="volatility_ratio")
    
    def calculate_volatility_term_structure(
        self,
        options_data: pd.DataFrame,
        date: datetime
    ) -> pd.DataFrame:
        """
        Calculate volatility term structure across expiries.
        
        Shows how IV varies across different expiry dates.
        Useful for identifying calendar spread opportunities.
        
        Args:
            options_data: DataFrame with options data
            date: Trading date
        
        Returns:
            DataFrame with expiry and ATM IV columns
        """
        date_data = options_data[pd.to_datetime(options_data["date"]) == pd.to_datetime(date)]
        
        if date_data.empty:
            return pd.DataFrame(columns=["expiry", "dte", "atm_iv"])
        
        expiries = pd.to_datetime(date_data["expiry"]).unique()
        term_structure = []
        
        for expiry in sorted(expiries):
            expiry_data = date_data[pd.to_datetime(date_data["expiry"]) == expiry]
            spot = expiry_data["spot_price"].iloc[0]
            
            # Find ATM options
            expiry_data = expiry_data.copy()
            expiry_data.loc[:, "distance"] = abs(expiry_data["strike"] - spot)
            atm_data = expiry_data[expiry_data["distance"] == expiry_data["distance"].min()]
            
            if not atm_data.empty and "iv" in atm_data.columns:
                term_structure.append({
                    "expiry": expiry,
                    "dte": (expiry - pd.to_datetime(date)).days,
                    "atm_iv": atm_data["iv"].mean()
                })
        
        return pd.DataFrame(term_structure)


def calculate_iv_skew(
    options_data: pd.DataFrame,
    date: datetime,
    expiry: datetime
) -> Dict[str, float]:
    """
    Calculate IV skew metrics for an option chain.
    
    Measures:
    - 25-delta skew: IV of 25-delta put - IV of 25-delta call
    - ATM-OTM skew: IV of OTM options vs ATM
    
    Args:
        options_data: DataFrame with options data
        date: Trading date
        expiry: Expiry date
    
    Returns:
        Dictionary with skew metrics
    """
    mask = (
        (pd.to_datetime(options_data["date"]) == pd.to_datetime(date)) &
        (pd.to_datetime(options_data["expiry"]) == pd.to_datetime(expiry))
    )
    data = options_data[mask]
    
    if data.empty:
        return {"delta_25_skew": np.nan, "atm_otm_skew": np.nan}
    
    calls = data[data["option_type"] == "CE"].copy()
    puts = data[data["option_type"] == "PE"].copy()
    
    # Calculate 25-delta skew
    if not calls.empty and not puts.empty and "delta" in data.columns:
        call_25d = calls[abs(calls["delta"] - 0.25).idxmin()] if len(calls) > 0 else None
        put_25d = puts[abs(puts["delta"] + 0.25).idxmin()] if len(puts) > 0 else None
        
        if call_25d is not None and put_25d is not None:
            delta_25_skew = put_25d["iv"] - call_25d["iv"]
        else:
            delta_25_skew = np.nan
    else:
        delta_25_skew = np.nan
    
    return {
        "delta_25_skew": delta_25_skew,
        "atm_otm_skew": np.nan  # Placeholder for additional skew calculations
    }
