import csv
from io import StringIO

import pytest

from breakout_ai.config import ROOT
from breakout_ai.finance import hypothetical_return, read_snapshots, safe_csv, valuation


def test_currency_scale_does_not_change_ratios():
    assert valuation(100000, 5000, 40000, 2000) == valuation(100, 5, 40, 2)
    assert valuation(100, 5, 40, 2) == {"pe": 20, "pb": 2.5, "dividend_yield_pct": 2}


@pytest.mark.parametrize("eps,bvps", [(0, 0), (-2, -10)])
def test_non_positive_denominators_are_not_valuation_signals(eps, bvps):
    result = valuation(100, eps, bvps)
    assert result["pe"] is None and result["pb"] is None


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_prices_are_rejected(price):
    with pytest.raises(ValueError):
        valuation(price, 5, 40)


def test_return_accounts_for_costs_and_losses():
    result = hypothetical_return(100, 90, 10, 5)
    assert result == {"invested": 1000, "net_pnl": -105, "return_pct": -10.5}


def test_extreme_finite_inputs_cannot_produce_infinite_results():
    with pytest.raises(ValueError):
        valuation(1e308, 1e-308, 40)
    with pytest.raises(ValueError):
        hypothetical_return(1e308, 1e308, 100)


@pytest.mark.parametrize("shares", [0, -2, 1.5, True])
def test_quantity_must_be_a_positive_integer(shares):
    with pytest.raises(ValueError):
        hypothetical_return(100, 110, shares)


def test_sample_csv_retains_separate_currencies():
    rows = read_snapshots((ROOT / "examples" / "financial_snapshot.csv").read_bytes())
    assert [(r.market, r.currency) for r in rows] == [("VN", "VND"), ("US", "USD")]
    assert rows[0].metrics()["pe"] == rows[1].metrics()["pe"] == 20


@pytest.mark.parametrize("original,replacement", [
    ("VN,DEMO,VND", "VN,DEMO,USD"),
    ("100000,5000", "NaN,5000"),
    ("2026-10-01", "2999-01-01"),
    ("2026-10-01", "invalid-date"),
    ("market,symbol", "market,ticker"),
])
def test_csv_invalid_records_fail_with_context(original, replacement):
    data = (ROOT / "examples" / "financial_snapshot.csv").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        read_snapshots(data.replace(original, replacement).encode())


def test_csv_duplicates_are_rejected():
    data = (ROOT / "examples" / "financial_snapshot.csv").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="nhiều lần"):
        read_snapshots((data + data.splitlines()[1] + "\n").encode())


def test_export_neutralizes_user_formulas_but_preserves_numbers():
    result = safe_csv([{"note": "  =HYPERLINK(1)", "pnl": -12}], ["note", "pnl"])
    row = next(csv.DictReader(StringIO(result)))
    assert row["note"].startswith("'") and row["pnl"] == "-12"
