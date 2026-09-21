"""Smoke tests for ops/loadtest.py: pure helpers + CLI parsing only.

No network calls, no DB, no imports of webapp/src at module load time — this
keeps the test fast and independent of a running server or seeded database.
"""

import pytest

from ops.loadtest import (
    EndpointStats,
    build_arg_parser,
    build_report,
    parse_args,
    percentile,
    record,
)


class FakeArgs:
    """Minimal stand-in for argparse.Namespace, only the fields build_report reads."""

    def __init__(self, base_url="http://localhost:8000", users=5, duration=1.0, scenario="mixed"):
        self.base_url = base_url
        self.users = users
        self.duration = duration
        self.scenario = scenario


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


def test_percentile_empty_is_zero():
    assert percentile([], 95) == 0.0


def test_percentile_single_value():
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 0) == 42.0
    assert percentile([42.0], 100) == 42.0


def test_percentile_p50_of_sorted_range():
    values = [float(i) for i in range(1, 11)]  # 1..10
    assert percentile(values, 50) == pytest.approx(5.5)


def test_percentile_p95_upper_bound():
    values = [float(i) for i in range(1, 101)]  # 1..100
    p95 = percentile(values, 95)
    assert 94.0 <= p95 <= 96.0


def test_percentile_unsorted_input_is_sorted_first():
    values = [50.0, 10.0, 30.0, 20.0, 40.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 50.0


def test_percentile_monotonic_across_levels():
    values = [1.0, 5.0, 9.0, 20.0, 500.0]
    p50 = percentile(values, 50)
    p95 = percentile(values, 95)
    p99 = percentile(values, 99)
    assert p50 <= p95 <= p99


# ---------------------------------------------------------------------------
# EndpointStats / record
# ---------------------------------------------------------------------------


def test_endpoint_stats_summary_counts_errors_and_429s():
    ep = EndpointStats("GET /jobs/search")
    ep.add(100.0, 200)
    ep.add(200.0, 200)
    ep.add(50.0, 429)
    ep.add(10.0, 500, "UPSTREAM_ERROR")

    summary = ep.summary()
    assert summary["count"] == 4
    assert summary["rate_limited_429"] == 1
    assert summary["errors"] == 2  # 429 + 500
    assert summary["error_codes"] == {"UPSTREAM_ERROR": 1}
    assert summary["max_ms"] == 200.0


def test_endpoint_stats_transport_error_has_status_zero():
    ep = EndpointStats("GET /jobs/search")
    ep.add(5.0, 0, "ConnectError")
    summary = ep.summary()
    assert summary["errors"] == 1
    assert summary["status_counts"] == {0: 1}


def test_record_creates_bucket_lazily():
    stats: dict = {}
    record(stats, "GET /saves", 12.3, 200)
    record(stats, "GET /saves", 45.6, 200)
    assert "GET /saves" in stats
    assert stats["GET /saves"].count == 2


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


def test_build_report_aggregates_totals_and_endpoints():
    stats = {}
    record(stats, "GET /jobs/search", 100.0, 200)
    record(stats, "GET /jobs/search", 150.0, 200)
    record(stats, "GET /jobs/{uid}", 80.0, 200)
    record(stats, "GET /jobs/{uid}", 5000.0, 429)

    report = build_report(stats, FakeArgs(), elapsed_seconds=2.0)

    assert report["totals"]["requests"] == 4
    assert report["totals"]["rate_limited_429"] == 1
    assert report["totals"]["requests_per_sec"] == 2.0
    assert {e["endpoint"] for e in report["endpoints"]} == {"GET /jobs/search", "GET /jobs/{uid}"}
    assert report["meta"]["scenario"] == "mixed"
    assert report["meta"]["users"] == 5


def test_build_report_empty_stats_has_zero_totals():
    report = build_report({}, FakeArgs(), elapsed_seconds=1.0)
    assert report["totals"]["requests"] == 0
    assert report["totals"]["p95_ms"] == 0.0
    assert report["endpoints"] == []


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def test_build_arg_parser_defaults():
    parser = build_arg_parser()
    args = parser.parse_args(["--bearer-file", "tokens.txt"])
    assert args.base_url == "http://localhost:8000"
    assert args.users == 50
    assert args.duration == 30.0
    assert args.scenario == "mixed"
    assert args.seed_sessions is None


def test_parse_args_requires_a_credential_source():
    with pytest.raises(SystemExit):
        parse_args(["--users", "10"])


def test_parse_args_accepts_bearer_file():
    args = parse_args(["--bearer-file", "tokens.txt", "--users", "10", "--duration", "5"])
    assert args.bearer_file == "tokens.txt"
    assert args.users == 10


def test_parse_args_accepts_init_data_file():
    args = parse_args(["--init-data-file", "initdata.txt"])
    assert args.init_data_file == "initdata.txt"


def test_parse_args_rejects_non_positive_users():
    with pytest.raises(SystemExit):
        parse_args(["--bearer-file", "tokens.txt", "--users", "0"])


def test_parse_args_seed_sessions_requires_db_path():
    with pytest.raises(SystemExit):
        parse_args(["--seed-sessions", "10"])


def test_parse_args_seed_sessions_with_db_path_ok():
    args = parse_args(["--seed-sessions", "10", "--db-path", "/tmp/loadtest.sqlite3"])
    assert args.seed_sessions == 10
    assert args.db_path == "/tmp/loadtest.sqlite3"


def test_parse_args_rejects_unknown_scenario():
    with pytest.raises(SystemExit):
        parse_args(["--bearer-file", "tokens.txt", "--scenario", "bogus"])
