from groq import Groq
from config import GROQ_API_KEY, MODEL_NAME

client = Groq(api_key=GROQ_API_KEY)

def narrate(chart_results: list) -> list:
    narrations = []
    for chart in chart_results:
        insight = _get_insight(chart)
        narrations.append({
            "chart_id": chart["chart_id"],
            "insight_text": insight
        })
    return narrations

def _get_insight(chart: dict) -> str:
    # Truncate data table to max 20 lines to stay within token limits
    data_lines = chart['data_table'].split('\n')[:20]
    truncated_table = '\n'.join(data_lines)

    prompt = f"""
You are writing a business report. Below is data from a chart.

Chart title: {chart['title']}
Question to answer: {chart['insight_question']}

Data:
{truncated_table}

Write 2-3 sentences of business insight based on this data.
Be specific, use the actual numbers. Professional tone. No bullet points.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3
    )

    return response.choices[0].message.content.strip()