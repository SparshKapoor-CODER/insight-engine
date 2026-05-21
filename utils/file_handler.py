import pandas as pd
import os
from config import ALLOWED_EXTENSIONS, MAX_ROWS

def load_file(filepath: str) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    if ext == ".csv":
        df = pd.read_csv(filepath, on_bad_lines='skip')
    elif ext == ".xlsx":
        df = pd.read_excel(filepath, on_bad_lines='skip')

    if len(df) > MAX_ROWS:
        raise ValueError(f"Dataset exceeds {MAX_ROWS} rows. Got {len(df)} rows.")

    return df