import os
import pandas as pd
from config import ALLOWED_EXTENSIONS, MAX_ROWS

# Known magic bytes for binary formats
# CSV has no magic bytes — pandas validates it on read
MAGIC_BYTES = {
    ".xlsx": b"PK\x03\x04",
    ".xls":  b"\xd0\xcf\x11\xe0",
}


def _validate_magic(filepath: str, ext: str) -> None:
    expected = MAGIC_BYTES.get(ext)
    if expected is None:
        return  # CSV — no magic bytes to check

    with open(filepath, "rb") as f:
        header = f.read(4)

    if header != expected:
        raise ValueError(
            f"File content does not match declared extension '{ext}'. "
            f"The file may be corrupted or intentionally misnamed."
        )


def load_file(filepath: str, max_rows: int = None) -> pd.DataFrame:
    """
    max_rows: caller-supplied cap (e.g. the current user's tier limit).
    Falls back to the global config.MAX_ROWS if not provided, so existing
    callers that don't pass it keep the old behaviour.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    # Validate file content before passing to pandas
    _validate_magic(filepath, ext)

    if ext == ".csv":
        try:
            df = pd.read_csv(filepath, on_bad_lines='skip')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, on_bad_lines='skip', encoding='latin-1')
    elif ext == ".xlsx":
        df = pd.read_excel(filepath)          # on_bad_lines not valid for excel
    elif ext == ".xls":
        df = pd.read_excel(filepath, engine="xlrd")

    effective_max_rows = MAX_ROWS if max_rows is None else min(max_rows, MAX_ROWS)

    if len(df) > effective_max_rows:
        raise ValueError(
            f"Dataset exceeds the {effective_max_rows} row limit for your plan. "
            f"Got {len(df):,} rows. Please upload a smaller file or upgrade your plan."
        )

    return df