"""Command line for the daily systems report."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from report.build import build_report
from report.fixture import build_fixture
from report.health import RANK
from report.render import write_report
from report.window import parse_end, window_ending


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m report")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="Write a standalone HTML report")
    generate.add_argument("--out", default="output", help="Directory for the HTML files")
    generate.add_argument("--fixture", action="store_true", help="Render deterministic offline data")
    generate.add_argument("--end", default=None, help="Window end as an ISO-8601 UTC instant")
    generate.add_argument("--workers", type=int, default=4, help="Parallel Azure queries")
    args = parser.parse_args(argv)
    if args.command == "generate":
        return _generate(args)
    return 2


def _generate(args) -> int:
    out = Path(args.out)
    if args.fixture:
        report = build_fixture(args.end) if args.end else build_fixture()
    else:
        from report.collect import collect

        moment = datetime.now(timezone.utc)
        end_epoch = parse_end(args.end) if args.end else None
        start, end = window_ending(end_epoch, moment)
        print(f"window {start} .. {end}", file=sys.stderr)
        series, states, queries, quality, unavailable = collect(start, end, args.workers)
        report = build_report(
            series,
            start=start,
            end=end,
            generated_epoch=int(moment.timestamp()),
            fixture=False,
            states=states,
            queries=queries,
            data_quality=quality,
            unavailable=unavailable,
        )
    dated, latest = write_report(report, out)
    _print_summary(report, dated, latest)
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
