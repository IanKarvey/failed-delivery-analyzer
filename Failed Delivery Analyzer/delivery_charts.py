"""
Matplotlib charts for the Failed Delivery and Redelivery Pattern Analyzer.

Every draw_* function fills a Matplotlib Figure. The same code therefore feeds
the Tkinter window and the console version (plt.show).

Each draw_* function also returns a reveal(progress) function (or None for an
empty chart). reveal(0) puts the chart in its "just starting" state (bars of
zero length, a line with no points...) and reveal(1) in its finished state.
The window plays progress from 0 to 1 to animate the chart in; the console
simply ignores it.
"""

from dataclasses import dataclass
from typing import Callable

from matplotlib.dates import date2num
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

import delivery_core as core

# Chart chrome (matches the white cards in the window)
SURFACE, INK, INK_2, GRID = "#ffffff", "#1e1b3a", "#5b5878", "#e8e6f5"
# Series colours: the app's purple and an orange. The pair was run through the
# palette validator (colour-blind separation, contrast, lightness) and passes.
PURPLE, ORANGE = "#6c4de6", "#eb6834"
# A delivery status keeps the same colour in every chart. Labels always
# name the status, so colour is never the only cue.
STATUS_COLORS = {core.SUCCESSFUL: "#0ca30c", core.FAILED: "#d03b3b", core.PENDING: "#fab219"}

PERIOD_LABELS = {"day": "Daily", "week": "Weekly", "month": "Monthly"}


plural = core.plural


def _late(progress):
    """0 for the first half of an animation, then fades up to 1: value labels appear last."""
    return max(0.0, (progress - 0.55) / 0.45)


def apply_layout(fig):
    """Automatic spacing, with a little breathing room at the edges."""
    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(w_pad=0.25, h_pad=0.2)


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


def draw_failure_reasons(fig, records, period="day"):
    """Bar chart: failed delivery attempts for each failure reason."""
    title = "Failed Deliveries by Reason"
    data = core.failed_by_reason(records)
    if not data:
        return _empty(fig, title, "No failed delivery attempts recorded.")
    total = sum(count for _, count in data)
    ax = _axes(fig, title, f"{plural(total, 'failed attempt')} across "
                           f"{plural(len(data), 'reason')}", grid_axis="x")
    labels = [reason for reason, _ in data]
    counts = [count for _, count in data]
    bars = ax.barh(range(len(data)), counts, height=0.55, color=PURPLE, edgecolor=SURFACE, linewidth=2)
    notes = [ax.annotate(f"{count}  ({count / total:.0%})", (count, i), xytext=(6, 0),
                         textcoords="offset points", va="center", fontsize=10,
                         fontweight="bold", color=INK)
             for i, count in enumerate(counts)]
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(labels, color=INK, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(counts) * 1.25 + 0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Failed delivery attempts", color=INK_2)

    def reveal(progress):  # the bars grow from the left, their labels follow and fade in
        for rect, count, note, i in zip(bars, counts, notes, range(len(counts))):
            rect.set_width(count * progress)
            note.xy = (count * progress, i)
            note.set_alpha(_late(progress))

    return reveal


def draw_success_by_area(fig, records, period="day"):
    """Bar chart: percent of unique deliveries completed successfully, per area."""
    title = "Delivery Success Rate by Area"
    stats = sorted(core.success_by_area(records), key=lambda s: (-s.rate, s.area))
    if not stats:
        return _empty(fig, title)
    overall = core.summarize(records).success_rate
    ax = _axes(fig, title, "Share of unique deliveries completed successfully"
                           f"  |  dashed line = all areas ({overall:.0f}%)", grid_axis="y")
    x = range(len(stats))
    rates = [s.rate for s in stats]
    bars = ax.bar(x, rates, width=0.5, color=PURPLE, edgecolor=SURFACE, linewidth=2)
    notes = [ax.annotate(f"{s.rate:.0f}%", (i, s.rate), xytext=(0, 5), textcoords="offset points",
                         ha="center", fontsize=11, fontweight="bold", color=INK)
             for i, s in enumerate(stats)]
    ax.axhline(overall, color=INK_2, linewidth=1, linestyle=(0, (4, 3)), zorder=3)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{s.area}\n{plural(s.deliveries, 'delivery')}" for s in stats],
                       color=INK, fontsize=10)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}%"))
    ax.set_ylabel("Success rate", color=INK_2)

    def reveal(progress):  # the bars rise from the baseline, their labels follow and fade in
        for rect, rate, note, i in zip(bars, rates, notes, range(len(rates))):
            rect.set_height(rate * progress)
            note.xy = (i, rate * progress)
            note.set_alpha(_late(progress))

    return reveal


def draw_trends(fig, records, period="day"):
    """Line graph: failed attempts and redelivery attempts over time."""
    title = "Redelivery Trends"
    points = core.trend(records, period)
    if not points:
        return _empty(fig, title)
    ax = _axes(fig, title, f"{PERIOD_LABELS[period]} totals: {plural(sum(p.failed_attempts for p in points), 'failed attempt')}, "
                           f"{plural(sum(p.redelivery_attempts for p in points), 'redelivery attempt')}", grid_axis="y")
    x = [p.start for p in points]
    # Different line style and marker shape as well as colour, so the lines stay
    # distinguishable where they overlap and for colour-blind readers.
    series = [("Failed attempts", [p.failed_attempts for p in points], PURPLE, (0, 9),
               {"linestyle": "-", "marker": "o", "markersize": 9}),
              ("Redelivery attempts", [p.redelivery_attempts for p in points], ORANGE, (0, -16),
               {"linestyle": (0, (5, 3)), "marker": "s", "markersize": 6})]
    area = ax.fill_between(x, series[0][1], color=PURPLE, alpha=0.10, linewidth=0)  # soft area under the main line
    lines, notes = [], []
    for name, values, color, offset, style in series:
        line, = ax.plot(x, values, color=color, linewidth=2, markeredgecolor=SURFACE,
                        markeredgewidth=1.5, label=name, **style)
        lines.append(line)
        peak = max(values)
        if peak > 0:  # label only the highest point of each line
            at = values.index(peak)
            notes.append(ax.annotate(str(peak), (x[at], peak), xytext=offset, textcoords="offset points",
                                     ha="center", fontsize=10, fontweight="bold", color=INK))
    top = max(max(s[1]) for s in series)
    ax.set_ylim(-0.3, top + 1.2)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=3))
    ax.set_ylabel("Number of attempts", color=INK_2)
    ax.margins(x=0.06)
    ticks = x if len(x) <= 12 else x[:: len(x) // 10 + 1]  # thin out the labels on long ranges
    prefix = "Week of " if period == "week" else ""
    fmt = "%b %Y" if period == "month" else "%b %d"
    ax.set_xticks(ticks)
    ax.set_xticklabels([prefix + d.strftime(fmt) for d in ticks], color=INK_2, fontsize=9,
                       rotation=0 if len(ticks) <= 6 else 35,
                       ha="center" if len(ticks) <= 6 else "right")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", ncol=2,
               frameon=False, labelcolor=INK_2)

    days = [float(v) for v in date2num(x)]  # numbers, so a point part-way between two dates is possible
    heights = [s[1] for s in series]
    # the area under the line is uncovered from the left by a clip box that grows with the line
    clip = Rectangle((ax.get_xlim()[0], -10), 0, 100, transform=ax.transData)

    def reveal(progress):  # both lines and the area are drawn left to right, then the labels fade in
        if progress >= 1.0 or len(x) < 2:
            for line, values in zip(lines, heights):
                line.set_data(days, values)
            area.set_clip_path(ax.patch)  # the normal clipping again
        else:
            position = progress * (len(x) - 1)
            k = int(position)
            frac = position - k
            tip = days[k] + frac * (days[k + 1] - days[k])  # where the lines have reached
            for line, values in zip(lines, heights):
                line.set_data(days[:k + 1] + [tip], values[:k + 1] + [values[k] + frac * (values[k + 1] - values[k])])
            clip.set_width(max(0.0, tip - clip.get_x()))
            area.set_clip_path(clip)
        for note in notes:
            note.set_alpha(_late(progress))

    return reveal


def draw_status_pie(fig, records, period="day"):
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
    wedges, texts = ax.pie(
        list(counts.values()), colors=[STATUS_COLORS[s] for s in names],
        startangle=90, counterclock=False, labeldistance=1.1,
        labels=[f"{plural(n, 'delivery')}\n{n / total:.1%}" for n in counts.values()],
        wedgeprops={"edgecolor": SURFACE, "linewidth": 2},
        textprops={"color": INK, "fontsize": 11},
    )
    fig.legend(wedges, names, loc="outside lower center", ncol=len(names),
               frameon=False, labelcolor=INK_2)

    def reveal(progress):  # the pie opens up from its centre, its labels fade in last
        for wedge in wedges:
            wedge.set_radius(max(progress, 0.001))
        for text in texts:
            text.set_alpha(_late(progress))

    return reveal


@dataclass(frozen=True)
class ChartSpec:
    key: str
    title: str
    draw: Callable
    size: tuple  # a good figure size, used by the console version


# the four visualizations of Section V of the requirements
CHARTS = [
    ChartSpec("reasons", "Failed Deliveries by Reason", draw_failure_reasons, (8, 5)),
    ChartSpec("areas", "Delivery Success Rate by Area", draw_success_by_area, (8, 5)),
    ChartSpec("trends", "Redelivery Trends", draw_trends, (9, 5)),
    ChartSpec("status", "Delivery Status", draw_status_pie, (7, 5.4)),
]
