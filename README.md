# Financial Analysis Skill

A Claude Code skill that turns Claude into a professional-grade stock analyst. It aggregates data from 14+ free APIs and 20+ RSS feeds to produce buy/sell ratings, price targets, and entry/exit levels across three workflows.

## Install as a Claude skill

```bash
git clone <repo-url> ~/.claude/skills/financial-analyst
```

Claude will automatically load `SKILL.md` and activate when you ask about stocks, portfolios, or market analysis.

## Three workflows

| Workflow | Command | Frequency |
|----------|---------|-----------|
| Portfolio Review | `python scripts/run_portfolio_review.py AAPL:100:150.50 MSFT:50:380` | Weekly |
| Opportunity Scanner | `python scripts/run_daily_scanner.py` | Daily |
| Stock Deep Dive | `python scripts/run_deep_dive.py AAPL MSFT` | On demand |

## Quick setup

```bash
./setup.sh                          # create venv + install deps + init config
source .venv/bin/activate
python scripts/api_config.py status # see which APIs are ready
```

Four APIs work immediately with no keys (yfinance, SEC EDGAR, ApeWisdom, StockTwits). Add free keys for Finnhub, Alpha Vantage, FMP, and Polygon to unlock the full feature set.

See [QUICKSTART.md](QUICKSTART.md) for detailed setup, API key signup links, and usage examples.

## How it works

Every API call flows through a resilient caller with automatic fallbacks — if the primary API fails or hits its rate limit, the next in the chain is tried automatically. Usage is tracked against free tier limits with paid-tier recommendations when any API exceeds 70% utilization.

See [SKILL.md](SKILL.md) for the full scoring methodology, fallback chains, and workflow details.

## Disclaimer

This tool provides data-driven analysis, not financial advice. Always do your own due diligence.
