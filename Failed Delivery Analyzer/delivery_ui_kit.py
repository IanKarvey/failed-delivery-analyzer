"""
Look and feel for the Delivery Analyzer window: lavender page, white rounded
cards, purple gradient pill buttons, a tab bar along the top.

Tkinter has no rounded corners, so shapes are drawn with Pillow at 4x size and
shrunk (anti-aliased) into images. Only Tkinter and Pillow are needed.

Accessibility built in:
  * every colour pair used for text is listed in TEXT_PAIRS and checked by a
    test to meet the WCAG contrast ratio (4.5:1);
  * every button and tab can be reached with Tab and used
    with Space / Enter, and shows a clear focus ring;
  * all fixed pixel sizes go through px(), so the window also looks right on
    125% / 150% display scaling.
"""

import math
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageTk

# ---------------------------------------------------------------- palette --
PAGE, CARD, SOFT, SOFT_2 = "#ebeaf8", "#ffffff", "#f3f1fd", "#e6e1fb"
INK, INK_2, MUTED, LINE = "#1e1b3a", "#5b5878", "#64618a", "#e6e4f3"
DISABLED_INK = "#74718f"
ACCENT, ACCENT_DARK, TITLE = "#6c4de6", "#5a3dd1", "#4f35c9"
FOCUS = "#4f35c9"  # the keyboard focus ring
GRADIENT = ("#6040d8", "#7b4cdf")
GRADIENT_HOVER = ("#5230c6", "#6c3fd0")
GRADIENT_PRESS = ("#4727b0", "#5d34c0")
DANGER = "#d03b3b"
SELECT = "#e9e3ff"
FLASH = "#cdbff9"  # a saved row lights up in this colour, then fades back

# A delivery status keeps one colour everywhere (tables, tiles, charts).
STATUS_COLORS = {"Successful": "#0ca30c", "Failed": "#d03b3b", "Pending": "#fab219"}
STATUS_TINT = {"Successful": CARD, "Failed": "#fdeaf0", "Pending": "#fff4da"}

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_PAGE = ("Segoe UI", 22, "bold")
FONT_PAGE_SHORT = ("Segoe UI", 16, "bold")  # page titles on short windows
FONT_SECTION = ("Segoe UI", 12, "bold")
FONT_BIG = ("Segoe UI", 24, "bold")

# Every (name, text colour, background, minimum contrast) used for text in the window.
# A test checks them all, so a colour change that hurts readability is caught.
TEXT_PAIRS = [
    ("body text on cards", INK, CARD, 4.5), ("secondary text on cards", INK_2, CARD, 4.5),
    ("secondary text on page", INK_2, PAGE, 4.5), ("hint text on cards", MUTED, CARD, 4.5),
    ("hint text on page", MUTED, PAGE, 4.5), ("hint text on soft fields", MUTED, SOFT, 4.5),
    ("accent text on cards", ACCENT, CARD, 4.5), ("accent text on soft fields", ACCENT, SOFT, 4.5),
    ("accent text on page", ACCENT, PAGE, 4.5), ("page titles", TITLE, PAGE, 4.5),
    ("white on accent banner", "#ffffff", ACCENT, 4.5),
    ("white on button (left end)", "#ffffff", GRADIENT[0], 4.5),
    ("white on button (right end)", "#ffffff", GRADIENT[1], 4.5),
    ("white on button (hover, right end)", "#ffffff", GRADIENT_HOVER[1], 4.5),
    ("white on button (pressed, right end)", "#ffffff", GRADIENT_PRESS[1], 4.5),
    ("disabled button text", DISABLED_INK, SOFT_2, 3.0),
    ("secondary button text (hover)", ACCENT, SOFT, 4.5),
    ("Delete button text", DANGER, CARD, 4.5),
    ("error text", "#c02f2f", CARD, 4.5),
    ("info toast", ACCENT_DARK, SOFT_2, 4.5), ("success toast", "#0a5c0a", "#e2f5e2", 4.5),
    ("warning toast", "#7a5200", "#fff1cf", 4.5), ("error toast", "#a32626", "#fde4ea", 4.5),
    ("text on failed rows", INK, STATUS_TINT["Failed"], 4.5),
    ("text on pending rows", INK, STATUS_TINT["Pending"], 4.5),
    ("tooltip", "#ffffff", INK, 4.5), ("focus ring on cards", FOCUS, CARD, 3.0),
    ("focus ring on page", FOCUS, PAGE, 3.0),
]


def _luminance(colour):
    r, g, b = (c / 255 for c in ImageColor.getrgb(colour))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _lin(c):
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(foreground, background):
    """WCAG contrast ratio between two '#rrggbb' colours (1 = identical, 21 = black on white)."""
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# ------------------------------------------------------------ display scaling --
class Scale:
    """1.0 at 100% Windows display scaling, 1.5 at 150%, and so on."""
    factor = 1.0


def px(value):
    """A pixel size made for 100% scaling, adjusted to this screen."""
    return int(round(value * Scale.factor)) if value else 0


def init_scaling(root):
    """Measure the screen's scaling once the first window exists (before widgets are built)."""
    try:
        factor = root.winfo_fpixels("1i") / 96.0
    except tk.TclError:
        factor = 1.0
    Scale.factor = min(3.0, max(1.0, round(factor * 4) / 4))


SCALE = 4  # supersampling factor for smooth edges
_images = {}  # PIL images only; PhotoImages are made per widget


# ------------------------------------------------------------------ motion --
class Motion:
    """The master switch for every animation (off when Windows asks for reduced motion)."""
    enabled = True


FRAME_MS = 16  # about 60 frames a second


def os_animations_enabled():
    """Follow Windows' own 'Show animations' setting (Accessibility > Visual effects)."""
    try:
        import ctypes
        flag = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(flag), 0)  # CLIENTAREAANIMATION
        return bool(flag.value)
    except Exception:
        return True


def blend(start, end, t):
    """A colour part-way between two '#rrggbb' colours (t=0 gives start, t=1 gives end)."""
    a, b = ImageColor.getrgb(start), ImageColor.getrgb(end)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ease_out(t):
    return 1 - (1 - t) ** 3  # fast start, gentle stop


def ease_in(t):
    return t ** 3  # gentle start, fast finish


_active = set()  # every animation that is currently scheduled


def cancel_all():
    """Stop every running animation (used when the window closes)."""
    for tween in list(_active):
        tween.cancel()


class Tween:
    """Runs step(progress) from 0 to 1 over duration_ms, then done().

    It is driven by the clock, not by counting frames, so an effect lasts the
    same time on a slow computer (it just shows fewer frames). With animations
    switched off it jumps straight to the end state.
    """

    def __init__(self, widget, duration_ms, step, done=None, ease=ease_out, delay_ms=0):
        self.widget, self.duration, self.step = widget, duration_ms, step
        self.done, self.ease = done, ease
        self.running, self.job, self.started = True, None, 0.0
        if not Motion.enabled or duration_ms <= 0:
            self.running = False
            step(1.0)
            if done:
                done()
            return
        _active.add(self)
        self.job = widget.after(max(0, int(delay_ms)), self._start)

    def _start(self):
        self.started = time.perf_counter()
        self._tick()

    def _tick(self):
        if not self.running:
            return
        try:
            if not self.widget.winfo_exists():
                self.running = False
                _active.discard(self)
                return
            progress = min(1.0, (time.perf_counter() - self.started) * 1000 / self.duration)
            self.step(self.ease(progress))
            if progress >= 1.0:
                self.running = False
                _active.discard(self)
                if self.done:
                    self.done()
            else:
                self.job = self.widget.after(FRAME_MS, self._tick)
        except tk.TclError:  # the window was closed mid-animation
            self.running = False
            _active.discard(self)

    def cancel(self):
        self.running = False
        _active.discard(self)
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def finish(self):
        """Jump to the end right now."""
        if self.running:
            self.cancel()
            self.step(1.0)
            if self.done:
                self.done()


def run(widget, duration_ms, step, done=None, ease=ease_out, delay_ms=0):
    return Tween(widget, duration_ms, step, done, ease, delay_ms)


# ----------------------------------------------------- image drawing ------
def _corner(radius, fill, backdrop):
    """Top-left quarter of a circle: `fill` inside, `backdrop` outside."""
    key = ("corner", radius, fill, backdrop)
    if key not in _images:
        size = radius * SCALE
        image = Image.new("RGB", (size, size), backdrop)
        ImageDraw.Draw(image).ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=fill)
        _images[key] = image.resize((radius, radius), Image.LANCZOS)
    return _images[key]


def _gradient(size, start, end):
    image = Image.new("RGB", size, start)
    if start != end:
        draw = ImageDraw.Draw(image)
        c0, c1 = ImageColor.getrgb(start), ImageColor.getrgb(end)
        for x in range(size[0]):
            t = x / max(1, size[0] - 1)
            draw.line([(x, 0), (x, size[1])], fill=tuple(round(a + (b - a) * t) for a, b in zip(c0, c1)))
    return image


def _pill(width, height, colors, backdrop, border=None, ring=None):
    """A pill (fully rounded rectangle) with a gradient fill, a 1px border or a keyboard focus ring."""
    key = ("pill", width, height, colors, backdrop, border, ring)
    if key not in _images:
        big = (width * SCALE, height * SCALE)
        canvas = Image.new("RGB", big, backdrop)

        def shape(inset):
            mask = Image.new("L", big, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (inset, inset, big[0] - 1 - inset, big[1] - 1 - inset),
                radius=max(1, (big[1] - 2 * inset) // 2), fill=255)
            return mask

        if ring:  # ring, a small gap, then the button
            canvas.paste(ring, (0, 0), shape(0))
            canvas.paste(backdrop, (0, 0), shape(2 * SCALE))
            canvas.paste(_gradient(big, *colors), (0, 0), shape(4 * SCALE))
        else:
            if border:
                canvas.paste(border, (0, 0), shape(0))
            canvas.paste(_gradient(big, *colors), (0, 0), shape(SCALE if border else 0))
        _images[key] = canvas.resize((width, height), Image.LANCZOS)
    return _images[key]


def _outline(width, height, radius, ring, fill, backdrop, thickness):
    """A rounded box with a coloured outline (used as the focus ring of text fields)."""
    key = ("outline", width, height, radius, ring, fill, backdrop, thickness)
    if key not in _images:
        big = (width * SCALE, height * SCALE)
        image = Image.new("RGB", big, backdrop)
        draw = ImageDraw.Draw(image)
        r, t = radius * SCALE, thickness * SCALE
        draw.rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), radius=r, fill=ring)
        draw.rounded_rectangle((t, t, big[0] - 1 - t, big[1] - 1 - t), radius=max(1, r - t), fill=fill)
        _images[key] = image.resize((width, height), Image.LANCZOS)
    return _images[key]


def make_icon(size=256):
    """The program logo: a parcel (box with tape) on the purple tile, marked with a red 'failed' badge.

    Used for the window icon, the .exe icon and the logo in the top bar. Drawn at 4x size and
    shrunk, so the edges are smooth.
    """
    s = size * 4
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 4, fill=255)
    icon.paste(_gradient((s, s), *GRADIENT), (0, 0), mask)
    draw = ImageDraw.Draw(icon)

    # the parcel: an isometric box (lid, left side, right side), a little up and to the left
    cx, cy, edge = 0.455 * s, 0.445 * s, 0.31 * s
    dx, dy = edge * 0.866, edge * 0.5
    top, upper_left, upper_right = (cx, cy - edge), (cx - dx, cy - dy), (cx + dx, cy - dy)
    middle, lower_left, lower_right, bottom = (cx, cy), (cx - dx, cy + dy), (cx + dx, cy + dy), (cx, cy + edge)
    draw.polygon([top, upper_right, middle, upper_left], fill="#ffffff")
    draw.polygon([upper_left, middle, bottom, lower_left], fill="#e6deff")
    draw.polygon([middle, upper_right, lower_right, bottom], fill="#c3b3f7")

    def along(a, b, t):
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

    lo, hi = 0.39, 0.61  # the packing tape: across the lid, then down the right side
    draw.polygon([along(top, upper_left, lo), along(top, upper_left, hi),
                  along(upper_right, middle, hi), along(upper_right, middle, lo)], fill="#8b6ef0")
    a, b = along(upper_right, middle, lo), along(upper_right, middle, hi)
    draw.polygon([a, b, (b[0], b[1] + 0.5 * edge), (a[0], a[1] + 0.5 * edge)], fill="#6d4fd8")

    # the red 'failed' badge on the corner, with a white rim to lift it off the box
    bx, by, radius, rim = 0.73 * s, 0.73 * s, 0.155 * s, 0.032 * s
    draw.ellipse((bx - radius - rim, by - radius - rim, bx + radius + rim, by + radius + rim), fill="#ffffff")
    draw.ellipse((bx - radius, by - radius, bx + radius, by + radius), fill="#e5484d")
    reach, thick = 0.068 * s, 0.043 * s
    for (x1, y1), (x2, y2) in (((bx - reach, by - reach), (bx + reach, by + reach)),
                               ((bx - reach, by + reach), (bx + reach, by - reach))):
        draw.line((x1, y1, x2, y2), fill="#ffffff", width=round(thick))
        for x, y in ((x1, y1), (x2, y2)):  # rounded ends
            draw.ellipse((x - thick / 2, y - thick / 2, x + thick / 2, y + thick / 2), fill="#ffffff")
    return icon.resize((size, size), Image.LANCZOS)


# ----------------------------------------------------------------- widgets --
class RoundedFrame(tk.Frame):
    """A card with rounded corners. Put child widgets in `.body`.

    A canvas behind the body draws the rounded shape; the card sizes itself
    around its content like any frame (or to a fixed width/height).
    `backdrop` must be the colour of whatever the card sits on, so the
    corners blend in. set_ring() draws a keyboard-focus outline around it.
    """

    def __init__(self, parent, radius=18, fill=CARD, backdrop=PAGE, width=None, height=None):
        super().__init__(parent, bg=backdrop)
        self.radius, self.fill, self.backdrop = px(radius), fill, backdrop
        self.ring, self._size = None, (1, 1)
        self.shape = tk.Canvas(self, bg=backdrop, highlightthickness=0, bd=0)
        self.shape.place(x=0, y=0, relwidth=1, relheight=1)
        pad = max(4, self.radius // 3)  # keeps content clear of the rounded corners
        self.body = tk.Frame(self, bg=fill)
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        if width or height:
            self.configure(width=px(width) or 1, height=px(height) or 1)
            self.pack_propagate(False)
        self._photos = []
        self.shape.bind("<Configure>", lambda e: self._draw(e.width, e.height))

    def set_ring(self, colour):
        """Show (colour) or hide (None) the focus outline."""
        self.ring = colour
        self._draw(*self._size)

    def _draw(self, w, h):
        self._size = (w, h)
        canvas = self.shape
        canvas.delete("all")
        r = max(2, min(self.radius, w // 2, h // 2))
        if self.ring:
            self._photos = [ImageTk.PhotoImage(_outline(w, h, r, self.ring, self.fill, self.backdrop, px(2)))]
            canvas.create_image(0, 0, anchor="nw", image=self._photos[0])
            return
        base = _corner(r, self.fill, self.backdrop)
        corners = [base, base.transpose(Image.FLIP_LEFT_RIGHT),
                   base.transpose(Image.FLIP_TOP_BOTTOM), base.transpose(Image.ROTATE_180)]
        self._photos = [ImageTk.PhotoImage(image) for image in corners]
        canvas.create_rectangle(r, 0, w - r + 1, h + 1, fill=self.fill, outline=self.fill)
        canvas.create_rectangle(0, r, w + 1, h - r + 1, fill=self.fill, outline=self.fill)
        for photo, (x, y) in zip(self._photos, [(0, 0), (w - r, 0), (0, h - r), (w - r, h - r)]):
            canvas.create_image(x, y, anchor="nw", image=photo)


class ResponsiveGrid(tk.Frame):
    """Places its children in as many columns as the width allows and wraps onto
    more rows when the window gets narrower. Children must be created with this
    frame as their parent and handed over with add().

    stretch=True gives equal-width columns that fill the row (used for tiles).
    """

    def __init__(self, parent, bg=PAGE, gap=12, stretch=False):
        super().__init__(parent, bg=bg)
        self.gap, self.stretch = px(gap), stretch
        self.items, self.columns = [], 0
        self.bind("<Configure>", lambda e: self.arrange())

    def add(self, widget):
        self.items.append(widget)
        self.columns = 0  # force a re-layout
        self.after_idle(self.arrange)

    def _needed_width(self, columns):
        widths = [0] * columns
        for index, item in enumerate(self.items):
            widths[index % columns] = max(widths[index % columns], item.winfo_reqwidth())
        return sum(widths) + self.gap * (columns - 1)

    def arrange(self):
        width, count = self.winfo_width(), len(self.items)
        if width <= 1 or not count:
            return
        # Try one row first, then 2 rows, 3 rows... and keep the first that fits.
        options = sorted({math.ceil(count / rows) for rows in range(1, count + 1)}, reverse=True)
        columns = next((c for c in options if self._needed_width(c) <= width), 1)
        if columns == self.columns:
            return
        self.columns = columns
        rows = math.ceil(count / columns)
        for column in range(count):
            self.columnconfigure(column, weight=0, uniform="")
        for index, item in enumerate(self.items):
            row, column = divmod(index, columns)
            item.grid(row=row, column=column, sticky="nsew" if self.stretch else "nw",
                      padx=(0, self.gap if column < columns - 1 else 0),
                      pady=(0, self.gap if row < rows - 1 else 0))
        if self.stretch:
            for column in range(columns):
                self.columnconfigure(column, weight=1, uniform="responsive")


class PillButton(tk.Canvas):
    """A pill-shaped button. style: 'primary' (purple gradient), 'secondary', or 'danger'.

    It can be reached with Tab and used with Space or Enter; the focus ring shows
    where you are. Hovering fades the colour, pressing darkens it.
    """

    LEVELS = 6  # the hover fade is drawn in this many shades (the images are cached)

    def __init__(self, parent, text, command, style="primary", backdrop=PAGE,
                 height=38, padx=22, font=FONT_BOLD):
        self.text, self.command, self.style = text, command, style
        self.backdrop, self.enabled = backdrop, True
        self.mix, self.pressed, self.focused = 0.0, False, False  # mix: 0 = rest, 1 = hovered
        self._level, self._tween = 0, None
        self.font = tkfont.Font(font=font)
        self.size = (self.font.measure(text) + px(2 * padx), px(height))
        super().__init__(parent, width=self.size[0], height=self.size[1], bg=backdrop,
                         highlightthickness=0, bd=0, takefocus=1)
        self._photo = None
        self._render()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.bind("<FocusOut>", lambda e: self._set_focus(False))
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            self.bind(key, self._key)

    def _look(self):
        """(fill colours, border, text colour) for the current state."""
        if not self.enabled:
            return (SOFT_2, SOFT_2), None, DISABLED_INK
        t = self._level / self.LEVELS
        if self.style == "primary":
            if self.pressed:
                return GRADIENT_PRESS, None, "#ffffff"
            return tuple(blend(a, b, t) for a, b in zip(GRADIENT, GRADIENT_HOVER)), None, "#ffffff"
        fill = blend(CARD, SOFT_2 if self.pressed else SOFT, 1.0 if self.pressed else t)
        if self.style == "danger":
            return (fill, fill), "#f0c6c6", DANGER
        return (fill, fill), "#d9d3f7", ACCENT

    def _render(self):
        colors, border, text_color = self._look()
        ring = FOCUS if (self.focused and self.enabled) else None
        self._photo = ImageTk.PhotoImage(_pill(*self.size, colors, self.backdrop, border, ring))
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._photo)
        self.create_text(self.size[0] // 2, self.size[1] // 2, text=self.text,
                         font=self.font, fill=text_color)
        self.configure(cursor="hand2" if self.enabled else "arrow")

    def _set_hover(self, value):
        """Fade towards the hovered (or resting) colour instead of snapping."""
        if not self.enabled:
            return
        start, end = self.mix, 1.0 if value else 0.0
        if self._tween:
            self._tween.cancel()
        self._tween = run(self, 130, lambda p: self._set_mix(start + (end - start) * p))

    def _set_mix(self, mix):
        self.mix = mix
        level = round(mix * self.LEVELS)
        if level != self._level:
            self._level = level
            self._render()

    def _set_focus(self, value):
        self.focused = value
        self._render()

    def _press(self, event):
        if self.enabled:
            self.pressed = True
            self._render()

    def _click(self, event):
        was_pressed, self.pressed = self.pressed, False
        if self.enabled:
            self._render()
        inside = 0 <= event.x <= self.size[0] and 0 <= event.y <= self.size[1]
        if self.enabled and was_pressed and inside:
            self.command()

    def _key(self, event):
        """Space / Enter: a short 'pressed' flash, then the action."""
        if not self.enabled:
            return "break"
        self.pressed = True
        self._render()
        run(self, 90, lambda p: None, done=self._release)  # (a Tween, so closing the window cancels it)
        self.command()
        return "break"

    def _release(self):
        try:
            self.pressed = False
            self._render()
        except tk.TclError:  # the button was closed by its own action
            pass

    def invoke(self):
        if self.enabled:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if self._tween:
            self._tween.cancel()
        self.mix, self._level, self.pressed = 0.0, 0, False
        self.configure(takefocus=1 if enabled else 0)  # a disabled button is skipped by Tab
        self._render()

    def set_style(self, style):
        self.style = style
        self._render()


class TabItem(tk.Frame):
    """One tab in the top bar: icon + label with an underline, highlighted when active.

    Reachable with Tab, activated with Space / Enter; the focus ring is the
    frame's own highlight border.
    """

    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=CARD, cursor="hand2", takefocus=1, highlightthickness=2,
                         highlightbackground=CARD, highlightcolor=FOCUS)
        self.text, self.command = text, command
        self.bar = tk.Frame(self, bg=CARD, height=px(3))
        self.bar.pack(side="bottom", fill="x")
        self.icon = tk.Label(self, text=icon, font=("Segoe UI Symbol", 13), bg=CARD, fg=MUTED)
        self.icon.pack(side="left", padx=(px(14), px(4)), pady=px(10))
        self.label = tk.Label(self, text=text, font=FONT_BOLD, bg=CARD, fg=INK_2)
        self.label.pack(side="left", padx=(0, px(14)))
        self.active = False
        self.level = {"hover": 0.0, "active": 0.0}  # 0..1, faded by tweens
        self._tweens = {}
        parts = (self, self.icon, self.label, self.bar)
        for widget in parts:
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e: self._fade("hover", 1.0))
            widget.bind("<Leave>", lambda e: self._left())
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            self.bind(key, lambda e: (command(), "break")[1])

    def _left(self):
        """Fade out only when the pointer really left the tab, not just moved onto its icon or label."""
        x, y = self.winfo_pointerxy()
        if self.winfo_containing(x, y) not in (self, self.icon, self.label, self.bar):
            self._fade("hover", 0.0)

    def _fade(self, key, target):
        start = self.level[key]
        if key in self._tweens:
            self._tweens[key].cancel()

        def step(p):
            self.level[key] = start + (target - start) * p
            self._paint()

        self._tweens[key] = run(self, 140, step)

    def _paint(self):
        active, hover = self.level["active"], self.level["hover"]
        background = blend(CARD, SOFT, max(active, hover))
        self.configure(bg=background, highlightbackground=background)
        self.icon.configure(bg=background, fg=blend(MUTED, ACCENT, active))
        self.label.configure(bg=background, fg=blend(INK_2, ACCENT, active))
        self.bar.configure(bg=blend(background, ACCENT, active))

    def set_active(self, active):
        self.active = active
        self._fade("active", 1.0 if active else 0.0)


class Tooltip:
    """A small dark label that appears under a widget after the pointer rests on it.

    `text` is a string, or a function returning a string (or "" / None for no tip),
    so a tip can depend on the widget's current state.
    """

    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self.window, self._job = None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def current_text(self):
        return self.text() if callable(self.text) else self.text

    def _schedule(self, event=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self.show)

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def show(self):
        self._cancel()
        text = self.current_text()
        if not text or self.window is not None:
            return
        try:
            window = tk.Toplevel(self.widget)
            window.wm_overrideredirect(True)
            window.attributes("-topmost", True)
            tk.Label(window, text=text, bg=INK, fg="#ffffff", font=FONT_SMALL,
                     padx=px(10), pady=px(5)).pack()
            window.update_idletasks()
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2 - window.winfo_reqwidth() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(6)
            x = max(4, min(x, self.widget.winfo_screenwidth() - window.winfo_reqwidth() - 4))
            window.wm_geometry(f"+{x}+{y}")
            self.window = window
        except tk.TclError:
            self.window = None

    def hide(self, event=None):
        self._cancel()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class ToastBar(tk.Frame):
    """A strip at the bottom where short messages slide in, wait, then slide out."""

    HEIGHT = 32
    KINDS = {  # (fill, text, dot)
        "info": (SOFT_2, ACCENT_DARK, ACCENT),
        "success": ("#e2f5e2", "#0a5c0a", STATUS_COLORS["Successful"]),
        "warning": ("#fff1cf", "#7a5200", STATUS_COLORS["Pending"]),
        "error": ("#fde4ea", "#a32626", STATUS_COLORS["Failed"]),
    }

    def __init__(self, parent, backdrop=PAGE):
        super().__init__(parent, bg=backdrop, height=px(self.HEIGHT))
        self.pack_propagate(False)
        self.backdrop, self.font = backdrop, tkfont.Font(font=("Segoe UI", 9, "bold"))
        self.chip, self._tween, self._hide_job = None, None, None

    def _shorten(self, text, room):
        """Keep the start and the end of a long message (for example a file path)."""
        while self.font.measure(text) > room and len(text) > 12:
            middle = len(text) // 2
            text = text[:middle - 2] + "..." + text[middle + 2:]
        return text

    def clear(self):
        if self._hide_job:
            self.after_cancel(self._hide_job)
            self._hide_job = None
        if self._tween:
            self._tween.cancel()
        if self.chip is not None:
            self.chip.destroy()
            self.chip = None

    def show(self, text, kind="info", seconds=4.0):
        self.clear()
        fill, ink, dot = self.KINDS.get(kind, self.KINDS["info"])
        chip = RoundedFrame(self, radius=14, fill=fill, backdrop=self.backdrop)
        row = tk.Frame(chip.body, bg=fill)
        row.pack(padx=12, pady=2)
        tk.Label(row, text="●", fg=dot, bg=fill, font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        # (before the window has been laid out the strip has no width yet: allow a generous one)
        room = max(200, self.winfo_width() - 90) if self.winfo_width() > 1 else 800
        tk.Label(row, text=self._shorten(text, room), fg=ink, bg=fill,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        chip.place(x=-3000, rely=0.5, anchor="w")
        self.update_idletasks()
        width = chip.winfo_reqwidth()
        self.chip = chip
        hidden = -(width + 16)  # fully off the left edge
        # the waiting time starts once the message has arrived, not while it is still sliding in
        self._tween = run(self, 260, lambda p: chip.place_configure(x=hidden * (1 - p)),
                          done=lambda: self._wait_then_leave(chip, hidden, seconds))

    def _wait_then_leave(self, chip, hidden, seconds):
        if chip is self.chip:
            self._hide_job = self.after(int(seconds * 1000), lambda: self._slide_out(chip, hidden))

    def _slide_out(self, chip, hidden):
        self._hide_job = None
        if chip is not self.chip:
            return

        def gone():
            chip.destroy()
            if chip is self.chip:
                self.chip = None

        self._tween = run(self, 220, lambda p: chip.place_configure(x=hidden * p),
                          done=gone, ease=ease_in)


# ----------------------------------------------------------------- ttk theme --
def apply_style(root):
    root.configure(bg=PAGE)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=FONT, background=CARD, foreground=INK, bordercolor=LINE, focuscolor=CARD)

    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # no frame border
    row_height = max(px(36), int(tkfont.Font(font=FONT).metrics("linespace") * 2.1))
    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                    rowheight=row_height, borderwidth=0)
    style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", INK)])
    style.configure("Treeview.Heading", background=SOFT, foreground=INK_2, font=FONT_BOLD,
                    relief="flat", borderwidth=0, bordercolor=SOFT, lightcolor=SOFT,
                    darkcolor=SOFT, padding=(10, 10))
    style.map("Treeview.Heading", background=[("active", SOFT_2)])

    style.configure("Vertical.TScrollbar", background="#d9d4f5", troughcolor=CARD, bordercolor=CARD,
                    lightcolor=CARD, darkcolor=CARD, arrowcolor=ACCENT, arrowsize=px(13), gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", "#c8c0f3")])

    for name in ("Soft.TCombobox", "Soft.TEntry", "Soft.TSpinbox"):
        style.configure(name, fieldbackground=SOFT, background=SOFT, foreground=INK,
                        bordercolor=SOFT, lightcolor=SOFT, darkcolor=SOFT, padding=6,
                        arrowcolor=ACCENT, insertcolor=INK)
        style.map(name, fieldbackground=[("readonly", SOFT), ("disabled", SOFT)],
                  foreground=[("disabled", DISABLED_INK)], bordercolor=[("focus", SOFT)],  # the shell draws the ring
                  selectbackground=[("readonly", SOFT)], selectforeground=[("readonly", INK)])
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", INK)
    root.option_add("*TCombobox*Listbox.font", FONT)

    style.configure("Card.TCheckbutton", background=CARD, foreground=INK, focuscolor=CARD)
    style.map("Card.TCheckbutton", indicatorcolor=[("selected", ACCENT)])
    style.configure("Card.TLabel", background=CARD, foreground=INK_2)
