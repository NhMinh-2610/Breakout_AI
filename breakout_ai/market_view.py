"""UI loading policy: cache first, bounded batches and a cooldown after failures."""
from dataclasses import dataclass
import time
from typing import MutableMapping

from breakout_ai.market import MarketError, MarketService, MarketSnapshot


@dataclass
class MarketView:
    snapshots: dict[tuple[str, str], MarketSnapshot]
    errors: list[str]
    attempted: bool = False


def load_quotes(service: MarketService, identities, state: MutableMapping, *, force=False, now=None) -> MarketView:
    requested = list(dict.fromkeys((market, symbol.strip().upper()) for market, symbol in identities))
    requested = requested[:service.settings.market_max_symbols]
    snapshots = {}
    for identity in requested:
        saved = service.cached(*identity)
        if saved is not None and (saved.market, saved.symbol) == identity:
            snapshots[identity] = saved
    if not requested or not service.settings.market_enabled:
        return MarketView(snapshots, [])
    settings = service.settings
    scope = (str(settings.database_path), settings.workspace_id, settings.vn_market_provider, settings.us_market_provider, settings.market_gateway_url, tuple(requested))
    records = state.setdefault("market_view_loads", {})
    if scope not in records and len(records) >= 32:
        records.pop(next(iter(records)))
    record = records.setdefault(scope, {"last_attempt": None, "errors": []})
    current = time.monotonic() if now is None else now
    missing = [identity for identity in requested if identity not in snapshots or snapshots[identity].cache_stale]
    pending = requested if force else missing
    retry_after = max(30, settings.market_cache_seconds)
    ready = record["last_attempt"] is None or current - record["last_attempt"] >= retry_after
    attempted = bool(pending and (force or ready))
    if attempted:
        record["last_attempt"] = current
        try:
            received, errors = service.many(pending, force=force)
            for snapshot in received:
                identity = (snapshot.market, snapshot.symbol)
                if identity in requested:
                    snapshots[identity] = snapshot
            stale = [":".join(pair) for pair in pending if pair in snapshots and snapshots[pair].cache_stale]
            absent = [":".join(pair) for pair in pending if pair not in snapshots]
            record["errors"] = list(errors)
            if stale:
                record["errors"].append("Chưa làm mới được: " + ", ".join(stale) + ". Đang giữ bản lưu cũ.")
            if absent and not errors:
                record["errors"].append("Chưa có dữ liệu: " + ", ".join(absent) + ".")
        except MarketError as exc:
            record["errors"] = [str(exc)]
    elif not missing:
        record["errors"] = []
    return MarketView(snapshots, list(record["errors"]), attempted)
