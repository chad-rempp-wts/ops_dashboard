"""Run profiles. A profile fixes the bucket size, the window, and how rates are smoothed.

snapshot: seven days at five minutes. Written to one standalone HTML file.
live:     one day at one minute. Served locally and refreshed while the page is open.
"""

from __future__ import annotations

from dataclasses import dataclass

# A headline figure is the latest sample inside this many seconds of the window end.
FRESHNESS_SECONDS = 600
# Rates are always judged over this many seconds, whatever the bucket size.
RATE_WINDOW_SECONDS = 300


@dataclass(frozen=True)
class Profile:
    name: str
    step: int
    span: int
    grain: str

    @property
    def count(self) -> int:
        return self.span // self.step

    @property
    def rate_window(self) -> int:
        """Buckets in the rolling window used for failure rates and their volume guard."""
        return max(1, RATE_WINDOW_SECONDS // self.step)

    @property
    def freshness(self) -> int:
        """Buckets a headline figure may trail the window end and still count as fresh."""
        return max(1, FRESHNESS_SECONDS // self.step)

    @property
    def live(self) -> bool:
        return self.name == "live"

    @property
    def span_label(self) -> str:
        days = self.span // 86400
        if days >= 2:
            return f"{_words(days)} days"
        return f"{self.span // 3600} hours"

    @property
    def bucket_label(self) -> str:
        minutes = self.step // 60
        return "one-minute" if minutes == 1 else f"{_words(minutes)}-minute"

    def buckets_for(self, seconds: int) -> int:
        return max(1, seconds // self.step)

    def localize(self, text: str) -> str:
        """Catalog wording is written for five-minute buckets. Adjust it for this profile."""
        minutes = self.step // 60
        if minutes == 5:
            return text
        unit = "min" if minutes == 1 else f"{minutes} min"
        plural = "minute" if minutes == 1 else f"{minutes} minutes"
        hyphen = "1-minute" if minutes == 1 else f"{minutes}-minute"
        return (
            text.replace("/ 5 min", f"/ {unit}")
            .replace("per 5 minutes", f"per {plural}")
            .replace("5-minute bucket", f"{hyphen} bucket")
        )


def _words(number: int) -> str:
    names = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 10: "ten", 15: "fifteen"}
    return names.get(number, str(number))


SNAPSHOT = Profile("snapshot", 300, 7 * 86400, "PT5M")
LIVE = Profile("live", 60, 86400, "PT1M")

PROFILES = {SNAPSHOT.name: SNAPSHOT, LIVE.name: LIVE}
