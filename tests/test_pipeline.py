import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.profiler import profile
from utils.data_cleaner import clean


def test_profiler_on_minimal_dataframe():
    """Full profile on a tiny real dataframe — no crashes, correct shape."""
    df = pd.DataFrame({
        "product":  ["Chocolate", "Candy", "Gum", "Mints", "Toffee",
                     "Chocolate", "Candy", "Gum", "Mints", "Toffee"],
        "region":   ["North", "South", "East", "West", "North",
                     "South", "East", "West", "North", "South"],
        "revenue":  [1200, 800, 500, 300, 950,
                     1100, 750, 480, 320, 870],
        "units":    [40, 30, 20, 15, 35,
                     38, 28, 19, 16, 33],
    })
    result = profile(df)

    assert result["shape"]["rows"]    == 10
    assert result["shape"]["columns"] == 4
    assert "revenue" in result["describe"]
    assert "product" in result["cardinality"]


def test_cleaner_strips_whitespace():
    df = pd.DataFrame({
        "name":  ["  Alice  ", "Bob ", "  Charlie"],
        "score": [10, 20, 30],
    })
    cleaned = clean(df.copy())
    assert all(cleaned["name"] == ["Alice", "Bob", "Charlie"])


def test_cleaner_drops_duplicate_rows():
    df = pd.DataFrame({
        "a": [1, 1, 2],
        "b": ["x", "x", "y"],
    })
    cleaned = clean(df.copy())
    assert len(cleaned) == 2


def test_cleaner_parses_date_column():
    df = pd.DataFrame({
        "date":    ["2024-01-01", "2024-01-02", "2024-01-03"],
        "revenue": [100, 200, 300],
    })
    cleaned = clean(df.copy())
    assert pd.api.types.is_datetime64_any_dtype(cleaned["date"])
