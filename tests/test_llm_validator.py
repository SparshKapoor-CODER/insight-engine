import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.llm_analyst import _validate_plan

VALID_COLUMNS = ["region", "revenue", "units_sold", "category", "date"]

def _make_plan(charts):
    return {
        "domain": "sales",
        "report_title": "Test Report",
        "executive_summary": "Test summary.",
        "charts": charts,
        "key_takeaways": [],
        "growth_areas": [],
        "focus_areas": [],
        "recommendations": [],
        "closing_summary": "Test closing."
    }


def test_valid_chart_passes():
    plan = _make_plan([{
        "chart_id":        "chart_1",
        "chart_type":      "bar",
        "x_column":        "region",
        "y_column":        "revenue",
        "aggregation":     "sum",
        "group_by":        None,
        "title":           "Revenue by Region",
        "insight_question": "Which region performs best?"
    }])
    result = _validate_plan(plan, VALID_COLUMNS)
    assert len(result["charts"]) == 1


def test_invalid_x_column_is_skipped():
    plan = _make_plan([{
        "chart_id":        "chart_1",
        "chart_type":      "bar",
        "x_column":        "nonexistent_column",   # bad
        "y_column":        "revenue",
        "aggregation":     "sum",
        "group_by":        None,
        "title":           "Bad Chart",
        "insight_question": "?"
    }])
    result = _validate_plan(plan, VALID_COLUMNS)
    assert len(result["charts"]) == 0


def test_invalid_chart_type_is_skipped():
    plan = _make_plan([{
        "chart_id":        "chart_1",
        "chart_type":      "waterfall",             # not in allowed list
        "x_column":        "region",
        "y_column":        "revenue",
        "aggregation":     "sum",
        "group_by":        None,
        "title":           "Bad Chart",
        "insight_question": "?"
    }])
    result = _validate_plan(plan, VALID_COLUMNS)
    assert len(result["charts"]) == 0


def test_valid_charts_kept_when_one_is_invalid():
    plan = _make_plan([
        {
            "chart_id":        "chart_1",
            "chart_type":      "bar",
            "x_column":        "region",
            "y_column":        "revenue",
            "aggregation":     "sum",
            "group_by":        None,
            "title":           "Good Chart",
            "insight_question": "?"
        },
        {
            "chart_id":        "chart_2",
            "chart_type":      "bar",
            "x_column":        "fake_column",       # bad
            "y_column":        "revenue",
            "aggregation":     "sum",
            "group_by":        None,
            "title":           "Bad Chart",
            "insight_question": "?"
        }
    ])
    result = _validate_plan(plan, VALID_COLUMNS)
    assert len(result["charts"]) == 1
    assert result["charts"][0]["chart_id"] == "chart_1"
