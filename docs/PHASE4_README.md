# Phase 4: Additional Trading Strategies

This document describes the implementation of three additional options trading strategies to complement the existing Premium Selling (Short Strangle) strategy.

## Overview

Phase 4 introduces three new strategy implementations:

1. **Iron Condor Strategy** - A neutral options strategy for range-bound markets
2. **Calendar Spread Strategy** - A time decay strategy for low volatility environments
3. **Ratio Spread Strategy** - A directional strategy with premium collection

All strategies extend the `BaseStrategy` class and follow the patterns established in the existing `premium_selling.py`.

---

## 1. Iron Condor Strategy

### Overview

An Iron Condor is a neutral options strategy that combines a bull put spread and bear call spread. It profits when the underlying stays within a defined range and implied volatility decreases.

### Structure

```
       Long Put    Short Put        Short Call    Long Call
           │           │                │            │
   ────────┼───────────┼────────────────┼────────────┼────────
           │           │    SPOT        │            │
      Lowest Strike  Lower Strike   Upper Strike  Highest Strike
```

- **Sell OTM Put** (lower strike) - Receive premium
- **Buy further OTM Put** (lowest strike) - Protection against downside
- **Sell OTM Call** (upper strike) - Receive premium
- **Buy further OTM Call** (highest strike) - Protection against upside

### Entry Conditions

| Parameter | Value | Description |
|-----------|-------|-------------|
| IV Rank | > 50 | Moderate to high IV environment |
| Short Delta | 0.15 - 0.20 | OTM strikes for short legs |
| Wing Width | NIFTY: 50, BANKNIFTY: 100 | Distance to long strikes |
| Min DTE | 14 days | Minimum days to expiry |
| Max DTE | 45 days | Maximum days to expiry |

### Exit Conditions

| Condition | Trigger | Description |
|-----------|---------|-------------|
| Profit Target | 50% of credit | Close when half of max profit achieved |
| Stop Loss | 200% of credit | Close when loss equals 2x credit received |
| Time Exit | 5-7 DTE | Close before expiry to avoid gamma risk |
| Strike Breach | Spot crosses short strike | Emergency exit if tested |

### Mathematical Formulas

```
Max Profit = Net Credit Received
Max Loss = Wing Width - Net Credit
Breakeven Upper = Short Call Strike + Net Credit
Breakeven Lower = Short Put Strike - Net Credit
```

### Example

```
NIFTY Spot: 18000
Expiry: 30 days

Position:
- Buy 17400 PE @ ₹50
- Sell 17500 PE @ ₹100  
- Sell 18500 CE @ ₹100
- Buy 18600 CE @ ₹50

Net Credit = (100 + 100) - (50 + 50) = ₹100
Wing Width = 100 points
Max Profit = ₹100 × Lot Size
Max Loss = (100 - 100) × Lot Size = ₹0 (rare case)
```

### Risk Profile

```
P&L
  │
  │                ════════════════════
  │               /                    \
  │              /                      \
──┼─────────────/────────────────────────\──────────
  │            /                          \
  │           /                            \
  │          /                              \
  └─────────┴──────────────────────────────┴────────→ Price
         17400   17500        18500   18600
```

---

## 2. Calendar Spread Strategy

### Overview

A Calendar Spread (Time Spread) profits from the differential time decay between near-term and far-term options. It benefits when implied volatility increases and the underlying stays near the strike price.

### Structure

```
Timeline
─────────────────────────────────────────────────────►
       │                    │                    │
    Entry              Near Expiry          Far Expiry
                           │                    │
                      Short Option         Long Option
                      (7-14 DTE)           (30-45 DTE)
```

- **Sell near-term option** - Captures faster time decay
- **Buy same-strike far-term option** - Maintains delta exposure

### Entry Conditions

| Parameter | Value | Description |
|-----------|-------|-------------|
| IV Rank | < 30 | Low IV environment (expecting expansion) |
| Strike Selection | ATM | At-the-money for maximum theta |
| Near Expiry | 7-14 days | Short-dated option to sell |
| Far Expiry | 30-45 days | Longer-dated option to buy |

### Exit Conditions

| Condition | Trigger | Description |
|-----------|---------|-------------|
| Profit Target | 35% of debit | Close when 35% profit achieved |
| Stop Loss | 50% of debit | Close when half of investment lost |
| Time Exit | 2-3 DTE near | Close before near-term expiry |
| Roll | Profitable | Can roll near option to next expiry |

### Mathematical Formulas

```
Max Profit = Achieved when underlying at strike at near expiry
Max Loss = Net Debit Paid
Theta Benefit = |Near Theta| - |Far Theta| (positive)
Vega Exposure = Far Vega - Near Vega (positive)
```

### Example

```
NIFTY Spot: 18000

Position:
- Sell 18000 CE (10 DTE) @ ₹80
- Buy 18000 CE (38 DTE) @ ₹150

Net Debit = 150 - 80 = ₹70
Max Loss = ₹70 × Lot Size
Profit Target = ₹70 × 35% = ₹24.50 profit
```

### Greeks Focus

| Greek | Direction | Reasoning |
|-------|-----------|-----------|
| Theta | Positive | Near option decays faster than far |
| Vega | Positive | Benefits from IV increase |
| Delta | Near-neutral | ATM strike minimizes directional risk |

### Risk Profile

```
P&L at Near Expiry
  │
  │         ╱╲
  │        ╱  ╲
  │       ╱    ╲
  │      ╱      ╲
──┼─────╱────────╲─────────────────
  │    ╱          ╲
  │   ╱            ╲
  │  ╱              ╲
  └──────────────────────────────► Price
              Strike
```

---

## 3. Ratio Spread Strategy

### Overview

A Ratio Spread involves buying and selling options at different strikes in unequal quantities. It combines directional exposure with premium selling.

### Structure

**Put Ratio Spread (Bullish):**
```
       1× Long ATM Put              2× Short OTM Put
             │                           │
   ──────────┼───────────────────────────┼────────────
             │         SPOT              │
        Long Strike                 Short Strike
        (Higher)                    (Lower)
```

**Call Ratio Spread (Bearish):**
```
       1× Long ATM Call             2× Short OTM Call
             │                           │
   ──────────┼───────────────────────────┼────────────
             │         SPOT              │
        Long Strike                 Short Strike
        (Lower)                     (Higher)
```

### Entry Conditions

| Parameter | Value | Description |
|-----------|-------|-------------|
| IV Rank | > 60 | High IV for selling extra options |
| Ratio | 1:2 | Buy 1, Sell 2 (can adjust to 1:3) |
| Long Delta | 0.50 | ATM strike for long leg |
| Short Delta | 0.20 - 0.25 | OTM strikes for short legs |
| Min DTE | 21 days | Minimum days to expiry |
| Max DTE | 45 days | Maximum days to expiry |

### Exit Conditions

| Condition | Trigger | Description |
|-----------|---------|-------------|
| Profit Target | 75% of max | Close when 75% of max profit achieved |
| Stop Loss | 2% breach | Exit if underlying moves 2% beyond short strike |
| Time Exit | 7 DTE | Close before expiry |
| Max Profit Zone | At short strike | Ideally close at expiry if at short strike |

### Mathematical Formulas

**1:2 Put Ratio Spread:**
```
Max Profit = (Long Strike - Short Strike) + Net Credit
Downside Breakeven = Short Strike - Max Profit
Upside Risk = Net Debit (if any)
Downside Risk = Unlimited below breakeven
```

**1:2 Call Ratio Spread:**
```
Max Profit = (Short Strike - Long Strike) + Net Credit
Upside Breakeven = Short Strike + Max Profit
Downside Risk = Net Debit (if any)
Upside Risk = Unlimited above breakeven
```

### Example

```
NIFTY Spot: 18000
Put Ratio Spread (Bullish View)

Position:
- Buy 1× 18000 PE @ ₹150
- Sell 2× 17500 PE @ ₹60 each

Net Credit/Debit = (2 × 60) - 150 = -30 (small debit)
Max Profit = (18000 - 17500) + (-30) = ₹470 (at 17500 at expiry)
Breakeven = 17500 - 470 = 17030
```

### Risk Profile

```
P&L (Put Ratio Spread)
  │
  │                    ╱╲
  │                   ╱  ╲ Max Profit at Short Strike
  │                  ╱    ╲
  │                 ╱      ╲
──┼────────────────╱────────╲─────────────────
  │               ╱          ╲
  │ Unlimited    ╱            ╲ Limited Risk
  │ Risk Below  ╱              ╲ Above
  └────────────┴───────────────┴────────────► Price
           Breakeven      Short    Long
                         Strike   Strike
```

---

## Configuration

All configurations are defined in `config/settings.py`:

```python
# Iron Condor Configuration
IRON_CONDOR_CONFIG = {
    "iv_rank_entry_threshold": 50,
    "short_delta_range": (0.15, 0.20),
    "wing_width": {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100},
    "profit_target_pct": 0.50,
    "stop_loss_pct": 2.00,
    "days_before_expiry_exit": 7,
    "min_days_to_expiry": 14,
    "max_days_to_expiry": 45,
    "position_size_pct": 0.02,
}

# Calendar Spread Configuration
CALENDAR_SPREAD_CONFIG = {
    "iv_rank_entry_threshold": 30,
    "iv_rank_entry_below": True,  # Enter when IV is LOW
    "strike_selection": "ATM",
    "near_expiry_days_range": (7, 14),
    "far_expiry_days_range": (30, 45),
    "profit_target_pct": 0.35,
    "stop_loss_pct": 0.50,
    "days_before_near_expiry_exit": 3,
    "position_size_pct": 0.015,
}

# Ratio Spread Configuration
RATIO_SPREAD_CONFIG = {
    "iv_rank_entry_threshold": 60,
    "ratio": (1, 2),
    "long_delta": 0.50,
    "short_delta_range": (0.20, 0.25),
    "profit_target_pct": 0.75,
    "stop_loss_breach_pct": 0.02,
    "days_before_expiry_exit": 7,
    "min_days_to_expiry": 21,
    "max_days_to_expiry": 45,
    "position_size_pct": 0.01,
}
```

---

## Usage

### Basic Usage

```python
from src.strategies import IronCondorStrategy, CalendarSpreadStrategy, RatioSpreadStrategy
from config.settings import IRON_CONDOR_CONFIG, CALENDAR_SPREAD_CONFIG, RATIO_SPREAD_CONFIG

# Initialize strategies
iron_condor = IronCondorStrategy(config=IRON_CONDOR_CONFIG)
calendar_spread = CalendarSpreadStrategy(config=CALENDAR_SPREAD_CONFIG)
ratio_spread = RatioSpreadStrategy(config=RATIO_SPREAD_CONFIG)

# Initialize with data
iron_condor.initialize(options_data)
calendar_spread.initialize(options_data)
ratio_spread.initialize(options_data)

# Generate signals
signal = iron_condor.generate_signal(data, timestamp)
if signal and signal.is_entry():
    quantity = iron_condor.calculate_position_size(capital, 0, signal)
    iron_condor.open_iron_condor(signal, quantity)
```

### With Backtesting Engine

```python
from src.backtesting.engine import BacktestEngine

# Run backtest
engine = BacktestEngine(initial_capital=1_000_000)
results = engine.run(iron_condor, options_data)

# Generate report
print(results.generate_report())
```

---

## Strategy Comparison

| Aspect | Iron Condor | Calendar Spread | Ratio Spread |
|--------|-------------|-----------------|--------------|
| **Market View** | Neutral | Neutral/Slightly Directional | Directional |
| **IV Environment** | High (>50) | Low (<30) | High (>60) |
| **Risk Profile** | Defined | Defined | Partially Undefined |
| **Max Profit** | Limited | Limited | Limited |
| **Max Loss** | Limited | Limited | Unlimited on one side |
| **Theta** | Positive | Positive | Positive |
| **Vega** | Negative | Positive | Mixed |
| **Complexity** | Medium | Medium | High |
| **Capital Req.** | Medium | Low | Low-Medium |

---

## File Structure

```
src/strategies/
├── __init__.py          # Updated exports
├── base_strategy.py     # Base class (unchanged)
├── premium_selling.py   # Short Strangle (unchanged)
├── iron_condor.py       # NEW - Iron Condor implementation
├── calendar_spread.py   # NEW - Calendar Spread implementation
└── ratio_spread.py      # NEW - Ratio Spread implementation

tests/
├── test_iron_condor.py      # NEW - 19 tests
├── test_calendar_spread.py  # NEW - 16 tests
└── test_ratio_spread.py     # NEW - 19 tests

config/
└── settings.py          # Updated with new configurations
```

---

## Testing

All strategies include comprehensive unit tests:

```bash
# Run all tests
pytest tests/ -v

# Run specific strategy tests
pytest tests/test_iron_condor.py -v
pytest tests/test_calendar_spread.py -v
pytest tests/test_ratio_spread.py -v

# Run with coverage
pytest tests/ --cov=src/strategies --cov-report=html
```

### Test Coverage

| Strategy | Tests | Coverage |
|----------|-------|----------|
| Iron Condor | 19 | Position, Strategy, Entry/Exit, IV Integration |
| Calendar Spread | 16 | Position, Strategy, Entry/Exit, Greeks |
| Ratio Spread | 19 | Position, Strategy, Entry/Exit, Multiple Types |

---

## Risk Warnings

⚠️ **IMPORTANT DISCLAIMER**

1. **Iron Condor**: While risk is defined, sudden large moves can result in maximum loss quickly
2. **Calendar Spread**: Term structure changes can cause unexpected losses
3. **Ratio Spread**: Has UNLIMITED RISK on one side - use with extreme caution

**Always:**
- Test extensively in paper trading
- Start with small position sizes
- Understand all risk scenarios before trading
- Have exit plans for all market conditions
- Monitor positions actively

---

## Future Enhancements

- [ ] Adjustment strategies for each spread type
- [ ] Rolling functionality for calendar spreads
- [ ] Dynamic ratio adjustment based on IV levels
- [ ] Greeks-based exit conditions
- [ ] Backtesting comparison across strategies
- [ ] Machine learning for optimal entry timing
