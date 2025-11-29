"""
Tests for IV Rank Calculator and Volatility Indicators.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indicators.volatility import (
    IVRankCalculator,
    VolatilityIndicators,
    calculate_iv_skew,
)


class TestIVRankCalculator:
    """Tests for IVRankCalculator class."""
    
    @pytest.fixture
    def calculator(self):
        """Create calculator instance for tests."""
        return IVRankCalculator(
            lookback_30d=30,
            lookback_252d=252,
            risk_free_rate=0.07
        )
    
    @pytest.fixture
    def sample_iv_history(self):
        """Create sample IV history for testing."""
        dates = pd.date_range(start="2023-01-01", periods=300, freq="D")
        # Create IV values ranging from 0.10 to 0.30
        np.random.seed(42)
        iv_values = 0.15 + 0.05 * np.sin(np.linspace(0, 4*np.pi, 300)) + \
                    np.random.normal(0, 0.02, 300)
        iv_values = np.clip(iv_values, 0.10, 0.40)
        return pd.Series(iv_values, index=dates, name="iv")
    
    def test_iv_rank_calculation(self, calculator, sample_iv_history):
        """Test basic IV Rank calculation."""
        iv_rank = calculator.calculate_iv_rank(sample_iv_history)
        
        # IV Rank should be between 0 and 100
        assert iv_rank.min() >= 0
        assert iv_rank.max() <= 100
        
        # Length should match input
        assert len(iv_rank) == len(sample_iv_history)
    
    def test_iv_rank_at_extremes(self, calculator):
        """Test IV Rank at minimum and maximum values."""
        # Create IV series with known min/max
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        iv_values = [0.15] * 50 + [0.10] * 25 + [0.30] * 24 + [0.30]  # Last is max
        iv_series = pd.Series(iv_values, index=dates)
        
        iv_rank = calculator.calculate_iv_rank(iv_series)
        
        # When IV is at max, rank should be 100
        # The last value is 0.30 which is the max, so rank should be ~100
        assert iv_rank.iloc[-1] == pytest.approx(100, abs=0.1)
    
    def test_iv_rank_at_minimum(self, calculator):
        """Test IV Rank when IV is at minimum."""
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        iv_values = [0.20] * 50 + [0.30] * 25 + [0.10] * 24 + [0.10]  # Last is min
        iv_series = pd.Series(iv_values, index=dates)
        
        iv_rank = calculator.calculate_iv_rank(iv_series)
        
        # When IV is at min, rank should be 0
        assert iv_rank.iloc[-1] == pytest.approx(0, abs=0.1)
    
    def test_iv_rank_with_short_lookback(self, calculator, sample_iv_history):
        """Test IV Rank with 30-day lookback."""
        iv_rank = calculator.calculate_iv_rank(sample_iv_history, lookback_days=30)
        
        # Should still produce valid results
        assert not iv_rank.isna().all()
        assert iv_rank.dropna().min() >= 0
        assert iv_rank.dropna().max() <= 100
    
    def test_iv_percentile_calculation(self, calculator, sample_iv_history):
        """Test IV Percentile calculation."""
        iv_percentile = calculator.calculate_iv_percentile(sample_iv_history)
        
        # IV Percentile should be between 0 and 100
        valid_values = iv_percentile.dropna()
        assert valid_values.min() >= 0
        assert valid_values.max() <= 100
    
    def test_iv_from_price_calculation(self, calculator):
        """Test IV calculation from option price."""
        # Test case: ATM call with known parameters
        spot = 18000
        strike = 18000
        time_to_expiry = 30 / 365
        
        # First calculate price with known IV
        known_iv = 0.20
        price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, known_iv, "CE"
        )
        
        # Now calculate IV from that price
        calculated_iv = calculator.calculate_iv_from_price(
            option_price=price,
            spot_price=spot,
            strike_price=strike,
            time_to_expiry=time_to_expiry,
            option_type="CE"
        )
        
        # Should recover the original IV
        assert calculated_iv == pytest.approx(known_iv, abs=0.001)
    
    def test_iv_from_price_put_option(self, calculator):
        """Test IV calculation for put option."""
        spot = 18000
        strike = 18000
        time_to_expiry = 30 / 365
        known_iv = 0.25
        
        price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, known_iv, "PE"
        )
        
        calculated_iv = calculator.calculate_iv_from_price(
            option_price=price,
            spot_price=spot,
            strike_price=strike,
            time_to_expiry=time_to_expiry,
            option_type="PE"
        )
        
        assert calculated_iv == pytest.approx(known_iv, abs=0.001)
    
    def test_iv_rank_signal(self, calculator):
        """Test IV Rank signal generation."""
        # High IV Rank
        assert calculator.get_iv_rank_signal(80) == "HIGH"
        assert calculator.get_iv_rank_signal(70) == "HIGH"
        
        # Low IV Rank
        assert calculator.get_iv_rank_signal(20) == "LOW"
        assert calculator.get_iv_rank_signal(30) == "LOW"
        
        # Neutral
        assert calculator.get_iv_rank_signal(50) == "NEUTRAL"
        assert calculator.get_iv_rank_signal(40) == "NEUTRAL"
    
    def test_iv_rank_formula(self, calculator):
        """Test IV Rank formula: (Current IV - Low IV) / (High IV - Low IV) * 100."""
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        # IV values: min=0.10, max=0.30, current=0.20
        # Expected IV Rank = (0.20 - 0.10) / (0.30 - 0.10) * 100 = 50
        iv_values = [0.15, 0.10, 0.25, 0.30, 0.20, 0.18, 0.22, 0.15, 0.12, 0.20]
        iv_series = pd.Series(iv_values, index=dates)
        
        iv_rank = calculator.calculate_iv_rank(iv_series, lookback_days=10)
        
        # Last value should be (0.20 - 0.10) / (0.30 - 0.10) * 100 = 50
        assert iv_rank.iloc[-1] == pytest.approx(50, abs=0.1)


class TestVolatilityIndicators:
    """Tests for VolatilityIndicators class."""
    
    @pytest.fixture
    def indicators(self):
        """Create indicators instance for tests."""
        return VolatilityIndicators(trading_days=252)
    
    @pytest.fixture
    def sample_prices(self):
        """Create sample price series."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=300, freq="D")
        returns = np.random.normal(0.0001, 0.01, 300)
        prices = 18000 * np.exp(np.cumsum(returns))
        return pd.Series(prices, index=dates, name="close")
    
    def test_historical_volatility(self, indicators, sample_prices):
        """Test historical volatility calculation."""
        hv = indicators.calculate_historical_volatility(sample_prices, window=20)
        
        # HV should be positive
        valid_hv = hv.dropna()
        assert (valid_hv > 0).all()
        
        # Annualized HV should be in reasonable range (1% - 100%)
        assert valid_hv.mean() > 0.01
        assert valid_hv.mean() < 1.0
    
    def test_historical_volatility_non_annualized(self, indicators, sample_prices):
        """Test non-annualized historical volatility."""
        hv_annual = indicators.calculate_historical_volatility(
            sample_prices, window=20, annualize=True
        )
        hv_daily = indicators.calculate_historical_volatility(
            sample_prices, window=20, annualize=False
        )
        
        # Annualized should be approximately sqrt(252) times daily
        ratio = hv_annual.dropna().mean() / hv_daily.dropna().mean()
        assert ratio == pytest.approx(np.sqrt(252), abs=0.5)
    
    def test_realized_volatility(self, indicators, sample_prices):
        """Test realized volatility calculation."""
        returns = np.log(sample_prices / sample_prices.shift(1))
        rv = indicators.calculate_realized_volatility(returns, window=20)
        
        # RV should be positive
        valid_rv = rv.dropna()
        assert (valid_rv > 0).all()
    
    def test_volatility_ratio(self, indicators):
        """Test IV/HV ratio calculation."""
        iv = pd.Series([0.20, 0.22, 0.18, 0.25, 0.15])
        hv = pd.Series([0.15, 0.20, 0.20, 0.20, 0.20])
        
        ratio = indicators.calculate_volatility_ratio(iv, hv)
        
        # Check first value: 0.20 / 0.15 = 1.33
        assert ratio.iloc[0] == pytest.approx(1.333, abs=0.01)
        
        # Check last value: 0.15 / 0.20 = 0.75
        assert ratio.iloc[4] == pytest.approx(0.75, abs=0.01)
    
    def test_parkinson_volatility(self, indicators):
        """Test Parkinson volatility calculation."""
        dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
        np.random.seed(42)
        
        # Generate OHLC data
        close = 18000 * np.exp(np.cumsum(np.random.normal(0, 0.01, 50)))
        high = close * (1 + np.abs(np.random.normal(0, 0.005, 50)))
        low = close * (1 - np.abs(np.random.normal(0, 0.005, 50)))
        
        high_series = pd.Series(high, index=dates)
        low_series = pd.Series(low, index=dates)
        
        pv = indicators.calculate_parkinson_volatility(high_series, low_series, window=20)
        
        # Should produce valid volatility
        valid_pv = pv.dropna()
        assert len(valid_pv) > 0
        assert (valid_pv > 0).all()
    
    def test_garman_klass_volatility(self, indicators):
        """Test Garman-Klass volatility calculation."""
        dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
        np.random.seed(42)
        
        # Generate OHLC data
        close = 18000 * np.exp(np.cumsum(np.random.normal(0, 0.01, 50)))
        open_price = close * (1 + np.random.normal(0, 0.002, 50))
        high = np.maximum(open_price, close) * (1 + np.abs(np.random.normal(0, 0.003, 50)))
        low = np.minimum(open_price, close) * (1 - np.abs(np.random.normal(0, 0.003, 50)))
        
        gkv = indicators.calculate_garman_klass_volatility(
            pd.Series(open_price, index=dates),
            pd.Series(high, index=dates),
            pd.Series(low, index=dates),
            pd.Series(close, index=dates),
            window=20
        )
        
        # Should produce valid volatility
        valid_gkv = gkv.dropna()
        assert len(valid_gkv) > 0
        assert (valid_gkv > 0).all()


class TestBlackScholesModel:
    """Tests for Black-Scholes model in IVRankCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return IVRankCalculator(risk_free_rate=0.07)
    
    def test_call_put_parity(self, calculator):
        """Test put-call parity: C - P = S*e^(-qT) - K*e^(-rT)."""
        spot = 18000
        strike = 18000
        time_to_expiry = 30 / 365
        sigma = 0.20
        r = 0.07
        
        call_price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, sigma, "CE"
        )
        put_price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, sigma, "PE"
        )
        
        # Put-call parity (no dividends)
        parity_diff = call_price - put_price
        expected_diff = spot - strike * np.exp(-r * time_to_expiry)
        
        assert parity_diff == pytest.approx(expected_diff, abs=1.0)
    
    def test_atm_call_price(self, calculator):
        """Test ATM call option price is approximately 0.4 * S * sigma * sqrt(T)."""
        spot = 18000
        strike = 18000
        time_to_expiry = 30 / 365
        sigma = 0.20
        
        call_price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, sigma, "CE"
        )
        
        # Approximate ATM call price
        approx_price = 0.4 * spot * sigma * np.sqrt(time_to_expiry)
        
        # Should be in same ballpark (within 20%)
        assert call_price == pytest.approx(approx_price, rel=0.3)
    
    def test_deep_itm_call(self, calculator):
        """Test deep ITM call is approximately intrinsic value."""
        spot = 18000
        strike = 17000  # Deep ITM
        time_to_expiry = 30 / 365
        sigma = 0.20
        r = 0.07
        
        call_price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, sigma, "CE"
        )
        
        # Intrinsic value
        intrinsic = spot - strike
        
        # Deep ITM call should be close to intrinsic + time value
        assert call_price >= intrinsic * 0.95
    
    def test_otm_put(self, calculator):
        """Test OTM put has only time value."""
        spot = 18000
        strike = 17000  # OTM put
        time_to_expiry = 30 / 365
        sigma = 0.20
        
        put_price = calculator._black_scholes_price(
            spot, strike, time_to_expiry, sigma, "PE"
        )
        
        # OTM put should be positive (time value only)
        assert put_price > 0
        
        # But less than ATM put
        atm_put = calculator._black_scholes_price(
            spot, 18000, time_to_expiry, sigma, "PE"
        )
        assert put_price < atm_put


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
