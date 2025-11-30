# Algo Trading System

⚠️ **IMPORTANT DISCLAIMER** ⚠️

> - This software is for **EDUCATIONAL purposes only**
> - Test **EXTENSIVELY** in paper trading before any live trading
> - Start with **SMALL** capital and understand **ALL** code before live trading
> - Trading involves **SIGNIFICANT risk of loss**
> - Past performance does not guarantee future results
> - The authors are **NOT responsible** for any financial losses

---

A comprehensive algorithmic trading system for Nifty, Bank Nifty, and Sensex options with Angel One broker integration and production-ready AWS deployment infrastructure.

## Features

### Phase 1: Core Trading Engine
- ✅ Historical data fetcher for options
- ✅ IV Rank calculator with Black-Scholes model
- ✅ Premium Selling Strategy (Short Strangle)
- ✅ Event-driven backtesting engine
- ✅ Comprehensive performance metrics
- ✅ Transaction cost modeling (Indian markets)

### Phase 2: Trading Dashboard
- ✅ Professional Streamlit trading dashboard
- ✅ Real-time P&L tracking and visualization
- ✅ Position monitoring with Greeks exposure
- ✅ Risk metrics dashboard (VaR, margin, drawdown)
- ✅ Order entry and management panel
- ✅ Alert system for strategy signals and risk warnings
- ✅ Dark/Light theme support
- ✅ Export functionality (CSV, reports)

### Phase 3: Angel One Broker Integration
- ✅ Angel One SmartAPI integration
- ✅ Authentication with TOTP support
- ✅ Real-time market data via WebSocket
- ✅ Order placement and management
- ✅ Position and portfolio tracking
- ✅ Paper trading simulator for testing
- ✅ Risk management configuration

### Phase 4: Advanced Trading Strategies
- ✅ Iron Condor Strategy - Neutral strategy for range-bound markets
- ✅ Calendar Spread Strategy - Time decay strategy for low IV environments
- ✅ Ratio Spread Strategy - Directional strategy with premium collection
- ✅ Comprehensive configuration for all strategies
- ✅ Comprehensive unit test coverage for all strategies
- ✅ Detailed documentation for each strategy

### Phase 6: Production Deployment
- ✅ Docker containerization (Trading, Dashboard, Data services)
- ✅ Terraform AWS infrastructure (VPC, ECS, RDS, S3)
- ✅ CI/CD pipeline with GitHub Actions
- ✅ CloudWatch monitoring and alerting
- ✅ Multi-environment support (dev, staging, prod)
- ✅ Deployment scripts and rollback procedures
- ✅ Comprehensive deployment documentation

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
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI/CD pipeline
├── config/
│   ├── settings.py            # Strategy configurations
│   ├── broker_settings.py     # Broker configurations
│   └── deployment.py          # Deployment settings
├── dashboard/                 # Streamlit Trading Dashboard (Phase 2)
│   ├── app.py                 # Main dashboard application
│   ├── components/            # UI components
│   │   ├── sidebar.py         # Sidebar controls
│   │   ├── charts.py          # P&L and chart components
│   │   ├── tables.py          # Position and order tables
│   │   ├── metrics.py         # Risk and market metrics
│   │   └── alerts.py          # Alert system
│   ├── utils/                 # Utility modules
│   │   ├── data_handler.py
│   │   ├── export.py
│   │   └── theme.py
│   └── styles/                # Custom CSS
│       └── custom.css
├── data/                      # Data storage
├── deployment/                # Production Deployment (Phase 6)
│   ├── docker/                # Dockerfiles
│   │   ├── Dockerfile.trading
│   │   ├── Dockerfile.dashboard
│   │   ├── Dockerfile.data
│   │   └── docker-compose.yml
│   ├── terraform/             # AWS infrastructure
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── environments/
│   │   └── modules/           # VPC, ECS, RDS, S3
│   ├── scripts/               # Deployment scripts
│   │   ├── deploy.sh
│   │   ├── rollback.sh
│   │   └── health_check.sh
│   ├── monitoring/            # CloudWatch configs
│   │   ├── alerts.json
│   │   └── cloudwatch_dashboards.json
│   └── docs/                  # Deployment documentation
│       ├── ARCHITECTURE.md
│       ├── DEPLOYMENT.md
│       └── RUNBOOK.md
├── docs/
│   ├── PHASE1_README.md
│   └── PHASE4_README.md
├── src/
│   ├── backtesting/           # Backtesting engine
│   │   ├── engine.py
│   │   ├── metrics.py
│   │   └── report.py
│   ├── data/                  # Market data modules
│   │   ├── historical_data.py
│   │   └── data_utils.py
│   ├── execution/             # Broker integration (Phase 3)
│   │   ├── broker.py          # Broker factory
│   │   ├── paper_broker.py    # Paper trading simulator
│   │   ├── utils.py           # Order utilities
│   │   └── angel_one/         # Angel One integration
│   │       ├── auth.py        # Authentication
│   │       ├── orders.py      # Order management
│   │       ├── positions.py   # Position tracking
│   │       ├── market_data.py # Market data
│   │       ├── websocket.py   # Real-time data
│   │       ├── account.py     # Account info
│   │       └── live_broker.py # Live broker
│   ├── indicators/            # Technical indicators
│   │   └── volatility.py
│   ├── risk/                  # Risk management
│   │   └── position_sizing.py
│   ├── strategies/            # Trading strategies
│   │   ├── base_strategy.py
│   │   ├── premium_selling.py
│   │   ├── iron_condor.py
│   │   ├── calendar_spread.py
│   │   └── ratio_spread.py
│   └── ui/                    # Legacy UI module
├── tests/
│   ├── test_backtesting.py
│   ├── test_broker.py
│   ├── test_calendar_spread.py
│   ├── test_dashboard.py
│   ├── test_iron_condor.py
│   ├── test_iv_rank.py
│   ├── test_premium_selling.py
│   └── test_ratio_spread.py
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

## Broker Integration

The system supports both paper trading and live trading with Angel One broker.

### Paper Trading (Default)

Paper trading is enabled by default for safe testing:

```python
from src.execution.broker import BrokerFactory

# Create a paper broker
broker = BrokerFactory.create(mode="paper", initial_capital=1_000_000)

# Login (no credentials required for paper trading)
broker.login()

# Place a test order
order_id = broker.place_order(
    symbol="NIFTY24DEC22000CE",
    quantity=50,
    order_type="MARKET",
    transaction_type="BUY"
)

# Check positions
positions = broker.get_positions()
print(positions)
```

### Live Trading with Angel One

For live trading, set up your credentials:

```bash
# Set environment variables (never commit credentials!)
# Use .env files with proper .gitignore entries, or use a secrets manager
export ANGEL_ONE_API_KEY="your-api-key"
export ANGEL_ONE_CLIENT_ID="your-client-id"
export ANGEL_ONE_PASSWORD="your-password"
export ANGEL_ONE_TOTP_SECRET="your-totp-secret"
```

> ⚠️ **Security Warning**: Never commit credentials to version control. Use environment variables, `.env` files (added to `.gitignore`), or a secrets manager like AWS Secrets Manager.

```python
from src.execution.broker import BrokerFactory

# Create a live broker
broker = BrokerFactory.create(mode="live")

# Login with TOTP
broker.login()

# Subscribe to market data
broker.subscribe_market_data(["NIFTY", "BANKNIFTY"])

# Place orders
order_id = broker.place_order(
    symbol="NIFTY24DEC22000CE",
    quantity=50,
    order_type="LIMIT",
    transaction_type="BUY",
    price=150.0
)
```

### Broker Configuration

Configure broker settings in `config/broker_settings.py`:

```python
BROKER_RISK_CONFIG = {
    "max_order_value": 500_000,      # 5 Lakhs max per order
    "max_daily_loss": 50_000,        # 50K daily loss limit
    "max_daily_trades": 100,
    "max_positions": 10,
}
```

## Production Deployment

The system includes complete AWS deployment infrastructure.

### Quick Deploy

```bash
# Deploy to development
./deployment/scripts/deploy.sh dev

# Deploy to staging
./deployment/scripts/deploy.sh staging

# Deploy to production
./deployment/scripts/deploy.sh prod
```

### Docker Compose (Local)

```bash
# Start all services locally
cd deployment/docker
docker-compose up -d

# Access the dashboard
open http://localhost:8501
```

### AWS Infrastructure

The Terraform configuration provisions:

- **VPC**: Secure network with public/private subnets
- **ECS**: Fargate-based container orchestration
- **RDS**: PostgreSQL database for trade storage
- **S3**: Data lake for market data and backups
- **CloudWatch**: Monitoring dashboards and alerts
- **ALB**: Application load balancer with HTTPS

### Terraform Deployment

```bash
cd deployment/terraform

# Initialize
terraform init

# Plan for development
terraform plan -var-file=environments/dev.tfvars

# Apply
terraform apply -var-file=environments/dev.tfvars
```

### CI/CD Pipeline

GitHub Actions workflow automatically:

1. Runs tests on every push
2. Builds Docker images
3. Pushes to Amazon ECR
4. Deploys to ECS
5. Runs health checks

### Monitoring

Access CloudWatch dashboards for:

- Container CPU/Memory utilization
- Application latency and errors
- Database connections
- Trading metrics

### Rollback

```bash
# Rollback to previous version
./deployment/scripts/rollback.sh dev

# Rollback to specific revision
./deployment/scripts/rollback.sh prod --to-revision 5
```

See [deployment/docs/DEPLOYMENT.md](deployment/docs/DEPLOYMENT.md) for detailed deployment instructions.

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
- streamlit>=1.29.0
- plotly>=5.18.0
- smartapi-python>=1.3.0
- pyotp>=2.8.0
- websocket-client>=1.5.0

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Documentation

- [docs/PHASE1_README.md](docs/PHASE1_README.md) - Phase 1 documentation (Core trading engine)
- [docs/PHASE4_README.md](docs/PHASE4_README.md) - Phase 4 documentation (Iron Condor, Calendar Spread, Ratio Spread)
- [deployment/docs/DEPLOYMENT.md](deployment/docs/DEPLOYMENT.md) - Deployment guide
- [deployment/docs/ARCHITECTURE.md](deployment/docs/ARCHITECTURE.md) - System architecture
- [deployment/docs/RUNBOOK.md](deployment/docs/RUNBOOK.md) - Operations runbook

---

**Remember**: Always paper trade first. Understand the risks. Start small.
