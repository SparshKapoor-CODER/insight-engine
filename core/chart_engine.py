import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from config import CHARTS_PATH

# Professional color palette
PALETTE   = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2"]
BG_FIGURE = "#f8fafc"
BG_AXES   = "#f1f5f9"
GRID_COL  = "#ffffff"
SPINE_COL = "#cbd5e1"
TEXT_COL  = "#0f172a"
TICK_COL  = "#475569"

def _style_axes(ax, title):
    ax.set_facecolor(BG_AXES)
    ax.yaxis.grid(True, color=GRID_COL, linewidth=1.5, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(SPINE_COL)
    ax.tick_params(colors=TICK_COL, labelsize=9)
    ax.set_title(title, fontsize=15, fontweight="bold", pad=15,
                 color=TEXT_COL, loc="left")
    if ax.get_xlabel():
        ax.set_xlabel(ax.get_xlabel(), fontsize=10, color=TICK_COL)
    if ax.get_ylabel():
        ax.set_ylabel(ax.get_ylabel(), fontsize=10, color=TICK_COL)


def generate_charts(df: pd.DataFrame, chart_plan: dict, report_id: str, log=None) -> list:
    results = []
    for chart in chart_plan["charts"]:
        try:
            if log:
                log(f"Plotting '{chart['title']}' as {chart['chart_type']} chart.")
            result = _plot(df, chart, report_id)
            results.append(result)
        except Exception as e:
            if log:
                log(f"WARNING: Skipping '{chart['chart_id']}' due to error: {e}")
            print(f"Skipping {chart['chart_id']}: {e}")
    return results


def _aggregate(df, chart):
    x      = chart["x_column"]
    y      = chart.get("y_column")
    agg    = chart.get("aggregation", "none")
    group_by = chart.get("group_by")

    if agg == "none" or y is None:
        return df

    group_cols = [x] if not group_by else [x, group_by]
    return df.groupby(group_cols)[y].agg(agg).reset_index()


def _plot(df, chart, report_id):
    chart_type = chart["chart_type"]
    x          = chart["x_column"]
    y          = chart.get("y_column")
    group_by   = chart.get("group_by")
    title      = chart["title"]

    data = _aggregate(df, chart)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG_FIGURE)

    if chart_type == "bar":
        sns.barplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                    palette=PALETTE, edgecolor="white", linewidth=0.6)
        # value labels on bars
        for p in ax.patches:
            h = p.get_height()
            if h > 0:
                ax.annotate(f"{h:,.0f}",
                            (p.get_x() + p.get_width() / 2, h),
                            ha="center", va="bottom", fontsize=8,
                            color=TEXT_COL, fontweight="bold")

    elif chart_type == "line":
        sns.lineplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                     palette=PALETTE, linewidth=2.5, markers=True)
        ax.fill_between(data[x], data[y], alpha=0.08, color=PALETTE[0])

    elif chart_type == "scatter":
        sns.scatterplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                        palette=PALETTE, s=60, alpha=0.75, edgecolor="white")

    elif chart_type == "histogram":
        sns.histplot(data=data, x=x, ax=ax,
                     color=PALETTE[0], edgecolor="white", linewidth=0.5)

    elif chart_type == "pie":
        counts = data[y] if y else data[x].value_counts()
        labels = data[x] if y else data[x].value_counts().index
        wedge_props = {"edgecolor": "white", "linewidth": 2}
        ax.pie(counts, labels=labels, autopct="%1.1f%%",
               colors=PALETTE[:len(counts)], wedgeprops=wedge_props,
               textprops={"fontsize": 9, "color": TEXT_COL})

    elif chart_type == "box":
        sns.boxplot(data=data, x=x, y=y, ax=ax,
                    palette=PALETTE, linewidth=1.2, fliersize=4)

    _style_axes(ax, title)
    plt.tight_layout(pad=2)

    filename = f"{report_id}_{chart['chart_id']}.png"
    filepath = os.path.join(CHARTS_PATH, filename)
    plt.savefig(filepath, dpi=150, bbox_inches="tight",
                facecolor=BG_FIGURE)
    plt.close()

    data_table = data.to_string(index=False)

    return {
        "chart_id":        chart["chart_id"],
        "png_path":        filepath,
        "data_table":      data_table,
        "insight_question": chart["insight_question"],
        "title":           title
    }
