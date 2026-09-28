"""In-memory report contract. Nothing here is persisted between runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class QueryRecord:
    name: str
    source: str
    duration_ms: int
    status: str
    error: Optional[str] = None
    detail: str = ""


@dataclass
class ChartView:
    id: str
    caption: str
    fmt: str
    y_max: float
    ticks: List[float]
    series: List[Tuple[str, str]]
    thresholds: List[dict]
    volume: Optional[str]
    sum_series: bool
    note: str
    present: int
    expected: int


@dataclass
class Fact:
    label: str
    text: str


@dataclass
class ComponentView:
    id: str
    title: str
    layer: str
    row: int
    stack: str
    icon: str
    runtime: str
    resource: str
    share: Optional[str]
    state: str
    reason: str
    threshold: Optional[str]
    evaluated_epoch: Optional[int]
    dominant: Fact
    secondary: Fact
    also: Fact
    facts: List[Fact]
    charts: List[ChartView]
    samples_present: int
    samples_expected: int
    on_map: bool


@dataclass
class Report:
    schema_version: int
    generated_epoch: int
    window_start: int
    window_end: int
    step: int
    count: int
    fixture: bool
    components: List[ComponentView]
    edges: Sequence[Tuple[str, str, int]]
    series: Dict[str, List[Optional[float]]]
    queries: List[QueryRecord] = field(default_factory=list)
    data_quality: List[str] = field(default_factory=list)
    absent_notes: List[str] = field(default_factory=list)
    maintenance_note: str = ""
