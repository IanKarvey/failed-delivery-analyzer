"""
Building blocks shared by the pages of the Delivery Analyzer window:
text fields, tables, the page base class and the count-up number tile.
"""

import tkinter as tk
from tkinter import ttk

import delivery_core as core
from delivery_ui_kit import (
    ACCENT, CARD, FOCUS, FONT, FONT_BIG, FONT_BOLD, FONT_PAGE, FONT_PAGE_SHORT, FONT_SMALL, INK, INK_2, MUTED,
    PAGE, SOFT, STATUS_TINT, TITLE, Motion, RoundedFrame, blend, px, run)


def label(parent, text="", fg=INK_2, font=FONT, bg=CARD, **options):
    return tk.Label(parent, text=text, fg=fg, font=font, bg=bg, **options)


def soft_combo(parent, backdrop, variable, values, width, state="readonly"):
    """A pill-shaped drop-down. Returns (shell, combobox)."""
    shell = RoundedFrame(parent, radius=18, fill=SOFT, backdrop=backdrop)
    box = ttk.Combobox(shell.body, textvariable=variable, values=values, state=state,
                       width=width, style="Soft.TCombobox")
    box.pack(padx=6, pady=3)
    box.bind("<FocusIn>", lambda e: shell.set_ring(FOCUS), add="+")
    box.bind("<FocusOut>", lambda e: shell.set_ring(None), add="+")
    return shell, box


def soft_entry(parent, backdrop, variable, width):
    """A pill-shaped text box. Returns (shell, entry)."""
    shell = RoundedFrame(parent, radius=18, fill=SOFT, backdrop=backdrop)
    entry = tk.Entry(shell.body, textvariable=variable, width=width, relief="flat", bd=0,
                     bg=SOFT, fg=INK, insertbackground=INK, font=FONT, highlightthickness=0)
    entry.pack(padx=14, pady=7)
    entry.bind("<FocusIn>", lambda e: shell.set_ring(FOCUS), add="+")
    entry.bind("<FocusOut>", lambda e: shell.set_ring(None), add="+")
    return shell, entry


def make_tree(parent, columns, height=3):
    """A table inside a white rounded card. columns: [(name, width, anchor)].

    The requested height is small on purpose: the card is stretched by its
    parent grid, so the table shows as many rows as the window has room for.
    The row under the pointer is highlighted. Returns (card, tree).
    """
    outer = RoundedFrame(parent, radius=18, fill=CARD, backdrop=PAGE)
    body = outer.body
    tree = ttk.Treeview(body, columns=[c[0] for c in columns], show="headings",
                        selectmode="browse", height=height)
    scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    for name, width, anchor in columns:
        tree.heading(name, text=name, anchor=anchor)
        tree.column(name, width=px(width), minwidth=px(60), anchor=anchor)
    tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
    scroll.grid(row=0, column=1, sticky="ns", padx=(4, 6), pady=8)
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    base_widths = {name: px(width) for name, width, _ in columns}

    def fit_columns(event):
        """Scale every column with the table's width, so the last column is never cut off."""
        if event.width <= 1:
            return
        scale = event.width / sum(base_widths.values())
        for name, width in base_widths.items():
            tree.column(name, width=max(px(56), int(width * scale)), stretch=False)

    tree.bind("<Configure>", fit_columns, add="+")
    for status, tint in STATUS_TINT.items():
        tree.tag_configure(status, background=tint)
        tree.tag_configure(status + "_hover", background=blend(tint, ACCENT, 0.12))
    tree.tag_configure("flag", background=STATUS_TINT[core.FAILED])

    # row under the pointer: swap its status tag for a slightly darker "<status>_hover" tag
    tree.hover_state = {"item": None}

    def unhover():
        item = tree.hover_state["item"]
        tree.hover_state["item"] = None
        if item and tree.exists(item):
            tags = tree.item(item, "tags")
            if len(tags) == 1 and tags[0].endswith("_hover"):
                tree.item(item, tags=(tags[0][:-len("_hover")],))

    def on_motion(event):
        item = tree.identify_row(event.y)
        if item == tree.hover_state["item"]:
            return
        unhover()
        if item:
            tags = tree.item(item, "tags")
            if len(tags) == 1 and tags[0] in STATUS_TINT:  # (a row that is flashing is left alone)
                tree.item(item, tags=(tags[0] + "_hover",))
                tree.hover_state["item"] = item

    tree.bind("<Motion>", on_motion, add="+")
    tree.bind("<Leave>", lambda e: unhover(), add="+")

    tree.empty_label = tk.Label(tree, font=FONT, fg=MUTED, bg=CARD)  # message shown over an empty table
    return outer, tree


def fill_tree(tree, rows, empty_text="No records to show."):
    """Replace the table's rows. rows: [(values, tags, key)]. Returns {item_id: key}."""
    tree.hover_state["item"] = None
    tree.delete(*tree.get_children())
    items = {}
    for values, tags, key in rows:
        items[tree.insert("", "end", values=values, tags=tags)] = key
    if rows or not empty_text:
        tree.empty_label.place_forget()
    else:
        tree.empty_label.configure(text=empty_text)
        tree.empty_label.place(relx=0.5, y=px(56), anchor="n")
    return items


class Page(tk.Frame):
    """Base page: a title row (title left, buttons right) above the content.

    The content row takes all remaining height, so pages scale with the window.
    On a short window (`short` is True) the title row shrinks and `set_short` lets
    a page drop what it can do without, so the tables keep room for their rows.
    """
    title = ""
    subtitle = ""
    SHORT_BELOW = 580  # a page shorter than this (window about 760 high) is "short"

    def __init__(self, parent, app):
        super().__init__(parent, bg=PAGE)
        self.app, self.store = app, app.store
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.head = tk.Frame(self, bg=PAGE)
        self.head.grid(row=0, column=0, sticky="ew", pady=(2, 16))
        self.actions = tk.Frame(self.head, bg=PAGE)
        self.actions.pack(side="right", anchor="n")
        titles = tk.Frame(self.head, bg=PAGE)
        titles.pack(side="left", fill="x", expand=True)
        self.title_label = label(titles, self.title, fg=TITLE, font=FONT_PAGE, bg=PAGE)
        self.title_label.pack(anchor="w")
        subtitle = label(titles, self.subtitle, fg=INK_2, bg=PAGE, justify="left")
        subtitle.pack(anchor="w")
        titles.bind("<Configure>", lambda e: subtitle.configure(wraplength=max(200, e.width - 8)))
        self.content = tk.Frame(self, bg=PAGE)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.short = False
        self.bind("<Configure>", self._fit_height)

    def _fit_height(self, event):
        short = event.height < px(self.SHORT_BELOW)
        if short == self.short:
            return
        self.short = short
        self.title_label.configure(font=FONT_PAGE_SHORT if short else FONT_PAGE)
        self.head.grid_configure(pady=(0, 4) if short else (2, 16))
        self.set_short(short)

    def set_short(self, short):
        """Hook: a page changes its own layout for a short (True) or normal (False) window."""

    def refresh(self):
        pass

    def on_show(self):
        """Called each time the page is opened from the tab bar (pages play their intro animation here)."""
        self.refresh()


class StatTile(RoundedFrame):
    """A summary number on a white card. The number counts up (or down) when it changes.

    `dot` adds a status-coloured marker before the title; `compact` makes a smaller
    card without the caption line (set_compact switches it later, for short windows).
    """

    def __init__(self, parent, title, hint="", dot=None, color=ACCENT, compact=False):
        super().__init__(parent, radius=18, fill=CARD, backdrop=PAGE)
        top = tk.Frame(self.body, bg=CARD)
        top.pack(fill="x", padx=14, pady=(5, 0))
        if dot:
            label(top, "●", fg=dot, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.title_label = label(top, title, fg=INK_2)
        self.title_label.pack(side="left")
        self.value = label(self.body, "-", fg=color, anchor="w")
        self.value.pack(fill="x", padx=14)
        self.hint = label(self.body, hint, fg=MUTED, font=FONT_SMALL, anchor="w") if hint else None
        self.compact = None
        self.set_compact(compact)
        self.shown, self.target, self._tween = 0.0, None, None

    def set_compact(self, compact):
        if compact == self.compact:
            return
        self.compact = compact
        self.title_label.configure(font=FONT_SMALL if compact else FONT_BOLD)
        self.value.configure(font=("Segoe UI", 18, "bold") if compact else FONT_BIG)
        self.value.pack_configure(pady=(0, 2) if compact else 0)
        if self.hint:
            if compact:
                self.hint.pack_forget()
            else:
                self.hint.pack(fill="x", padx=14, pady=(0, 4))

    def set(self, number, text=None, unit="", from_zero=False, delay_ms=0):
        """Show `number`. `text` is the exact final text (for example '66.7%'); `unit` is
        added while counting. from_zero replays the count-up from 0."""
        text = text if text is not None else f"{number}{unit}"
        if not from_zero and self.target == number:
            if not (self._tween and self._tween.running):
                self.value.configure(text=text)  # unchanged: nothing to animate
            return
        self.target = number
        if self._tween:
            self._tween.cancel()
        if from_zero:
            self.shown = 0.0
            if Motion.enabled:
                self.value.configure(text=f"0{unit}")
        start = self.shown

        def step(progress):
            self.shown = start + (number - start) * progress
            self.value.configure(text=f"{self.shown:.0f}{unit}")

        def done():
            self.shown = float(number)
            self.value.configure(text=text)

        self._tween = run(self, 550, step, done=done, delay_ms=delay_ms)
