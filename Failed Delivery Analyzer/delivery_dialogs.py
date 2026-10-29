"""
Pop-up windows in the app's own style (no plain Windows message boxes):
  * message()  - errors
  * DatePicker - a calendar for the Delivery Date box, usable with mouse or keyboard
  * RecordDialog - the Add / Edit form for one delivery attempt (the six fields of the
    requirements), with a message next to each box that has a problem
"""

import calendar
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk

import delivery_core as core
from delivery_ui_kit import (
    ACCENT, ACCENT_DARK, CARD, FOCUS, FONT, FONT_BOLD, FONT_SMALL, INK, INK_2, MUTED, PAGE, SOFT,
    STATUS_COLORS, TITLE, PillButton, RoundedFrame, px)
from delivery_widgets import label, soft_combo, soft_entry

ERROR_INK = "#c02f2f"
FIELD_CAPTIONS = [("id", "Delivery ID"), ("date", "Delivery Date"), ("area", "Delivery Area"),
                  ("attempt", "Attempt Number"), ("status", "Final Status"), ("reason", "Failure Reason")]


class ModalDialog(tk.Toplevel):
    """A modal window: a white rounded card on the lavender page. Put content in `.body`."""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PAGE)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.result = None
        outer = RoundedFrame(self, radius=22, fill=CARD, backdrop=PAGE)
        outer.pack(padx=18, pady=18)
        self.body = tk.Frame(outer.body, bg=CARD)
        self.body.pack(padx=24, pady=20)
        self.bind("<Escape>", lambda e: self.close(None))

    def present(self, focus=None):
        """Centre it over the parent window, make it modal and put the cursor where it belongs."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + max(40, (parent.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        if focus is not None:
            focus.focus_set()
        self.wait_visibility()
        self.grab_set()

    def close(self, result=None):
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def message(parent, heading, text, kind="error"):
    """Tell the user something (an error by default) and wait for OK."""
    dialog = ModalDialog(parent, heading)
    top = tk.Frame(dialog.body, bg=CARD)
    top.pack(anchor="w")
    dot = STATUS_COLORS["Failed"] if kind == "error" else ACCENT
    label(top, "●", fg=dot, font=("Segoe UI", 12)).pack(side="left", padx=(0, 8))
    label(top, heading, fg=TITLE, font=("Segoe UI", 15, "bold")).pack(side="left")
    label(dialog.body, text, fg=INK_2, wraplength=px(440), justify="left").pack(anchor="w", pady=(8, 18))
    ok = PillButton(dialog.body, "OK", lambda: dialog.close(True), "primary", backdrop=CARD)
    ok.pack(anchor="e")
    dialog.ok_button = ok
    dialog.bind("<Return>", lambda e: dialog.close(True))
    dialog.present(focus=ok)
    parent.wait_window(dialog)


class DatePicker(tk.Toplevel):
    """A small calendar that opens under a date box.

    Mouse: click a day, or the arrows to change month. Keyboard: arrow keys move
    by a day or a week, Page Up / Page Down change month, Enter picks, Esc closes.
    """

    WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    def __init__(self, anchor, current, on_pick):
        super().__init__(anchor)
        self.anchor, self.on_pick = anchor, on_pick
        self.today = date.today()
        self.selected = current or self.today
        self.view = self.selected.replace(day=1)
        self.wm_overrideredirect(True)
        self.configure(bg="#c8c0f3")  # a 1px border around the card
        card = tk.Frame(self, bg=CARD, padx=px(12), pady=px(10))
        card.pack(padx=1, pady=1)

        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x")
        self.previous = self._arrow(head, "◀", lambda: self.change_month(-1))
        self.previous.pack(side="left")
        self.month_label = label(head, "", fg=INK, font=FONT_BOLD, width=17)
        self.month_label.pack(side="left", expand=True)
        self.following = self._arrow(head, "▶", lambda: self.change_month(1))
        self.following.pack(side="right")

        grid = tk.Frame(card, bg=CARD)
        grid.pack(pady=(8, 4))
        for column, name in enumerate(self.WEEKDAYS):
            label(grid, name, fg=MUTED, font=FONT_SMALL, width=4).grid(row=0, column=column, pady=(0, 2))
        self.days = []
        for row in range(6):
            for column in range(7):
                cell = tk.Label(grid, text="", width=4, font=FONT, bg=CARD, fg=INK, cursor="hand2",
                                highlightthickness=1, highlightbackground=CARD, pady=px(3))
                cell.grid(row=row + 1, column=column, padx=1, pady=1)
                cell.bind("<Button-1>", lambda e, c=cell: self.choose(c.date))
                cell.bind("<Enter>", lambda e, c=cell: self._hover(c, True))
                cell.bind("<Leave>", lambda e, c=cell: self._hover(c, False))
                self.days.append(cell)
        today = tk.Label(card, text="Today", fg=ACCENT_DARK, bg=CARD, cursor="hand2",
                         font=("Segoe UI", 9, "bold underline"))
        today.pack(anchor="w")
        today.bind("<Button-1>", lambda e: self.choose(self.today))

        for key, days in (("<Left>", -1), ("<Right>", 1), ("<Up>", -7), ("<Down>", 7)):
            self.bind(key, lambda e, d=days: self.move(days=d))
        self.bind("<Prior>", lambda e: self.move(months=-1))
        self.bind("<Next>", lambda e: self.move(months=1))
        self.bind("<Return>", lambda e: self.choose(self.selected))
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<ButtonPress-1>", self._maybe_outside)
        self.render()

        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + px(4)
        x = max(4, min(x, self.winfo_screenwidth() - self.winfo_reqwidth() - 4))
        y = min(y, self.winfo_screenheight() - self.winfo_reqheight() - 4)
        self.geometry(f"+{x}+{y}")
        self.focus_force()
        self.grab_set()

    @staticmethod
    def _arrow(parent, glyph, command):
        arrow = tk.Label(parent, text=glyph, fg=ACCENT, bg=CARD, cursor="hand2", padx=8,
                         font=("Segoe UI Symbol", 10))
        arrow.bind("<Button-1>", lambda e: command())
        return arrow

    def _hover(self, cell, inside):
        if cell.date != self.selected:
            cell.configure(bg=SOFT if inside else CARD)

    def render(self):
        self.month_label.configure(text=self.view.strftime("%B %Y"))
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.view.year, self.view.month)
        while len(weeks) < 6:  # always six rows, so the popup keeps the same size
            weeks.append([weeks[-1][-1] + timedelta(days=i + 1) for i in range(7)])
        for cell, day in zip(self.days, [d for week in weeks for d in week]):
            cell.date = day
            in_month = day.month == self.view.month
            chosen = day == self.selected
            cell.configure(
                text=str(day.day), bg=ACCENT if chosen else CARD,
                fg="#ffffff" if chosen else (INK if in_month else MUTED),
                highlightbackground=ACCENT_DARK if day == self.today and not chosen else (ACCENT if chosen else CARD))

    def change_month(self, step):
        month = self.view.month - 1 + step
        self.view = self.view.replace(year=self.view.year + month // 12, month=month % 12 + 1, day=1)
        self.render()

    def move(self, days=0, months=0):
        """Keyboard: shift the highlighted day by days, or by whole months."""
        if months:
            month = self.selected.month - 1 + months
            year, month = self.selected.year + month // 12, month % 12 + 1
            last = calendar.monthrange(year, month)[1]
            self.selected = date(year, month, min(self.selected.day, last))
        else:
            self.selected += timedelta(days=days)
        self.view = self.selected.replace(day=1)
        self.render()

    def choose(self, day):
        self.close()
        self.on_pick(day)

    def _maybe_outside(self, event):
        inside = (0 <= event.x_root - self.winfo_rootx() <= self.winfo_width()
                  and 0 <= event.y_root - self.winfo_rooty() <= self.winfo_height())
        if not inside:
            self.close()

    def close(self):
        try:
            self.grab_release()
            self.destroy()
            self.anchor.winfo_toplevel().grab_set()  # hand the modal grab back to the form
        except tk.TclError:
            pass


class RecordDialog(ModalDialog):
    """Add a new attempt, or edit an existing one.

    Each box that has a problem gets its message beside it (in red), and the
    keyboard focus goes to the first of them.
    """

    REASON_NOTES = {
        core.SUCCESSFUL: "not needed: click here if it failed",
        core.FAILED: "required: pick one or type your own",
        core.PENDING: "optional: pick one or type your own",
    }
    NOTES = {"id": "e.g. D006", "date": "YYYY-MM-DD, or use Calendar", "area": "pick one or type a new one",
             "attempt": "2 or more = a redelivery", "status": "", "reason": ""}

    def __init__(self, app, record=None):
        heading = "Edit delivery record" if record else "Add delivery record"
        super().__init__(app, heading)
        self.store, self.editing = app.store, record

        self.id_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().strftime(core.DATE_FORMAT))
        self.area_var = tk.StringVar()
        self.attempt_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value=core.SUCCESSFUL)
        self.reason_var = tk.StringVar(value=core.NO_REASON)
        self.hint_var = tk.StringVar()
        self.error_var = tk.StringVar()  # problems that belong to no single box (for example a locked file)
        self.field_errors = {}
        if record:
            self.id_var.set(record.delivery_id)
            self.date_var.set(record.day.strftime(core.DATE_FORMAT))
            self.area_var.set(record.area)
            self.attempt_var.set(str(record.attempt))
            self.status_var.set(record.status)
            self.reason_var.set(record.reason)

        body = self.body
        label(body, heading, fg=TITLE, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        label(body, "One row = one delivery attempt. A redelivery is a new attempt of the same Delivery ID.",
              font=FONT_SMALL, wraplength=px(520), justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 14))

        id_shell, self.id_entry = soft_entry(body, CARD, self.id_var, 28)
        self.date_row = tk.Frame(body, bg=CARD)
        date_shell, self.date_entry = soft_entry(self.date_row, CARD, self.date_var, 13)
        date_shell.pack(side="left")
        self.calendar_button = PillButton(self.date_row, "Calendar", self.open_calendar, "secondary",
                                          backdrop=CARD, height=32, padx=14)
        self.calendar_button.pack(side="left", padx=(8, 0))
        area_shell, self.area_box = soft_combo(body, CARD, self.area_var, self.store.known_areas(), 26, "normal")
        attempt_shell = RoundedFrame(body, radius=18, fill=SOFT, backdrop=CARD)
        self.attempt_box = ttk.Spinbox(attempt_shell.body, from_=1, to=99, textvariable=self.attempt_var,
                                       width=6, style="Soft.TSpinbox")
        self.attempt_box.pack(padx=6, pady=3)
        self.attempt_box.bind("<FocusIn>", lambda e: attempt_shell.set_ring(FOCUS), add="+")
        self.attempt_box.bind("<FocusOut>", lambda e: attempt_shell.set_ring(None), add="+")
        status_shell, self.status_box = soft_combo(body, CARD, self.status_var, core.STATUSES, 26)
        reason_shell, self.reason_box = soft_combo(body, CARD, self.reason_var, [], 26, "normal")
        widgets = {"id": id_shell, "date": self.date_row, "area": area_shell, "attempt": attempt_shell,
                   "status": status_shell, "reason": reason_shell}
        self.focus_targets = {"id": self.id_entry, "date": self.date_entry, "area": self.area_box,
                              "attempt": self.attempt_box, "status": self.status_box, "reason": self.reason_box}
        self.notes = {}
        for row, (field, caption) in enumerate(FIELD_CAPTIONS, start=2):
            label(body, caption, fg=INK, font=FONT_BOLD).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 18))
            widgets[field].grid(row=row, column=1, sticky="w", pady=6)
            note = label(body, "", fg=MUTED, font=FONT_SMALL, anchor="w", wraplength=px(250), justify="left")
            note.grid(row=row, column=2, sticky="w", padx=(12, 0))
            self.notes[field] = note
        label(body, fg=ACCENT, font=FONT_SMALL, textvariable=self.hint_var, wraplength=px(520),
              justify="left").grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 0))
        label(body, fg=ERROR_INK, font=FONT_BOLD, textvariable=self.error_var, wraplength=px(520),
              justify="left").grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 0))

        buttons = tk.Frame(body, bg=CARD)
        buttons.grid(row=10, column=0, columnspan=3, sticky="e", pady=(18, 0))
        PillButton(buttons, "Cancel", lambda: self.close(None), "secondary", backdrop=CARD).pack(side="left", padx=(0, 10))
        self.save_button = PillButton(buttons, "Save", self.save, "primary", backdrop=CARD)
        self.save_button.pack(side="left")

        # Clicking the greyed-out reason box means "this one failed": switch the status for them.
        for widget in (self.reason_box, reason_shell, reason_shell.body, reason_shell.shape):
            widget.bind("<Button-1>", self._reason_clicked, add="+")
        for field, variable in (("id", self.id_var), ("date", self.date_var), ("area", self.area_var),
                                ("attempt", self.attempt_var), ("status", self.status_var),
                                ("reason", self.reason_var)):
            variable.trace_add("write", lambda *_, f=field: self._clear_error(f))
        self.status_var.trace_add("write", self._on_status)
        self._on_status()
        for field in self.notes:
            self._show_note(field)
        if not record:
            self.id_var.trace_add("write", self._on_id)
        self.bind("<Return>", lambda e: self.save())
        self.present(focus=self.area_box if record else self.id_entry)

    # ---- the little message beside each box -------------------------------------
    def _default_note(self, field):
        if field == "reason":
            return self.REASON_NOTES.get(self.status_var.get(), "")
        return self.NOTES[field]

    def _show_note(self, field):
        error = self.field_errors.get(field)
        self.notes[field].configure(text=error or self._default_note(field),
                                   fg=ERROR_INK if error else MUTED,
                                   font=FONT_BOLD if error else FONT_SMALL)

    def _clear_error(self, field):
        if field in self.field_errors:
            del self.field_errors[field]
        if hasattr(self, "notes"):
            self._show_note(field)

    def show_errors(self, fields):
        """Put each message beside its box, and move the cursor to the first box with a problem."""
        self.field_errors = dict(fields)
        for field in self.notes:
            self._show_note(field)
        for field, _ in FIELD_CAPTIONS:
            if field in self.field_errors:
                self.focus_targets[field].focus_set()
                break

    # ---- date helper -----------------------------------------------------------
    def open_calendar(self):
        try:
            current = datetime.strptime(self.date_var.get().strip(), core.DATE_FORMAT).date()
        except ValueError:
            current = None
        self.picker = DatePicker(self.date_row, current,
                                 lambda day: self.date_var.set(day.strftime(core.DATE_FORMAT)))

    # ---- behaviour -------------------------------------------------------------
    def _reason_clicked(self, event=None):
        if self.status_var.get() == core.SUCCESSFUL:
            self.status_var.set(core.FAILED)
            self.hint_var.set("Status changed to Failed so you can choose a reason. "
                              "Change it back if the delivery actually succeeded.")
            self.reason_box.focus_set()

    def _on_id(self, *_):
        """Typing an existing Delivery ID pre-fills its area and next attempt number."""
        delivery_id = self.id_var.get().strip().upper()
        attempts = self.store.attempts_of(delivery_id) if delivery_id else []
        if attempts:
            last = attempts[-1]
            if any(a.status == core.SUCCESSFUL for a in attempts):
                self.hint_var.set(f"{delivery_id} was already delivered successfully, "
                                  "so another attempt cannot be added.")
                return
            number = self.store.next_attempt(delivery_id)
            self.area_var.set(last.area)
            self.attempt_var.set(str(number))
            self.hint_var.set(f"{delivery_id} already has {core.plural(len(attempts), 'attempt')} "
                              f"(latest: {last.status}). This will be attempt {number}, a redelivery.")
        else:
            self.attempt_var.set("1")
            self.hint_var.set("New delivery." if delivery_id else "")

    def _on_status(self, *_):
        """A successful attempt has no failure reason; a failed one must have one."""
        status = self.status_var.get()
        known = self.store.known_reasons()
        if hasattr(self, "notes"):
            self._show_note("reason")
        if status == core.SUCCESSFUL:
            self.reason_var.set(core.NO_REASON)
            self.reason_box.configure(state="disabled", values=[core.NO_REASON])
            return
        self.reason_box.configure(state="normal",
                                  values=known if status == core.FAILED else [core.NO_REASON] + known)
        if status == core.FAILED and self.reason_var.get() == core.NO_REASON:
            self.reason_var.set("")
        elif status == core.PENDING and not self.reason_var.get():
            self.reason_var.set(core.NO_REASON)

    def save(self):
        self.error_var.set("")
        try:
            record = core.make_attempt(
                self.id_var.get(), self.date_var.get(), self.area_var.get(),
                self.attempt_var.get(), self.reason_var.get(), self.status_var.get(),
                areas=self.store.known_areas(), reasons=self.store.known_reasons(),
                records=self.store.records, editing=self.editing)
            if self.editing:
                self.store.update(self.editing, record)
            else:
                self.store.add(record)
        except core.ValidationError as error:
            if error.fields:
                self.show_errors(error.fields)
            else:
                self.error_var.set("\n".join(error.errors))
            return
        except OSError as error:
            self.error_var.set(f"Could not write the CSV file (is it open in Excel?)\n{error}")
            return
        self.close(record)
