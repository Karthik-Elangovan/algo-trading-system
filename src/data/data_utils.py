"""
Data Processing Utilities Module

This module provides utilities for data cleaning, validation,
and processing for options trading data.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import logging

# Configure logging
logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Utility class for cleaning and preprocessing options data.
    
    Provides methods for:
    - Handling missing values
    - Removing outliers
    - Normalizing data formats
    - Filling gaps in time series
    """
    
    @staticmethod
    def clean_options_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean options data by handling missing values and outliers.
        
        Args:
            df: Raw options DataFrame
        
        Returns:
            Cleaned DataFrame
        """
        df = df.copy()
        
        # Convert date columns to datetime
        date_cols = ["date", "expiry"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # Remove rows with negative prices
        price_cols = ["ltp", "bid", "ask"]
        for col in price_cols:
            if col in df.columns:
                df = df[df[col] >= 0]
        
        # Remove rows with invalid IV (must be positive and reasonable)
        if "iv" in df.columns:
            df = df[(df["iv"] > 0) & (df["iv"] < 2.0)]  # IV < 200%
        
        # Remove rows with invalid delta (must be between -1 and 1)
        if "delta" in df.columns:
            df = df[(df["delta"] >= -1) & (df["delta"] <= 1)]
        
        # Remove duplicate rows
        df = df.drop_duplicates()
        
        # Sort by date and strike
        sort_cols = [col for col in ["date", "expiry", "strike", "option_type"] 
                    if col in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols)
        
        return df.reset_index(drop=True)
    
    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame,
        method: str = "forward_fill",
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Handle missing values in the DataFrame.
        
        Args:
            df: DataFrame with potential missing values
            method: Method for handling ('forward_fill', 'interpolate', 'drop')
            columns: Specific columns to handle (all if None)
        
        Returns:
            DataFrame with missing values handled
        """
        df = df.copy()
        
        if columns is None:
            columns = df.columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == "forward_fill":
                df[col] = df[col].ffill()
            elif method == "interpolate":
                if df[col].dtype in [np.float64, np.int64]:
                    df[col] = df[col].interpolate(method="linear")
            elif method == "drop":
                df = df.dropna(subset=[col])
        
        return df
    
    @staticmethod
    def remove_outliers(
        df: pd.DataFrame,
        column: str,
        method: str = "iqr",
        threshold: float = 1.5
    ) -> pd.DataFrame:
        """
        Remove outliers from a specific column.
        
        Args:
            df: Input DataFrame
            column: Column to check for outliers
            method: Method for outlier detection ('iqr', 'zscore')
            threshold: Threshold for outlier detection
        
        Returns:
            DataFrame with outliers removed
        """
        df = df.copy()
        
        if column not in df.columns:
            return df
        
        if method == "iqr":
            Q1 = df[column].quantile(0.25)
            Q3 = df[column].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            df = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
        
        elif method == "zscore":
            mean = df[column].mean()
            std = df[column].std()
            if std > 0:
                z_scores = np.abs((df[column] - mean) / std)
                df = df[z_scores < threshold]
        
        return df.reset_index(drop=True)
    
    @staticmethod
    def normalize_option_symbols(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize option symbol formats to a standard format.
        
        Standard format: UNDERLYING_EXPIRY_STRIKE_TYPE
        Example: NIFTY_20240125_18000_CE
        
        Args:
            df: DataFrame with option data
        
        Returns:
            DataFrame with normalized symbols
        """
        df = df.copy()
        
        if all(col in df.columns for col in ["underlying", "expiry", "strike", "option_type"]):
            df["symbol"] = (
                df["underlying"].astype(str) + "_" +
                pd.to_datetime(df["expiry"]).dt.strftime("%Y%m%d") + "_" +
                df["strike"].astype(int).astype(str) + "_" +
                df["option_type"].astype(str)
            )
        
        return df


class DataValidator:
    """
    Utility class for validating options data integrity.
    
    Provides methods for:
    - Schema validation
    - Data quality checks
    - Consistency validation
    """
    
    REQUIRED_COLUMNS = [
        "date", "underlying", "spot_price", "strike", 
        "option_type", "expiry", "ltp"
    ]
    
    OPTIONAL_COLUMNS = [
        "bid", "ask", "iv", "delta", "gamma", "theta", "vega",
        "volume", "open_interest", "dte"
    ]
    
    @classmethod
    def validate_schema(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate that the DataFrame has required columns.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            Tuple of (is_valid, list of missing columns)
        """
        missing_cols = [col for col in cls.REQUIRED_COLUMNS if col not in df.columns]
        return len(missing_cols) == 0, missing_cols
    
    @staticmethod
    def validate_data_types(df: pd.DataFrame) -> Dict[str, str]:
        """
        Validate and return data types of columns.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            Dictionary mapping column names to their data types
        """
        return {col: str(df[col].dtype) for col in df.columns}
    
    @staticmethod
    def validate_date_range(
        df: pd.DataFrame,
        start_date: str,
        end_date: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that data covers the expected date range.
        
        Args:
            df: DataFrame with 'date' column
            start_date: Expected start date
            end_date: Expected end date
        
        Returns:
            Tuple of (is_valid, details dict)
        """
        if "date" not in df.columns:
            return False, {"error": "No 'date' column found"}
        
        df_start = pd.to_datetime(df["date"].min())
        df_end = pd.to_datetime(df["date"].max())
        expected_start = pd.to_datetime(start_date)
        expected_end = pd.to_datetime(end_date)
        
        is_valid = (df_start <= expected_start) and (df_end >= expected_end)
        
        return is_valid, {
            "data_start": df_start,
            "data_end": df_end,
            "expected_start": expected_start,
            "expected_end": expected_end,
            "is_valid": is_valid
        }
    
    @staticmethod
    def check_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform comprehensive data quality checks.
        
        Args:
            df: DataFrame to check
        
        Returns:
            Dictionary with quality metrics
        """
        quality_report = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "missing_values": {},
            "unique_values": {},
            "numeric_stats": {},
        }
        
        # Missing values
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                quality_report["missing_values"][col] = {
                    "count": int(missing_count),
                    "percentage": round(missing_count / len(df) * 100, 2)
                }
        
        # Unique values for categorical columns
        categorical_cols = ["underlying", "option_type"]
        for col in categorical_cols:
            if col in df.columns:
                quality_report["unique_values"][col] = df[col].unique().tolist()
        
        # Statistics for numeric columns
        numeric_cols = ["spot_price", "strike", "ltp", "iv", "delta", "volume"]
        for col in numeric_cols:
            if col in df.columns and df[col].dtype in [np.float64, np.int64]:
                quality_report["numeric_stats"][col] = {
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std()),
                }
        
        return quality_report
    
    @staticmethod
    def validate_option_chain_consistency(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate consistency of option chain data.
        
        Checks:
        - Call/Put parity
        - Strike price continuity
        - Expiry consistency
        
        Args:
            df: DataFrame with option chain data
        
        Returns:
            Dictionary with consistency check results
        """
        consistency_report = {
            "is_consistent": True,
            "issues": []
        }
        
        # Check for both calls and puts
        if "option_type" in df.columns:
            option_types = df["option_type"].unique()
            if "CE" not in option_types:
                consistency_report["issues"].append("Missing call options (CE)")
                consistency_report["is_consistent"] = False
            if "PE" not in option_types:
                consistency_report["issues"].append("Missing put options (PE)")
                consistency_report["is_consistent"] = False
        
        # Check strike price continuity
        if "strike" in df.columns:
            strikes = sorted(df["strike"].unique())
            if len(strikes) > 1:
                diffs = np.diff(strikes)
                if not np.allclose(diffs, diffs[0], rtol=0.01):
                    consistency_report["issues"].append(
                        "Inconsistent strike price intervals"
                    )
        
        return consistency_report


def calculate_returns(
    prices: pd.Series,
    method: str = "log"
) -> pd.Series:
    """
    Calculate returns from price series.
    
    Args:
        prices: Series of prices
        method: 'log' for log returns, 'simple' for simple returns
    
    Returns:
        Series of returns
    """
    if method == "log":
        return np.log(prices / prices.shift(1))
    else:  # simple
        return prices.pct_change()


def calculate_rolling_stats(
    series: pd.Series,
    window: int = 20,
    stats: List[str] = None
) -> pd.DataFrame:
    """
    Calculate rolling statistics for a time series.
    
    Args:
        series: Input time series
        window: Rolling window size
        stats: List of statistics to calculate ('mean', 'std', 'min', 'max')
    
    Returns:
        DataFrame with rolling statistics
    """
    if stats is None:
        stats = ["mean", "std", "min", "max"]
    
    result = pd.DataFrame(index=series.index)
    
    if "mean" in stats:
        result["rolling_mean"] = series.rolling(window=window).mean()
    if "std" in stats:
        result["rolling_std"] = series.rolling(window=window).std()
    if "min" in stats:
        result["rolling_min"] = series.rolling(window=window).min()
    if "max" in stats:
        result["rolling_max"] = series.rolling(window=window).max()
    
    return result


def resample_ohlc(
    df: pd.DataFrame,
    date_column: str = "date",
    price_column: str = "ltp",
    freq: str = "W"
) -> pd.DataFrame:
    """
    Resample price data to OHLC format.
    
    Args:
        df: DataFrame with price data
        date_column: Name of date column
        price_column: Name of price column
        freq: Resampling frequency ('D', 'W', 'M')
    
    Returns:
        DataFrame with OHLC data
    """
    df = df.copy()
    df = df.set_index(pd.to_datetime(df[date_column]))
    
    ohlc = df[price_column].resample(freq).ohlc()
    ohlc["volume"] = df["volume"].resample(freq).sum() if "volume" in df.columns else 0
    
    return ohlc.reset_index()
