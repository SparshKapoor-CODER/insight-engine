import json
from groq import Groq, APIStatusError, APITimeoutError
from config import GROQ_API_KEY, MODEL_NAME, MAX_CHARTS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

client = Groq(api_key=GROQ_API_KEY)


def build_prompt(profile: dict) -> str:
    return f"""
You are a senior data analyst and business consultant. Analyze the dataset profile below and suggest charts and business recommendations for a report.

Dataset Profile:
----------------
Shape: {profile['shape']['rows']} rows x {profile['shape']['columns']} columns

Columns and types:
{json.dumps(profile['dtypes'], indent=2)}

Sample data (3 rows):
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
- Suggest as many charts as you think are relevant, but no more than {MAX_CHARTS}
- For each chart, also suggest an insight_question that the chart should answer
- Your recommendations should be based on the data profile and the charts you suggest
- Your executive summary should summarize the overall story the data is telling in 5-10 sentences
- Your key takeaways should be the 5-10 most important insights from the data as short sentences
- Your growth areas should be 6-10 specific areas where the data shows strong positive trends or untapped potential
- Your focus areas should be 6-10 specific areas where the data shows weakness, decline, or risk that needs attention
- Your recommendations should be 10-15 concrete, actionable recommendations the client should act on based on the data
- Your closing summary should be a 10-20 sentence closing paragraph addressed to the client

Return ONLY a valid JSON object. No explanation. No markdown. No backticks.

{{
  "domain": "...",
  "report_title": "...",
  "executive_summary": "5-10 sentence paragraph summarizing the dataset and its main story.",

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

  "key_takeaways": [
    "5-10 most important findings from the data as short sentences"
  ],

  "growth_areas": [
    "6-10 specific areas where the data shows strong positive trends or untapped potential"
  ],

  "focus_areas": [
    "6-10 specific areas where the data shows weakness, decline, or risk that needs attention"
  ],

  "recommendations": [
    "10-15 concrete, actionable recommendations the client should act on based on the data"
  ],

  "closing_summary": "A 10-20 sentence closing paragraph addressed to the client. Summarize the overall health of their data, what they should prioritize, and what outcome they can expect if they act on the recommendations."
}}
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
    retry=retry_if_exception_type((APIStatusError, APITimeoutError, json.JSONDecodeError))
)
def _call_groq_analyse(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


def _validate_plan(plan: dict, df_columns: list) -> dict:
    valid_chart_types = ["bar", "line", "scatter", "histogram", "pie", "box"]
    valid_aggregations = ["sum", "mean", "count", "max", "min", "none"]
    valid_charts = []

    for chart in plan["charts"]:
        try:
            assert chart["x_column"] in df_columns, \
                f"x_column '{chart['x_column']}' not in dataset"
            if chart.get("y_column"):
                assert chart["y_column"] in df_columns, \
                    f"y_column '{chart['y_column']}' not in dataset"
            if chart.get("group_by"):
                assert chart["group_by"] in df_columns, \
                    f"group_by '{chart['group_by']}' not in dataset"
            assert chart["chart_type"] in valid_chart_types, \
                f"Invalid chart_type '{chart['chart_type']}'"
            assert chart["aggregation"] in valid_aggregations, \
                f"Invalid aggregation '{chart['aggregation']}'"
            valid_charts.append(chart)
        except AssertionError as e:
            # Skip invalid chart, don't crash the whole report
            print(f"Skipping invalid chart '{chart.get('chart_id', '?')}': {e}")

    plan["charts"] = valid_charts
    return plan


def analyse(profile: dict) -> dict:
    prompt     = build_prompt(profile)
    raw        = _call_groq_analyse(prompt)
    df_columns = profile["columns"]

    # Safety strip in case model adds backticks anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    plan = json.loads(raw)
    plan = _validate_plan(plan, df_columns)

    return plan