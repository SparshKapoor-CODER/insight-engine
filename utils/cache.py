import hashlib
import json
import pandas as pd
from models.database import db, AnalysisCache


def hash_dataframe(df: pd.DataFrame) -> str:
    """
    Deterministic content hash of a CLEANED dataframe (call this after
    data_cleaner.clean(), not on the raw upload). Two uploads that are
    byte-different but logically identical post-cleaning — different
    filename, stray whitespace, row order aside — hash the same and
    share a cache entry.

    Includes column names in the hash, not just row values: two frames
    with identical values under different column names must NOT collide,
    since the LLM prompt is built from column names too.
    """
    row_hashes = pd.util.hash_pandas_object(df, index=False).values.tobytes()
    col_sig    = "|".join(df.columns).encode("utf-8")
    return hashlib.sha256(row_hashes + col_sig).hexdigest()


def get_cached_analysis(data_hash: str):
    """Returns {'plan': dict, 'stories': list} or None on a cache miss."""
    entry = AnalysisCache.query.get(data_hash)
    if not entry:
        return None
    return {
        "plan":    json.loads(entry.analysis_json),
        "stories": json.loads(entry.narration_json),
    }


def save_analysis_cache(data_hash: str, plan: dict, stories: list) -> None:
    existing = AnalysisCache.query.get(data_hash)
    if existing:
        existing.analysis_json  = json.dumps(plan)
        existing.narration_json = json.dumps(stories)
    else:
        db.session.add(AnalysisCache(
            data_hash      = data_hash,
            analysis_json  = json.dumps(plan),
            narration_json = json.dumps(stories),
        ))
    db.session.commit()