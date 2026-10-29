"""
Tkinter window for the Failed Delivery and Redelivery Pattern Analyzer.

A tab bar along the top switches between four pages, all taken from the project requirements:
  Records              Add / View and Search / Update / Filter Delivery Records
  Redelivery Tracking  attempts per delivery, with each delivery's attempt history
  Analysis             failed delivery analysis, success rate, area-based analysis, summary
  Charts               the four visualizations (Matplotlib)

All data work is done by delivery_core, all chart drawing by delivery_charts,
shared widgets are in delivery_widgets, pop-ups in delivery_dialogs, and all colours /
rounded widgets in delivery_ui_kit.

The layout scales with the window and with the display scaling: tables share the
free space, and filter rows, tiles and chart buttons wrap onto more rows when the
window is narrow.
"""

import os
import tkinter as tk
import traceback
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import ImageTk

import delivery_charts as charts
import delivery_core as core
from delivery_dialogs import RecordDialog, message
from delivery_ui_kit import (
    ACCENT, CARD, FLASH, FONT_BOLD, FONT_SECTION, FONT_SMALL, INK, MUTED, PAGE, STATUS_COLORS,
    STATUS_TINT, Motion, PillButton, ResponsiveGrid, RoundedFrame, TabItem, ToastBar, Tooltip,
    apply_style, blend, cancel_all, init_scaling, make_icon, os_animations_enabled, px, run)
from delivery_widgets import Page, StatTile, fill_tree, label, make_tree, soft_combo, soft_entry

ALL_AREAS, ALL_STATUSES, ALL_REASONS, ANY_ATTEMPTS = (
    "All areas", "All statuses", "All reasons", "Any attempts")
ATTEMPT_CHOICES = {ANY_ATTEMPTS: None, "1 attempt": "1", "2 attempts": "2", "3+ attempts": "3+"}

MIN_WIDTH, MIN_HEIGHT = 1000, 680
COMPACT_BELOW = 1240  # narrower windows drop the top bar's title text and file note so the tabs keep their room
RECORDS, TRACKING, ANALYSIS, CHARTS_PAGE = range(4)  # tab order


# ------------------------------------------------------------ Records page --
class RecordsPage(Page):
    title = "Records"
    subtitle = ("Add, view, search, update and filter delivery records. One row per delivery attempt; "
                "a redelivery is a new row with the same Delivery ID.")
    # the column names are the six fields of the requirements' delivery_records.csv
    COLUMNS = [("Delivery ID", 105, "w"), ("Delivery Date", 125, "w"), ("Delivery Area", 130, "w"),
               ("Attempt Number", 135, "center"), ("Failure Reason", 210, "w"), ("Final Status", 120, "w")]
    SORT_KEYS = {
        "Delivery ID": lambda r: (r.delivery_id, r.attempt),
        "Delivery Date": lambda r: (r.day, r.delivery_id, r.attempt),
        "Delivery Area": lambda r: (r.area, r.delivery_id, r.attempt),
        "Attempt Number": lambda r: (r.attempt, r.delivery_id),
        "Failure Reason": lambda r: (r.reason, r.delivery_id, r.attempt),
        "Final Status": lambda r: (r.status, r.delivery_id, r.attempt),
    }

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.items = {}
        self.sort_column, self.sort_reverse = "Delivery Date", False
        self.search_var = tk.StringVar()
        self.area_var = tk.StringVar(value=ALL_AREAS)
        self.status_var = tk.StringVar(value=ALL_STATUSES)
        self.reason_var = tk.StringVar(value=ALL_REASONS)
        self.attempts_var = tk.StringVar(value=ANY_ATTEMPTS)
        self.count_var = tk.StringVar()
        self._flash = None  # the highlight animation of a row that was just saved

        self.add_button = PillButton(self.actions, "+  Add delivery", app.add_record, "primary")
        self.add_button.pack(side="left", padx=(0, 10))
        self.edit_button = PillButton(self.actions, "Edit", self.edit_selected, "secondary")
        self.edit_button.pack(side="left")
        # say why the button is greyed out
        self.edit_tip = Tooltip(self.edit_button, lambda: "" if self.edit_button.enabled
                                else "Select a record in the table first")

        c = self.content
        c.rowconfigure(2, weight=1)
        strip = ResponsiveGrid(c, bg=PAGE, gap=12, stretch=True)  # quick totals; the numbers count up
        strip.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.strip_grid = strip
        self.strip = {}
        for key, title in (("attempts", "Total delivery attempts"), ("deliveries", "Unique deliveries"),
                           ("failed_attempts", "Failed delivery attempts"), ("rate", "Delivery success rate")):
            tile = StatTile(strip, title, compact=True)
            strip.add(tile)
            self.strip[key] = tile
        filters = RoundedFrame(c, radius=18, fill=CARD, backdrop=PAGE)
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        fields = ResponsiveGrid(filters.body, bg=CARD, gap=14)
        fields.pack(fill="x", padx=16, pady=12)
        self.search_entry = self._field(fields, "Search Delivery ID", lambda p: soft_entry(
            p, CARD, self.search_var, 16))[1]
        self.area_box = self._field(fields, "Area", lambda p: soft_combo(
            p, CARD, self.area_var, [ALL_AREAS], 13))[1]
        self._field(fields, "Status", lambda p: soft_combo(
            p, CARD, self.status_var, [ALL_STATUSES] + core.STATUSES, 13))
        self.reason_box = self._field(fields, "Failure reason", lambda p: soft_combo(
            p, CARD, self.reason_var, [ALL_REASONS], 19))[1]
        self._field(fields, "Attempts per delivery", lambda p: soft_combo(
            p, CARD, self.attempts_var, list(ATTEMPT_CHOICES), 12))
        self._field(fields, " ", lambda p: (PillButton(
            p, "Clear filters", self.clear_filters, "secondary", backdrop=CARD), None))

        table, self.tree = make_tree(c, self.COLUMNS)
        table.grid(row=2, column=0, sticky="nsew")
        for name, _, _ in self.COLUMNS:
            self.tree.heading(name, command=lambda n=name: self.sort_by(n))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Return>", lambda e: self.edit_selected())
        self.footer = label(c, bg=PAGE, font=FONT_SMALL, textvariable=self.count_var)
        self.footer.grid(row=3, column=0, sticky="w", pady=(10, 0))

        for variable in (self.area_var, self.status_var, self.reason_var, self.attempts_var,
                         self.search_var):
            variable.trace_add("write", lambda *_: self.refresh())
        self._update_buttons()

    def set_short(self, short):
        """Short windows: the totals (also on the Analysis page) make way for more table rows."""
        if short:
            self.strip_grid.grid_remove()
        else:
            self.strip_grid.grid()

    @staticmethod
    def _field(grid, caption, make_widget):
        """A caption above a widget, handed to the responsive grid as one unit."""
        box = tk.Frame(grid, bg=CARD)
        label(box, caption, font=FONT_SMALL).pack(anchor="w")
        made = make_widget(box)
        made[0].pack(anchor="w", pady=(3, 0))
        grid.add(box)
        return made

    def clear_filters(self):
        self.search_var.set("")
        self.area_var.set(ALL_AREAS)
        self.status_var.set(ALL_STATUSES)
        self.reason_var.set(ALL_REASONS)
        self.attempts_var.set(ANY_ATTEMPTS)

    def sort_by(self, column):
        self.sort_reverse = (not self.sort_reverse) if column == self.sort_column else False
        self.sort_column = column
        self.refresh()

    def selected(self):
        chosen = self.tree.selection()
        return self.items.get(chosen[0]) if chosen else None

    def _update_buttons(self):
        self.edit_button.set_enabled(self.selected() is not None)

    def edit_selected(self):
        record = self.selected()
        if record:
            self.app.edit_record(record)

    def on_show(self):
        self.refresh()
        self._update_strip(from_zero=True)  # the totals count up each time the page opens

    def _update_strip(self, from_zero=False):
        s = core.summarize(self.store.records)
        numbers = {"attempts": (s.total_attempts, ""), "deliveries": (s.deliveries, ""),
                   "failed_attempts": (s.failed_attempts, ""), "rate": (s.success_rate, "%")}
        for index, (key, (number, unit)) in enumerate(numbers.items()):
            text = core.format_percent(number) if unit else str(number)
            self.strip[key].set(number, text, unit, from_zero=from_zero, delay_ms=index * 60)

    def _flash_row(self, item, record):
        """Light a just-saved row up and fade it back to normal, then select it."""
        base = STATUS_TINT[record.status]

        def step(progress):
            self.tree.tag_configure("flash", background=blend(FLASH, base, progress))

        def done():
            if self.tree.exists(item):
                self.tree.item(item, tags=(record.status,))
                self.tree.selection_set(item)

        step(0.0)
        self.tree.item(item, tags=("flash",))
        self._flash = run(self, 900, step, done=done)

    def refresh(self, select=None):
        if self._flash:
            self._flash.cancel()
        areas = [ALL_AREAS] + self.store.known_areas()
        reasons = [ALL_REASONS, core.NO_REASON] + self.store.known_reasons()
        self.area_box.configure(values=areas)
        self.reason_box.configure(values=reasons)
        if self.area_var.get() not in areas:
            self.area_var.set(ALL_AREAS)
        if self.reason_var.get() not in reasons:
            self.reason_var.set(ALL_REASONS)

        records = core.filter_records(
            self.store.records, self.search_var.get(),
            area=None if self.area_var.get() == ALL_AREAS else self.area_var.get(),
            status=None if self.status_var.get() == ALL_STATUSES else self.status_var.get(),
            reason=None if self.reason_var.get() == ALL_REASONS else self.reason_var.get(),
            attempts=ATTEMPT_CHOICES[self.attempts_var.get()],
        )
        records.sort(key=self.SORT_KEYS[self.sort_column], reverse=self.sort_reverse)
        rows = [((r.delivery_id, r.day.strftime(core.DATE_FORMAT), r.area, r.attempt,
                  r.reason, r.status), (r.status,), r) for r in records]
        empty = ("No delivery records match these filters." if self.store.records
                 else "No delivery records yet. Use + Add delivery to add the first one.")
        self.items = fill_tree(self.tree, rows, empty)
        for name, _, _ in self.COLUMNS:
            arrow = (" ▲" if not self.sort_reverse else " ▼") if name == self.sort_column else ""
            self.tree.heading(name, text=name + arrow)
        for item, record in self.items.items():
            if record is select:
                self.tree.see(item)
                self._flash_row(item, record)
        self._update_strip()
        self.count_var.set(
            f"Showing {len(records)} of {core.plural(len(self.store.records), 'delivery attempt')}")
        self._update_buttons()


# ----------------------------------------------- Redelivery tracking page --
class TrackingPage(Page):
    title = "Redelivery Tracking"
    subtitle = "How many attempts each delivery needed, and what happened on every attempt."
    COLUMNS = [("Delivery ID", 110, "w"), ("Area", 130, "w"), ("Attempts", 90, "center"),
               ("First attempt", 130, "w"), ("Latest attempt", 130, "w"),
               ("Latest status", 130, "w"), ("Latest failure reason", 220, "w")]
    HISTORY = [("Attempt Number", 130, "center"), ("Delivery Date", 130, "w"),
               ("Failure Reason", 240, "w"), ("Final Status", 130, "w")]

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.items = {}
        self.only_var = tk.BooleanVar(value=True)
        self.summary_var = tk.StringVar()

        c = self.content
        c.rowconfigure(1, weight=3)  # the two tables share the free height, 3 : 2
        c.rowconfigure(3, weight=2)
        bar = RoundedFrame(c, radius=18, fill=CARD, backdrop=PAGE)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        row = tk.Frame(bar.body, bg=CARD)
        row.pack(fill="x", padx=16, pady=12)
        self.only_check = ttk.Checkbutton(
            row, text="Show only deliveries that needed more than one attempt",
            variable=self.only_var, command=self.refresh, style="Card.TCheckbutton")
        self.only_check.pack(side="left")
        label(row, textvariable=self.summary_var, fg=ACCENT, font=FONT_BOLD).pack(side="right")

        table, self.tree = make_tree(c, self.COLUMNS)
        table.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_history())
        label(c, "Attempt history", fg=INK, font=FONT_SECTION, bg=PAGE).grid(
            row=2, column=0, sticky="w", pady=(16, 8))
        history, self.history_tree = make_tree(c, self.HISTORY)
        history.grid(row=3, column=0, sticky="nsew")

    def refresh(self):
        infos = core.delivery_infos(self.store.records)
        shown = [i for i in infos if i.redelivered] if self.only_var.get() else infos
        shown.sort(key=lambda i: (-i.attempts, i.delivery_id))
        rows = [((i.delivery_id, i.area, i.attempts, i.first_day.strftime(core.DATE_FORMAT),
                  i.last_day.strftime(core.DATE_FORMAT), i.status, i.last_reason),
                 (i.status,), i.delivery_id) for i in shown]
        self.items = fill_tree(self.tree, rows, "No deliveries needed a redelivery.")
        redelivered = sum(1 for i in infos if i.redelivered)
        self.summary_var.set(
            f"{redelivered} of {core.plural(len(infos), 'delivery')} needed redelivery "
            f"({core.format_percent(core.percent(redelivered, len(infos)))})")
        self._show_history()

    def _show_history(self):
        chosen = self.tree.selection()
        delivery_id = self.items.get(chosen[0]) if chosen else None
        attempts = self.store.attempts_of(delivery_id) if delivery_id else []
        rows = [((a.attempt, a.day.strftime(core.DATE_FORMAT), a.reason, a.status), (a.status,), a)
                for a in attempts]
        fill_tree(self.history_tree, rows, "Select a delivery above to see its attempts.")


# ------------------------------------------------------------ Analysis page --
class AnalysisPage(Page):
    title = "Analysis"
    subtitle = ("Failed delivery analysis, delivery success rate, area-based analysis and the delivery "
                "summary, from the saved records.")
    AREA_COLUMNS = [("Area", 150, "w"), ("Deliveries", 90, "center"), ("Successful", 95, "center"),
                    ("Rate", 75, "center"), ("Redeliveries", 105, "center")]
    REASON_COLUMNS = [("Failure reason", 150, "w"), ("Count", 60, "center"),
                      ("Share", 65, "center")]

    def __init__(self, parent, app):
        super().__init__(parent, app)
        c = self.content
        c.rowconfigure(2, weight=1)
        grid = ResponsiveGrid(c, bg=PAGE, gap=14, stretch=True)
        grid.grid(row=0, column=0, sticky="ew")
        # titles use the requirements' wording for its analysis table
        spec = [
            ("attempts", "Total delivery attempts", "all rows in the file", None, ACCENT),
            ("deliveries", "Unique deliveries", "distinct delivery IDs", None, ACCENT),
            ("successful", "Successful deliveries", "latest attempt succeeded", STATUS_COLORS[core.SUCCESSFUL], INK),
            ("failed", "Failed deliveries", "latest attempt failed", STATUS_COLORS[core.FAILED], INK),
            ("pending", "Pending deliveries", "waiting for an outcome", STATUS_COLORS[core.PENDING], INK),
            ("redeliveries", "Requiring redelivery", "deliveries with 2+ attempts", None, ACCENT),
            ("failed_attempts", "Failed delivery attempts", "attempts with a failure reason", None, ACCENT),
            ("rate", "Delivery success rate", "successful / all deliveries", None, ACCENT),
        ]
        self.tiles = {}
        for key, title, hint, dot, color in spec:
            tile = StatTile(grid, title, hint, dot, color)
            grid.add(tile)
            self.tiles[key] = tile

        banner = RoundedFrame(c, radius=18, fill=ACCENT, backdrop=PAGE)
        banner.grid(row=1, column=0, sticky="ew", pady=12)
        self.banner = banner
        self.top_reason = label(banner.body, fg="#ffffff", font=FONT_BOLD, bg=ACCENT, anchor="w")
        self.top_reason.pack(fill="x", padx=16, pady=6)

        lower = tk.Frame(c, bg=PAGE)
        lower.grid(row=2, column=0, sticky="nsew")
        lower.columnconfigure(0, weight=7, uniform="lower")  # uniform: share the width by weight
        lower.columnconfigure(1, weight=4, uniform="lower")
        lower.rowconfigure(1, weight=1)
        label(lower, "Delivery success rate by area", fg=INK, font=FONT_SECTION, bg=PAGE).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        label(lower, "Failure reasons", fg=INK, font=FONT_SECTION, bg=PAGE).grid(
            row=0, column=1, sticky="w", padx=(14, 0), pady=(0, 8))
        area_card, self.area_tree = make_tree(lower, self.AREA_COLUMNS)
        area_card.grid(row=1, column=0, sticky="nsew")
        reason_card, self.reason_tree = make_tree(lower, self.REASON_COLUMNS)
        reason_card.grid(row=1, column=1, sticky="nsew", padx=(14, 0))

    def set_short(self, short):
        """Short windows: smaller tiles and less spacing, so the two tables keep room for their rows."""
        for tile in self.tiles.values():
            tile.set_compact(short)
        self.banner.grid_configure(pady=4 if short else 12)
        self.top_reason.pack_configure(pady=2 if short else 6)

    def on_show(self):
        self.refresh(from_zero=True)  # the tiles count up each time the page opens

    def refresh(self, from_zero=False):
        records = self.store.records
        s = core.summarize(records)
        numbers = {
            "attempts": s.total_attempts, "deliveries": s.deliveries, "successful": s.successful,
            "failed": s.failed, "pending": s.pending, "redeliveries": s.redeliveries,
            "failed_attempts": s.failed_attempts, "rate": s.success_rate,
        }
        for index, (key, number) in enumerate(numbers.items()):
            unit = "%" if key == "rate" else ""
            text = core.format_percent(number) if unit else str(number)
            self.tiles[key].set(number, text, unit, from_zero=from_zero, delay_ms=index * 45)
        self.top_reason.configure(text=f"Most common failure reason:   {s.top_reason}")

        stats = core.success_by_area(records)
        rates = [a.rate for a in stats]
        rows = []
        for a in stats:
            lowest = len(stats) > 1 and a.rate == min(rates) < max(rates)
            rows.append(((f"{a.area}  (lowest rate)" if lowest else a.area, a.deliveries,
                          a.successful, core.format_percent(a.rate), a.redeliveries),
                         ("flag",) if lowest else (), a))
        fill_tree(self.area_tree, rows, "No data yet.")

        reasons = core.failed_by_reason(records)
        total = sum(count for _, count in reasons)
        rows = [((name, count, core.format_percent(core.percent(count, total))), (), name)
                for name, count in reasons]
        fill_tree(self.reason_tree, rows, "No failed attempts recorded.")


# -------------------------------------------------------------- Charts page --
class ChartsPage(Page):
    title = "Charts"
    subtitle = ("Data visualization with Matplotlib: failed deliveries by reason, delivery success rate "
                "by area, redelivery trends and delivery status.")

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.chart_key = charts.CHARTS[0].key

        c = self.content
        c.rowconfigure(1, weight=1)
        bar = ResponsiveGrid(c, bg=PAGE, gap=10)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.buttons = {}
        for spec in charts.CHARTS:
            button = PillButton(bar, spec.title, lambda key=spec.key: self.select(key), "secondary")
            bar.add(button)
            self.buttons[spec.key] = button

        holder = RoundedFrame(c, radius=18, fill=CARD, backdrop=PAGE)
        holder.grid(row=1, column=0, sticky="nsew")
        self.figure = Figure(figsize=(4, 3), facecolor=charts.SURFACE)
        charts.apply_layout(self.figure)
        self._play = None  # the animation that draws the chart in
        self.canvas = FigureCanvasTkAgg(self.figure, master=holder.body)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(bg=charts.SURFACE, highlightthickness=0)
        self.widget.pack(fill="both", expand=True, padx=6, pady=6)

    def spec(self):
        return next(s for s in charts.CHARTS if s.key == self.chart_key)

    def select(self, key):
        self.chart_key = key
        self.refresh(animate=True)

    def on_show(self):
        self.refresh(animate=True)  # the chart draws itself in each time the page opens

    def refresh(self, animate=False):
        """Draw the chart. With animate=True it plays in (bars grow, the line is drawn...)."""
        if self._play:
            self._play.cancel()
        spec = self.spec()
        for key, button in self.buttons.items():
            button.set_style("primary" if key == spec.key else "secondary")
        charts.apply_layout(self.figure)
        reveal = spec.draw(self.figure, self.store.records)
        if animate and reveal and Motion.enabled:
            self._play_in(reveal)
        else:
            self.canvas.draw_idle()

    def _play_in(self, reveal):
        """Lay the finished chart out once, freeze that layout, then play progress 0 -> 1 on it.

        Re-laying-out on every frame would be slow, and the finished chart is what
        decides where everything sits, so the picture never jumps at the end.
        """
        self.canvas.draw()
        self.figure.set_layout_engine("none")
        reveal(0.0)

        def step(progress):
            reveal(progress)
            self.canvas.draw()

        def done():
            reveal(1.0)
            charts.apply_layout(self.figure)  # back to automatic spacing, so resizing still works
            self.canvas.draw_idle()

        self._play = run(self, 480, step, done=done)


# --------------------------------------------------------------------- app --
class DeliveryApp(tk.Tk):
    PAGES = [("☰", "Records", RecordsPage), ("↻", "Redelivery Tracking", TrackingPage),
             ("◔", "Analysis", AnalysisPage), ("▥", "Charts", ChartsPage)]

    def __init__(self, store=None):
        super().__init__()
        init_scaling(self)  # measure the display scaling before any widget is built
        self.store = store or core.DeliveryStore()
        self.title("Failed Delivery and Redelivery Pattern Analyzer")
        self._icon = ImageTk.PhotoImage(make_icon(64))  # keep a reference or Tk drops it
        self.iconphoto(True, self._icon)
        # Applied again once the window is up: after the "Starting up..." box (the first window the
        # process opens) Windows keeps the default icon unless it is set a second time.
        self._icon_job = self.after(150, lambda: self.iconphoto(True, self._icon))
        # Open at a comfortable size, but never bigger than the screen.
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(px(1320), screen_w - 60), min(px(860), screen_h - 110)
        self.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{max(8, (screen_h - height) // 2 - 20)}")
        self.minsize(min(px(MIN_WIDTH), width), min(px(MIN_HEIGHT), height))
        apply_style(self)
        Motion.enabled = os_animations_enabled()  # animations are built in; Windows' own "reduce motion" is respected
        self.file_var = tk.StringVar()

        shell = tk.Frame(self, bg=PAGE)
        shell.pack(fill="both", expand=True, padx=20, pady=20)
        self._build_topbar(shell)
        main = tk.Frame(shell, bg=PAGE)
        main.pack(fill="both", expand=True)
        self.toast = ToastBar(main, backdrop=PAGE)
        self.toast.pack(side="bottom", fill="x", pady=(6, 0))
        stack = tk.Frame(main, bg=PAGE)
        stack.pack(fill="both", expand=True)
        stack.rowconfigure(0, weight=1)
        stack.columnconfigure(0, weight=1)

        self.pages, self.tabs = [], []
        for index, (icon, name, page_class) in enumerate(self.PAGES):
            page = page_class(stack, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages.append(page)
            tab = TabItem(self.tab_box, icon, name, lambda i=index: self.show(i))
            tab.pack(side="left", fill="y", padx=(0, 4))
            self.tabs.append(tab)
        self.records_page, self.tracking_page, self.analysis_page, self.charts_page = self.pages

        self.refresh_all()
        self.show(RECORDS)
        if self.store.skipped:
            self.notify(f"{core.plural(self.store.skipped, 'row')} in the file could not be read and "
                        "was skipped.", kind="warning", seconds=10)
        else:
            self.notify(f"Loaded {core.plural(len(self.store.records), 'record')} from "
                        f"{os.path.basename(self.store.path)}.")

    def _build_topbar(self, shell):
        """Logo and title on the left, the page tabs next to them, the file note on the right."""
        self.topbar = RoundedFrame(shell, radius=22, fill=CARD, backdrop=PAGE)
        self.topbar.pack(side="top", fill="x", pady=(0, 16))
        body = self.topbar.body
        self.brand = tk.Frame(body, bg=CARD)
        self.brand.pack(side="left", padx=(8, 22), pady=4)
        self._logo = ImageTk.PhotoImage(make_icon(px(42)))  # the parcel logo; keep a reference or Tk drops it
        self.logo = tk.Label(self.brand, image=self._logo, bg=CARD, bd=0)
        self.logo.pack(side="left")
        self.brand_words = tk.Frame(self.brand, bg=CARD)
        self.brand_words.pack(side="left", padx=(12, 0))
        label(self.brand_words, "Delivery Analyzer", fg=INK, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        label(self.brand_words, "Pattern analyzer", fg=MUTED, font=FONT_SMALL).pack(anchor="w")

        self.file_note = label(body, fg=MUTED, font=FONT_SMALL, textvariable=self.file_var,
                               justify="right", anchor="e")
        self.file_note.pack(side="right", padx=(16, 10))
        self.file_tip = Tooltip(self.file_note, self._file_location)
        self.tab_box = tk.Frame(body, bg=CARD)
        self.tab_box.pack(side="left", fill="y")
        self.compact = False
        self.bind("<Configure>", self._fit_topbar, add="+")

    def _fit_topbar(self, event):
        """Narrow windows: leave out the title text and the file note so every tab stays fully visible."""
        if event.widget is not self:
            return
        compact = event.width < px(COMPACT_BELOW)
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.brand_words.pack_forget()
            self.file_note.pack_forget()
        else:
            self.brand_words.pack(side="left", padx=(12, 0))
            self.file_note.pack(side="right", padx=(16, 10))

    def _file_location(self):
        """Where the records are saved, when that is not the program's own folder."""
        folder = os.path.dirname(self.store.path)
        same = os.path.normcase(folder) == os.path.normcase(core.BASE_DIR)
        return "" if same else f"Saved in: {folder}"

    def destroy(self):
        cancel_all()  # no animation may be left waiting for a window that is gone
        try:
            self.after_cancel(self._icon_job)
            self.toast.clear()
            self.update_idletasks()  # let a queued chart redraw finish before the window goes away
        except tk.TclError:
            pass
        super().destroy()

    def show(self, index):
        self.pages[index].tkraise()
        for i, tab in enumerate(self.tabs):
            tab.set_active(i == index)
        self.pages[index].on_show()

    def refresh_all(self, select=None):
        self.records_page.refresh(select)
        for page in self.pages[1:]:
            page.refresh()
        deliveries = len({r.delivery_id for r in self.store.records})
        self.file_var.set(f"{os.path.basename(self.store.path)}\n"
                          f"{core.plural(len(self.store.records), 'attempt')}, "
                          f"{core.plural(deliveries, 'delivery')} · saved automatically")

    def report_callback_exception(self, exc_type, exc, tb):
        """A bug inside a button/menu action: keep the program running and keep a record of it."""
        log = core.log_error("".join(traceback.format_exception(exc_type, exc, tb)))
        message(self, "Something went wrong",
                f"{exc}\n\nYour records are safe. Details were saved to:\n{log}")

    def notify(self, text, kind="info", seconds=4.0):
        """Slide a short message in at the bottom of the window (kind: info, success, warning, error)."""
        self.toast.show(text, kind, seconds)

    # ---- the two things you can do to a record (Add and Update, from the requirements) ----
    def add_record(self):
        dialog = RecordDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_all(select=dialog.result)
            self.notify(f"Added {dialog.result.delivery_id}, attempt {dialog.result.attempt}. Saved to file.",
                        kind="success")

    def edit_record(self, record):
        dialog = RecordDialog(self, record)
        self.wait_window(dialog)
        if dialog.result:
            self.refresh_all(select=dialog.result)
            self.notify(f"Updated {dialog.result.delivery_id}, attempt {dialog.result.attempt}. Saved to file.",
                        kind="success")


def main():
    try:  # sharper text on high-DPI Windows screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError, ImportError):
        pass
    DeliveryApp().mainloop()


if __name__ == "__main__":
    main()
