import json
from groq import Groq
from config import GROQ_API_KEY, MODEL_NAME, MAX_CHARTS

client = Groq(api_key=GROQ_API_KEY)

def build_prompt(profile: dict) -> str:
    return f"""
You are a senior data analyst. Analyze the dataset profile below and suggest charts for a business report.

Dataset Profile:
----------------
Shape: {profile['shape']['rows']} rows x {profile['shape']['columns']} columns

Columns and types:
{json.dumps(profile['dtypes'], indent=2)}

Sample data (5 rows):
{json.dumps(profile['sample'], indent=2)}

Numerical summary:
{json.dumps(profile['describe'], indent=2)}

Null counts:
{json.dumps(profile.get('null_counts', {}), indent=2)}

Categorical columns (unique counts and top values):
{json.dumps(profile.get('cardinality', {}), indent=2)}
----------------

Rules you must follow:
- Only use column names that exist in the dataset above
- chart_type must be one of: bar, line, scatter, histogram, pie, box
- aggregation must be one of: sum, mean, count, max, min, none
- Do not suggest pie charts if a column has more than 6 unique values
- Do not suggest bar charts if x_column has more than 15 unique values
- Only suggest scatter plots between two numerical columns
- datetime columns must go on x_axis in line charts
- Suggest between 4 and {MAX_CHARTS} charts only

Return ONLY a valid JSON object. No explanation. No markdown. No backticks.

{{
  "domain": "...",
  "report_title": "...",
  "executive_summary": "...",
  "charts": [
    {{
      "chart_id": "chart_1",
      "chart_type": "bar",
      "x_column": "exact_column_name",
      "y_column": "exact_column_name",
      "aggregation": "sum",
      "group_by": null,
      "title": "...",
      "insight_question": "..."
    }}
  ],
  "key_takeaways": ["...", "...", "..."]
}}
"""

def analyse(profile: dict) -> dict:
    prompt = build_prompt(profile)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()

    # Safety strip in case model adds backticks anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)