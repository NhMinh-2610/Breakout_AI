"""Opt-in network smoke check: python -m breakout_ai.verify_data."""

import argparse
import json
from pathlib import Path

from breakout_ai.config import ROOT, Settings
from breakout_ai.market import MarketService
from breakout_ai.screening import rank_candidates
from breakout_ai.storage import Store, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch real daily data and save a provenance report; no LLM or trading calls.")
    parser.add_argument("--symbols", nargs="+", default=["VN:FPT", "US:AAPL"])
    parser.add_argument("--output", default=".artifacts/market_check.json")
    args = parser.parse_args()
    identities = []
    for item in args.symbols:
        parts = item.upper().split(":")
        if len(parts) != 2 or parts[0] not in {"VN", "US"}:
            parser.error("Use symbols such as VN:FPT or US:AAPL.")
        identities.append((parts[0], parts[1]))
    settings = Settings.from_env()
    service = MarketService(settings, Store(settings.database_path, settings.workspace_id))
    snapshots, errors = service.many(identities, force=True)
    report = {"checked_at": utc_now(), "requested": identities, "snapshots": [snapshot.summary() for snapshot in snapshots],
              "screening": rank_candidates(snapshots), "errors": errors,
              "method": "Daily bars; not realtime. Technical screening is not a validated return prediction."}
    output = Path(args.output)
    output = output if output.is_absolute() else ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for snapshot in snapshots:
        print(f"{snapshot.market}:{snapshot.symbol} {snapshot.provider} {snapshot.currency} as_of={snapshot.latest.date} bars={len(snapshot.bars)} stale={snapshot.cache_stale}")
    print(f"Report: {output}")
    print(f"Successful sources: {len(snapshots)}; errors: {len(errors)}")
    return 0 if len(snapshots) == len(identities) and not errors and not any(s.cache_stale for s in snapshots) else 1


if __name__ == "__main__":
    raise SystemExit(main())
