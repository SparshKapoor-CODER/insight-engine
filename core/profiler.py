import pandas as pd


def profile(df: pd.DataFrame) -> dict:
    result = {}

    # Shape
    result["shape"] = {"rows": df.shape[0], "columns": df.shape[1]}

    # Column names
    result["columns"] = list(df.columns)

    # Dtypes as strings
    result["dtypes"] = {col: str(dtype) for col, dtype in df.dtypes.items()}

    # Sample rows
    result["sample"] = df.head(3).astype(str).to_dict(orient="records")

    # Describe — only numerical
    desc = df.describe(include="number")
    result["describe"] = desc.round(2).to_dict()

    # Null counts — only columns with nulls
    nulls = df.isnull().sum()
    result["null_counts"] = {col: int(count) for col, count in nulls.items() if count > 0}

    # ── Cardinality for object columns ────────────────────────────────────────
    # Change 2: also compute avg_label_length over the top-10 most frequent
    # values so the LLM prompt can guard against long-string bar/line charts.
    result["cardinality"] = {}
    for col in df.select_dtypes(include=["object", "str"]).columns:
        unique_count = df[col].nunique()
        top_values   = df[col].value_counts().head(10)   # top-10 for avg length

        # Average character length of the top-10 label strings (post-strip)
        label_lengths = [len(str(v).strip()) for v in top_values.index]
        avg_label_length = round(
            sum(label_lengths) / len(label_lengths), 1
        ) if label_lengths else 0.0

        result["cardinality"][col] = {
            "unique_count":     unique_count,
            "top_values":       top_values.head(5).to_dict(),   # keep top-5 for prompt
            "avg_label_length": avg_label_length,               # NEW — Change 2
        }

    return result