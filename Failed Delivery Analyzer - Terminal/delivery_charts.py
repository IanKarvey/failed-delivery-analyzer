"""
Matplotlib charts for the Failed Delivery and Redelivery Pattern Analyzer (terminal version).

These are the four visualizations of Section V of the project requirements. Every draw_*
function fills a Matplotlib Figure; show() opens the chosen charts in Matplotlib's own
windows (close them to return to the menu).
"""

from dataclasses import dataclass
from typing import Callable

from matplotlib.ticker import FuncFormatter, MaxNLocator

import delivery_core as core

SURFACE, INK, INK_2, GRID = "#ffffff", "#1e1b3a", "#5b5878", "#e8e6f5"  # chart background, text, grid
# Two series colours, a purple and an orange (they stay apart for colour-blind readers).
PURPLE, ORANGE = "#6c4de6", "#eb6834"
# A delivery status keeps the same colour in every chart. Labels always
# name the status, so colour is never the only cue.
STATUS_COLORS = {core.SUCCESSFUL: "#0ca30c", core.FAILED: "#d03b3b", core.PENDING: "#fab219"}

plural = core.plural


def _axes(fig, title, subtitle, grid_axis="y", centered=False):
    """Add the single plot area with the shared look: title, subtitle, light grid."""
    fig.clear()
    fig.set_facecolor(SURFACE)
    ax = fig.add_subplot()
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    align, x = ("center", 0.5) if centered else ("left", 0)
    ax.set_title(title, loc=align, fontsize=14, fontweight="bold", color=INK, pad=26)
    ax.text(x, 1.03, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, ha=align)
    return ax


def _empty(fig, title, message="No delivery records yet. Add some to see this chart."):
    ax = _axes(fig, title, "", grid_axis=None)
    ax.set_axis_off()
    ax.text(0.5, 0.5, message, transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color=INK_2)


def draw_failure_reasons(fig, records):
    """Bar chart: failed delivery attempts for each failure reason."""
    title = "Failed Deliveries by Reason"
    data = core.failed_by_reason(records)
    if not data:
        return _empty(fig, title, "No failed delivery attempts recorded.")
    total = sum(count for _, count in data)
    ax = _axes(fig, title, f"{plural(total, 'failed attempt')} across "
                           f"{plural(len(data), 'reason')}", grid_axis="x")
    counts = [count for _, count in data]
    ax.barh(range(len(data)), counts, height=0.55, color=PURPLE, edgecolor=SURFACE, linewidth=2)
    for i, count in enumerate(counts):
        ax.annotate(f"{count}  ({count / total:.0%})", (count, i), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=10,
                    fontweight="bold", color=INK)
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels([reason for reason, _ in data], color=INK, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(counts) * 1.25 + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Failed delivery attempts", color=INK_2)


def draw_success_by_area(fig, records):
    """Bar chart: percent of unique deliveries completed successfully, per area."""
    title = "Delivery Success Rate by Area"
    stats = sorted(core.success_by_area(records), key=lambda s: (-s.rate, s.area))
    if not stats:
        return _empty(fig, title)
    overall = core.summarize(records).success_rate
    ax = _axes(fig, title, "Share of unique deliveries completed successfully"
                           f"  |  dashed line = all areas ({overall:.0f}%)", grid_axis="y")
    x = range(len(stats))
    ax.bar(x, [s.rate for s in stats], width=0.5, color=PURPLE, edgecolor=SURFACE, linewidth=2)
    for i, s in enumerate(stats):
        ax.annotate(f"{s.rate:.0f}%", (i, s.rate), xytext=(0, 5), textcoords="offset points",
                    ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.axhline(overall, color=INK_2, linewidth=1, linestyle=(0, (4, 3)), zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{s.area}\n{plural(s.deliveries, 'delivery')}" for s in stats],
                       color=INK, fontsize=10)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}%"))
    ax.set_ylabel("Success rate", color=INK_2)


def draw_trends(fig, records):
    """Line graph: failed attempts and redelivery attempts over time (per day)."""
    title = "Redelivery Trends"
    points = core.trend(records)
    if not points:
        return _empty(fig, title)
    ax = _axes(fig, title, f"Daily totals: {plural(sum(p.failed_attempts for p in points), 'failed attempt')}, "
                           f"{plural(sum(p.redelivery_attempts for p in points), 'redelivery attempt')}",
               grid_axis="y")
    x = [p.day for p in points]
    # Different line style and marker shape as well as colour, so the lines stay
    # distinguishable where they overlap and for colour-blind readers.
    series = [("Failed attempts", [p.failed_attempts for p in points], PURPLE, (0, 9),
               {"linestyle": "-", "marker": "o", "markersize": 9}),
              ("Redelivery attempts", [p.redelivery_attempts for p in points], ORANGE, (0, -16),
               {"linestyle": (0, (5, 3)), "marker": "s", "markersize": 6})]
    ax.fill_between(x, series[0][1], color=PURPLE, alpha=0.10, linewidth=0)  # soft area under the main line
    for name, values, color, offset, style in series:
        ax.plot(x, values, color=color, linewidth=2, markeredgecolor=SURFACE,
                markeredgewidth=1.5, label=name, **style)
        peak = max(values)
        if peak > 0:  # label only the highest point of each line
            at = values.index(peak)
            ax.annotate(str(peak), (x[at], peak), xytext=offset, textcoords="offset points",
                        ha="center", fontsize=10, fontweight="bold", color=INK)
    ax.set_ylim(-0.3, max(max(s[1]) for s in series) + 1.2)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=3))
    ax.set_ylabel("Number of attempts", color=INK_2)
    ax.margins(x=0.06)
    ticks = x if len(x) <= 12 else x[:: len(x) // 10 + 1]  # thin out the labels on long ranges
    ax.set_xticks(ticks)
    ax.set_xticklabels([d.strftime("%b %d") for d in ticks], color=INK_2, fontsize=9,
                       rotation=0 if len(ticks) <= 6 else 35,
                       ha="center" if len(ticks) <= 6 else "right")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", ncol=2,
               frameon=False, labelcolor=INK_2)


def draw_status_pie(fig, records):
    """Pie chart: share of unique deliveries by status."""
    title = "Delivery Status"
    counts = {s: n for s, n in core.status_counts(records).items() if n}
    if not counts:
        return _empty(fig, title)
    total = sum(counts.values())
    ax = _axes(fig, title, f"Latest status of {plural(total, 'unique delivery')}",
               grid_axis=None, centered=True)
    ax.set_axis_off()
    names = list(counts)
    wedges, _ = ax.pie(
        list(counts.values()), colors=[STATUS_COLORS[s] for s in names],
        startangle=90, counterclock=False, labeldistance=1.1,
        labels=[f"{plural(n, 'delivery')}\n{n / total:.1%}" for n in counts.values()],
        wedgeprops={"edgecolor": SURFACE, "linewidth": 2},
        textprops={"color": INK, "fontsize": 11},
    )
    fig.legend(wedges, names, loc="outside lower center", ncol=len(names),
               frameon=False, labelcolor=INK_2)


@dataclass(frozen=True)
class ChartSpec:
    key: str
    name: str      # the name used in Section V of the requirements (shown in the menu)
    draw: Callable
    size: tuple    # a good figure size


# the four visualizations of Section V of the requirements
CHARTS = [
    ChartSpec("reasons", "Failed Deliveries by Reason Bar Chart", draw_failure_reasons, (8, 5)),
    ChartSpec("areas", "Delivery Success Rate by Area Bar Chart", draw_success_by_area, (8, 5)),
    ChartSpec("trends", "Redelivery Trends Line Graph", draw_trends, (9, 5)),
    ChartSpec("status", "Delivery Status Pie Chart", draw_status_pie, (7, 5.4)),
]


def new_figure(spec, records):
    """Draw one chart into a new Matplotlib figure and return it."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=spec.size, facecolor=SURFACE, layout="constrained")
    spec.draw(fig, records)
    fig.canvas.manager.set_window_title(spec.name)
    return fig


def show(specs, records):
    """Open the charts in Matplotlib windows and wait until they are all closed."""
    import matplotlib.pyplot as plt

    for spec in specs:
        new_figure(spec, records)
    plt.show()
    plt.close("all")
