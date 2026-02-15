# Overnight Range Analysis

Standalone toolkit for analyzing overnight range scenarios in futures markets. Classifies trading days into 17 scenarios based on 06:00-09:00 ET price action relative to the overnight range (18:00-06:00 ET), then computes outcome metrics and generates detailed graphics.

## Features

- **Overnight Range Calculation**: Compute high, low, and middle for 18:00 ET → 06:00 ET sessions
- **17 Scenario Classification**: Bull (1-3, 7-11), Bear (4-6, 12-16), Inside (17) patterns
- **Outcome Metrics**: Track price behavior 09:00-16:00 ET and 09:00-11:30 ET windows
- **Individual Day Graphics**: Generate detailed candlestick charts for each analyzed day
- **Schematic Diagrams**: Visual reference diagrams for each scenario type

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Database Path

Edit `config.json` to point to your SQLite database containing `raw_bars_1min` table:

```json
{
  "database": {
    "path": "sqlite:///C:/path/to/your/trading.db"
  }
}
```

The database must have a `raw_bars_1min` table with columns: `timestamp`, `symbol`, `open`, `high`, `low`, `close`, `volume`.

## Usage

All scripts are run from the repository root directory.

### Overnight Range Service

Compute overnight range (18:00 ET → 06:00 ET) for a symbol and date range:

```bash
# Single day
python -m src.overnight_range_service --symbol NQ --date 2026-02-13

# Date range
python -m src.overnight_range_service --symbol NQ --start 2025-02-14 --end 2026-02-13

# JSON output
python -m src.overnight_range_service --symbol NQ --date 2026-02-13 --json

# Override database
python -m src.overnight_range_service --symbol NQ --date 2026-02-13 --db /path/to/other.db
```

### Scenario Analysis

Classify days into scenarios and compute outcome metrics:

```bash
# Single day
python -m src.overnight_range_scenarios --symbol NQ --date 2026-02-13

# 1-year analysis
python -m src.overnight_range_scenarios --symbol NQ --start 2025-02-14 --end 2026-02-13

# 3-year analysis
python -m src.overnight_range_scenarios --symbol NQ --start 2023-02-14 --end 2026-02-13
```

Output shows:
- Total days per scenario
- Percentage breakdown
- Bull scenarios: % above mid, above 06-09 low, above 18-09 low, new high 09-11:30
- Bear scenarios: % below mid, below 06-09 high, below 18-09 high, new low 09-11:30

### Generate Day Graphics

Create individual candlestick charts for each analyzed day:

```bash
# Single day
python -m src.generate_scenario_graphics --symbol NQ --date 2026-02-13

# Date range (automatically clears old graphics)
python -m src.generate_scenario_graphics --symbol NQ --start 2025-02-14 --end 2026-02-13

# Filter specific scenarios
python -m src.generate_scenario_graphics --symbol NQ --start 2025-01-01 --end 2025-12-31 --scenarios 1,2,3
```

Graphics are saved to `scenario_graphics/scenario_N/` folders with filename format: `{date}_scenario_{N}.png`

Each graphic shows:
- Overnight range reference box (yellow) with high/mid/low lines
- 06:00-09:00 ET window (medium gray) with 1-minute candlesticks
- 09:00-11:30 ET window (light gray) with 1-minute candlesticks

### Generate Schematic Diagrams

Create reference diagrams for scenarios 1-6:

```bash
python -m src.draw_overnight_scenarios
```

Saves diagrams to `docs/overnight_scenario_*.png`

## Documentation

See [docs/OVERNIGHT_RANGE_SCENARIOS.md](docs/OVERNIGHT_RANGE_SCENARIOS.md) for detailed explanation of:
- All 17 scenario definitions
- Overnight range calculation
- Time windows and classifications
- Outcome metrics

## Project Structure

```
Overnight range/
├── config.json                 # Database and output configuration
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── src/                        # Source code
│   ├── __init__.py
│   ├── database_models.py      # SQLAlchemy models
│   ├── overnight_range_service.py
│   ├── overnight_range_scenarios.py
│   ├── generate_scenario_graphics.py
│   └── draw_overnight_scenarios.py
├── docs/                       # Documentation and diagrams
│   ├── OVERNIGHT_RANGE_SCENARIOS.md
│   └── overnight_scenario_*.png
└── scenario_graphics/          # Generated day graphics (output)
    ├── scenario_1/
    ├── scenario_2/
    ...
    └── scenario_17/
```

## Requirements

- Python 3.9+
- SQLite database with 1-minute bar data
- Timezone: America/New_York (handles EDT/EST automatically)

## Examples

**Example 1: Analyze 1 year of NQ data**
```bash
python -m src.overnight_range_scenarios --symbol NQ --start 2025-02-14 --end 2026-02-13
```

**Example 2: Generate graphics for bull scenarios only**
```bash
python -m src.generate_scenario_graphics --symbol NQ --start 2025-02-14 --end 2026-02-13 --scenarios 1,2,3,7,8,9,10,11
```

**Example 3: Use different database**
```bash
python -m src.overnight_range_scenarios --symbol ES --start 2026-01-01 --end 2026-02-13 --db /path/to/es_data.db
```

## Notes

- All times are Eastern Time (ET) with automatic EDT/EST handling via `America/New_York` timezone
- Overnight range: 18:00 ET previous day → 06:00 ET session date
- Morning classification: 06:00 ET → 09:00 ET
- Outcome window: 09:00 ET → 16:00 ET
- New high/low window: 09:00 ET → 11:30 ET
- Graphics generation clears existing PNGs before each run for clean results

## License

Proprietary
