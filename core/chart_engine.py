import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, important for servers
import matplotlib.pyplot as plt
import seaborn as sns
from config import CHARTS_PATH

sns.set_theme(style="whitegrid")

def generate_charts(df: pd.DataFrame, chart_plan: dict, report_id: str) -> list:
    results = []

    for chart in chart_plan["charts"]:
        try:
            result = _plot(df, chart, report_id)
            results.append(result)
        except Exception as e:
            print(f"Skipping {chart['chart_id']}: {e}")

    return results

def _aggregate(df, chart):
    x = chart["x_column"]
    y = chart.get("y_column")
    agg = chart.get("aggregation", "none")
    group_by = chart.get("group_by")

    if agg == "none" or y is None:
        return df

    group_cols = [x] if not group_by else [x, group_by]
    return df.groupby(group_cols)[y].agg(agg).reset_index()

def _plot(df, chart, report_id):
    chart_type = chart["chart_type"]
    x = chart["x_column"]
    y = chart.get("y_column")
    group_by = chart.get("group_by")
    title = chart["title"]

    data = _aggregate(df, chart)

    fig, ax = plt.subplots(figsize=(10, 5))

    if chart_type == "bar":
        sns.barplot(data=data, x=x, y=y, hue=group_by, ax=ax)
    elif chart_type == "line":
        sns.lineplot(data=data, x=x, y=y, hue=group_by, ax=ax)
    elif chart_type == "scatter":
        sns.scatterplot(data=data, x=x, y=y, hue=group_by, ax=ax)
    elif chart_type == "histogram":
        sns.histplot(data=data, x=x, ax=ax)
    elif chart_type == "pie":
        counts = data[y] if y else data[x].value_counts()
        labels = data[x] if y else data[x].value_counts().index
        ax.pie(counts, labels=labels, autopct="%1.1f%%")
    elif chart_type == "box":
        sns.boxplot(data=data, x=x, y=y, ax=ax)

    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()

    filename = f"{report_id}_{chart['chart_id']}.png"
    filepath = os.path.join(CHARTS_PATH, filename)
    plt.savefig(filepath, dpi=150)
    plt.close()

    # Build data table string to send back to LLM
    data_table = data.to_string(index=False)

    return {
        "chart_id": chart["chart_id"],
        "png_path": filepath,
        "data_table": data_table,
        "insight_question": chart["insight_question"],
        "title": title
    }