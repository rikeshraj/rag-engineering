"""
CSV Analyzer - Core analysis logic.

Loads a CSV file and computes:
- Basic info (row count, column count, headers)
- Per-column stats (numeric: mean/min/max/std, categorical: top values)
- Missing value report
- Correlation between numeric columns (optional)
"""

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter


# ──────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────

@dataclass
class ColumnStats:
    """Stats for a single column."""
    name: str
    dtype: str                        # "numeric" or "categorical"
    count: int = 0                    # non-missing values
    missing: int = 0

    # Numeric only
    mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    std_dev: float | None = None
    median: float | None = None

    # Categorical only
    unique_count: int = 0
    top_values: list[tuple] = field(default_factory=list)   # [(value, freq), ...]

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.dtype,
            "count": self.count,
            "missing": self.missing,
        }
        if self.dtype == "numeric":
            d.update({
                "mean": round(self.mean, 4) if self.mean is not None else None,
                "min": self.minimum,
                "max": self.maximum,
                "std_dev": round(self.std_dev, 4) if self.std_dev is not None else None,
                "median": self.median,
            })
        else:
            d.update({
                "unique_count": self.unique_count,
                "top_values": self.top_values,
            })
        return d


@dataclass
class AnalysisResult:
    """Full analysis result for a CSV file."""
    file_name: str
    total_rows: int
    total_columns: int
    headers: list[str]
    columns: list[ColumnStats] = field(default_factory=list)
    correlations: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "file": self.file_name,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "headers": self.headers,
            "columns": [c.to_dict() for c in self.columns],
            "correlations": self.correlations,
        }


# ──────────────────────────────────────────────
# Helpers — pure functions
# ──────────────────────────────────────────────

def _is_numeric(values: list[str]) -> bool:
    """
    Returns True if more than 80% of non-empty values
    can be parsed as floats. This handles columns that
    are mostly numeric but have a few bad rows.
    """
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return False
    numeric_count = sum(1 for v in non_empty if _to_float(v) is not None)
    return (numeric_count / len(non_empty)) >= 0.8


def _to_float(value: str) -> float | None:
    """Try to parse a string as float, return None on failure."""
    try:
        return float(value.strip().replace(",", ""))
    except ValueError:
        return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std_dev(values: list[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _median(values: list[float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]


def _correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient between two lists."""
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = _mean(x), _mean(y)
    numerator = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom = math.sqrt(
        sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)
    )
    return round(numerator / denom, 4) if denom != 0 else 0.0


# ──────────────────────────────────────────────
# Main analyzer class
# ──────────────────────────────────────────────

class CSVAnalyzer:
    """
    Analyzes a CSV file and produces an AnalysisResult.

    Usage:
        analyzer = CSVAnalyzer("data.csv")
        result = analyzer.analyze()
        print(result.to_dict())
    """

    def __init__(self, filepath: str | Path, top_n: int = 5):
        """
        Args:
            filepath: Path to the CSV file.
            top_n:    How many top values to show for categorical columns.
        """
        self.filepath = Path(filepath)
        self.top_n = top_n
        self._rows: list[dict] = []
        self._headers: list[str] = []

    # ── Public ──────────────────────────────

    def analyze(self, correlations: bool = False) -> AnalysisResult:
        """
        Run the full analysis pipeline.

        Args:
            correlations: If True, compute pairwise Pearson correlations
                          between all numeric columns.
        """
        self._load()

        result = AnalysisResult(
            file_name=self.filepath.name,
            total_rows=len(self._rows),
            total_columns=len(self._headers),
            headers=self._headers,
        )

        # Analyze each column
        for header in self._headers:
            raw_values = [row.get(header, "") for row in self._rows]
            result.columns.append(self._analyze_column(header, raw_values))

        # Optional correlation matrix
        if correlations:
            result.correlations = self._compute_correlations()

        return result

    # ── Private ─────────────────────────────

    def _load(self) -> None:
        """Read CSV into a list of dicts. Handles encoding gracefully."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")
        if self.filepath.suffix.lower() != ".csv":
            raise ValueError(f"Expected a .csv file, got: {self.filepath.suffix}")

        try:
            with open(self.filepath, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                self._headers = list(reader.fieldnames or [])
                self._rows = [dict(row) for row in reader]
        except UnicodeDecodeError:
            with open(self.filepath, encoding="latin-1", newline="") as f:
                reader = csv.DictReader(f)
                self._headers = list(reader.fieldnames or [])
                self._rows = [dict(row) for row in reader]

        if not self._headers:
            raise ValueError("CSV file has no headers.")

    def _analyze_column(self, name: str, raw_values: list[str]) -> ColumnStats:
        """Dispatch to numeric or categorical analysis based on content."""
        missing = sum(1 for v in raw_values if not v.strip())
        non_missing = [v for v in raw_values if v.strip()]

        stats = ColumnStats(
            name=name,
            count=len(non_missing),
            missing=missing,
            dtype="numeric" if _is_numeric(raw_values) else "categorical",
        )

        if stats.dtype == "numeric":
            self._compute_numeric(stats, non_missing)
        else:
            self._compute_categorical(stats, non_missing)

        return stats

    def _compute_numeric(self, stats: ColumnStats, raw: list[str]) -> None:
        """Fill in numeric stats in place."""
        values = [_to_float(v) for v in raw if _to_float(v) is not None]
        if not values:
            return
        stats.mean = _mean(values)
        stats.minimum = min(values)
        stats.maximum = max(values)
        stats.std_dev = _std_dev(values)
        stats.median = _median(values)

    def _compute_categorical(self, stats: ColumnStats, raw: list[str]) -> None:
        """Fill in categorical stats in place."""
        counter = Counter(raw)
        stats.unique_count = len(counter)
        stats.top_values = counter.most_common(self.top_n)

    def _compute_correlations(self) -> dict:
        """
        Compute Pearson correlation between all pairs of numeric columns.
        Returns a nested dict: {col_a: {col_b: correlation_value}}.
        """
        numeric_cols = {
            h: [] for h in self._headers
            if _is_numeric([row.get(h, "") for row in self._rows])
        }

        # Build column value lists
        for row in self._rows:
            for col in numeric_cols:
                val = _to_float(row.get(col, ""))
                if val is not None:
                    numeric_cols[col].append(val)

        col_names = list(numeric_cols.keys())
        matrix = {}

        for i, col_a in enumerate(col_names):
            matrix[col_a] = {}
            for col_b in col_names:
                # Align lengths (only rows where both cols have values)
                pairs = [
                    (_to_float(row.get(col_a, "")), _to_float(row.get(col_b, "")))
                    for row in self._rows
                ]
                valid = [(a, b) for a, b in pairs if a is not None and b is not None]
                if valid:
                    xs, ys = zip(*valid)
                    matrix[col_a][col_b] = _correlation(list(xs), list(ys))
                else:
                    matrix[col_a][col_b] = None

        return matrix
