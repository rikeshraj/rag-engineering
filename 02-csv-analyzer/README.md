# CSV Analyzer 

A command-line tool that analyzes CSV files and produces summary statistics — built with pure Python stdlib, no external dependencies. 

## What it does 

- Detects column types automatically (numeric vs categorical) 
- Computes stats for numeric columns: mean, median, min, max, std dev 
- Computes stats for categorical columns: unique count, top values with frequency bars 
- Reports missing values per column 
- Optional Pearson correlation matrix between numeric columns 
- Outputs to terminal or saves as JSON 

## Usage 

```bash
# Full analysis
python main.py sample_data.csv

# Save report to JSON
python main.py sample_data.csv --output report.json

# Single column stats
python main.py sample_data.csv --column salary

# Missing values report only
python main.py sample_data.csv --missing

# Include correlation matrix
python main.py sample_data.csv --correlations

# Show top 10 values for categorical columns (default is 5)
python main.py sample_data.csv --top 10
```

## Project Structure 

```
csv-analyzer/
├── main.py             # CLI entry point
├── analyzer.py         # CSVAnalyzer class + ColumnStats dataclasses
├── sample_data.csv     # 30-row employee dataset for testing
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Dataclasses | `ColumnStats`, `AnalysisResult` in `analyzer.py` |
| OOP / Classes | `CSVAnalyzer` with private methods |
| File handling | CSV reading with encoding fallback |
| Error handling | FileNotFoundError, ValueError, PermissionError |
| Pure functions | `_mean`, `_median`, `_std_dev`, `_correlation` |
| Type hints | Throughout |
| argparse CLI | `build_arg_parser()` in `main.py` |
