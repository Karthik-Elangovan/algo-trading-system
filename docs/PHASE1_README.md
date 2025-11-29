# Phase 1 Documentation - Algorithmic Trading System

## Overview

This document provides detailed documentation for Phase 1 of the Algorithmic Trading System. This phase focuses on building the foundation for backtesting options trading strategies, specifically targeting Nifty, Bank Nifty, and Sensex options.

## Architecture

### Module Structure

```
src/
├── data/                    # Market data handling
│   ├── historical_data.py   # Data fetching and storage
│   └── data_utils.py        # Data cleaning and validation
├── indicators/              # Technical indicators
│   └── volatility.py        # IV Rank and volatility calculations
├── strategies/              # Trading strategies
│   ├── base_strategy.py     # Abstract base class
│   └── premium_selling.py   # Short Strangle strategy
├── risk/                    # Risk management
│   └── position_sizing.py   # Position sizing algorithms
└── backtesting/             # Backtesting framework
    ├── engine.py            # Main backtesting engine
    ├── metrics.py           # Performance metrics
    └── report.py            # Report generation
```

## Components

### 1. Historical Data Fetcher

The `HistoricalDataFetcher` class handles loading and managing historical options data.

#### Features
- Load data from CSV files
- Generate mock data for testing
- Support for multiple underlyings (NIFTY, BANKNIFTY, SENSEX)
- Option chain extraction
- Data caching for performance

#### Usage

```python
from src.data.historical_data import HistoricalDataFetcher

# Initialize fetcher
fetcher = HistoricalDataFetcher()

# Load Nifty options data
data = fetcher.load_nifty_options(
    start_date="2020-01-01",
    end_date="2024-12-31",
    use_mock=True  # Use mock data for testing
)

# Get option chain for specific date and expiry
chain = fetcher.get_option_chain(data, date, expiry)
```

### 2. IV Rank Calculator

The `IVRankCalculator` calculates implied volatility metrics.

#### Key Metrics

1. **IV Rank**: Measures current IV relative to its historical range
   ```
   IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) × 100
   ```

2. **IV Percentile**: Percentage of historical readings below current IV

3. **Implied Volatility**: Calculated from option prices using Black-Scholes

#### Usage

```python
from src.indicators.volatility import IVRankCalculator

calculator = IVRankCalculator()

# Calculate IV Rank from historical IV data
iv_rank = calculator.calculate_iv_rank(iv_history, lookback_days=252)

# Calculate IV from option price
iv = calculator.calculate_iv_from_price(
    option_price=150,
    spot_price=18000,
    strike_price=18000,
    time_to_expiry=30/365,
    option_type="CE"
)

# Get trading signal based on IV Rank
signal = calculator.get_iv_rank_signal(iv_rank=80)  # Returns "HIGH"
```

### 3. Premium Selling Strategy

The `PremiumSellingStrategy` implements a Short Strangle strategy.

#### Strategy Rules

**Entry Conditions:**
- IV Rank > 70 (high implied volatility environment)
- Select strikes at 15-20 delta
- Minimum 7 days to expiry
- Maximum 45 days to expiry

**Exit Conditions:**
- Profit target: 50% of premium collected
- Stop loss: 150% of premium (2.5x initial credit)
- Time exit: 2-3 days before expiry

**Position Sizing:**
- Risk 1-2% of capital per trade
- Maximum 5 concurrent positions

#### Usage

```python
from src.strategies.premium_selling import PremiumSellingStrategy

config = {
    "iv_rank_entry_threshold": 70,
    "delta_range": (0.15, 0.20),
    "profit_target_pct": 0.50,
    "stop_loss_pct": 1.50,
    "days_before_expiry_exit": 3,
    "position_size_pct": 0.02,
}

strategy = PremiumSellingStrategy(config=config)
```

### 4. Backtesting Engine

The `BacktestEngine` provides event-driven backtesting with realistic simulation.

#### Features

- Slippage modeling (default 0.5% for options)
- Complete transaction costs:
  - Brokerage (₹20 per order)
  - STT (0.05% on sell)
  - GST (18% on brokerage)
  - Exchange charges
  - SEBI charges
  - Stamp duty
- Walk-forward analysis support
- Detailed trade logging

#### Usage

```python
from src.backtesting.engine import BacktestEngine

engine = BacktestEngine(
    initial_capital=1_000_000,
    config={
        "slippage_pct": 0.005,
        "brokerage_per_order": 20,
    }
)

# Run backtest
results = engine.run(strategy, data)

# Generate report
print(results.generate_report())
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
```

### 5. Performance Metrics

The `PerformanceMetrics` class calculates comprehensive performance statistics.

#### Available Metrics

**Return Metrics:**
- Total Return
- CAGR (Compound Annual Growth Rate)
- Monthly Returns

**Risk Metrics:**
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Volatility (annualized)
- Maximum Drawdown
- Value at Risk (VaR)

**Trade Statistics:**
- Win Rate
- Profit Factor
- Average Win/Loss
- Maximum Consecutive Wins/Losses

### 6. Position Sizing

The `PositionSizer` provides multiple sizing algorithms.

#### Methods

1. **Fixed Percentage**: Allocate fixed % of capital
2. **Risk-Based**: Size based on stop loss distance
3. **Kelly Criterion**: Optimal sizing based on edge
4. **Volatility-Based**: Normalize risk across positions

## Configuration

All system parameters are centralized in `config/settings.py`:

```python
PREMIUM_SELLING_CONFIG = {
    "iv_rank_entry_threshold": 70,
    "delta_range": (0.15, 0.20),
    "profit_target_pct": 0.50,
    "stop_loss_pct": 1.50,
    "days_before_expiry_exit": 3,
    "position_size_pct": 0.02,
}

BACKTEST_CONFIG = {
    "initial_capital": 1_000_000,
    "slippage_pct": 0.005,
    "brokerage_per_order": 20,
    "stt_rate": 0.0005,
}

RISK_CONFIG = {
    "max_position_size_pct": 0.02,
    "max_portfolio_risk_pct": 0.10,
    "daily_loss_limit_pct": 0.05,
}
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_iv_rank.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Future Phases

### Phase 2: Additional Strategies
- Iron Condor strategy
- Calendar spreads
- Ratio spreads

### Phase 3: Broker Integration
- Angel One API integration
- Real-time data streaming
- Order execution

### Phase 4: UI Dashboard
- Streamlit interface
- Live monitoring
- Position management

## Mathematical Formulas

### Black-Scholes Model

Call option price:
```
C = S × N(d1) - K × e^(-rT) × N(d2)
```

Put option price:
```
P = K × e^(-rT) × N(-d2) - S × N(-d1)
```

Where:
```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 - σ√T
```

### IV Rank

```
IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) × 100
```

### Sharpe Ratio

```
Sharpe Ratio = (Rp - Rf) / σp × √252
```

Where:
- Rp = Portfolio daily return
- Rf = Risk-free daily rate
- σp = Standard deviation of returns

### Maximum Drawdown

```
Max Drawdown = (Peak Value - Trough Value) / Peak Value
```

## Notes

- All dates should be in 'YYYY-MM-DD' format
- Capital values are in INR
- Returns are expressed as decimals (0.10 = 10%)
- Volatility values are annualized

## Support

For questions or issues, please create an issue in the repository.
