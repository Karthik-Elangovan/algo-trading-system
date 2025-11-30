"""
Historical Data Fetcher Module

This module provides functionality to fetch and manage historical market data
for Nifty, Bank Nifty, and Sensex options trading.

Supports:
- Loading data from CSV files
- Mock data generation for testing
- Option chain data retrieval with strikes, expiries, and premiums
- Data validation and cleaning
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class OptionData:
    """Data class representing an option contract."""
    
    symbol: str
    underlying: str
    strike: float
    option_type: str  # 'CE' or 'PE'
    expiry: datetime
    ltp: float  # Last traded price
    bid: float
    ask: float
    volume: int
    open_interest: int
    iv: float  # Implied volatility
    delta: float
    gamma: float
    theta: float
    vega: float
    timestamp: datetime


@dataclass
class OptionChain:
    """Data class representing an option chain for a specific expiry."""
    
    underlying: str
    spot_price: float
    expiry: datetime
    timestamp: datetime
    calls: List[OptionData]
    puts: List[OptionData]
    
    def get_strike_range(self) -> Tuple[float, float]:
        """Get the range of strikes in the option chain."""
        all_strikes = [c.strike for c in self.calls] + [p.strike for p in self.puts]
        return min(all_strikes), max(all_strikes)
    
    def get_atm_strike(self, strike_interval: float = 50) -> float:
        """Get the at-the-money strike price."""
        return round(self.spot_price / strike_interval) * strike_interval


class HistoricalDataFetcher:
    """
    Class to fetch and manage historical options data.
    
    This class supports multiple data sources:
    - CSV files
    - Mock data generation for testing
    - Future: API integration with Angel One
    
    Attributes:
        data_dir: Directory path for data storage
        cache: Dictionary for caching loaded data
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the HistoricalDataFetcher.
        
        Args:
            data_dir: Directory path for data storage. Defaults to 'data/' in project root.
        """
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).parent.parent.parent / "data"
        
        self.cache: Dict[str, pd.DataFrame] = {}
        self._ensure_data_dir()
    
    def _ensure_data_dir(self) -> None:
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_nifty_options(
        self,
        start_date: str,
        end_date: str,
        use_mock: bool = True
    ) -> pd.DataFrame:
        """
        Load historical Nifty options data.
        
        Args:
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            use_mock: If True, generate mock data for testing
        
        Returns:
            DataFrame with historical options data
        """
        return self.load_options_data("NIFTY", start_date, end_date, use_mock)
    
    def load_banknifty_options(
        self,
        start_date: str,
        end_date: str,
        use_mock: bool = True
    ) -> pd.DataFrame:
        """
        Load historical Bank Nifty options data.
        
        Args:
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            use_mock: If True, generate mock data for testing
        
        Returns:
            DataFrame with historical options data
        """
        return self.load_options_data("BANKNIFTY", start_date, end_date, use_mock)
    
    def load_options_data(
        self,
        underlying: str,
        start_date: str,
        end_date: str,
        use_mock: bool = True
    ) -> pd.DataFrame:
        """
        Load historical options data for a given underlying.
        
        Args:
            underlying: Name of the underlying ('NIFTY', 'BANKNIFTY', 'SENSEX')
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            use_mock: If True, generate mock data for testing
        
        Returns:
            DataFrame with historical options data including:
            - date: Trading date
            - underlying: Name of underlying
            - spot_price: Spot price of underlying
            - strike: Strike price
            - option_type: 'CE' or 'PE'
            - expiry: Expiry date
            - ltp: Last traded price
            - iv: Implied volatility
            - delta: Option delta
            - volume: Trading volume
            - open_interest: Open interest
        """
        cache_key = f"{underlying}_{start_date}_{end_date}"
        
        if cache_key in self.cache:
            logger.info(f"Returning cached data for {cache_key}")
            return self.cache[cache_key]
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        if use_mock:
            data = self._generate_mock_data(underlying, start, end)
        else:
            data = self._load_from_csv(underlying, start, end)
        
        self.cache[cache_key] = data
        return data
    
    def _load_from_csv(
        self,
        underlying: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Load options data from CSV files.
        
        Args:
            underlying: Name of the underlying
            start: Start datetime
            end: End datetime
        
        Returns:
            DataFrame with options data
        
        Raises:
            FileNotFoundError: If CSV file is not found
        """
        csv_path = self.data_dir / f"{underlying.lower()}_options.csv"
        
        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}. Generating mock data instead.")
            return self._generate_mock_data(underlying, start, end)
        
        df = pd.read_csv(csv_path, parse_dates=["date", "expiry"])
        
        # Filter by date range
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        
        return df
    
    def _generate_mock_data(
        self,
        underlying: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Generate realistic mock options data for testing.
        
        The mock data simulates realistic market behavior with:
        - Trending spot prices with volatility
        - Multiple expiries (weekly and monthly)
        - Realistic IV levels and variations
        - Greeks calculated based on standard models
        
        Args:
            underlying: Name of the underlying
            start: Start datetime
            end: End datetime
        
        Returns:
            DataFrame with mock options data
        """
        # Set base parameters based on underlying
        params = self._get_underlying_params(underlying)
        base_price = params["base_price"]
        strike_interval = params["strike_interval"]
        base_iv = params["base_iv"]
        
        # Generate trading days
        trading_days = pd.bdate_range(start=start, end=end)
        
        records = []
        np.random.seed(42)  # For reproducibility
        
        # Simulate spot price path with GBM
        returns = np.random.normal(0.0001, 0.015, len(trading_days))
        spot_prices = base_price * np.exp(np.cumsum(returns))
        
        for day_idx, (date, spot) in enumerate(zip(trading_days, spot_prices)):
            # Generate expiries (weekly for next 4 weeks, monthly for next 3 months)
            expiries = self._generate_expiries(date)
            
            for expiry in expiries:
                dte = (expiry - date).days
                if dte <= 0:
                    continue
                
                # Generate strikes around ATM
                atm_strike = round(spot / strike_interval) * strike_interval
                strikes = [atm_strike + i * strike_interval 
                          for i in range(-10, 11)]
                
                # IV varies with time and market conditions
                iv_base = base_iv + np.random.normal(0, 0.03)
                iv_base = max(0.10, min(0.50, iv_base))  # Clamp IV
                
                for strike in strikes:
                    # Generate call and put data
                    for opt_type in ["CE", "PE"]:
                        moneyness = strike / spot
                        
                        # IV smile - higher IV for OTM options
                        iv_adjustment = 0.05 * abs(1 - moneyness)
                        iv = iv_base + iv_adjustment
                        
                        # Calculate approximate premium and Greeks
                        premium, delta, gamma, theta, vega = self._calculate_greeks(
                            spot, strike, dte / 365, iv, opt_type
                        )
                        
                        if premium < 0.5:  # Skip very low premium options
                            continue
                        
                        # Add realistic spread and noise
                        bid = premium * (1 - 0.01)
                        ask = premium * (1 + 0.01)
                        ltp = premium * (1 + np.random.uniform(-0.005, 0.005))
                        
                        records.append({
                            "date": date,
                            "underlying": underlying,
                            "spot_price": spot,
                            "strike": strike,
                            "option_type": opt_type,
                            "expiry": expiry,
                            "dte": dte,
                            "ltp": round(ltp, 2),
                            "bid": round(bid, 2),
                            "ask": round(ask, 2),
                            "iv": round(iv, 4),
                            "delta": round(delta, 4),
                            "gamma": round(gamma, 6),
                            "theta": round(theta, 4),
                            "vega": round(vega, 4),
                            "volume": np.random.randint(100, 10000),
                            "open_interest": np.random.randint(1000, 100000),
                        })
        
        return pd.DataFrame(records)
    
    def _get_underlying_params(self, underlying: str) -> Dict[str, Any]:
        """Get parameters for different underlyings."""
        params = {
            "NIFTY": {
                "base_price": 24200,
                "strike_interval": 50,
                "base_iv": 0.15,
            },
            "BANKNIFTY": {
                "base_price": 52000,
                "strike_interval": 100,
                "base_iv": 0.18,
            },
            "SENSEX": {
                "base_price": 80000,
                "strike_interval": 100,
                "base_iv": 0.14,
            },
        }
        return params.get(underlying, params["NIFTY"])
    
    def _generate_expiries(self, date: datetime) -> List[datetime]:
        """
        Generate expiry dates from a given date.
        
        Generates:
        - Weekly expiries (every Thursday) for next 4 weeks
        - Monthly expiries (last Thursday) for next 3 months
        
        Args:
            date: Reference date
        
        Returns:
            List of expiry dates
        """
        expiries = []
        
        # Weekly expiries (Thursdays)
        current = date
        for _ in range(4):
            # Find next Thursday
            days_ahead = 3 - current.weekday()  # Thursday = 3
            if days_ahead <= 0:
                days_ahead += 7
            next_thursday = current + timedelta(days=days_ahead)
            expiries.append(next_thursday)
            current = next_thursday
        
        # Monthly expiries (last Thursday of month)
        for month_offset in range(1, 4):
            next_month = date.month + month_offset
            year = date.year
            if next_month > 12:
                next_month -= 12
                year += 1
            
            # Find last Thursday of month
            if next_month == 12:
                first_of_next = datetime(year + 1, 1, 1)
            else:
                first_of_next = datetime(year, next_month + 1, 1)
            
            last_day = first_of_next - timedelta(days=1)
            days_back = (last_day.weekday() - 3) % 7
            last_thursday = last_day - timedelta(days=days_back)
            
            if last_thursday not in expiries:
                expiries.append(last_thursday)
        
        return sorted(expiries)
    
    def _calculate_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        iv: float,
        option_type: str,
        risk_free_rate: float = 0.07
    ) -> Tuple[float, float, float, float, float]:
        """
        Calculate option price and Greeks using Black-Scholes model.
        
        Args:
            spot: Spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            iv: Implied volatility (annualized)
            option_type: 'CE' for call, 'PE' for put
            risk_free_rate: Risk-free interest rate
        
        Returns:
            Tuple of (price, delta, gamma, theta, vega)
        """
        from scipy.stats import norm
        
        if time_to_expiry <= 0:
            time_to_expiry = 1 / 365  # Minimum 1 day
        
        # Black-Scholes formula
        d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * iv ** 2) * time_to_expiry) / (iv * np.sqrt(time_to_expiry))
        d2 = d1 - iv * np.sqrt(time_to_expiry)
        
        if option_type == "CE":
            price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            delta = norm.cdf(d1)
        else:  # PE
            price = strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            delta = norm.cdf(d1) - 1
        
        # Common Greeks
        gamma = norm.pdf(d1) / (spot * iv * np.sqrt(time_to_expiry))
        theta = -(spot * norm.pdf(d1) * iv) / (2 * np.sqrt(time_to_expiry)) - \
                risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * \
                (norm.cdf(d2) if option_type == "CE" else norm.cdf(-d2))
        theta = theta / 365  # Daily theta
        vega = spot * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100  # Per 1% change
        
        return price, delta, gamma, theta, vega
    
    def get_option_chain(
        self,
        data: pd.DataFrame,
        date: datetime,
        expiry: datetime
    ) -> Optional[OptionChain]:
        """
        Get option chain for a specific date and expiry.
        
        Args:
            data: DataFrame with options data
            date: Trading date
            expiry: Expiry date
        
        Returns:
            OptionChain object or None if no data available
        """
        # Filter data for the specific date and expiry
        mask = (data["date"] == pd.to_datetime(date)) & \
               (data["expiry"] == pd.to_datetime(expiry))
        filtered = data[mask]
        
        if filtered.empty:
            return None
        
        underlying = filtered["underlying"].iloc[0]
        spot_price = filtered["spot_price"].iloc[0]
        
        calls = []
        puts = []
        
        for _, row in filtered.iterrows():
            option = OptionData(
                symbol=f"{underlying}{row['expiry'].strftime('%d%b%y')}{row['strike']}{row['option_type']}",
                underlying=underlying,
                strike=row["strike"],
                option_type=row["option_type"],
                expiry=pd.to_datetime(row["expiry"]),
                ltp=row["ltp"],
                bid=row["bid"],
                ask=row["ask"],
                volume=row["volume"],
                open_interest=row["open_interest"],
                iv=row["iv"],
                delta=row["delta"],
                gamma=row["gamma"],
                theta=row["theta"],
                vega=row["vega"],
                timestamp=pd.to_datetime(row["date"]),
            )
            
            if row["option_type"] == "CE":
                calls.append(option)
            else:
                puts.append(option)
        
        return OptionChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=pd.to_datetime(expiry),
            timestamp=pd.to_datetime(date),
            calls=sorted(calls, key=lambda x: x.strike),
            puts=sorted(puts, key=lambda x: x.strike),
        )
    
    def get_spot_price_history(
        self,
        data: pd.DataFrame,
        underlying: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Extract spot price history from options data.
        
        Args:
            data: DataFrame with options data
            underlying: Filter by specific underlying (optional)
        
        Returns:
            DataFrame with date and spot_price columns
        """
        if underlying:
            data = data[data["underlying"] == underlying]
        
        return data.groupby("date").agg({
            "spot_price": "first",
            "underlying": "first"
        }).reset_index()
    
    def save_to_csv(self, data: pd.DataFrame, filename: str) -> str:
        """
        Save DataFrame to CSV file.
        
        Args:
            data: DataFrame to save
            filename: Name of the file (without path)
        
        Returns:
            Full path to saved file
        """
        filepath = self.data_dir / filename
        data.to_csv(filepath, index=False)
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def clear_cache(self) -> None:
        """Clear the data cache."""
        self.cache.clear()
        logger.info("Data cache cleared")
