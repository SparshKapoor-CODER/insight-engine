import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from config import CHARTS_PATH

# ── Brand palette (6 canonical colors) ──────────────────────────────────────
_BRAND_COLORS = [
    "#2563eb", "#16a34a", "#dc2626",
    "#d97706", "#7c3aed", "#0891b2"
]

BG_FIGURE = "#f8fafc"
BG_AXES   = "#f1f5f9"
GRID_COL  = "#ffffff"
SPINE_COL = "#cbd5e1"
TEXT_COL  = "#0f172a"
TICK_COL  = "#475569"

# ── Label rotation thresholds ────────────────────────────────────────────────
_ROT_MILD_COUNT  = 6
_ROT_STEEP_COUNT = 12
_ROT_MILD_LEN    = 12
_ROT_STEEP_LEN   = 20
_TRUNCATE_LEN    = 25


def get_palette(n: int) -> list:
    """
    Return n visually distinct hex colors.

    - For n <= 6 : returns the 6 canonical brand colors (sliced to n).
    - For n > 6  : generates n colors from matplotlib's 'tab20' colormap,
                   which covers up to 20 distinct hues, then falls back to
                   a linearly-spaced sample across the full colormap for n > 20.
    - Never crashes regardless of how large n is.

    Returns a list of hex strings in "#rrggbb" format.
    """
    if n <= 0:
        return []
    if n <= 6:
        return _BRAND_COLORS[:n]

    # tab20 has 20 distinct colors; for n > 20 we sample the full colormap range
    cmap   = matplotlib.colormaps["tab20"]
    colors = [cmap(i / max(n - 1, 1)) for i in range(n)]
    # Convert RGBA floats → "#rrggbb" hex strings
    return [
        "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )
        for r, g, b, _ in colors
    ]


def _truncate_label(label: str, maxlen: int = _TRUNCATE_LEN) -> str:
    s = str(label)
    return s if len(s) <= maxlen else s[:maxlen - 1] + "…"


def _fix_xaxis_labels(ax):
    """
    Inspect the current x-axis tick labels on *ax* and apply rotation /
    truncation so they never overlap.
    """
    fig = ax.get_figure()
    fig.canvas.draw()

    labels = [t.get_text() for t in ax.get_xticklabels()]
    if not labels:
        return

    truncated = [_truncate_label(lbl) for lbl in labels]
    max_len   = max(len(lbl) for lbl in truncated)
    count     = len(truncated)

    if count > _ROT_STEEP_COUNT or max_len > _ROT_STEEP_LEN:
        rotation, ha = 90, "right"
    elif count > _ROT_MILD_COUNT or max_len > _ROT_MILD_LEN:
        rotation, ha = 45, "right"
    else:
        rotation, ha = 0, "center"

    ax.set_xticks(ax.get_xticks())  # lock positions before relabeling
    ax.set_xticklabels(truncated, rotation=rotation, ha=ha,
                       fontsize=9, color=TICK_COL)


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


def generate_charts(df: pd.DataFrame, chart_plan: dict,
                    report_id: str, log=None) -> list:
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
    x        = chart["x_column"]
    y        = chart.get("y_column")
    agg      = chart.get("aggregation", "none")
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

    _categorical_x = False

    if chart_type == "bar":
        _categorical_x = True
        # n = number of unique values in group_by column if group_by exists, else 1
        n = int(data[group_by].nunique()) if group_by and group_by in data.columns \
            else max(1, int(data[x].nunique()) if x in data.columns else 1)
        palette = get_palette(n)
        if group_by:
            sns.barplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                        palette=palette, edgecolor="white", linewidth=0.6)
        else:
            # No group_by: color each bar by x itself instead of passing
            # palette with hue=None (deprecated, removed in seaborn 0.14)
            sns.barplot(data=data, x=x, y=y, hue=x, legend=False, ax=ax,
                        palette=palette, edgecolor="white", linewidth=0.6)
        for p in ax.patches:
            h = p.get_height()
            if h > 0:
                ax.annotate(f"{h:,.0f}",
                            (p.get_x() + p.get_width() / 2, h),
                            ha="center", va="bottom", fontsize=8,
                            color=TEXT_COL, fontweight="bold")

    elif chart_type == "line":
        _categorical_x = True
        # n = number of unique values in group_by column if group_by exists, else 1
        n = int(data[group_by].nunique()) if group_by and group_by in data.columns else 1
        palette = get_palette(n)
        if group_by:
            sns.lineplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                         palette=palette, linewidth=2.5, markers=True)
        else:
            # Single series: a plain color avoids the palette-without-hue
            # deprecation without hue=x, which would incorrectly split a
            # continuous line into disconnected per-category segments.
            sns.lineplot(data=data, x=x, y=y, ax=ax,
                         color=palette[0], linewidth=2.5, markers=True)
        ax.fill_between(data[x], data[y], alpha=0.08, color=palette[0])

    elif chart_type == "scatter":
        # n = number of unique hue categories if group_by exists, else 1
        n = int(data[group_by].nunique()) if group_by and group_by in data.columns else 1
        palette = get_palette(n)
        if group_by:
            sns.scatterplot(data=data, x=x, y=y, hue=group_by, ax=ax,
                            palette=palette, s=60, alpha=0.75, edgecolor="white")
        else:
            sns.scatterplot(data=data, x=x, y=y, ax=ax,
                            color=palette[0], s=60, alpha=0.75, edgecolor="white")

    elif chart_type == "histogram":
        # always n = 1 for histogram
        palette = get_palette(1)
        sns.histplot(data=data, x=x, ax=ax,
                     color=palette[0], edgecolor="white", linewidth=0.5)

    elif chart_type == "pie":
        counts = data[y] if y else data[x].value_counts()
        labels = data[x] if y else data[x].value_counts().index
        labels = [_truncate_label(str(lbl)) for lbl in labels]
        # n = number of slices being plotted
        n = len(counts)
        palette = get_palette(n)
        wedge_props = {"edgecolor": "white", "linewidth": 2}
        ax.pie(counts, labels=labels, autopct="%1.1f%%",
               colors=palette, wedgeprops=wedge_props,
               textprops={"fontsize": 9, "color": TEXT_COL})

    elif chart_type == "box":
        _categorical_x = True
        # n = number of unique values in x_column
        n = int(data[x].nunique()) if x in data.columns else 1
        palette = get_palette(n)
        sns.boxplot(data=data, x=x, y=y, hue=x, legend=False, ax=ax,
                    palette=palette, linewidth=1.2, fliersize=4)

    _style_axes(ax, title)

    if _categorical_x:
        _fix_xaxis_labels(ax)

    plt.tight_layout(pad=2)

    filename = f"{report_id}_{chart['chart_id']}.png"
    filepath = os.path.join(CHARTS_PATH, filename)
    plt.savefig(filepath, dpi=300, bbox_inches="tight",
                facecolor=BG_FIGURE)
    plt.close()

    data_table = data.to_string(index=False)

    return {
        "chart_id":         chart["chart_id"],
        "png_path":         filepath,
        "data_table":       data_table,
        "insight_question": chart["insight_question"],
        "title":            title
    }