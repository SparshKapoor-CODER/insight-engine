import pandas as pd

def clean(df: pd.DataFrame) -> pd.DataFrame:
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # Strip whitespace from string values
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Try to parse date columns automatically
    for col in df.columns:
        if "date" in col.lower() or "time" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

    # Drop columns that are entirely null
    df.dropna(axis=1, how="all", inplace=True)

    # Drop duplicate rows
    df.drop_duplicates(inplace=True)

    return df