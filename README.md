# Algo Trading System

⚠️ **IMPORTANT DISCLAIMER** ⚠️

> - This software is for **EDUCATIONAL purposes only**
> - Test **EXTENSIVELY** in paper trading before any live trading
> - Start with **SMALL** capital and understand **ALL** code before live trading
> - Trading involves **SIGNIFICANT risk of loss**
> - Past performance does not guarantee future results
> - The authors are **NOT responsible** for any financial losses

---

An algorithmic trading system for Nifty, Bank Nifty, and Sensex options with Angel One broker integration (planned).

## Features

### Phase 1
- ✅ Historical data fetcher for options
- ✅ IV Rank calculator with Black-Scholes model
- ✅ Premium Selling Strategy (Short Strangle)
- ✅ Event-driven backtesting engine
- ✅ Comprehensive performance metrics
- ✅ Transaction cost modeling (Indian markets)

### Phase 2 (Current)
- ✅ Professional Streamlit trading dashboard
- ✅ Real-time P&L tracking and visualization
- ✅ Position monitoring with Greeks exposure
- ✅ Risk metrics dashboard (VaR, margin, drawdown)
- ✅ Order entry and management panel
- ✅ Alert system for strategy signals and risk warnings
- ✅ Dark/Light theme support
- ✅ Export functionality (CSV, reports)

### Future Phases
- 📋 Phase 3: Additional strategies (Iron Condor, Calendar Spreads)
- 📋 Phase 4: Angel One broker integration

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/algo-trading-system.git
cd algo-trading-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```python
from src.data.historical_data import HistoricalDataFetcher
from src.indicators.volatility import IVRankCalculator
from src.strategies.premium_selling import PremiumSellingStrategy
from src.backtesting.engine import BacktestEngine
from config.settings import PREMIUM_SELLING_CONFIG

# Load historical data
data_fetcher = HistoricalDataFetcher()
data = data_fetcher.load_nifty_options(
    start_date="2020-01-01",
    end_date="2024-12-31",
    use_mock=True  # Use mock data for testing
)

# Initialize strategy
strategy = PremiumSellingStrategy(config=PREMIUM_SELLING_CONFIG)

# Run backtest
engine = BacktestEngine(initial_capital=1_000_000)
results = engine.run(strategy, data)

# Generate report
print(results.generate_report())
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
```

## Project Structure

```
algo-trading-system/
├── src/
│   ├── data/              # Market data modules
│   │   ├── historical_data.py
│   │   └── data_utils.py
│   ├── strategies/        # Strategy implementations
│   │   ├── base_strategy.py
│   │   └── premium_selling.py
│   ├── risk/              # Risk management
│   │   └── position_sizing.py
│   ├── execution/         # Broker integration (Phase 3)
│   ├── backtesting/       # Backtesting engine
│   │   ├── engine.py
│   │   ├── metrics.py
│   │   └── report.py
│   ├── indicators/        # Technical indicators
│   │   └── volatility.py
│   └── ui/                # Legacy UI module
├── dashboard/             # Streamlit Trading Dashboard (Phase 2)
│   ├── app.py             # Main dashboard application
│   ├── components/        # UI components
│   │   ├── sidebar.py     # Sidebar controls
│   │   ├── charts.py      # P&L and chart components
│   │   ├── tables.py      # Position and order tables
│   │   ├── metrics.py     # Risk and market metrics
│   │   └── alerts.py      # Alert system
│   ├── utils/             # Utility modules
│   │   ├── data_handler.py
│   │   ├── export.py
│   │   └── theme.py
│   └── styles/            # Custom CSS
│       └── custom.css
├── config/
│   └── settings.py        # Configuration
├── tests/
│   ├── test_iv_rank.py
│   ├── test_backtesting.py
│   └── test_premium_selling.py
├── docs/
│   └── PHASE1_README.md
├── data/                  # Data storage
├── requirements.txt
└── README.md
```

## Strategy: Short Strangle (Premium Selling)

### Entry Criteria
- IV Rank > 70 (high implied volatility environment)
- Select strikes at 15-20 delta
- Minimum 7 days to expiry, maximum 45 days

### Exit Criteria
- **Profit Target**: 50% of premium collected
- **Stop Loss**: 150% of premium (2.5x initial credit)
- **Time Exit**: Close 2-3 days before expiry

### Position Sizing
- Risk 1-2% of capital per trade
- Maximum 5 concurrent positions

## Performance Metrics

The system calculates:
- **Returns**: Total return, CAGR, monthly returns
- **Risk**: Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown
- **Trade Stats**: Win rate, profit factor, average win/loss, consecutive wins/losses
- **Risk-adjusted**: VaR, CVaR, volatility

## Configuration

Edit `config/settings.py` to customize:

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
    "initial_capital": 1_000_000,  # 10 Lakhs INR
    "slippage_pct": 0.005,
    "brokerage_per_order": 20,
    "stt_rate": 0.0005,
}
```

## Trading Dashboard

The trading dashboard provides a professional web interface for monitoring and managing trades.

### Running the Dashboard

```bash
# From the project root directory
streamlit run dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`.

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **P&L Chart** | Real-time profit/loss tracking with daily and cumulative views |
| **Position Table** | Current positions with Greeks (Delta, Gamma, Theta, Vega) |
| **Risk Metrics** | VaR, CVaR, margin usage, drawdown monitoring |
| **Market Data** | Live spot price, IV, IV Rank for NIFTY/BANKNIFTY/SENSEX |
| **Order Entry** | Quick order form with market/limit orders |
| **Alert System** | Strategy signals, risk warnings, order confirmations |
| **Theme Toggle** | Dark/Light mode support |
| **Export** | Download positions, orders, and P&L reports as CSV |

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Algo Trading Dashboard                                   │
├──────────────┬──────────────────────────────────────────────┤
│  SIDEBAR     │  MAIN AREA                                    │
│              │                                               │
│  Strategy    │  [Market Data]    [Capital Overview]          │
│  Selector    │                                               │
│              │  ─────────────────────────────────────────── │
│  Controls    │                                               │
│  - Start     │  [P&L Chart]                                  │
│  - Stop      │  [Drawdown Chart]  [Equity Curve]             │
│  - Pause     │                                               │
│              │  ─────────────────────────────────────────── │
│  Theme       │                                               │
│  Toggle      │  [Position Table with Greeks]                 │
│              │                                               │
│  Export      │  ─────────────────────────────────────────── │
│  - Positions │                                               │
│  - Orders    │  [Order Log]       [Alerts]                   │
│  - P&L       │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

### Configuration Options

The dashboard can be customized via the sidebar:

- **Strategy Selection**: Choose from available strategies
- **Parameter Tuning**: Adjust IV threshold, delta range, profit targets
- **Auto-refresh**: Enable/disable automatic data refresh (30-second default)
- **Theme**: Toggle between dark and light modes

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_iv_rank.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Mathematical Formulas

### IV Rank
```
IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) × 100
```

### Sharpe Ratio
```
Sharpe = (Portfolio Return - Risk Free Rate) / Std(Returns) × √252
```

### Black-Scholes (for IV calculation)
```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 - σ√T
Call = S×N(d1) - K×e^(-rT)×N(d2)
```

## Dependencies

- numpy>=1.24.0
- pandas>=2.0.0
- scipy>=1.10.0
- matplotlib>=3.7.0
- seaborn>=0.12.0
- pytest>=7.0.0
- python-dateutil>=2.8.0

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Documentation

See [docs/PHASE1_README.md](docs/PHASE1_README.md) for detailed Phase 1 documentation.

---

**Remember**: Always paper trade first. Understand the risks. Start small.
