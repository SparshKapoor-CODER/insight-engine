import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.profiler import profile

def test_profiler_returns_expected_keys():
    df = pd.DataFrame({
        "name":    ["Alice", "Bob", "Charlie"],
        "age":     [25, 30, 35],
        "revenue": [1000.0, 2000.0, 1500.0],
        "city":    ["Delhi", "Mumbai", "Pune"],
    })
    result = profile(df)

    assert "shape"       in result
    assert "columns"     in result
    assert "dtypes"      in result
    assert "sample"      in result
    assert "describe"    in result
    assert "null_counts" in result
    assert "cardinality" in result

    assert result["shape"]["rows"]    == 3
    assert result["shape"]["columns"] == 4
    assert "name"    in result["columns"]
    assert "revenue" in result["columns"]


def test_profiler_cardinality_only_for_object_columns():
    df = pd.DataFrame({
        "category": ["A", "B", "A"],
        "value":    [10, 20, 30],
    })
    result = profile(df)
    assert "category" in result["cardinality"]
    assert "value"    not in result["cardinality"]


def test_profiler_null_counts_only_when_nulls_exist():
    import numpy as np
    df = pd.DataFrame({
        "a": [1, 2, None],
        "b": [4, 5, 6],
    })
    result = profile(df)
    assert "a" in result["null_counts"]
    assert "b" not in result["null_counts"]
