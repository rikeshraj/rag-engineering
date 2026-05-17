# CSV Analyzer — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
02-csv-analyzer/
├── main.py                # CLI entry point
├── analyzer.py            # CSVLoader + CSVAnalyzer + stat helpers
├── formatter.py           # Terminal report formatting
├── sample_employees.csv   # Sample data for testing
├── requirements.txt
├── README.md
└── tests/
    └── test_analyzer.py
```

### How the files connect

```
main.py
  ├── analyzer.py    ← load CSV, compute statistics
  └── formatter.py  ← format results for terminal output
```

Analysis and display are kept in separate files. `analyzer.py` knows nothing about terminal output. `formatter.py` knows nothing about CSV files. This means you can swap out the formatter (e.g. output HTML instead) without touching any analysis code.

---

## `analyzer.py`

### What it does
Three responsibilities: loading the CSV (`CSVLoader`), computing statistics (`CSVAnalyzer`), and the math helper functions that power the stats. All pure Python — no pandas, no numpy.

### `ColumnStats` dataclass

```python
@dataclass
class ColumnStats:
    name: str
    dtype: str          # "numeric" or "categorical"
    count: int = 0
    null_count: int = 0
    mean: float | None = None
    median: float | None = None
    ...
    top_values: list[tuple] = field(default_factory=list)

    @property
    def null_pct(self) -> float:
        return round((self.null_count / self.count) * 100, 2)
```

**Why `None` for numeric fields on categorical columns?**
A categorical column has no `mean` or `median`. Using `None` makes this explicit — the field exists but has no value for this column type. The alternative (separate dataclasses for numeric and categorical) would require more code and a union type everywhere.

**`null_pct` as a `@property`**
Computed from `null_count` and `count`. A property means it's always consistent — you can't set `null_pct` to a value that contradicts `null_count`. It's calculated on demand, not stored.

### `CSVLoader`

**Why auto-detect the delimiter?**
CSVs aren't always comma-separated. Real-world files use semicolons (European Excel), tabs (TSV), and pipes. `csv.Sniffer().sniff(sample)` reads the first 4096 bytes and guesses the delimiter automatically. If sniffing fails, it falls back to comma.

**Why read a sample first?**
```python
sample = f.read(4096)
f.seek(0)
dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
```
`Sniffer` needs some text to analyze. Reading 4096 bytes, sniffing it, then seeking back to the start is the standard pattern. Reading the whole file just to detect the delimiter would be wasteful for large files.

**Multiple encoding fallback**
Same pattern as the resume parser — tries `utf-8`, `utf-8-sig`, `latin-1`, `cp1252` in order. `utf-8-sig` handles files saved by Excel on Windows which adds a BOM (byte order mark) at the start.

### Type detection — `_try_float()`

```python
def _try_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
```

A column is numeric if **every** non-null value parses as a float. The `.replace(",", "")` handles locale-formatted numbers like `1,000` or `1,234.56`. If even one value fails, the whole column is categorical.

**Why not check dtype by column name?**
Column names like `"age"` or `"salary"` are unreliable — a file could have a column called `"zip_code"` that stores text. Checking the actual values is the only reliable approach.

### Statistics — pure Python math

**Why no numpy?**
Numpy adds a large dependency for what are simple calculations. These implementations are also more readable and easier to understand:

```python
def _mean(values):
    return sum(values) / len(values)

def _median(values):
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    return (sorted_vals[mid-1] + sorted_vals[mid]) / 2 if n % 2 == 0 else sorted_vals[mid]

def _std(values):
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)
```

Note: `_std` uses `n-1` (Bessel's correction) — sample standard deviation, not population. This is the correct formula when working with a sample of a larger population.

### Pearson correlation — `_correlation()`

```python
def _correlation(x, y):
    mx, my = _mean(x), _mean(y)
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    den_x = math.sqrt(sum((v - mx) ** 2 for v in x))
    den_y = math.sqrt(sum((v - my) ** 2 for v in y))
    return round(num / (den_x * den_y), 4)
```

Returns a value between -1 and 1:
- `1.0` = perfect positive correlation
- `-1.0` = perfect negative correlation
- `0.0` = no linear relationship

Only computed when there are at least 5 rows (`CORRELATION_THRESHOLD`) to avoid meaningless results on tiny datasets.

---

## `formatter.py`

### What it does
Takes an `AnalysisReport` object and formats it as a human-readable terminal string. No analysis logic here — purely presentation.

### Key decisions

**`format(report, section=None)` — single entry point**
One method handles both full reports and single-section output. If `section` is provided, only that section is formatted and returned. The CLI passes `args.section` directly.

**`_null_bar()` — visual indicator**
```python
def _null_bar(self, pct: float) -> str:
    filled = int(pct / 10)
    color = "🔴" if pct > 20 else "🟡" if pct > 5 else "🟢"
    return f"{color} [{'█' * filled}{'░' * empty}]"
```

A 10-character bar where each block represents 10% nulls, colored by severity. This gives instant visual feedback on data quality without reading numbers.

**`_correlations()` — aligned table**
Column widths are fixed at 12 characters so the correlation matrix stays aligned regardless of column name length. Names longer than 12 characters are truncated with `[:12]`.

**Why separate from `analyzer.py`?**
If you wanted to output the report as JSON, HTML, or CSV instead of terminal text, you'd write a new formatter and call it from `main.py` — `analyzer.py` would be untouched. This is the **open/closed principle** — open for extension, closed for modification.

---

## `main.py`

### What it does
Parses CLI arguments, calls the analyzer, calls the formatter, prints output, and optionally saves JSON.

### Key decisions

**Validation before analysis**
```python
if not args.file.exists():
    print(f"Error: File '{args.file}' not found.", file=sys.stderr)
    sys.exit(1)
```
File existence is checked before calling `analyzer.analyze()`. This gives a clear error message instead of letting the exception bubble up with a Python traceback.

**`try/except` around analysis**
```python
try:
    report = analyzer.analyze(args.file)
except (ValueError, FileNotFoundError) as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```
`ValueError` covers: unsupported extension, empty CSV, encoding failures. Catching specific exceptions means unexpected bugs still surface as full tracebacks — only known error conditions are handled gracefully.

**JSON output is always the full report**
The `--output` flag always saves the complete report regardless of `--section`. If you display only skills but save to file, the file contains everything. This is the most useful behaviour — the file is for later analysis, the terminal is for quick inspection.

---

## `tests/test_analyzer.py`

### What it does
Tests stat helpers, type detection, column analysis, correlation, and error handling using a small in-memory CSV created with `tmp_path`.

### Key decisions

**`scope="module"` fixture**
```python
@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    ...
```
The test CSV is created once and shared across all tests in the module. Without `scope="module"`, pytest would recreate it before every test — wasteful for a fixture that never changes.

**Testing stat helpers in isolation**
`TestStatHelpers` tests `_mean`, `_median`, `_std`, `_correlation` directly with known inputs and expected outputs. This makes it immediately obvious if a math bug is introduced, without having to parse a whole CSV to find it.

**`tmp_path` for test files**
pytest's built-in `tmp_path` fixture provides a temporary directory that's automatically cleaned up after the test session. No manual cleanup needed, no leftover test files.

---

## `requirements.txt`

```
pytest>=7.0    # Optional: for running tests
```

Zero runtime dependencies. The entire analyzer uses Python stdlib: `csv`, `math`, `collections.Counter`, `pathlib`, `dataclasses`. This means the tool runs on any Python 3.11+ installation with no setup beyond cloning the repo.
