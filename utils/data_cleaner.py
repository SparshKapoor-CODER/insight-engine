import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the dataframe in a safe, deterministic order.

    Change 5 note
    -------------
    The strip-whitespace step runs *first* (before profiling) so that
    avg_label_length values computed by profiler.py reflect the actual
    post-cleaning label lengths.  No other step in this function alters
    string column values in a way that would invalidate label lengths:
    - date parsing only affects columns whose names contain "date"/"time"
    - dropna removes fully-null columns, not string values
    - drop_duplicates removes rows but does not change cell content
    """

    # ── 1. Strip whitespace from column names ────────────────────────────────
    df.columns = df.columns.str.strip()

    # ── 2. Strip whitespace from string cell values (MUST run before profiling)
    #       This ensures avg_label_length in profiler.py is based on clean text.
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # ── 3. Try to parse date/time columns automatically ──────────────────────
    #       Only touches columns whose names contain "date" or "time".
    #       These become datetime64, so they are excluded from object-column
    #       cardinality in the profiler and do not affect avg_label_length.
    for col in df.columns:
        if "date" in col.lower() or "time" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

    # ── 4. Drop columns that are entirely null ───────────────────────────────
    df.dropna(axis=1, how="all", inplace=True)

    # ── 5. Drop duplicate rows ───────────────────────────────────────────────
    df.drop_duplicates(inplace=True)

    return df