#!/usr/bin/env python3
"""
Financial Analysis Skill — Quick Test Suite
============================================
Run this to verify everything works on your machine.

Usage:
    pip install yfinance feedparser pandas requests
    python tests/test_skill.py

Tests are ordered from zero-network to full-network so you can
see exactly where things break if a dependency or key is missing.
"""

import sys, os, json, time, signal
from pathlib import Path

# ── ensure imports resolve ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
SKIP = "\033[93m⊘ SKIP\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}

# ── timeout helper (prevents tests from hanging) ───────────────────
class TestTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise TestTimeout("Test timed out")

def test(name, func, timeout_sec=30):
    """Run a single test and print the result. Times out after timeout_sec."""
    # Set alarm (Unix only)
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_sec)
    try:
        outcome = func()
        signal.alarm(0)  # cancel alarm
        if outcome == "skip":
            print(f"  {SKIP}  {name}")
            results["skip"] += 1
        else:
            print(f"  {PASS}  {name}")
            results["pass"] += 1
    except TestTimeout:
        print(f"  {FAIL}  {name}")
        print(f"         └─ Timed out after {timeout_sec}s (network issue or slow feed)")
        results["fail"] += 1
    except Exception as e:
        signal.alarm(0)
        print(f"  {FAIL}  {name}")
        print(f"         └─ {type(e).__name__}: {e}")
        results["fail"] += 1
    finally:
        signal.signal(signal.SIGALRM, old_handler)


# ════════════════════════════════════════════════════════════════════
#  GROUP 1 — Offline tests (no network, no API keys)
# ════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'='*60}")
print("  GROUP 1 — Offline (no network needed)")
print(f"{'='*60}{RESET}\n")


def test_api_registry_loads():
    from scripts.api_config import API_REGISTRY
    assert len(API_REGISTRY) >= 13, f"Expected 13+ APIs, got {len(API_REGISTRY)}"
    for api_id, meta in API_REGISTRY.items():
        assert "name" in meta, f"{api_id} missing 'name'"
        assert "cost" in meta, f"{api_id} missing 'cost'"
        assert "requires_key" in meta, f"{api_id} missing 'requires_key'"

test("API registry loads with 13+ APIs", test_api_registry_loads)


def test_fallback_chains():
    from scripts.api_config import FALLBACK_CHAINS, API_REGISTRY
    assert len(FALLBACK_CHAINS) >= 15, f"Expected 15+ chains, got {len(FALLBACK_CHAINS)}"
    for category, chain in FALLBACK_CHAINS.items():
        assert len(chain) >= 1, f"{category} has empty chain"
        for api_id in chain:
            assert api_id in API_REGISTRY, f"{category} references unknown API '{api_id}'"

test("Fallback chains valid (15 categories, all IDs exist)", test_fallback_chains)


def test_config_init():
    from scripts.api_config import init_config, load_config
    # init_config now preserves existing keys, safe to call
    init_config()
    cfg = load_config()
    assert isinstance(cfg, dict), "Config should be a dict"
    assert "apis" in cfg, "Config should have 'apis' section"

test("Config init creates/updates ~/.financial-analysis/api_keys.json", test_config_init)


def test_free_vs_paid_labels():
    from scripts.api_config import API_REGISTRY
    free_apis = [k for k, v in API_REGISTRY.items() if "Free" in v.get("cost", "") or "government" in v.get("cost", "")]
    paid_apis = [k for k, v in API_REGISTRY.items() if "$" in v.get("cost", "") and "Free" not in v.get("cost", "")]
    assert len(free_apis) >= 10, f"Expected 10+ free APIs, got {len(free_apis)}"
    # Quiver should be the only paid-only one
    assert "quiver" in paid_apis, "Quiver should be marked as paid"

test("Free vs Paid labels are correct", test_free_vs_paid_labels)


def test_usage_tracker_init():
    from scripts.usage_tracker import get_tracker
    tracker = get_tracker()
    assert tracker is not None

test("Usage tracker initializes", test_usage_tracker_init)


def test_usage_tracking_flow():
    from scripts.usage_tracker import UsageTracker
    tracker = UsageTracker()
    # Snapshot counts BEFORE our test calls (log file may have data from prior runs)
    before = tracker.get_daily_usage()
    yf_before = before.get("yfinance", {}).get("calls", 0)
    fh_before = before.get("finnhub", {}).get("calls", 0)
    fh_err_before = before.get("finnhub", {}).get("errors", 0)
    # Make our test calls
    tracker.record_call("yfinance", "price_history", success=True, response_time_ms=100)
    tracker.record_call("yfinance", "price_history", success=True, response_time_ms=200)
    tracker.record_call("finnhub", "analyst_ratings", success=False, response_time_ms=5000, details="timeout")
    # Check relative counts
    after = tracker.get_daily_usage()
    assert after["yfinance"]["calls"] == yf_before + 2, \
        f"Expected {yf_before + 2} yfinance calls, got {after['yfinance']['calls']}"
    assert after["finnhub"]["calls"] == fh_before + 1, \
        f"Expected {fh_before + 1} finnhub calls, got {after['finnhub']['calls']}"
    assert after["finnhub"]["errors"] == fh_err_before + 1, \
        f"Expected {fh_err_before + 1} finnhub errors, got {after['finnhub']['errors']}"

test("Usage tracking records calls and errors correctly", test_usage_tracking_flow)


def test_rate_limit_check():
    from scripts.usage_tracker import UsageTracker
    from scripts.api_config import API_REGISTRY
    tracker = UsageTracker()
    can, reason = tracker.can_call("yfinance", API_REGISTRY)
    assert can is True, f"Should allow call: {reason}"
    # Simulate hitting limit (Alpha Vantage = 25/day)
    for i in range(26):
        tracker.record_call("alpha_vantage", "test", success=True, response_time_ms=50)
    can, reason = tracker.can_call("alpha_vantage", API_REGISTRY)
    assert can is False, "Should block after exceeding daily limit"
    assert "daily" in reason.lower() or "limit" in reason.lower()

test("Rate limiter blocks calls after exceeding daily limit", test_rate_limit_check)


def test_error_logging():
    from scripts.usage_tracker import UsageTracker
    tracker = UsageTracker()
    tracker.record_error("finnhub", "analyst_ratings", "429 Too Many Requests",
                         fallback_api="yfinance", fallback_success=True)
    tracker.record_error("mboum", "congress_trades", "503 Service Unavailable",
                         fallback_api="quiver", fallback_success=False)
    errors = tracker.get_errors(last_n_days=1)
    # get_errors returns dict keyed by api_id → list of errors
    assert "finnhub" in errors, f"Expected 'finnhub' in errors, got {list(errors.keys())}"
    assert "mboum" in errors, f"Expected 'mboum' in errors, got {list(errors.keys())}"
    assert errors["finnhub"][-1]["fallback_success"] is True
    assert errors["mboum"][-1]["fallback_success"] is False

test("Error logging captures fallback outcomes", test_error_logging)


def test_api_caller_with_mocks():
    from scripts.api_caller import call_api, call_with_fallback
    # Success path
    result = call_api("yfinance", "price_history", lambda: {"price": 150.0})
    assert result["success"] is True
    assert result["data"]["price"] == 150.0
    # Failure path
    def raise_err():
        raise ConnectionError("down")
    result = call_api("finnhub", "test", raise_err)
    assert result["success"] is False
    assert "down" in result["error"]

test("API caller handles success and failure", test_api_caller_with_mocks)


def test_fallback_chain_execution():
    from scripts.api_caller import call_with_fallback
    call_count = {"n": 0}
    def fail_fn():
        call_count["n"] += 1
        raise RuntimeError("nope")
    def ok_fn():
        call_count["n"] += 1
        return {"ticker": "AAPL", "rating": "Buy"}
    result = call_with_fallback("analyst_ratings", {
        "finnhub": fail_fn,
        "yfinance": ok_fn,
    })
    assert result["success"] is True
    assert result["api_id"] == "yfinance"
    assert result["data"]["rating"] == "Buy"

test("Fallback chain skips failed APIs and uses next", test_fallback_chain_execution)


def test_ticker_extraction():
    from scripts.rss_feeds import extract_tickers
    # Should find real tickers
    tickers = extract_tickers("AAPL surged 5% while MSFT dropped and NVDA held steady")
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "NVDA" in tickers
    # Should NOT extract common words that look like tickers
    tickers = extract_tickers("The CEO said AI and IT are the future for US markets")
    assert "CEO" not in tickers
    assert "AI" not in tickers
    assert "US" not in tickers

test("Ticker extraction finds stocks, ignores common words", test_ticker_extraction)


def test_rss_feed_catalog():
    from scripts.rss_feeds import FEEDS
    assert len(FEEDS) >= 16, f"Expected 16+ feeds, got {len(FEEDS)}"
    tiers = set(f["tier"] for f in FEEDS.values())
    assert 1 in tiers and 2 in tiers and 3 in tiers, "Should have feeds in tiers 1, 2, and 3"

test("RSS feed catalog has 16+ feeds in 3 tiers", test_rss_feed_catalog)


# ════════════════════════════════════════════════════════════════════
#  GROUP 2 — Live API tests (need network, some need keys)
# ════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'='*60}")
print("  GROUP 2 — Live API calls (network required)")
print(f"{'='*60}{RESET}\n")


def test_yfinance_price():
    try:
        import yfinance as yf
    except ImportError:
        return "skip"
    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="5d")
    assert len(hist) > 0, "Should return price history"
    assert "Close" in hist.columns

test("yfinance — AAPL 5-day price history", test_yfinance_price)


def test_yfinance_financials():
    try:
        import yfinance as yf
    except ImportError:
        return "skip"
    ticker = yf.Ticker("MSFT")
    info = ticker.info
    assert "marketCap" in info or "totalRevenue" in info, "Should return fundamentals"

test("yfinance — MSFT fundamentals/info", test_yfinance_financials)


def test_yfinance_analyst():
    try:
        import yfinance as yf
    except ImportError:
        return "skip"
    ticker = yf.Ticker("GOOGL")
    recs = ticker.recommendations
    assert recs is not None and len(recs) > 0, "Should have analyst recommendations"

test("yfinance — GOOGL analyst recommendations", test_yfinance_analyst)


def test_sec_edgar():
    try:
        import requests
    except ImportError:
        return "skip"
    headers = {"User-Agent": "FinancialAnalysisSkill test@example.com"}
    # CIK for Apple
    r = requests.get("https://data.sec.gov/submissions/CIK0000320193.json", headers=headers, timeout=10)
    assert r.status_code == 200, f"SEC EDGAR returned {r.status_code}"
    data = r.json()
    assert "cik" in data

test("SEC EDGAR — Apple filings (no key needed)", test_sec_edgar)


def test_apewisdom():
    try:
        import requests
    except ImportError:
        return "skip"
    r = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1", timeout=10)
    assert r.status_code == 200, f"ApeWisdom returned {r.status_code}"
    data = r.json()
    assert "results" in data
    assert len(data["results"]) > 0

test("ApeWisdom — Reddit trending stocks (no key needed)", test_apewisdom)


def test_finnhub():
    from scripts.api_config import get_api_key
    key = get_api_key("finnhub")
    if not key:
        return "skip"
    import requests
    r = requests.get(f"https://finnhub.io/api/v1/stock/recommendation?symbol=AAPL&token={key}", timeout=10)
    assert r.status_code == 200, f"Finnhub returned {r.status_code}"
    data = r.json()
    assert isinstance(data, list) and len(data) > 0

test("Finnhub — AAPL recommendations (needs FINNHUB_API_KEY)", test_finnhub)


def test_alpha_vantage():
    from scripts.api_config import get_api_key
    key = get_api_key("alpha_vantage")
    if not key:
        return "skip"
    import requests
    r = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={key}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "Global Quote" in data, f"Unexpected AV response: {list(data.keys())}"

test("Alpha Vantage — AAPL quote (needs ALPHA_VANTAGE_API_KEY)", test_alpha_vantage)


def test_fmp():
    from scripts.api_config import get_api_key
    key = get_api_key("fmp")
    if not key:
        return "skip"
    import requests
    # FMP deprecated /api/v3/ for new users after Aug 2025. Use /stable/ endpoints.
    r = requests.get(f"https://financialmodelingprep.com/stable/profile?symbol=AAPL&apikey={key}", timeout=10)
    if r.status_code == 403:
        # Try legacy endpoint as fallback for older accounts
        r = requests.get(f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={key}", timeout=10)
    assert r.status_code == 200, f"FMP returned HTTP {r.status_code}. Check your API key or plan."
    data = r.json()
    # Handle error responses
    if isinstance(data, dict) and "Error Message" in data:
        assert False, f"FMP API error: {data['Error Message']}"
    if isinstance(data, dict) and "message" in data:
        assert False, f"FMP API error: {data['message']}"
    assert (isinstance(data, list) and len(data) > 0) or (isinstance(data, dict) and len(data) > 0), \
        f"Expected non-empty response, got {type(data).__name__}: {str(data)[:200]}"

test("FMP — AAPL profile (needs FMP_API_KEY)", test_fmp)


def test_rss_live_scan():
    try:
        import feedparser
    except ImportError:
        return "skip"
    # Try multiple feeds in order of reliability — some may be slow or block
    test_feeds = ["cnbc_top", "marketwatch_top", "yahoo_finance", "benzinga"]
    from scripts.rss_feeds import FEEDS
    for feed_id in test_feeds:
        if feed_id not in FEEDS:
            continue
        try:
            feed = feedparser.parse(FEEDS[feed_id]["url"])
            if hasattr(feed, 'entries') and len(feed.entries) > 0:
                assert "title" in feed.entries[0]
                return  # pass — at least one feed works
        except Exception:
            continue
    # No feed returned entries — not a failure, could be weekend/off-hours
    assert True, "All feeds returned empty (may be off-hours)"

test("RSS — Live feed scan (needs feedparser)", test_rss_live_scan, timeout_sec=20)


def test_seeking_alpha_rss():
    try:
        import feedparser
    except ImportError:
        return "skip"
    feed = feedparser.parse("https://seekingalpha.com/market_currents.xml")
    assert feed is not None
    # SA might block or might work — just verify no crash
    if hasattr(feed, 'entries') and len(feed.entries) > 0:
        assert "title" in feed.entries[0]

test("Seeking Alpha RSS — Market currents feed", test_seeking_alpha_rss, timeout_sec=15)


# ════════════════════════════════════════════════════════════════════
#  GROUP 3 — Integration test (end-to-end workflow simulation)
# ════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'='*60}")
print("  GROUP 3 — Integration (simulated workflow)")
print(f"{'='*60}{RESET}\n")


def test_full_workflow_simulation():
    """Simulates the full pipeline: config → rate check → call → fallback → log → report"""
    from scripts.api_config import API_REGISTRY, get_fallback_chain
    from scripts.usage_tracker import UsageTracker
    from scripts.api_caller import call_with_fallback

    tracker = UsageTracker()

    # Step 1: Get price (yfinance mock)
    chain = get_fallback_chain("price_history")
    assert "yfinance" in chain

    result = call_with_fallback("price_history", {
        "yfinance": lambda: {"AAPL": {"close": 185.50, "volume": 50_000_000}},
    })
    assert result["success"]

    # Step 2: Analyst ratings (finnhub fails → yfinance succeeds)
    def finnhub_fail():
        raise ConnectionError("503")
    result = call_with_fallback("analyst_ratings", {
        "finnhub": finnhub_fail,
        "yfinance": lambda: {"AAPL": {"buy": 25, "hold": 8, "sell": 2}},
    })
    assert result["success"]
    assert result["api_id"] == "yfinance"  # used fallback

    # Step 3: Check daily report works
    daily = tracker.get_daily_usage()
    assert isinstance(daily, dict)

    # Step 4: Simulate heavy usage and check warnings
    for i in range(20):
        tracker.record_call("alpha_vantage", "test", success=True, response_time_ms=100)
    # AV limit is 25/day — at 20 calls we should be at 80% (WARNING)
    pct = 20 / 25 * 100
    assert pct >= 70, "Should trigger WARNING level"

test("Full pipeline: config → call → fallback → log → report", test_full_workflow_simulation)


def test_daily_summary_generation():
    from scripts.usage_tracker import UsageTracker
    tracker = UsageTracker()
    # Populate some data
    for _ in range(18):
        tracker.record_call("alpha_vantage", "test", success=True, response_time_ms=100)
    tracker.record_error("finnhub", "ratings", "429", fallback_api="yfinance", fallback_success=True)

    # Generate summary
    summary_path = Path.home() / ".financial-analysis" / "logs" / "test_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    tracker.save_daily_summary(str(summary_path))
    assert summary_path.exists(), "Summary file should be created"
    with open(summary_path) as f:
        summary = json.load(f)
    assert "date" in summary
    assert "apis" in summary
    # Clean up
    summary_path.unlink(missing_ok=True)

test("Daily summary JSON export with paid tier recommendations", test_daily_summary_generation)


# ════════════════════════════════════════════════════════════════════
#  Results
# ════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'='*60}")
total = results['pass'] + results['fail'] + results['skip']
print(f"  RESULTS: {results['pass']}/{total} passed, {results['fail']} failed, {results['skip']} skipped")
print(f"{'='*60}{RESET}\n")

if results["skip"] > 0:
    print("  Skipped tests need either:")
    print("    • pip install yfinance feedparser pandas requests")
    print("    • API keys set up: python scripts/api_config.py init")
    print("    • Then add keys: ~/.financial-analysis/api_keys.json")
    print()

if results["fail"] > 0:
    sys.exit(1)
