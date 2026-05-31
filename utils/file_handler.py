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


def load_file(filepath: str) -> pd.DataFrame:
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

    if len(df) > MAX_ROWS:
        raise ValueError(
            f"Dataset exceeds the {MAX_ROWS} row limit. "
            f"Got {len(df):,} rows. Please upload a smaller file."
        )

    return df