import pandas as pd

def profile(df: pd.DataFrame) -> dict:
    profile = {}

    # Shape
    profile["shape"] = {"rows": df.shape[0], "columns": df.shape[1]}

    # Column names
    profile["columns"] = list(df.columns)

    # Dtypes as strings
    profile["dtypes"] = {col: str(dtype) for col, dtype in df.dtypes.items()}

    # Sample rows
    profile["sample"] = df.head(3).astype(str).to_dict(orient="records")

    # Describe — only numerical
    desc = df.describe(include="number")
    profile["describe"] = desc.round(2).to_dict()

    # Null counts — only columns with nulls
    nulls = df.isnull().sum()
    profile["null_counts"] = {col: int(count) for col, count in nulls.items() if count > 0}

    # Cardinality for object columns
    profile["cardinality"] = {}
    for col in df.select_dtypes(include="object").columns:
        unique_count = df[col].nunique()
        top_values = df[col].value_counts().head(5).to_dict()
        profile["cardinality"][col] = {
            "unique_count": unique_count,
            "top_values": top_values
        }

    return profile