# Financial Analysis Skill — Quick Start

Complete guide to setting up, configuring, and testing the skill from a fresh clone.

## Prerequisites

You need Python 3.10+ (3.12 recommended). Check your version:

```bash
python3 --version
```

If you see Python 3.9.x (common on macOS — that's the old Apple system Python), you need to install a newer version:

```bash
brew install python@3.12
```

Homebrew installs it to `/opt/homebrew/opt/python@3.12/bin/` but doesn't override the system `python3`. To make it your default, add these to your `~/.zshrc`:

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"' >> ~/.zshrc
echo 'alias python3=python3.12' >> ~/.zshrc
echo 'alias python=python3' >> ~/.zshrc
source ~/.zshrc
```

**Important:** Close and reopen your terminal after editing `.zshrc` for the changes to fully take effect. Verify:

```bash
python3 --version   # should show 3.12.x
python --version    # should show 3.12.x
```

If `python3 --version` still shows 3.9.x after reopening the terminal, create a symlink:

```bash
ln -sf /opt/homebrew/opt/python@3.12/bin/python3.12 /opt/homebrew/bin/python3
```

## Step 1 — Clone and enter the directory

```bash
git clone <your-repo-url>
cd financial-analysis
```

## Step 2 — Run the setup script

```bash
chmod +x setup.sh
./setup.sh
```

This does three things:
1. Creates a Python virtual environment at `.venv/` using your system Python
2. Installs all dependencies from `requirements.txt` (yfinance, pandas, feedparser, requests, etc.)
3. Initializes the API config file at `~/.financial-analysis/api_keys.json`

If `pandas-ta` fails to install, the script continues — it's optional (used for local technical analysis computations). Everything else works without it.

Verify you see `Setup complete!` at the end. If the setup picked up the wrong Python version (e.g. "Using: Python 3.9.6"), force it explicitly:

```bash
rm -rf .venv
PYTHON=python3.12 ./setup.sh
```

## Step 3 — Activate the virtual environment

```bash
source .venv/bin/activate
```

Your terminal prompt should change to show `(.venv)` at the beginning. **You need to do this every time you open a new terminal before running any skill commands.**

## Step 4 — Check what's working out of the box

```bash
python scripts/api_config.py status
```

You'll see a table like this:

```
API                            Tier     Key?   Status       Rate Limit           Cost
──────────────────────────────────────────────────────────────────────────────────────────
Yahoo Finance (yfinance)       FREE     No     READY        2000/day             Free (unofficial)
Finnhub                        FREE     Yes    NEEDS KEY    86400/day            Free (60/min), paid $50/mo
SEC EDGAR (Official)           FREE     No     READY        864000/day           Free (government)
Mboum Finance                  FREE     Yes    NEEDS KEY    20/day               Free (~600/mo), paid $9.95/mo
Alpha Vantage                  FREE     Yes    NEEDS KEY    25/day               Free (25/day), paid $29.99/mo
Seeking Alpha (RSS)            FREE     No     READY        30/min               Free (unlimited RSS)
...
```

**4 APIs work immediately with zero keys:** yfinance, SEC EDGAR, ApeWisdom, StockTwits, and Seeking Alpha RSS. The rest need free API keys.

## Step 5 — Add API keys

Open the config file:

```bash
nano ~/.financial-analysis/api_keys.json
```

For each API you want to activate, fill in the `api_key` field and change `enabled` to `true`. The file already contains signup URLs for every API.

Example — activating Finnhub:

```json
"finnhub": {
    "api_key": "your_actual_key_here",
    "tier": "FREE",
    "cost": "Free (60/min), paid $50/mo",
    "signup_url": "https://finnhub.io/register",
    "enabled": true
}
```

**Your keys are safe.** They're stored at `~/.financial-analysis/api_keys.json` (in your home directory, not in the repo). Running `setup.sh` again or running tests will never overwrite them.

**Recommended signup order** (all free, all instant):

| Priority | API | Signup | What you get |
|----------|-----|--------|-------------|
| 1 | Finnhub | https://finnhub.io/register | Analyst ratings, insider trades, earnings, news (60/min) |
| 2 | Alpha Vantage | https://www.alphavantage.co/support/#api-key | Technical indicators, AI news sentiment (25/day) |
| 3 | FMP | https://financialmodelingprep.com/developer/docs/ | Financial statements, company profiles (250/day) |
| 4 | Polygon | https://polygon.io/dashboard/signup | Price history backup, dividends (5/min) |
| 5 | Alpaca | https://app.alpaca.markets/signup | Real-time news, options data (200/min) |
| 6 | Mboum | https://rapidapi.com/sparkhub-sparkhub-default/api/mboum-finance | Congress trades, options (600/mo) |
| 7 | Seeking Alpha (RapidAPI) | https://rapidapi.com/apidojo/api/seeking-alpha | Quant ratings, factor grades (1K/mo) |
| 8 | Quiver Quantitative | https://www.quiverquant.com/ | Congress trades, lobbying, dark pool ($10/mo — only paid API) |

You can also set keys as environment variables instead of editing the JSON file:

```bash
export FINNHUB_API_KEY=your_key
export ALPHA_VANTAGE_API_KEY=your_key
export FMP_API_KEY=your_key
export POLYGON_API_KEY=your_key
export ALPACA_API_KEY=your_key
export MBOUM_API_KEY=your_key
export SEEKING_ALPHA_RAPIDAPI_KEY=your_key
export QUIVER_API_KEY=your_key
```

After adding keys, verify they're detected:

```bash
python scripts/api_config.py status
```

APIs you configured should now show `READY`.

For more details on each API (endpoints, headers, authentication), see `references/api_setup_guide.md`.

## Step 6 — Run the test suite

```bash
python tests/test_skill.py
```

The tests run in 3 groups:

| Group | What it tests | Needs network? | Needs keys? |
|-------|--------------|----------------|-------------|
| **1 — Offline (12 tests)** | Config registry, fallback chains, rate limiter, error logging, ticker extraction, pipeline mocks | No | No |
| **2 — Live APIs (10 tests)** | yfinance, SEC EDGAR, ApeWisdom, Finnhub, Alpha Vantage, FMP, RSS feeds, Seeking Alpha | Yes | Some |
| **3 — Integration (2 tests)** | End-to-end pipeline simulation, daily summary export | No | No |

What the results mean:
- `✓ PASS` — Working correctly
- `⊘ SKIP` — Missing a dependency or API key (not a failure — add the key and re-run to unlock)
- `✗ FAIL` — Something is broken (check the error message below it)

Group 1 and Group 3 should all pass with zero configuration. Group 2 tests light up as you add API keys.

## Step 7 — Check usage reports

After running tests or any real workflow, the tracker logs every API call:

```bash
# See today's API usage with % of free limits
python scripts/usage_tracker.py daily

# See recent errors and which fallback APIs were used
python scripts/usage_tracker.py errors

# Export a JSON summary (for tracking usage trends over time)
python scripts/usage_tracker.py summary
```

The daily report shows WARNING (>70% of limit) and CRITICAL (>90%) alerts with paid tier upgrade recommendations when warranted.

## Step 8 — Deactivate when done

```bash
deactivate
```

## Every time you come back

```bash
cd financial-analysis
source .venv/bin/activate
# ... run commands ...
deactivate
```

## Use Case 1 — Weekly Portfolio Review

Review your current holdings with P&L-aware Buy More / Hold / Trim / Sell recommendations. Cost basis is required so the tool can factor your actual gains/losses into the action (e.g., take partial profits at 2x, don't sell at a loss if fundamentals support recovery).

**From command line** (format: `TICKER:SHARES:AVG_COST`):

```bash
python scripts/run_portfolio_review.py AAPL:100:150.50 MSFT:50:380 NVDA:25:500
```

**From a CSV file** (must have `ticker`, `shares`, and `avg_cost` columns):

```csv
ticker,shares,avg_cost
AAPL,100,150.50
MSFT,50,380.00
NVDA,25,500.00
```

```bash
python scripts/run_portfolio_review.py --file portfolio.csv
```

**Save results to JSON:**

```bash
python scripts/run_portfolio_review.py --file portfolio.csv --output review.json
```

**Output:** Every run automatically saves a human-readable markdown report to `data/portfolio_review_{date}.md`. This file contains the full portfolio summary, macro context, sector exposure, per-stock details (price, P&L, scores, sub-scores, entry/exit levels, action), and warnings — all in one document you can search and reference later. The `--output` flag additionally saves the structured JSON for programmatic access.

The review includes: macro context header (upcoming earnings, FOMC, CPI, jobs reports), sector rotation analysis (11 sectors vs SPY), per-stock deep dives with P&L calculations, and a portfolio summary with total P&L, sector exposure, concentration warnings, and biggest winner/loser.

## Use Case 2 — Daily Opportunity Scanner

Scans RSS, Reddit, StockTwits, and Congress trades for new opportunities, then quick-scores and promotes the best candidates to full deep dives.

```bash
python scripts/run_daily_scanner.py
```

**Options:**

```bash
# Score top 15 candidates, deep-dive the best 5
python scripts/run_daily_scanner.py --top 15 --deep-dive-count 5

# Skip specific sources
python scripts/run_daily_scanner.py --skip-rss --skip-congress

# Save results
python scripts/run_daily_scanner.py --output scan.json
```

The scanner works in 4 phases:
1. Scans data sources for mentioned tickers
2. Merges and ranks candidates by mention frequency across sources
3. Quick-scores the top candidates (yfinance + TradingView only — fast, no API quota)
4. Deep-dives candidates scoring 6.0+ with full analysis and entry/exit levels

## Use Case 3 — On-Demand Stock Deep Dive

Full analyst-grade report on 1-10 specific tickers with every available data source.

```bash
python scripts/run_deep_dive.py AAPL
```

**Multiple tickers:**

```bash
python scripts/run_deep_dive.py AAPL MSFT NVDA
```

**Save to JSON:**

```bash
python scripts/run_deep_dive.py AAPL --output aapl_analysis.json
```

Each report includes: composite score (0-10), fundamental/technical/sentiment sub-scores, TradingView consensus, 3 entry levels, 3 exit targets, stop loss, risk/reward ratios, position sizing, and a data source attribution table showing which APIs succeeded or failed.

**Force fresh data (bypass cache):**

```bash
python scripts/run_deep_dive.py AAPL --no-cache
```

## Data Cache

Every deep dive automatically saves all raw API data to `data/{TICKER}_{YYYY-MM-DD}.md` — a human-readable markdown file you can search and review later. If you run the same ticker again on the same day, it loads from cache instead of re-fetching from APIs.

**View cached tickers for today:**

```bash
python scripts/data_cache.py list
```

**View a cached file:**

```bash
python scripts/data_cache.py view AAPL
```

**Force refresh (ignore cache):**

```bash
python scripts/run_deep_dive.py AAPL --no-cache
python scripts/run_portfolio_review.py AAPL:100:150.50 MSFT:50:380 --no-cache
python scripts/run_daily_scanner.py --no-cache
```

Each `.md` file contains all data from every API call: price history, fundamentals (valuation, growth, profitability, financial health), technical indicators (SMA, RSI, MACD, Bollinger, support/resistance, Fibonacci), TradingView consensus, analyst ratings, earnings, insider trades, news sentiment with headlines, Reddit mentions, StockTwits sentiment, Congress trades, dividends, key articles with links, composite score breakdown, and entry/exit levels.

The raw JSON data is also included in code blocks within each section for programmatic access.

## Macro Calendar

Surfaces timing-critical events (earnings, FOMC, CPI, jobs reports, options expiration) that should influence portfolio decisions.

```bash
python scripts/macro_calendar.py AAPL MSFT NVDA
```

Shows upcoming earnings dates for the specified tickers plus all major economic events in the next 14 days. Risk flags are raised for imminent earnings (≤3 days) and high-impact macro events (≤5 days). This runs automatically as part of the portfolio review — you only need the standalone command for quick checks.

## Sector Rotation

Tracks all 11 S&P sector ETFs (XLK, XLF, XLE, XLV, etc.) against SPY to identify which sectors are leading or lagging the market over 1-week, 1-month, and 3-month windows.

```bash
python scripts/sector_rotation.py
```

The sector rotation data feeds into two places: a ±0.5 score modifier in the composite scoring (tailwind for strong sectors, headwind for weak ones), and a sector exposure analysis in the portfolio review that warns about concentration in underperforming sectors.

## File structure

```
financial-analysis/
├── setup.sh                         ← One-command setup (venv + deps + config)
├── requirements.txt                 ← Pinned Python dependencies
├── .gitignore                       ← Keeps .venv/ and logs out of version control
├── SKILL.md                         ← Main skill instructions (3 use cases)
├── QUICKSTART.md                    ← You are here
├── tests/test_skill.py                    ← Test suite (24 tests in 3 groups)
├── .venv/                           ← Python virtual environment (created by setup.sh)
├── data/                            ← Cached API data (auto-created on first run)
│   ├── AAPL_2026-02-14.md           ← Human-readable data dump for searching
│   ├── MSFT_2026-02-14.md
│   └── .cache/                      ← JSON sidecar files (used for cache lookups)
│       ├── AAPL_2026-02-14.json
│       └── MSFT_2026-02-14.json
├── scripts/
│   ├── api_config.py                ← API registry (14 APIs), key management, fallback chains
│   ├── api_caller.py                ← Resilient caller with automatic fallback on failure
│   ├── usage_tracker.py             ← Rate limit enforcement, error logs, daily reports
│   ├── data_cache.py                ← Data caching layer (.md + .json per ticker per day)
│   ├── rss_feeds.py                 ← 18 RSS feeds in 3 tiers, ticker extraction
│   ├── data_fetchers.py             ← API fetch implementations for all 14 sources
│   ├── technical_analysis.py        ← Local TA engine (pandas-ta + manual fallbacks)
│   ├── scoring.py                   ← Composite scoring (40% fund + 30% tech + 30% sent)
│   ├── entry_exit.py                ← 3 entry levels + 3 exit targets + position sizing
│   ├── macro_calendar.py            ← Earnings dates, FOMC/CPI/Jobs/OPEX calendar, risk flags
│   ├── sector_rotation.py           ← 11 sector ETFs vs SPY, relative strength, score modifier
│   ├── run_deep_dive.py             ← Use Case 3: on-demand deep dive workflow
│   ├── run_daily_scanner.py         ← Use Case 2: daily opportunity scanner workflow
│   └── run_portfolio_review.py      ← Use Case 1: weekly portfolio review (P&L-aware)
└── references/
    └── api_setup_guide.md           ← Detailed setup guide for every API
```

Config and logs (not in the repo):

```
~/.financial-analysis/
├── api_keys.json             ← Your API keys (created by setup.sh, never overwritten)
└── logs/
    ├── api_usage.jsonl       ← Every API call logged with timestamps
    ├── error_log.jsonl       ← Failed calls with fallback outcomes
    └── daily_summary.json    ← Aggregated daily report
```

## Troubleshooting

**setup.sh picks up Python 3.9 instead of 3.12:**
Aliases in `~/.zshrc` don't work inside scripts. Either create a symlink (see Prerequisites above) or override explicitly:
```bash
PYTHON=python3.12 ./setup.sh
```

**pandas-ta won't install:**
It sometimes lags behind the latest pandas. Try:
```bash
pip install pandas-ta --no-deps
```
Or pin an older pandas: `pip install "pandas<2.2" pandas-ta`

**urllib3 LibreSSL warning:**
Harmless. Means your system SSL library is older than urllib3 expects. Does not affect functionality.

**Reset everything:**
```bash
rm -rf .venv ~/.financial-analysis
./setup.sh
```

**API keys disappeared after re-running setup:**
This was a bug in earlier versions. The current `init_config()` preserves existing keys. If you're on an older version, pull the latest code.

## Scoring breakdown

The composite score combines three dimensions:

**Fundamental (40% weight) — 10 factors:** PE ratio, PB ratio, revenue growth, EPS growth, profit margin, debt-to-equity, free cash flow, ROE, analyst consensus, earnings surprises.

**Technical (30% weight) — 8 factors:** Trend (price vs SMA 50/200), RSI, MACD, Bollinger Band position, support/resistance proximity, volume trend, Fibonacci levels, ADX/stochastic. Plus TradingView consensus as a cross-check.

**Sentiment (30% weight) — 7 factors:** Reddit mentions, StockTwits bull/bear ratio, AI news sentiment, TradingView consensus, RSS buzz, insider activity, Congress trades.

**Sector rotation modifier (±0.5):** After the weighted composite is computed, a sector rotation adjustment of -0.5 to +0.5 is applied based on the stock's sector relative strength vs SPY. Strong-performing sectors get a tailwind boost; weak sectors get a headwind penalty. The final score is clamped to 0-10.

Score mapping: 8+ = STRONG BUY, 6.5-8 = BUY, 5-6.5 = WATCH·HOLD, 3.5-5 = HOLD, below 3.5 = SELL.

**P&L-aware actions (portfolio review only):** When reviewing holdings with cost basis, the action recommendation combines the composite score with your actual P&L position. For example: 100%+ gains trigger partial profit-taking even on strong scores, -20% losses with strong fundamentals suggest buying the dip, and -50% losses with weak scores recommend cutting losses to redeploy capital.
