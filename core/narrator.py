from concurrent.futures import ThreadPoolExecutor
from groq import Groq, APIStatusError, APITimeoutError
from config import GROQ_API_KEY, MODEL_NAME
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Lazy singleton — see llm_analyst.py for the same pattern and rationale:
# keeps this module importable without GROQ_API_KEY set, e.g. in tests
# that never actually call the API.
_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
    retry=retry_if_exception_type((APIStatusError, APITimeoutError))
)
def _call_groq_narrator(prompt: str) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=850,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


def _get_insight(chart: dict) -> str:
    data_lines      = chart['data_table'].split('\n')[:20]
    truncated_table = '\n'.join(data_lines)

    prompt = f"""
You are a senior business analyst writing a detailed insight section for a client report.

Chart title: {chart['title']}
Question to answer: {chart['insight_question']}

Data:
{truncated_table}

Write a detailed insight paragraph of 10-15 sentences for this chart.

Rules:
- Sentence 1: State the single most important finding with the exact number
- Sentence 2: Provide context or comparison (second highest, lowest, gap between top and bottom, etc.)
- Sentence 3: Explain what this pattern likely means for the business
- Sentence 4: Identify any risk or opportunity this reveals
- Sentence 5: Dig deeper — what could be causing this pattern?
- Sentence 6: How does this compare to what a healthy benchmark would look like?
- Sentence 7: What departments or teams does this most affect?
- Sentence 8: What happens if this trend continues unchanged for 6-12 months?
- Sentence 9: Is there a quick win the client can act on immediately?
- Sentence 10: Suggest one medium-term strategic action (1-3 months)
- Sentence 11: Suggest one long-term structural change if applicable
- Sentence 12-15: Any additional context, nuance, or caveats worth noting

Additional rules:
- Bold any important numbers, percentages, or key terms using **bold** markdown syntax
- Professional business tone, no bullet points, no headers
- Do not start with "The chart shows" or "Based on the data"
- Be specific, use actual numbers from the data, not vague language
"""

    return _call_groq_narrator(prompt)


def generate_insight(chart: dict) -> str:
    """Public entry point to narrate a single chart (used for cache-miss fallback)."""
    return _get_insight(chart)


def narrate(chart_results: list, log=None) -> list:
    if log:
        log(f"Narrating {len(chart_results)} charts in parallel (max 4 workers).")

    # Log per-chart before firing — can't log mid-parallel easily
    for chart in chart_results:
        if log:
            log(f"Generating insight for: {chart['title']}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        insights = list(executor.map(_get_insight, chart_results))

    return [
        {"chart_id": c["chart_id"], "insight_text": i}
        for c, i in zip(chart_results, insights)
    ]