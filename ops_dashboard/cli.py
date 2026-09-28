"""Command line for Ops dashboard."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ops_dashboard.build import build_report
from ops_dashboard.fixture import build_fixture
from ops_dashboard.health import RANK
from ops_dashboard.profile import LIVE, SNAPSHOT
from ops_dashboard.render import write_report
from ops_dashboard.window import parse_end, window_ending


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ops_dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Write a standalone HTML snapshot (7 days, 5-minute buckets)")
    generate.add_argument("--out", default="output", help="Directory for the HTML files")
    generate.add_argument("--fixture", action="store_true", help="Render deterministic offline data")
    generate.add_argument("--end", default=None, help="Window end as an ISO-8601 UTC instant")
    generate.add_argument("--workers", type=int, default=4, help="Parallel Azure queries")

    serve = sub.add_parser("serve", help="Serve the live view (1 day, 1-minute buckets) on this machine")
    serve.add_argument("--host", default="127.0.0.1", help="Address to bind. Keep it local; there is no login")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--refresh", type=int, default=60, help="Seconds between Azure refreshes")
    serve.add_argument("--workers", type=int, default=4, help="Parallel Azure queries")
    serve.add_argument("--fixture", action="store_true", help="Serve deterministic offline data")

    args = parser.parse_args(argv)
    if args.command == "generate":
        return _generate(args)
    if args.command == "serve":
        return _serve(args)
    return 2


def _generate(args) -> int:
    out = Path(args.out)
    if args.fixture:
        report = build_fixture(args.end) if args.end else build_fixture()
    else:
        from ops_dashboard.collect import collect

        moment = datetime.now(timezone.utc)
        end_epoch = parse_end(args.end) if args.end else None
        start, end = window_ending(end_epoch, moment, SNAPSHOT)
        print(f"window {start} .. {end}", file=sys.stderr)
        result = collect(start, end, args.workers, SNAPSHOT)
        report = build_report(
            result.series,
            start=start,
            end=end,
            generated_epoch=int(moment.timestamp()),
            fixture=False,
            profile=SNAPSHOT,
            states=result.states,
            queries=result.queries,
            data_quality=result.quality,
            unavailable=result.unavailable,
        )
    dated, latest = write_report(report, out)
    _print_summary(report, dated, latest)
    return 0


def _serve(args) -> int:
    try:
        from ops_dashboard.serve import run
    except ImportError:
        print('Live mode needs the "live" extra: pip install -e ".[live]"', file=sys.stderr)
        return 1
    from ops_dashboard.live import FixtureEngine, LiveEngine

    if args.refresh < 15:
        print("--refresh below 15 seconds would only repeat Azure's own delay.", file=sys.stderr)
        return 2
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"warning: {args.host} exposes production metrics with no login.", file=sys.stderr)
    print(f"live view at http://{args.host}:{args.port}/  ({LIVE.span_label}, {LIVE.bucket_label} buckets)", file=sys.stderr)
    if args.fixture:
        run(FixtureEngine(), args.host, args.port, args.refresh)
        return 0
    from ops_dashboard.collect import Collector

    with Collector(profile=LIVE, workers=args.workers, quiet=True) as collector:
        run(LiveEngine(collector), args.host, args.port, args.refresh)
    return 0


def _print_summary(report, dated: Path, latest: Path) -> None:
    counts = {state: 0 for state in ("critical", "degraded", "unknown", "maintenance", "healthy")}
    for component in report.components:
        if component.on_map:
            counts[component.state] = counts.get(component.state, 0) + 1
    print(f"wrote {dated} ({dated.stat().st_size} bytes)")
    print(f"wrote {latest} ({latest.stat().st_size} bytes)")
    print("health " + " ".join(f"{name}={counts[name]}" for name in counts))
    flagged = [item for item in report.components if item.on_map and item.state != "healthy"]
    flagged.sort(key=lambda item: (-RANK.get(item.state, 0), item.title))
    for item in flagged:
        print(f"{item.state}\t{item.title}\t{item.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
