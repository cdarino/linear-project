"""
diet_gui.py
===========
The Diet Optimizer window. Every answer comes from the Python solver in
diet_optimizer.py. This file only draws the screens.

Run:   python diet_gui.py          (or: python diet_optimizer.py --gui)

Layout:
    Left panel     who the menu is for, eating style and variety
    Top bar        page tabs, Reset all and Copy menu
    Summary tiles  daily cost, cost per meal, foods used and targets met (on every page)

Pages (Ctrl+1 to Ctrl+8 switch between them):
    Menu           the cheapest day of eating, with amounts and costs
    Nutrition      the totals N @ x checked against every limit
    Foods          turn foods on or off, edit prices and serving limits
    Limits         edit the minimum and maximum for each nutrient
    Why            which requirements push the cost up, and which foods just missed
    Variety        what a more varied menu costs, for every group (report figure 5)
    Solver steps   every simplex pivot and the guaranteed minimum after each one (report figure 4)
    Guide          how to use the program and how the math works, with the 2-food
                   example drawn in two dimensions (report figure 6)

Needs only Tkinter and Matplotlib. Pillow, which Matplotlib already
installs, draws the smooth rounded corners. All the math is done in
diet_optimizer.py with plain Python lists.
"""

import math
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PIL import Image, ImageColor, ImageDraw, ImageTk  # noqa: E402

import diet_optimizer as d  # noqa: E402

# ---------------------------------------------------------------------------
# LOOK: colors, data labels and guide text
# ---------------------------------------------------------------------------
BG, SURFACE, SUNKEN, TRACK, HOVER = "#F4F5F7", "#FFFFFF", "#E9EBEF", "#F0F2F5", "#F3F5F7"
BORDER, BORDER_STRONG = "#E4E7EC", "#D0D5DD"
TEXT, TEXT_2, MUTED, SUBTLE = "#101828", "#344054", "#667085", "#98A2B3"
ACCENT, ACCENT_HOVER, ACCENT_SOFT, ACCENT_TEXT = "#0F6E56", "#0B5947", "#E7F5EF", "#05463A"
GOOD, GOOD_ZONE = "#1D9E75", "#CDEEDF"
PURPLE, CORAL, DANGER = "#7F77DD", "#D85A30", "#D92D20"
TONES = {                                    # badge colors: (background, text)
    "good": ("#E3F6EC", "#067647"),
    "warn": ("#FEF0DC", "#B54708"),
    "info": ("#E8F1FD", "#175CD3"),
    "danger": ("#FEECEB", "#B42318"),
    "neutral": ("#F0F2F5", "#475467"),
}
PALETTE = ["#1D9E75", "#7F77DD", "#D85A30", "#E3A008", "#0EA5E9",
           "#D4537E", "#5DCAA5", "#A16207", "#64748B", "#84CC16"]

DIETS = {"Anything": "anything", "No meat or fish": "no-meat-fish", "Plant-based": "plant-based"}
DIET_NOTES = {"Anything": "Every food", "No meat or fish": "Keeps eggs and dairy",
              "Plant-based": "Plants only"}
KIND_NAMES = {d.PLANT: "Plant", d.MEAT_FISH: "Meat or fish", d.EGG_DAIRY: "Egg or dairy"}
GROUPS = list(d.PRESETS)
DEFAULTS = {f[0]: (f[2], f[3]) for f in d.FOODS}           # food name -> (price, own max)
KIND_OF = {f[0]: f[4] for f in d.FOODS}
SERVING_OF = {f[0]: f[1] for f in d.FOODS}

# (tab name, page title, one-line description)
PAGES = [
    ("Menu", "Cheapest menu",
     "One day of eating for the settings on the left, most expensive food first."),
    ("Nutrition", "Nutrition check",
     "The day's totals N x, a linear combination of the food columns, against every limit."),
    ("Foods", "Foods and prices",
     "Turn foods on or off and set prices to match your market. The menu updates as you type."),
    ("Limits", "Nutrition limits",
     "The daily minimum and maximum for each nutrient. Leave a box empty for no limit."),
    ("Why", "What drives the cost",
     "Prices from the mirror problem: how the daily cost reacts when a limit or a price moves."),
    ("Variety", "What variety costs",
     "Allowing fewer servings of any one food makes the menu more varied, but usually more expensive. "
     "Use this page to choose a variety level."),
    ("Solver steps", "Solver steps",
     "The simplex method on the mirror problem. Each pivot is one Gauss-Jordan step on the tableau."),
    ("Guide", "Guide", "How to use the program and how the math works."),
]

# Guide blocks: ("h", heading), ("p", paragraph), ("ol", numbered list), ("dl", [(term, meaning)])
GUIDE = [
    ("h", "Quick start"),
    ("ol", ["Pick who the menu is for, an eating style and a variety level in the left panel.",
            "The Menu page shows the cheapest day of eating. The daily cost at the top updates "
            "as soon as you change anything.",
            "Open Nutrition to confirm that every target is met.",
            "Press Copy menu (top right) to copy the menu as text."]),
    ("h", "What each page does"),
    ("dl", [("Menu", "foods, amounts and costs. Click a food to edit its price."),
            ("Nutrition", "each total checked against its limits."),
            ("Foods", "turn foods on or off, search, and edit prices and serving limits."),
            ("Limits", "edit minimums and maximums. Leave a box empty for no limit."),
            ("Why", "which limits push the cost up, and how much cheaper an unused food "
                    "would need to be."),
            ("Variety", "what a more varied menu costs, for every group. Click a point or a row to "
                        "use that setting."),
            ("Solver steps", "every pivot the simplex method makes."),
            ("Guide", "this page. The picture on the right shows the method on a 2-food problem.")]),
    ("h", "How the math works"),
    ("ol", ["Foods are vectors. Each food's nutrition label is a column of the matrix N.",
            "A menu is a vector x of servings. The day's totals are the product N x, a linear "
            "combination of the food columns. The cost is the dot product c · x.",
            "Every limit is a linear inequality. Together they form a region of valid menus "
            "with flat sides, and the cheapest menu is at a corner.",
            "The simplex method moves from corner to corner. Each move (a pivot) is one "
            "Gauss-Jordan step: scale the pivot row, then clear its column with row operations.",
            "The solver works on the mirror problem built from the transpose of the requirement "
            "matrix. It puts a price on every requirement, and the same final table also holds "
            "the menu."]),
    ("p", "In symbols, with G x ≥ h holding every limit as one system:"),
    ("code", "Cheapest menu\n"
             "  minimize    c · x\n"
             "  subject to  lo ≤ N x ≤ hi,  0 ≤ x ≤ cap\n"
             "Mirror problem\n"
             "  maximize    h · y\n"
             "  subject to  Gᵀ y ≤ c,  y ≥ 0"),
    ("p", "At the answer both problems have the same value: c · x = h · y."),
    ("h", "Words you will see"),
    ("dl", [("Serving", "one standard portion, such as 1 cup or 1 piece."),
            ("Requirement price", "how much the daily cost changes if a limit moves by one unit."),
            ("Reduced cost", "how much cheaper an unused food would need to be to join the menu."),
            ("Pivot", "one move from a corner to a cheaper neighboring corner.")]),
    ("h", "Where the limits come from"),
    ("p", "Every group uses the Philippine Dietary Reference Intakes 2015 (FNRI-DOST). "
          "Adults are ages 19 to 29 and teens are 16 to 18."),
    ("dl", [("Calories", "at least the Recommended Energy Intake."),
            ("Protein, calcium, iron and vitamin C", "at least the Recommended Nutrient Intake."),
            ("Fat and carbohydrates", "the recommended percent of calories, turned into grams."),
            ("Sodium", "at least 500 mg and under 2,000 mg.")]),
    ("p", "The PDRI says the 28 mg of iron for women and teen girls usually needs iron-rich or "
          "fortified foods or a supplement. That is why iron drives the cost for those groups."),
    ("h", "Good to know"),
    ("p", "Amounts like 2.3 cups are fine for the model. Round to the nearest half serving "
          "in practice."),
    ("p", "Prices and nutrition values are rough estimates for coursework, not medical advice."),
    ("h", "Shortcuts"),
    ("dl", [("Ctrl+1 to Ctrl+8", "switch pages, in the order of the tabs."),
            ("Esc", "clear the food search.")]),
]


# ---------------------------------------------------------------------------
# SMALL HELPERS
# ---------------------------------------------------------------------------
class UI:
    """Shared look, filled in by DietApp: pixel scale, fonts and the shape painter."""
    k = 1.0
    font = {}
    paint = None


def px(v):
    """Pixels scaled for high-resolution screens."""
    return int(round(v * UI.k))


def number(text, default=None):
    """Read a non-negative number from a text box, or return the default."""
    try:
        value = float(text)
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


def fmt(v):
    """A number for display: 1,930 or 28 or 37.6."""
    if abs(v) >= 100:
        return f"{v:,.0f}"
    text = f"{v:,.1f}"
    return text[:-2] if text.endswith(".0") else text


def need_text(lo, hi, unit):
    if lo is not None and hi is not None:
        return f"{fmt(lo)} to {fmt(hi)} {unit}"
    if lo is not None:
        return f"at least {fmt(lo)} {unit}"
    if hi is not None:
        return f"at most {fmt(hi)} {unit}"
    return "no limit"


def money(v):
    """Pesos with enough decimals to stay readable for small unit prices."""
    return f"₱{v:.2f}" if v >= 1 else f"₱{v:.3f}" if v >= 0.01 else f"₱{v:.4f}"


def rgba(color, alpha=255):
    return ImageColor.getrgb(color)[:3] + (alpha,)


# ---------------------------------------------------------------------------
# DRAWING: smooth rounded shapes on Tk canvases
# ---------------------------------------------------------------------------
class Painter:
    """
    Tk draws curves without smoothing, so the curved parts are drawn by Pillow
    at 4x size, shrunk, and cached as see-through images. Straight edges are
    plain canvas rectangles and lines.
    """
    SS = 4

    def __init__(self, root):
        self.root, self.cache = root, {}

    def _corners(self, r, fill, line):
        key = ("corner", r, fill, line)
        if key not in self.cache:
            k, size = self.SS, 2 * r + 2
            img = Image.new("RGBA", (size * k, size * k), rgba(line, 0))
            ImageDraw.Draw(img).rounded_rectangle((0, 0, size * k - 1, size * k - 1), radius=r * k,
                                                   fill=rgba(fill), outline=rgba(line), width=k)
            img, e = img.reduce(k), r + 1
            boxes = ((0, 0, e, e), (e, 0, size, e), (0, e, e, size), (e, e, size, size))
            self.cache[key] = [ImageTk.PhotoImage(img.crop(b), master=self.root) for b in boxes]
        return self.cache[key]

    def rect(self, cv, x0, y0, x1, y1, r, fill, line=None, tags=()):
        """A rounded rectangle covering pixels x0..x1-1 and y0..y1-1."""
        line = line or fill
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        r = int(max(0, min(r, (x1 - x0 - 2) // 2, (y1 - y0 - 2) // 2)))
        if r < 2:
            cv.create_rectangle(x0, y0, x1 - 1, y1 - 1, fill=fill, outline=line, tags=tags)
            return
        e = r + 1
        cv.create_rectangle(x0 + e, y0, x1 - e, y1, fill=fill, outline="", tags=tags)
        cv.create_rectangle(x0, y0 + e, x1, y1 - e, fill=fill, outline="", tags=tags)
        if line != fill:
            cv.create_line(x0 + e, y0, x1 - e, y0, fill=line, tags=tags)
            cv.create_line(x0 + e, y1 - 1, x1 - e, y1 - 1, fill=line, tags=tags)
            cv.create_line(x0, y0 + e, x0, y1 - e, fill=line, tags=tags)
            cv.create_line(x1 - 1, y0 + e, x1 - 1, y1 - e, fill=line, tags=tags)
        tl, tr, bl, br = self._corners(r, fill, line)
        cv.create_image(x0, y0, image=tl, anchor="nw", tags=tags)
        cv.create_image(x1, y0, image=tr, anchor="ne", tags=tags)
        cv.create_image(x0, y1, image=bl, anchor="sw", tags=tags)
        cv.create_image(x1, y1, image=br, anchor="se", tags=tags)

    def circle(self, cv, cx, cy, r, fill, line=None, width=1.0, tags=()):
        key = ("circle", r, fill, line, width)
        if key not in self.cache:
            k, size = self.SS, 2 * r
            img = Image.new("RGBA", (size * k, size * k), rgba(line or fill, 0))
            ImageDraw.Draw(img).ellipse((0, 0, size * k - 1, size * k - 1), fill=rgba(fill),
                                        outline=rgba(line) if line else None,
                                        width=round(width * k) if line else 0)
            self.cache[key] = ImageTk.PhotoImage(img.reduce(k), master=self.root)
        cv.create_image(round(cx), round(cy), image=self.cache[key], tags=tags)

    def badge(self, cv, x, cy, text, tone, anchor="w"):
        """A rounded label drawn straight onto a canvas. Returns its width."""
        fill, fg = TONES[tone]
        font = UI.font["small_strong"]
        w, h = font.measure(text) + px(18), px(22)
        x0 = x if anchor == "w" else x - w
        y0 = round(cy - h / 2)
        self.rect(cv, x0, y0, x0 + w, y0 + h, h // 2, fill)
        cv.create_text(x0 + w / 2, cy, text=text, fill=fg, font=font)
        return w


# ---------------------------------------------------------------------------
# WIDGETS
# ---------------------------------------------------------------------------
class Shape(tk.Canvas):
    """A canvas widget that redraws itself whenever its size changes."""

    def __init__(self, parent, width, height):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.hover = self.focused = False
        self.bind("<Configure>", lambda e: self.paint())

    def dims(self):
        return self.winfo_width(), self.winfo_height()

    def paint(self):
        pass

    def clickable(self, action):
        """Hover, click and keyboard (Space or Enter) handling."""
        self.configure(cursor="hand2", takefocus=1)

        def flag(name, value):
            setattr(self, name, value)
            self.paint()

        self.bind("<Enter>", lambda e: flag("hover", True))
        self.bind("<Leave>", lambda e: flag("hover", False))
        self.bind("<FocusIn>", lambda e: flag("focused", True))
        self.bind("<FocusOut>", lambda e: flag("focused", False))
        self.bind("<Button-1>", lambda e: action())
        self.bind("<space>", lambda e: action())
        self.bind("<Return>", lambda e: action())


class Button(Shape):
    STYLES = {  # fill, fill under the pointer, border, text (None = background color)
        "primary": (ACCENT, ACCENT_HOVER, None, "#FFFFFF"),
        "secondary": (SURFACE, HOVER, BORDER_STRONG, TEXT_2),
        "ghost": (None, SUNKEN, None, TEXT_2),
    }

    def __init__(self, parent, text, command, kind="secondary", height=36, other_texts=()):
        self.text, self.kind = text, kind
        font = UI.font["strong"]
        width = max(font.measure(t) for t in (text, *other_texts)) + px(30)
        super().__init__(parent, width, px(height))
        self.clickable(command)

    def set_text(self, text):
        self.text = text
        self.paint()

    def paint(self):
        self.delete("all")
        w, h = self.dims()
        if w < 4:
            return
        fill, hover, line, fg = self.STYLES[self.kind]
        fill = (hover if self.hover else fill) or self["bg"]
        UI.paint.rect(self, 0, 0, w, h, px(9), fill, ACCENT if self.focused else (line or fill))
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=UI.font["strong"])


class Choice(Shape):
    """One option tied to a shared variable, like a radio button drawn as a chip or a card."""

    def __init__(self, parent, text, variable, value, command=None, note=None, radio=False):
        self.text, self.variable, self.value, self.command = text, variable, value, command
        self.note, self.radio = note, radio
        width = UI.font["strong"].measure(text) + px(30 + (28 if radio else 0))
        super().__init__(parent, width, px(56 if note else 36))
        self.clickable(self.choose)
        variable.trace_add("write", lambda *_: self.paint())

    def choose(self):
        self.variable.set(self.value)
        if self.command:
            self.command()

    def paint(self):
        self.delete("all")
        w, h = self.dims()
        if w < 4:
            return
        chosen = str(self.variable.get()) == str(self.value)
        fill = ACCENT_SOFT if chosen else HOVER if self.hover else SURFACE
        line = ACCENT if chosen or self.focused else BORDER_STRONG
        UI.paint.rect(self, 0, 0, w, h, px(10), fill, line)
        x = px(14)
        if self.radio:
            UI.paint.circle(self, x + px(8), h / 2, px(8), SURFACE, ACCENT if chosen else BORDER_STRONG,
                            width=1.6 if chosen else 1.2)
            if chosen:
                UI.paint.circle(self, x + px(8), h / 2, px(4), ACCENT)
            x += px(28)
        color = ACCENT_TEXT if chosen else TEXT_2
        if self.note:
            self.create_text(x, h / 2 - px(9), text=self.text, anchor="w", fill=color,
                             font=UI.font["strong"])
            self.create_text(x, h / 2 + px(10), text=self.note, anchor="w", fill=MUTED,
                             font=UI.font["small"])
        elif self.radio:
            self.create_text(x, h / 2, text=self.text, anchor="w", fill=color, font=UI.font["strong"])
        else:
            self.create_text(w / 2, h / 2, text=self.text, fill=color, font=UI.font["strong"])


class Segmented(Shape):
    """A row of options in one rounded track. The chosen option is raised."""

    def __init__(self, parent, options, variable, command=None, height=38, pad=14, stretch=False,
                 track=SUNKEN):
        self.options, self.variable, self.command = list(options), variable, command
        self.stretch, self.track, self.hot = stretch, track, None
        self.natural = [UI.font["strong"].measure(label) + 2 * pad for _, label in self.options]
        super().__init__(parent, sum(self.natural) + 2 * px(4), px(height))
        self.configure(cursor="hand2", takefocus=1)
        self.bind("<Motion>", lambda e: self._set_hot(self._at(e.x)))
        self.bind("<Leave>", lambda e: self._set_hot(None))
        self.bind("<Button-1>", lambda e: self._pick(self._at(e.x)))
        self.bind("<Left>", lambda e: self._step(-1))
        self.bind("<Right>", lambda e: self._step(1))
        self.bind("<FocusIn>", lambda e: (setattr(self, "focused", True), self.paint()))
        self.bind("<FocusOut>", lambda e: (setattr(self, "focused", False), self.paint()))
        variable.trace_add("write", lambda *_: self.paint())

    def _spans(self):
        inset, n = px(4), len(self.options)
        if self.stretch:
            step = (self.winfo_width() - 2 * inset) / n
            return [(inset + i * step, inset + (i + 1) * step) for i in range(n)]
        spans, x = [], inset
        for width in self.natural:
            spans.append((x, x + width))
            x += width
        return spans

    def _at(self, x):
        return next((i for i, (a, b) in enumerate(self._spans()) if a <= x < b), None)

    def _set_hot(self, i):
        if i != self.hot:
            self.hot = i
            self.paint()

    def _pick(self, i):
        if i is None:
            return
        self.variable.set(self.options[i][0])
        if self.command:
            self.command()

    def _step(self, direction):
        values = [str(v) for v, _ in self.options]
        current = str(self.variable.get())
        i = values.index(current) if current in values else 0
        self._pick(max(0, min(len(values) - 1, i + direction)))

    def paint(self):
        self.delete("all")
        w, h = self.dims()
        if w < 10:
            return
        UI.paint.rect(self, 0, 0, w, h, px(10), self.track, ACCENT if self.focused else self.track)
        current, inset = str(self.variable.get()), px(4)
        for i, ((a, b), (value, label)) in enumerate(zip(self._spans(), self.options)):
            chosen = str(value) == current
            if chosen:
                UI.paint.rect(self, a, inset, b, h - inset, px(7), SURFACE, BORDER)
            color = TEXT if chosen else TEXT_2 if i == self.hot else MUTED
            self.create_text((a + b) / 2, h / 2, text=label, fill=color,
                             font=UI.font["strong" if chosen else "body"])


class Toggle(Shape):
    """An on/off switch tied to a BooleanVar."""

    def __init__(self, parent, variable):
        self.variable = variable
        super().__init__(parent, px(38), px(22))
        self.clickable(lambda: variable.set(not variable.get()))
        variable.trace_add("write", lambda *_: self.paint())

    def paint(self):
        self.delete("all")
        w, h = self.dims()
        if w < 10:
            return
        on = self.variable.get()
        track = (ACCENT_HOVER if self.hover else ACCENT) if on else ("#B9C0CB" if self.hover else
                                                                      BORDER_STRONG)
        UI.paint.rect(self, 0, 0, w, h, h // 2, track, TEXT if self.focused else track)
        UI.paint.circle(self, w - h / 2 if on else h / 2, h / 2, h // 2 - px(3), SURFACE)


class Badge(Shape):
    """A small rounded label, such as "In menu" or "Edited"."""

    def __init__(self, parent, text="", tone="neutral"):
        super().__init__(parent, 1, px(22))
        self.update_badge(text, tone)

    def update_badge(self, text, tone="neutral"):
        self.text, self.tone = text, tone
        self.configure(width=UI.font["small_strong"].measure(text) + px(18) if text else 1)
        self.paint()

    def paint(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        if self.text:
            fill, fg = TONES[self.tone]
            UI.paint.rect(self, 0, 0, w, h, h // 2, fill)
            self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=UI.font["small_strong"])


class Card(tk.Frame):
    """A rounded white panel. Put its content in .body."""

    def __init__(self, parent, pad=18, fill=SURFACE, line=BORDER, radius=14):
        bg = parent["bg"]
        super().__init__(parent, bg=bg)
        self.fill, self.line, self.radius = fill, line, radius
        self._cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=fill)
        self.body.pack(fill="both", expand=True, padx=px(pad), pady=px(pad))
        self.bind("<Configure>", self._paint)

    def _paint(self, e):
        self._cv.delete("all")
        UI.paint.rect(self._cv, 0, 0, e.width, e.height, px(self.radius), self.fill, self.line)

    def header(self, title, subtitle=None):
        """Title and subtitle at the top of the card. Returns a frame for controls on the right."""
        head = tk.Frame(self.body, bg=self.fill)
        head.pack(fill="x", pady=(0, px(12)))
        right = tk.Frame(head, bg=self.fill)
        right.pack(side="right", anchor="n")
        words = tk.Frame(head, bg=self.fill)
        words.pack(side="left", fill="x", expand=True)
        tk.Label(words, text=title, font=UI.font["h3"], fg=TEXT, bg=self.fill, anchor="w").pack(fill="x")
        if subtitle:
            wrapping_label(words, subtitle, UI.font["small"], MUTED, self.fill).pack(fill="x")
        return right


def wrapping_label(parent, text, font, fg, bg):
    """A label that re-wraps its text to whatever width it is given."""
    label = tk.Label(parent, text=text, font=font, fg=fg, bg=bg, anchor="w", justify="left",
                     wraplength=px(360))
    label.bind("<Configure>", lambda e: label.configure(wraplength=max(e.width - 4, 80)))
    return label


class Scroll(tk.Frame):
    """A vertically scrolling area. Put widgets in .inner. The scrollbar shows only when needed."""

    def __init__(self, parent):
        bg = parent["bg"]
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=1, height=1,
                            yscrollincrement=px(16))
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview,
                                 style="Thin.Vertical.TScrollbar")
        self.inner = tk.Frame(self.cv, bg=bg)
        window = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.cv.configure(scrollregion=(0, 0, e.width, e.height)))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(window, width=e.width))
        self.cv.configure(yscrollcommand=self._bar)
        self.cv.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns", padx=(px(6), 0))
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, minsize=px(14))
        self.scroll_canvas = self.cv               # found by the mouse-wheel handler

    def _bar(self, first, last):
        self.bar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.bar.grid_remove()
        else:
            self.bar.grid()


class RowList(tk.Canvas):
    """A list drawn on one canvas. Rows can light up under the pointer and be clicked."""

    def __init__(self, parent, draw_row, row_height, on_click=None, draw_footer=None, fit=False,
                 min_row=None, empty="Nothing to show"):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0, width=1, height=1,
                         yscrollincrement=px(16))
        self.draw_row, self.row_h, self.on_click, self.draw_footer = draw_row, row_height, on_click, draw_footer
        self.fit, self.min_row, self.empty = fit, min_row or row_height, empty
        self.rows, self.footer, self.hover = [], None, None
        self.scroll_canvas = self
        self.bind("<Configure>", lambda e: self.redraw())
        if on_click:
            self.bind("<Motion>", lambda e: self._set_hover(self._index(e)))
            self.bind("<Leave>", lambda e: self._set_hover(None))
            self.bind("<Button-1>", self._click)

    def show(self, rows, footer=None, empty=None):
        self.rows, self.footer, self.hover = rows, footer, None
        self.empty = empty or self.empty
        self.yview_moveto(0)
        self.redraw()

    def _rh(self):
        n = len(self.rows) + (self.footer is not None)
        if self.fit and n:
            return max(self.min_row, min(self.row_h, self.winfo_height() // n))
        return self.row_h

    def _index(self, e):
        i = int(self.canvasy(e.y) // self._rh())
        return i if 0 <= i < len(self.rows) else None

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.configure(cursor="hand2" if i is not None else "")
            self.redraw()

    def _click(self, e):
        i = self._index(e)
        if i is not None:
            self.on_click(self.rows[i])

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        if not self.rows:
            self.create_text(w / 2, h / 2, text=self.empty, fill=SUBTLE, font=UI.font["body"],
                             width=max(w - px(40), 60), justify="center")
            self.configure(scrollregion=(0, 0, w, h))
            return
        rh, pad, y = self._rh(), px(10), 0
        for i, row in enumerate(self.rows):
            if i == self.hover:
                UI.paint.rect(self, 0, y + px(2), w, y + rh - px(2), px(8), HOVER)
            elif i and i - 1 != self.hover:
                self.create_line(pad, y, w - pad, y, fill=BORDER)
            self.draw_row(self, row, pad, y, w - pad, rh)
            y += rh
        if self.draw_footer and self.footer is not None:
            self.create_line(0, y, w, y, fill=BORDER_STRONG)
            self.draw_footer(self, self.footer, pad, y, w - pad, rh)
            y += rh
        self.configure(scrollregion=(0, 0, w, max(y, h)))


class SearchBox(Shape):
    """A rounded search field with a placeholder and a clear button."""

    def __init__(self, parent, variable, placeholder="Search foods", width=240):
        self.variable = variable
        super().__init__(parent, px(width), px(36))
        self.entry = tk.Entry(self, textvariable=variable, relief="flat", bd=0, bg=SURFACE, fg=TEXT,
                              insertbackground=TEXT, font=UI.font["body"], highlightthickness=0)
        self.hint = tk.Label(self.entry, text=placeholder, font=UI.font["body"], fg=SUBTLE, bg=SURFACE,
                             cursor="xterm", bd=0, padx=0)
        self.hint.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: (setattr(self, "focused", True), self.paint()))
        self.entry.bind("<FocusOut>", lambda e: (setattr(self, "focused", False), self.paint()))
        self.entry.bind("<Escape>", lambda e: variable.set(""))
        self.bind("<Button-1>", self._click)
        variable.trace_add("write", lambda *_: self.paint())

    def _click(self, e):
        if self.variable.get() and e.x > self.winfo_width() - px(30):
            self.variable.set("")
        self.entry.focus_set()

    def paint(self):
        self.delete("all")
        w, h = self.dims()
        if w < 10:
            return
        UI.paint.rect(self, 0, 0, w, h, px(9), SURFACE, ACCENT if self.focused else BORDER_STRONG)
        cx, cy, r = px(17), h / 2 - px(1), px(5)                 # magnifying glass
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=MUTED, width=px(2))
        self.create_line(cx + r - px(1), cy + r - px(1), cx + r + px(4), cy + r + px(4), fill=MUTED,
                         width=px(2), capstyle="round")
        self.create_window(px(32), h / 2, window=self.entry, anchor="w", width=w - px(64))
        if self.variable.get():
            self.create_text(w - px(16), h / 2, text="×", fill=MUTED, font=UI.font["h3"])
        if self.variable.get() or self.focused:
            self.hint.place_forget()
        else:
            self.hint.place(x=0, rely=0.5, anchor="w")


# ---------------------------------------------------------------------------
# THE WINDOW
# ---------------------------------------------------------------------------
class DietApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Diet Optimizer")
        UI.k = max(1.0, self.winfo_fpixels("1i") / 96)
        UI.paint = Painter(self)
        self._fonts()
        self._style()
        self._icon()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(px(1300), sw - px(40)), min(px(860), sh - px(90))
        self.geometry(f"{width}x{height}")
        self.minsize(min(px(1100), width), min(px(640), height))
        self.configure(bg=BG)

        self.group = tk.StringVar(value="Adult woman")
        self.diet = tk.StringVar(value="Anything")
        self.variety = tk.IntVar(value=4)
        self.on = {name: tk.BooleanVar(value=True) for name in DEFAULTS}
        self.price = {name: tk.StringVar(value=f"{p:g}") for name, (p, _) in DEFAULTS.items()}
        self.own_max = {name: tk.StringVar(value=f"{m:g}") for name, (_, m) in DEFAULTS.items()}
        self.limit_vars = [(tk.StringVar(), tk.StringVar()) for _ in d.NUTRIENTS]
        self.page = tk.StringVar(value="Menu")
        self.search = tk.StringVar()
        self.food_filter = tk.StringVar(value="all")
        self._filling, self._pending, self.menu_text = False, None, ""
        self.last_group = "Adult woman"           # remembered when limits are customized
        self.prev_cost = None                     # for the "+₱2.10 after your last change" note
        self.in_menu = {}                         # food name -> servings in the current menu
        self.page_names = [name for name, *_ in PAGES]
        self.extras, self.compact = [], False      # helper text hidden when the window is short

        self._sidebar()
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=px(28), pady=(px(20), px(22)))
        self._topbar(main)
        self._tiles(main)
        self._banner(main)
        self.stack = tk.Frame(main, bg=BG)
        self.stack.pack(fill="both", expand=True, pady=(px(20), 0))
        self.stack.rowconfigure(0, weight=1)
        self.stack.columnconfigure(0, weight=1)
        self.pages = {}
        self._menu_page()
        self._nutrition_page()
        self._foods_page()
        self._limits_page()
        self._why_page()
        self._variety_page()
        self._steps_page()
        self._guide_page()
        self.show_page("Menu")

        for i, name in enumerate(self.page_names, start=1):
            self.bind(f"<Control-Key-{i}>", lambda e, n=name: self.show_page(n))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel)
        self.bind("<Configure>", self._resized)

        self.fill_limits("Adult woman")
        for var in [*self.price.values(), *self.own_max.values()]:
            var.trace_add("write", lambda *_: self.schedule())
        for var in self.on.values():
            var.trace_add("write", lambda *_: self.schedule(60))
        for lo, hi in self.limit_vars:
            for var in (lo, hi):
                var.trace_add("write", self.limit_edited)
        self.group.trace_add("write", lambda *_: self._group_note())
        self.variety.trace_add("write", lambda *_: self._variety_note())
        self.search.trace_add("write", lambda *_: self.filter_foods())
        self.food_filter.trace_add("write", lambda *_: self.filter_foods())
        self._group_note()
        self._variety_note()
        self.solve()

    # ------------------------------------------------------------------ look
    def _fonts(self):
        families = set(tkfont.families(self))
        base = "Segoe UI" if "Segoe UI" in families else tkfont.nametofont("TkDefaultFont").actual("family")
        semi = "Segoe UI Semibold" if "Segoe UI Semibold" in families else base
        weight = "normal" if semi != base else "bold"
        mono = next((m for m in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono") if m in families),
                    "TkFixedFont")

        def font(size, strong=False, family=None):
            if family:
                return tkfont.Font(self, family=family, size=size)
            return tkfont.Font(self, family=semi if strong else base, size=size,
                               weight=weight if strong else "normal")

        UI.font = dict(body=font(10), small=font(9), tiny=font(8), strong=font(10, True),
                       small_strong=font(9, True), label=font(8, True), h1=font(18, True),
                       h2=font(13, True), h3=font(11, True), kpi=font(21, True), brand=font(13, True),
                       mono=font(10, family=mono))
        for name in ("TkDefaultFont", "TkTextFont"):
            tkfont.nametofont(name).configure(family=base, size=10)

        matplotlib.rcParams.update(d.figure_style())       # charts match the saved report figures

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=SURFACE, foreground=TEXT)
        s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER_STRONG,
                    lightcolor=SURFACE, darkcolor=SURFACE, insertcolor=TEXT, padding=(px(8), px(5)))
        s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
        s.configure("Invalid.TEntry", fieldbackground="#FFF6F5", bordercolor="#F04438",
                    lightcolor="#FFF6F5", darkcolor="#FFF6F5")
        s.map("Invalid.TEntry", bordercolor=[("focus", "#F04438")], lightcolor=[("focus", "#F04438")])
        s.layout("Thin.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
            "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        s.configure("Thin.Vertical.TScrollbar", troughcolor=SURFACE, background=BORDER_STRONG,
                    bordercolor=SURFACE, lightcolor=BORDER_STRONG, darkcolor=BORDER_STRONG,
                    arrowsize=px(8), gripcount=0, relief="flat")
        s.map("Thin.Vertical.TScrollbar", background=[("pressed", SUBTLE), ("active", SUBTLE)])
        s.configure("Clean.Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                    rowheight=px(34), borderwidth=0, relief="flat", font=UI.font["body"])
        s.layout("Clean.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Clean.Treeview.Heading", background=SURFACE, foreground=MUTED,
                    font=UI.font["label"], relief="flat", borderwidth=1, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=BORDER, padding=(px(6), px(6)))
        s.map("Clean.Treeview.Heading", background=[("active", SURFACE)])
        s.map("Clean.Treeview", background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", ACCENT_TEXT)])

    def _icon(self):
        """The app mark: a plate on a green tile. Used for the window icon and the left panel."""
        def mark(size):
            k = 4
            n = size * k
            img = Image.new("RGBA", (n, n), rgba(ACCENT, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((0, 0, n - 1, n - 1), radius=n * 0.26, fill=rgba(ACCENT))
            for frac, color in ((0.30, "#FFFFFF"), (0.20, "#5DCAA5"), (0.08, "#FFFFFF")):
                r = n * frac
                draw.ellipse((n / 2 - r, n / 2 - r, n / 2 + r, n / 2 + r), fill=rgba(color))
            return ImageTk.PhotoImage(img.reduce(k), master=self)

        self._app_icon = mark(64)
        self._mark = mark(px(38))
        self.iconphoto(True, self._app_icon)

    def _chart(self, parent):
        fig = Figure(figsize=(3.2, 2.6), dpi=100, facecolor=SURFACE, layout="constrained")
        ax = fig.add_subplot(111)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().configure(bg=SURFACE, highlightthickness=0, bd=0)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return fig, ax, canvas

    def _rows(self, parent, *args, **kw):
        """A RowList packed into `parent`, with a thin scrollbar that shows only when rows overflow."""
        box = tk.Frame(parent, bg=parent["bg"])
        box.pack(fill="both", expand=True)
        rows = RowList(box, *args, **kw)
        bar = ttk.Scrollbar(box, orient="vertical", command=rows.yview, style="Thin.Vertical.TScrollbar")
        shown = [False]

        def set_bar(first, last):
            bar.set(first, last)
            need = not (float(first) <= 0 and float(last) >= 1)
            if need != shown[0]:
                shown[0] = need
                if need:
                    bar.pack(side="right", fill="y", padx=(px(6), 0), before=rows)
                else:
                    bar.pack_forget()

        rows.configure(yscrollcommand=set_bar)
        rows.pack(side="left", fill="both", expand=True)
        return rows

    # ------------------------------------------------------------------ left panel
    def _section(self, parent, title):
        tk.Label(parent, text=title.upper(), font=UI.font["label"], fg=MUTED, bg=SURFACE).pack(
            anchor="w", pady=(px(24), px(10)))

    def _sidebar(self):
        side = tk.Frame(self, bg=SURFACE, width=px(292))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self, bg=BORDER, width=1).pack(side="left", fill="y")
        box = tk.Frame(side, bg=SURFACE)
        box.pack(fill="both", expand=True, padx=px(22), pady=(px(22), px(18)))

        brand = tk.Frame(box, bg=SURFACE)
        brand.pack(fill="x")
        tk.Label(brand, image=self._mark, bg=SURFACE).pack(side="left", padx=(0, px(12)))
        names = tk.Frame(brand, bg=SURFACE)
        names.pack(side="left")
        tk.Label(names, text="Diet Optimizer", font=UI.font["brand"], fg=TEXT, bg=SURFACE).pack(anchor="w")
        tk.Label(names, text="Cheapest day that meets every target", font=UI.font["small"], fg=MUTED,
                 bg=SURFACE).pack(anchor="w")

        self._section(box, "Who is the menu for?")
        grid = tk.Frame(box, bg=SURFACE)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="who")
        for i, g in enumerate(GROUPS):
            Choice(grid, g, self.group, g, command=self.group_chosen).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else px(8), 0), pady=(0, px(8)))
        self.group_info = tk.Label(box, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE,
                                   justify="left", anchor="w", wraplength=px(244))
        self.group_info.pack(fill="x")
        self.custom_row = tk.Frame(box, bg=SURFACE)
        Badge(self.custom_row, "Custom limits", "warn").pack(side="left")
        link = tk.Label(self.custom_row, text="Reset limits", font=UI.font["small_strong"], fg=ACCENT,
                        bg=SURFACE, cursor="hand2")
        link.pack(side="left", padx=px(10))
        link.bind("<Button-1>", lambda e: self.reset_limits())

        self._section(box, "Eating style")
        for name in DIETS:
            count = sum(f[4] not in d.DIETS[DIETS[name]] for f in d.FOODS)
            Choice(box, name, self.diet, name, command=self.solve, radio=True,
                   note=f"{DIET_NOTES[name]} · {count} foods").pack(fill="x", pady=(0, px(8)))

        self._section(box, "Variety")
        Segmented(box, [(v, str(v)) for v in range(2, 9)], self.variety, command=self.solve,
                  stretch=True, height=34, pad=8, track=TRACK).pack(fill="x")
        ends = tk.Frame(box, bg=SURFACE)
        ends.pack(fill="x", pady=(px(5), 0))
        tk.Label(ends, text="← more variety", font=UI.font["tiny"], fg=SUBTLE, bg=SURFACE).pack(side="left")
        tk.Label(ends, text="lower cost →", font=UI.font["tiny"], fg=SUBTLE, bg=SURFACE).pack(side="right")
        self.variety_info = tk.Label(box, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE,
                                     justify="left", anchor="w", wraplength=px(244))
        self.variety_info.pack(fill="x", pady=(px(8), 0))
        disclaimer = tk.Label(box, text="Prices and nutrition values are rough estimates for coursework, "
                                        "not medical advice.", font=UI.font["tiny"], fg=SUBTLE, bg=SURFACE,
                              justify="left", wraplength=px(244))
        disclaimer.pack(side="bottom", anchor="w")
        self.extras.append((disclaimer, dict(side="bottom", anchor="w")))     # hidden on short windows

    def _group_note(self):
        group = self.group.get()
        if group in d.PRESETS:
            mins = [lo for lo, _ in d.PRESETS[group]]            # order of d.NUTRIENTS
            cal, protein, iron = mins[0], mins[1], mins[6]
            ages = "16 to 18" if group.startswith("Teen") else "19 to 29"
            self.group_info.configure(text=f"{fmt(cal)} kcal · {fmt(protein)} g protein · {fmt(iron)} mg iron"
                                           f"\nPDRI 2015, ages {ages}")
            self.custom_row.pack_forget()
        else:
            self.group_info.configure(text=f"You edited the limits, starting from {self.last_group}.")
            self.custom_row.pack(after=self.group_info, fill="x", pady=(px(8), 0))

    def _variety_note(self):
        self.variety_info.configure(text=f"At most {self.variety.get()} servings of any one food.")

    # ------------------------------------------------------------------ top of the main area
    def _topbar(self, main):
        bar = tk.Frame(main, bg=BG)
        bar.pack(fill="x")
        Segmented(bar, [(n, n) for n in self.page_names], self.page, pad=11,
                  command=lambda: self.show_page(self.page.get())).pack(side="left")
        self.copy_btn = Button(bar, "Copy menu", self.copy_menu, kind="primary", height=38,
                               other_texts=("Copied ✓",))
        self.copy_btn.pack(side="right")
        Button(bar, "Reset all", self.reset, kind="ghost", height=38).pack(side="right", padx=(0, px(6)))

    def _tiles(self, main):
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x", pady=(px(20), 0))
        self.tiles = {}
        for i, (key, label) in enumerate((("cost", "Daily cost"), ("meal", "Per meal"),
                                          ("foods", "Foods on the menu"), ("targets", "Targets met"))):
            row.columnconfigure(i, weight=1, uniform="tile")
            card = Card(row, pad=14)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else px(14), 0))
            tk.Label(card.body, text=label.upper(), font=UI.font["label"], fg=MUTED, bg=SURFACE).pack(anchor="w")
            value = tk.Label(card.body, text="–", font=UI.font["kpi"], fg=TEXT, bg=SURFACE)
            value.pack(anchor="w", pady=(px(2), 0))
            note = tk.Label(card.body, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE)
            note.pack(anchor="w")
            self.extras.append((note, dict(anchor="w")))
            self.tiles[key] = (value, note)

    def _banner(self, main):
        fill, fg = TONES["danger"]
        self.banner = Card(main, pad=14, fill=fill, line="#F9C9C4", radius=12)
        icon = tk.Canvas(self.banner.body, width=px(22), height=px(22), bg=fill, highlightthickness=0)
        UI.paint.circle(icon, px(11), px(11), px(11), DANGER)
        icon.create_text(px(11), px(11), text="!", fill="#FFFFFF", font=UI.font["strong"])
        icon.pack(side="left", anchor="n")
        self.banner_text = wrapping_label(self.banner.body, "", UI.font["body"], fg, fill)
        self.banner_text.pack(side="left", fill="x", expand=True, padx=(px(12), 0))

    def _page(self, name):
        """A page with a title row. Returns (body frame, frame for buttons on the right)."""
        _, title, subtitle = next(p for p in PAGES if p[0] == name)
        page = tk.Frame(self.stack, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        head = tk.Frame(page, bg=BG)
        head.pack(fill="x", pady=(0, px(14)))
        actions = tk.Frame(head, bg=BG)
        actions.pack(side="right", anchor="s")
        words = tk.Frame(head, bg=BG)
        words.pack(side="left", fill="x", expand=True)
        tk.Label(words, text=title, font=UI.font["h1"], fg=TEXT, bg=BG).pack(anchor="w")
        sub = wrapping_label(words, subtitle, UI.font["body"], MUTED, BG)
        sub.pack(fill="x")
        self.extras.append((sub, dict(fill="x")))
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True)
        self.pages[name] = page
        return body, actions

    # ------------------------------------------------------------------ pages
    def _menu_page(self):
        body, _ = self._page("Menu")
        body.columnconfigure(0, weight=3, uniform="menu")
        body.columnconfigure(1, weight=2, uniform="menu")
        body.rowconfigure(0, weight=1)
        left = Card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        left.header("Today's foods", "Click a food to change its price.")
        self.menu_list = self._rows(left.body, self._draw_menu_row, px(56), draw_footer=self._draw_menu_total,
                                 on_click=lambda row: self.focus_food(row[0]), fit=True, min_row=px(44))
        right = Card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.header("Where the money goes", "Each slice is one food's share of the daily cost.")
        self.menu_fig, self.menu_ax, self.menu_canvas = self._chart(right.body)

    def _nutrition_page(self):
        body, _ = self._page("Nutrition")
        card = Card(body)
        card.pack(fill="both", expand=True)
        right = card.header("Daily totals", "Each dot is the day's total. It must sit inside the green range.")
        legend = tk.Canvas(right, bg=SURFACE, highlightthickness=0, height=px(22), width=1)
        legend.pack(pady=(px(6), 0))
        x, cy = 0, px(11)
        for kind, label in (("zone", "Allowed range"), ("dot", "Day's total"), ("min", "Minimum"),
                            ("max", "Maximum")):
            if kind == "zone":
                UI.paint.rect(legend, x, cy - px(5), x + px(22), cy + px(5), px(5), GOOD_ZONE)
                x += px(28)
            elif kind == "dot":
                UI.paint.circle(legend, x + px(7), cy, px(7), SURFACE, GOOD, width=2.2)
                x += px(20)
            else:
                legend.create_line(x + px(2), cy - px(8), x + px(2), cy + px(8), width=px(2),
                                   fill=TEXT_2 if kind == "min" else CORAL)
                x += px(10)
            item = legend.create_text(x, cy, text=label, anchor="w", font=UI.font["small"], fill=MUTED)
            x = legend.bbox(item)[2] + px(18)
        legend.configure(width=x)
        self.nut_list = self._rows(card.body, self._draw_nut_row, px(60), fit=True, min_row=px(42))
        note = tk.Label(card.body, text="Drives the cost: raising this limit raises the price (see Why).   "
                                        "At the limit: the total sits exactly on a minimum or maximum.",
                        font=UI.font["small"], fg=SUBTLE, bg=SURFACE, anchor="w")
        note.pack(fill="x", pady=(px(10), 0))
        self.extras.append((note, dict(fill="x", pady=(px(10), 0))))

    FOOD_COLUMNS = ((52, 0), (220, 1), (130, 0), (128, 0), (118, 0), (150, 0))   # (min width, weight)

    def _columns(self, frame):
        for i, (width, weight) in enumerate(self.FOOD_COLUMNS):
            frame.columnconfigure(i, minsize=px(width), weight=weight)

    def _foods_page(self):
        body, actions = self._page("Foods")
        SearchBox(actions, self.search).pack(side="left")
        card = Card(body)
        card.pack(fill="both", expand=True)
        tools = tk.Frame(card.body, bg=SURFACE)
        tools.pack(fill="x", pady=(0, px(14)))
        Segmented(tools, (("all", "All foods"), ("menu", "In the menu"), ("off", "Turned off")),
                  self.food_filter, height=34, pad=12, track=TRACK).pack(side="left")
        Button(tools, "Turn all off", lambda: self.set_all(False), height=34).pack(side="right")
        Button(tools, "Turn all on", lambda: self.set_all(True), height=34).pack(side="right", padx=px(8))

        head = tk.Frame(card.body, bg=SURFACE)
        head.pack(fill="x", padx=(0, px(20)))
        self._columns(head)
        for col, text in enumerate(("Use", "Food", "Type", "Price per serving", "Max servings", "Today")):
            tk.Label(head, text=text.upper(), font=UI.font["label"], fg=MUTED, bg=SURFACE).grid(
                row=0, column=col, sticky="w", pady=(0, px(8)))
        tk.Frame(card.body, bg=BORDER, height=1).pack(fill="x")

        scroll = Scroll(card.body)
        scroll.pack(fill="both", expand=True)
        inner = scroll.inner
        inner.columnconfigure(0, weight=1)
        self.food_rows = {}
        for r, name in enumerate(DEFAULTS):
            row = tk.Frame(inner, bg=SURFACE)
            row.grid(row=r, column=0, sticky="ew")
            self._columns(row)
            Toggle(row, self.on[name]).grid(row=0, column=0, sticky="w", pady=px(11))
            words = tk.Frame(row, bg=SURFACE, cursor="hand2")
            words.grid(row=0, column=1, sticky="w")
            label = tk.Label(words, text=name, font=UI.font["strong"], fg=TEXT, bg=SURFACE, cursor="hand2")
            label.pack(anchor="w")
            serving = tk.Label(words, text=SERVING_OF[name], font=UI.font["small"], fg=MUTED, bg=SURFACE,
                               cursor="hand2")
            serving.pack(anchor="w")
            for w in (words, label, serving):
                w.bind("<Button-1>", lambda e, n=name: self.on[n].set(not self.on[n].get()))
            Badge(row, KIND_NAMES[KIND_OF[name]]).grid(row=0, column=2, sticky="w")
            cell = tk.Frame(row, bg=SURFACE)
            cell.grid(row=0, column=3, sticky="w")
            tk.Label(cell, text="₱", font=UI.font["body"], fg=MUTED, bg=SURFACE).pack(side="left", padx=(0, px(4)))
            price = ttk.Entry(cell, textvariable=self.price[name], width=7, font=UI.font["body"])
            price.pack(side="left")
            own = ttk.Entry(row, textvariable=self.own_max[name], width=6, font=UI.font["body"])
            own.grid(row=0, column=4, sticky="w")
            status = Badge(row)
            status.grid(row=0, column=5, sticky="w")
            tk.Frame(row, bg=BORDER, height=1).grid(row=1, column=0, columnspan=6, sticky="ew")
            self.food_rows[name] = dict(row=row, label=label, price=price, own=own, status=status)
        self.no_foods = tk.Label(inner, text="No foods match.", font=UI.font["body"], fg=SUBTLE, bg=SURFACE)

    def _limits_page(self):
        body, actions = self._page("Limits")
        self.reset_limits_btn = Button(actions, "Reset to Adult woman", self.reset_limits,
                                       other_texts=[f"Reset to {g}" for g in GROUPS])
        self.reset_limits_btn.pack(side="left")
        body.columnconfigure(0, weight=2, uniform="limits")
        body.columnconfigure(1, weight=1, uniform="limits")
        body.rowconfigure(0, weight=1)
        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        table = tk.Frame(card.body, bg=SURFACE)
        table.pack(fill="x")
        for col, (text, width) in enumerate((("Nutrient", 118), ("Minimum", 128), ("Maximum", 128),
                                             ("Preset", 128), ("", 64))):
            table.columnconfigure(col, minsize=px(width), weight=1 if col == 3 else 0)
            tk.Label(table, text=text.upper(), font=UI.font["label"], fg=MUTED, bg=SURFACE).grid(
                row=0, column=col, sticky="w", pady=(0, px(8)))
        tk.Frame(table, bg=BORDER, height=1).grid(row=1, column=0, columnspan=5, sticky="ew")
        self.limit_rows = []
        for i, ((name, unit), (lo, hi)) in enumerate(zip(d.NUTRIENTS, self.limit_vars)):
            r = 2 + 2 * i
            tk.Label(table, text=name, font=UI.font["strong"], fg=TEXT, bg=SURFACE).grid(
                row=r, column=0, sticky="w", pady=px(9))
            entries = []
            for col, var in ((1, lo), (2, hi)):
                cell = tk.Frame(table, bg=SURFACE)
                cell.grid(row=r, column=col, sticky="w")
                entry = ttk.Entry(cell, textvariable=var, width=8, font=UI.font["body"])
                entry.pack(side="left")
                tk.Label(cell, text=unit, font=UI.font["small"], fg=MUTED, bg=SURFACE).pack(side="left", padx=px(6))
                entries.append(entry)
            ref = tk.Label(table, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE)
            ref.grid(row=r, column=3, sticky="w")
            mark = Badge(table)
            mark.grid(row=r, column=4, sticky="w")
            tk.Frame(table, bg=BORDER, height=1).grid(row=r + 1, column=0, columnspan=5, sticky="ew")
            self.limit_rows.append(dict(entries=entries, ref=ref, mark=mark))

        info = Card(body)
        info.grid(row=0, column=1, sticky="nsew")
        info.header("Where the limits come from")
        for text in ("Every group uses the Philippine Dietary Reference Intakes 2015 (FNRI-DOST). "
                     "Adults are ages 19 to 29 and teens are 16 to 18.",
                     "Calories: at least the Recommended Energy Intake. Protein, calcium, iron and "
                     "vitamin C: at least the Recommended Nutrient Intake.",
                     "Fat and carbohydrates: the recommended percent of calories, turned into grams.",
                     "Sodium: at least 500 mg and under 2,000 mg.",
                     "Editing any box switches the group to custom limits. The reset button puts "
                     "the preset back."):
            wrapping_label(info.body, text, UI.font["body"], TEXT_2, SURFACE).pack(fill="x", pady=(0, px(10)))

    def _why_page(self):
        body, _ = self._page("Why")
        body.columnconfigure((0, 1), weight=1, uniform="why")
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)
        drivers = Card(body)
        drivers.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)), pady=(0, px(16)))
        drivers.header("Limits that push the cost up",
                       "Requirement prices: the change in daily cost when a limit moves by one unit.")
        self.why_drivers = self._rows(drivers.body, self._draw_driver_row, px(58), fit=True, min_row=px(46))
        caps = Card(body)
        caps.grid(row=1, column=0, sticky="nsew", padx=(0, px(16)))
        caps.header("Variety caps that bind", "Foods held back by the most-servings limit.")
        self.why_caps = self._rows(caps.body, self._draw_cap_row, px(52), fit=True, min_row=px(44),
                                on_click=lambda row: self.focus_food(row[1]))
        missed = Card(body)
        missed.grid(row=0, column=1, rowspan=2, sticky="nsew")
        missed.header("Foods that just missed out",
                      "Reduced costs: how much cheaper each food would need to be to join the menu. "
                      "Click one to edit its price.")
        self.why_missed = self._rows(missed.body, self._draw_missed_row, px(58), fit=True, min_row=px(46),
                                  on_click=lambda row: self.focus_food(row[1]))

    def _steps_page(self):
        body, _ = self._page("Solver steps")
        stats = tk.Frame(body, bg=BG)
        stats.pack(fill="x", pady=(0, px(16)))
        self.step_stats = {}
        for i, (key, label, note) in enumerate((("N", "Nutrition matrix N", "nutrients × foods"),
                                                ("G", "Requirement system G", "rows × foods"),
                                                ("GT", "Mirror problem Gᵀ", "foods × rows"),
                                                ("pivots", "Pivots", "Gauss-Jordan steps"))):
            stats.columnconfigure(i, weight=1, uniform="stat")
            card = Card(stats, pad=14)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else px(14), 0))
            tk.Label(card.body, text=label, font=UI.font["small"], fg=MUTED, bg=SURFACE).pack(anchor="w")
            value = tk.Label(card.body, text="–", font=UI.font["h2"], fg=TEXT, bg=SURFACE)
            value.pack(anchor="w")
            tk.Label(card.body, text=note, font=UI.font["tiny"], fg=SUBTLE, bg=SURFACE).pack(anchor="w")
            self.step_stats[key] = value

        row = tk.Frame(body, bg=BG)
        row.pack(fill="both", expand=True)
        row.columnconfigure((0, 1), weight=1, uniform="steps")
        row.rowconfigure(0, weight=1)
        left = Card(row)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        left.header("Every pivot", "What joins the solution at each step, and the proven minimum after it.")
        box = tk.Frame(left.body, bg=SURFACE)
        box.pack(fill="both", expand=True)
        cols = ("#", "Joins the solution", "Proven minimum")
        self.steps_tree = ttk.Treeview(box, columns=cols, show="headings", style="Clean.Treeview")
        for col, width, anchor, stretch in ((cols[0], 40, "center", False), (cols[1], 170, "w", True),
                                            (cols[2], 120, "e", False)):
            self.steps_tree.heading(col, text=col.upper(), anchor=anchor)
            self.steps_tree.column(col, width=px(width), minwidth=px(width if not stretch else 100),
                                   anchor=anchor, stretch=stretch)
        self.steps_tree.tag_configure("odd", background="#FAFBFC")
        bar = ttk.Scrollbar(box, orient="vertical", command=self.steps_tree.yview,
                            style="Thin.Vertical.TScrollbar")
        self.steps_tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y", padx=(px(6), 0))
        self.steps_tree.pack(side="left", fill="both", expand=True)
        right = Card(row)
        right.grid(row=0, column=1, sticky="nsew")
        right.header("Proven minimum after each pivot", "The mirror value rises until it meets a real menu.")
        self.steps_fig, self.steps_ax, self.steps_canvas = self._chart(right.body)

    def _variety_page(self):
        body, _ = self._page("Variety")
        body.columnconfigure(0, weight=3, uniform="variety")
        body.columnconfigure(1, weight=2, uniform="variety")
        body.rowconfigure(0, weight=1)
        left = Card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        left.header("Cheapest day at each variety level",
                    "One line per group, using your eating style, prices and foods. "
                    "Your setting is circled. Click any point to switch to it.")
        # Packed before the chart so that on a short window the chart shrinks, not this note
        note = wrapping_label(left.body, "This chart is figure 5 of the report. python diet_optimizer.py "
                                         "--plots saves it with the default prices.",
                              UI.font["small"], SUBTLE, SURFACE)
        note.pack(side="bottom", fill="x", pady=(px(8), 0))
        self.extras.append((note, dict(side="bottom", fill="x", pady=(px(8), 0))))
        self.variety_fig, self.variety_ax, self.variety_canvas = self._chart(left.body)
        self.variety_canvas.mpl_connect("button_press_event", self._variety_click)
        self.variety_canvas.mpl_connect("motion_notify_event", self._variety_hover)
        self._variety_stale, self._variety_costs = True, {}

        right = Card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.header("Your cost at each level", "Compared with your current setting. Click a row to switch to it.")
        self.level_list = self._rows(right.body, self._draw_level_row, px(54), fit=True, min_row=px(40),
                                     on_click=lambda row: self.use_setting(row[3], row[0]))

    def _guide_page(self):
        body, _ = self._page("Guide")
        body.columnconfigure((0, 1), weight=1, uniform="guide")
        body.rowconfigure(0, weight=1)
        card = Card(body, pad=10)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        text = tk.Text(card.body, wrap="word", bg=SURFACE, fg=TEXT_2, relief="flat", bd=0,
                       highlightthickness=0, padx=px(12), pady=px(8), font=UI.font["body"], cursor="arrow",
                       spacing2=px(2), spacing3=px(6), tabs=(px(26),))
        text.tag_configure("h", font=UI.font["h2"], foreground=TEXT, spacing1=px(16), spacing3=px(8))
        text.tag_configure("first", spacing1=0)
        text.tag_configure("li", lmargin1=px(2), lmargin2=px(26))
        text.tag_configure("num", foreground=ACCENT, font=UI.font["strong"])
        text.tag_configure("term", foreground=TEXT, font=UI.font["strong"])
        text.tag_configure("code", font=UI.font["mono"], foreground=TEXT, background=TRACK,
                           spacing1=0, spacing3=0)
        for i, (kind, content) in enumerate(GUIDE):
            if kind == "h":
                text.insert("end", content + "\n", ("h", "first") if i == 0 else "h")
            elif kind == "p":
                text.insert("end", content + "\n")
            elif kind == "code":                     # each line keeps its newline so the shading is full width
                text.insert("end", "".join(f"  {line}\n" for line in content.split("\n")), "code")
            elif kind == "ol":
                for n, item in enumerate(content, start=1):
                    text.insert("end", f"{n}.\t", ("li", "num"))
                    text.insert("end", item + "\n", "li")
            else:
                for term, meaning in content:
                    text.insert("end", "•\t", ("li", "num"))
                    text.insert("end", term, ("li", "term"))
                    text.insert("end", f": {meaning}\n", "li")
        text.configure(state="disabled")
        bar = ttk.Scrollbar(card.body, orient="vertical", command=text.yview, style="Thin.Vertical.TScrollbar")
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y", pady=px(8))
        text.pack(side="left", fill="both", expand=True)

        picture = Card(body)
        picture.grid(row=0, column=1, sticky="nsew")
        picture.header("See it in two dimensions",
                       "An illustration, not your menu: the same method on a problem with only rice and "
                       "eggs, small enough to draw.")
        # Packed before the chart so that on a short window the chart shrinks, not the explanation
        notes = tk.Frame(picture.body, bg=SURFACE)
        notes.pack(side="bottom", fill="x", pady=(px(8), 0))
        for i, line in enumerate((
                "Each point is a menu (cups of rice, eggs). The shaded region holds every menu with at "
                "least 1,200 kcal and 48 g protein.",
                "Corners A, B and C are where two edges meet, so each one solves a 2 × 2 system. The dotted "
                "cost line first touches the region at B: 4 cups of rice and 4 eggs for ₱80, the cheapest menu.",
                "Your real menu works the same way, but with 25 foods its region has 25 dimensions, so it "
                "can't be drawn.")):
            label = wrapping_label(notes, line, UI.font["small"], TEXT_2, SURFACE)
            label.pack(fill="x", pady=(0, px(4)))
            if i == 2:
                self.extras.append((label, dict(fill="x", pady=(0, px(4)))))
        source = wrapping_label(notes, "This picture is figure 6 of the report. python diet_optimizer.py "
                                       "--example shows every row operation.", UI.font["small"], SUBTLE, SURFACE)
        source.pack(fill="x")
        self.extras.append((source, dict(fill="x")))
        _, ax, canvas = self._chart(picture.body)
        d.draw_two_food(ax)
        canvas.draw_idle()

    # ------------------------------------------------------------------ list rows (drawn on canvases)
    def _draw_menu_row(self, cv, row, x0, y, x1, h):
        name, amount, cost, share, color = row
        cy, f = y + h / 2, UI.font
        UI.paint.circle(cv, x0 + px(6), cy, px(6), color)
        cv.create_text(x0 + px(24), cy - px(9), text=name, anchor="w", font=f["strong"], fill=TEXT)
        cv.create_text(x0 + px(24), cy + px(10), text=amount, anchor="w", font=f["small"], fill=MUTED)
        cv.create_text(x1, cy - px(9), text=f"₱{cost:.2f}", anchor="e", font=f["strong"], fill=TEXT)
        cv.create_text(x1, cy + px(10), text=f"{share:.0%} of the cost", anchor="e", font=f["small"], fill=MUTED)

    def _draw_menu_total(self, cv, total, x0, y, x1, h):
        cy = y + h / 2
        cv.create_text(x0, cy, text="Total for the day", anchor="w", font=UI.font["strong"], fill=TEXT)
        cv.create_text(x1, cy, text=f"₱{total:.2f}", anchor="e", font=UI.font["h3"], fill=ACCENT)

    def _draw_nut_row(self, cv, row, x0, y, x1, h):
        name, unit, total, lo, hi, status = row
        cy, f = y + h / 2, UI.font
        cv.create_text(x0, cy - px(9), text=name, anchor="w", font=f["strong"], fill=TEXT)
        cv.create_text(x0, cy + px(10), text="need " + need_text(lo, hi, unit), anchor="w", font=f["small"],
                       fill=MUTED)
        value_x = x0 + px(290)
        cv.create_text(value_x, cy, text=f"{fmt(total)} {unit}", anchor="e", font=f["strong"], fill=TEXT)
        text, tone = {"drives": ("Drives the cost", "warn"), "limit": ("At the limit", "info"),
                      "met": ("Met", "good"), "missed": ("Not met", "danger")}[status]
        self._range_bar(cv, value_x + px(30), x1 - px(150), cy, total, lo, hi)
        UI.paint.badge(cv, x1, cy, text, tone, anchor="e")

    def _range_bar(self, cv, x0, x1, cy, total, lo, hi):
        """Gray track, green allowed range, a dot at the total, ticks at the minimum and maximum."""
        if x1 - x0 < px(40):
            return
        if hi is not None:                    # a range: the maximum sits near the right end
            top = max(total, hi) * 1.12
        elif lo:                              # a minimum only: "exactly enough" sits in the middle
            top = max(total * 1.12, 2 * lo)
        else:
            top = total * 1.12
        top = top or 1.0

        def at(v):
            return x0 + (x1 - x0) * min(max(v / top, 0), 1)

        t = px(10)
        UI.paint.rect(cv, x0, cy - t / 2, x1, cy + t / 2, t // 2, TRACK)
        if lo is not None or hi is not None:
            UI.paint.rect(cv, at(lo or 0), cy - t / 2, at(hi if hi is not None else top), cy + t / 2, t // 2,
                          GOOD_ZONE)
        if lo:
            cv.create_line(at(lo), cy - px(10), at(lo), cy + px(10), fill=TEXT_2, width=px(2))
        if hi is not None:
            cv.create_line(at(hi), cy - px(10), at(hi), cy + px(10), fill=CORAL, width=px(2))
        UI.paint.circle(cv, at(total), cy, px(7), SURFACE, GOOD, width=2.2)

    def _draw_driver_row(self, cv, row, x0, y, x1, h):
        value, kind, name, unit = row
        cy, f = y + h / 2, UI.font
        bound = "minimum" if kind == "min" else "maximum"
        effect = "adds" if kind == "min" else "saves"
        self._two_lines(cv, x0, x1, cy, f"{name} {bound}", f"Raising it by 1 {unit} {effect} {money(value)} a day",
                        money(value), f"per {unit}", CORAL)

    def _draw_cap_row(self, cv, row, x0, y, x1, h):
        value, name, cap = row
        self._two_lines(cv, x0, x1, y + h / 2, name, f"Held at its cap of {fmt(cap)} servings",
                        money(value), "saved per extra serving", TEXT_2)

    def _draw_missed_row(self, cv, row, x0, y, x1, h):
        reduced, name, price = row
        cy = y + h / 2
        cv.create_text(x1, cy, text="›", anchor="e", font=UI.font["h2"], fill=SUBTLE)
        self._two_lines(cv, x0, x1 - px(22), cy, name, f"Now ₱{price:.2f} · joins below ₱{price - reduced:.2f}",
                        f"₱{reduced:.2f}", "price cut needed", TONES["warn"][1])

    @staticmethod
    def _two_lines(cv, x0, x1, cy, title, detail, value, unit, color):
        """A list row: title over detail on the left, value over unit on the right."""
        f = UI.font
        cv.create_text(x0, cy - px(9), text=title, anchor="w", font=f["strong"], fill=TEXT)
        cv.create_text(x0, cy + px(10), text=detail, anchor="w", font=f["small"], fill=MUTED)
        cv.create_text(x1, cy - px(9), text=value, anchor="e", font=f["strong"], fill=color)
        cv.create_text(x1, cy + px(10), text=unit, anchor="e", font=f["small"], fill=MUTED)

    # ------------------------------------------------------------------ navigation and small actions
    def show_page(self, name):
        self.page.set(name)
        self.pages[name].tkraise()
        if name == "Variety":
            self.after_idle(self.show_variety)

    def _resized(self, e):
        """On a short window, hide helper text (page subtitles, tile notes) to make room for the data."""
        if e.widget is not self:
            return
        compact = e.height < px(820)
        if compact != self.compact:
            self.compact = compact
            for widget, how in self.extras:
                widget.pack_forget() if compact else widget.pack(**how)

    def _wheel(self, e):
        """Scroll whichever scrolling area is under the pointer."""
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        while w is not None and not hasattr(w, "scroll_canvas"):
            w = w.master
        if w is None or w.scroll_canvas.yview() == (0.0, 1.0):
            return
        step = -1 if e.num == 4 or getattr(e, "delta", 0) > 0 else 1
        w.scroll_canvas.yview_scroll(step * 3, "units")

    def schedule(self, delay=250):
        """Re-solve shortly after the last edit, so typing a price stays smooth."""
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(delay, self.solve)

    def fill_limits(self, group):
        self._filling = True
        for (lo, hi), (vlo, vhi) in zip(d.PRESETS[group], self.limit_vars):
            vlo.set("" if lo is None else f"{lo:g}")
            vhi.set("" if hi is None else f"{hi:g}")
        self._filling = False
        self._mark_limits()

    def group_chosen(self):
        self.last_group = self.group.get()
        self.reset_limits_btn.set_text(f"Reset to {self.last_group}")
        self.fill_limits(self.last_group)
        self.solve()

    def limit_edited(self, *_):
        self._mark_limits()
        if not self._filling:
            self.group.set("")                       # no group is selected any more
            self.schedule()

    def _mark_limits(self):
        """Show each preset value and flag the rows that were edited by hand."""
        preset = d.PRESETS[self.last_group]
        for row, (lo, hi), (vlo, vhi), (_, unit) in zip(self.limit_rows, preset, self.limit_vars, d.NUTRIENTS):
            row["ref"].configure(text=need_text(lo, hi, unit))
            edited = False
            for var, ref in ((vlo, lo), (vhi, hi)):
                text = var.get().strip()
                value = None if text == "" else number(text, -1)
                edited |= (value is None) != (ref is None) or (value is not None and abs(value - ref) > 1e-9)
            row["mark"].update_badge("Edited" if edited else "", "warn")

    def reset_limits(self):
        self.group.set(self.last_group)
        self.group_chosen()

    def set_all(self, value):
        for var in self.on.values():
            var.set(value)

    def filter_foods(self):
        q, kind = self.search.get().strip().lower(), self.food_filter.get()
        shown = 0
        for name, row in self.food_rows.items():
            keep = q in name.lower() and (kind == "all" or (kind == "menu" and name in self.in_menu)
                                          or (kind == "off" and not self.on[name].get()))
            (row["row"].grid if keep else row["row"].grid_remove)()
            shown += keep
        if shown:
            self.no_foods.grid_remove()
        else:
            self.no_foods.grid(row=len(self.food_rows), column=0, pady=px(30))

    def focus_food(self, name):
        """Jump to a food's row on the Foods page and select its price."""
        self.food_filter.set("all")
        self.search.set(name)
        self.show_page("Foods")
        entry = self.food_rows[name]["price"]
        self.after(60, lambda: (entry.focus_set(), entry.select_range(0, "end")))

    def copy_menu(self):
        if not self.menu_text:
            return
        self.clipboard_clear()
        self.clipboard_append(self.menu_text)
        self.copy_btn.set_text("Copied ✓")
        self.after(1600, lambda: self.copy_btn.set_text("Copy menu"))

    def reset(self):
        self._filling = True
        for name, (p, m) in DEFAULTS.items():
            self.on[name].set(True)
            self.price[name].set(f"{p:g}")
            self.own_max[name].set(f"{m:g}")
        self._filling = False
        self.diet.set("Anything")
        self.variety.set(4)
        self.search.set("")
        self.food_filter.set("all")
        self.prev_cost = None
        if self._pending:
            self.after_cancel(self._pending)
            self._pending = None
        self.group.set("Adult woman")
        self.group_chosen()
        self.show_page("Menu")

    # ------------------------------------------------------------------ solving
    def read_limits(self):
        limits = []
        for (name, _), (vlo, vhi) in zip(d.NUTRIENTS, self.limit_vars):
            pair = []
            for var in (vlo, vhi):
                text = var.get().strip()
                value = None if text == "" else number(text)
                if text != "" and value is None:
                    raise ValueError(f"The {name} limit must be a number of zero or more.")
                pair.append(value)
            limits.append(tuple(pair))
        return limits

    def _check_fields(self):
        """Outline in red every box that does not hold a usable number."""
        def mark(entry, ok):
            entry.configure(style="TEntry" if ok else "Invalid.TEntry")

        for name, row in self.food_rows.items():
            mark(row["price"], number(self.price[name].get()) is not None)
            text = self.own_max[name].get().strip()
            mark(row["own"], text == "" or number(text) is not None)
        for row, pair in zip(self.limit_rows, self.limit_vars):
            for entry, var in zip(row["entries"], pair):
                text = var.get().strip()
                mark(entry, text == "" or number(text) is not None)

    def solve(self):
        if self._pending:                              # this solve replaces any re-solve still waiting
            self.after_cancel(self._pending)
            self._pending = None
        diet = DIETS[self.diet.get()]
        excluded_kinds = d.DIETS[diet]
        for name, row in self.food_rows.items():
            blocked = KIND_OF[name] in excluded_kinds
            row["blocked"] = blocked
            row["label"].configure(fg=SUBTLE if blocked or not self.on[name].get() else TEXT)
        self._check_fields()
        prices = {n: number(v.get(), DEFAULTS[n][0]) for n, v in self.price.items()}
        own_max = {n: number(v.get(), 1e9) if v.get().strip() else 1e9 for n, v in self.own_max.items()}
        exclude = {n for n, v in self.on.items() if not v.get()}
        try:
            limits = self.read_limits()
        except ValueError as err:
            limits, error = None, str(err)
        self.figure_inputs = (diet, prices, exclude, own_max, limits)    # the Variety page follows these
        self._variety_stale = True
        if self.page.get() == "Variety":
            self.after_idle(self.show_variety)
        if limits is None:
            return self.no_menu(error)
        if all(KIND_OF[n] in excluded_kinds or n in exclude for n in DEFAULTS):
            return self.no_menu("Every food is turned off or left out by the eating style. "
                                "Turn some on in Foods, or pick another eating style.")

        p = d.build_problem("Adult woman", diet, self.variety.get(), prices, exclude, limits, own_max)
        s = d.solve_diet(p)
        if s is None:
            caps = [-v for v in p.h[len(p.h) - len(p.names):]]      # the last rows of h are -cap
            best = d.mat_vec(p.N, caps)                 # the most of each nutrient we could ever get
            hints = [f"{name} can't reach {fmt(lo)} {unit}" for (name, unit), (lo, _), b
                     in zip(d.NUTRIENTS, limits, best) if lo is not None and b < lo - 1e-9]
            return self.no_menu("No menu meets every limit" + (f" ({'; '.join(hints)})" if hints else "")
                                + ". Try a higher variety level, “Anything”, more foods, or a lower minimum.")
        self.banner.pack_forget()
        self.show_tiles(p, s, limits)
        self.show_menu(p, s)
        self.show_nutrition(p, s, limits)
        self.show_foods(p, s)
        self.show_why(p, s)
        self.show_steps(p, s)

    def no_menu(self, text):
        self.banner_text.configure(text=text)
        self.banner.pack(fill="x", pady=(px(16), 0), before=self.stack)
        self.menu_text, self.prev_cost, self.in_menu = "", None, {}
        value, note = self.tiles["cost"]
        value.configure(text="No menu", fg=DANGER)
        note.configure(text="see the message below", fg=MUTED)
        for key in ("meal", "foods", "targets"):
            self.tiles[key][0].configure(text="–", fg=TEXT)
            self.tiles[key][1].configure(text="")
        empty = "No menu to show. Change the settings to find one."
        for rows in (self.menu_list, self.nut_list, self.why_drivers, self.why_caps, self.why_missed):
            rows.show([], empty=empty)
        for name, row in self.food_rows.items():
            row["status"].update_badge(*self._food_status(name, 0))
        if self.food_filter.get() == "menu":
            self.filter_foods()
        self.steps_tree.delete(*self.steps_tree.get_children())
        for label in self.step_stats.values():
            label.configure(text="–")
        for ax, canvas in ((self.menu_ax, self.menu_canvas), (self.steps_ax, self.steps_canvas)):
            ax.clear()
            ax.set_axis_off()
            ax.text(0.5, 0.5, "No menu", ha="center", va="center", color=SUBTLE, fontsize=12,
                    transform=ax.transAxes)
            canvas.draw_idle()

    # ------------------------------------------------------------------ views
    def show_tiles(self, p, s, limits):
        value, note = self.tiles["cost"]
        value.configure(text=f"₱{s.cost:.2f}", fg=ACCENT)
        if self.prev_cost is None:
            note.configure(text="cheapest for these settings", fg=MUTED)
        elif abs(s.cost - self.prev_cost) > 0.005:
            diff = s.cost - self.prev_cost
            note.configure(text=f"{'+' if diff > 0 else '−'}₱{abs(diff):.2f} after your last change",
                           fg=DANGER if diff > 0 else GOOD)
        else:
            note.configure(text="unchanged by your last change", fg=MUTED)
        self.prev_cost = s.cost

        self.tiles["meal"][0].configure(text=f"₱{s.cost / 3:.2f}", fg=TEXT)
        self.tiles["meal"][1].configure(text="if split into three meals")
        used = sum(x > 1e-6 for x in s.x)
        self.tiles["foods"][0].configure(text=str(used), fg=TEXT)
        self.tiles["foods"][1].configure(text=f"out of {len(p.names)} available")

        totals = d.mat_vec(p.N, s.x)                         # N x: the day's nutrient totals
        limited = [(t, lo, hi) for t, (lo, hi) in zip(totals, limits) if lo is not None or hi is not None]
        met = sum((lo is None or t >= lo - 1e-6) and (hi is None or t <= hi + 1e-6) for t, lo, hi in limited)
        drivers = sum(v > 1e-7 and lab[0] != "cap" for v, lab in zip(s.y, p.labels))
        self.tiles["targets"][0].configure(text=f"{met} of {len(limited)}",
                                           fg=GOOD if met == len(limited) else DANGER)
        self.tiles["targets"][1].configure(text=f"{drivers} limit{'s' if drivers != 1 else ''} drive the cost"
                                           if drivers else "none is holding the cost up")

    def show_menu(self, p, s):
        costs = [x * c for x, c in zip(s.x, p.c)]           # what each food adds to c . x
        used = [j for j in sorted(range(len(costs)), key=lambda j: -costs[j]) if s.x[j] > 1e-6]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(used))]
        total = s.cost if s.cost > 1e-9 else 1.0
        rows = [(p.names[j], f"{s.x[j]:.1f} × {p.servings[j]}", costs[j], costs[j] / total, color)
                for j, color in zip(used, colors)]
        self.menu_list.show(rows, footer=s.cost)
        group = self.group.get() or f"custom limits from {self.last_group}"
        self.menu_text = (f"Cheapest day: ₱{s.cost:.2f} ({group}, {self.diet.get().lower()}, at most "
                          f"{self.variety.get()} servings of any food)\n" + "\n".join(
                              f"- {p.names[j]}: {s.x[j]:.1f} × {p.servings[j]} (₱{costs[j]:.2f})" for j in used))

        ax = self.menu_ax
        ax.clear()
        ax.set_axis_off()
        if s.cost > 1e-9:
            ax.pie([costs[j] for j in used], colors=colors, startangle=90, counterclock=False,
                   wedgeprops=dict(width=0.3, edgecolor=SURFACE, linewidth=2.5))
        ax.set_aspect("equal")
        ax.text(0, 0.08, f"₱{s.cost:.2f}", ha="center", va="center", fontsize=18, fontweight="semibold",
                color=TEXT)
        ax.text(0, -0.16, "per day", ha="center", va="center", fontsize=9.5, color=MUTED)
        self.menu_canvas.draw_idle()

    def show_nutrition(self, p, s, limits):
        totals = d.mat_vec(p.N, s.x)                         # N x: the day's nutrient totals
        priced = {(k, n) for v, (k, n, _) in zip(s.y, p.labels) if v > 1e-7 and k != "cap"}
        rows = []
        for (name, unit), (lo, hi), t in zip(d.NUTRIENTS, limits, totals):
            if (lo is not None and t < lo - 1e-6) or (hi is not None and t > hi + 1e-6):
                status = "missed"
            elif ("min", name) in priced or ("max", name) in priced:
                status = "drives"
            elif (lo is not None and abs(t - lo) < 1e-6) or (hi is not None and abs(t - hi) < 1e-6):
                status = "limit"
            else:
                status = "met"
            rows.append((name, unit, t, lo, hi, status))
        self.nut_list.show(rows)

    def _food_status(self, name, servings):
        """The badge in the Today column of the Foods page."""
        if servings > 1e-6:
            return f"{servings:.1f} in menu", "good"
        if self.food_rows[name].get("blocked"):
            return "Not in this style", "neutral"
        return ("Turned off" if not self.on[name].get() else ""), "neutral"

    def show_foods(self, p, s):
        self.in_menu = {name: x for name, x in zip(p.names, s.x) if x > 1e-6}
        for name, row in self.food_rows.items():
            row["status"].update_badge(*self._food_status(name, self.in_menu.get(name, 0)))
        if self.food_filter.get() != "all":
            self.filter_foods()

    def show_why(self, p, s):
        drivers = sorted(((v, *lab) for v, lab in zip(s.y, p.labels) if v > 1e-7 and lab[0] != "cap"),
                         key=lambda row: -row[0])
        self.why_drivers.show(drivers, empty="No limit is holding the cost up.")
        caps = sorted(((v, lab[1], -h) for v, lab, h in zip(s.y, p.labels, p.h) if v > 1e-7 and lab[0] == "cap"),
                      key=lambda row: -row[0])
        self.why_caps.show(caps, empty="No food is held back by the variety level.")
        rc = d.reduced_costs(p, s)                            # c_j - (column j of G) . y
        missed = sorted((rc[j], p.names[j], p.c[j]) for j in range(len(p.names)) if s.x[j] <= 1e-6)[:8]
        self.why_missed.show(missed, empty="Every available food is on the menu.")

    def show_steps(self, p, s):
        (n_rows, n_cols), (g_rows, g_cols) = d.shape(p.N), d.shape(p.G)
        self.step_stats["N"].configure(text=f"{n_rows} × {n_cols}")
        self.step_stats["G"].configure(text=f"{g_rows} × {g_cols}")
        self.step_stats["GT"].configure(text=f"{g_cols} × {g_rows}")
        self.step_stats["pivots"].configure(text=str(len(s.steps)))
        self.steps_tree.delete(*self.steps_tree.get_children())
        for k, st in enumerate(s.steps, 1):
            self.steps_tree.insert("", "end", values=(k, "  " + d.describe(p, st.entering), f"₱{st.value:.2f}  "),
                                   tags=("odd",) if k % 2 else ())

        self.steps_ax.clear()
        d.draw_solver_progress(self.steps_ax, s, line=ACCENT)          # figure 4 of the report
        self.steps_canvas.draw_idle()

    VARIETIES = range(2, 9)

    def show_variety(self):
        """The Variety page for the current eating style, prices and foods. About 0.2 s (28 solves)."""
        if not self._variety_stale or not hasattr(self, "figure_inputs"):
            return
        self._variety_stale = False
        diet, prices, exclude, own_max, limits = self.figure_inputs
        groups, current = dict(d.PRESETS), self.group.get()
        if not current and limits is not None:          # custom limits get their own line
            groups["Your limits"] = limits
            current = "Your limits"
        costs = d.variety_costs(diet, prices, exclude, own_max, groups, self.VARIETIES)
        self._variety_costs = costs
        self.variety_ax.clear()
        d.draw_variety(self.variety_ax, costs, self.VARIETIES,
                       mark=(current, self.variety.get()) if current else None)
        self.variety_canvas.draw_idle()

        if not current:
            return self.level_list.show([], empty="Fix the limits marked in red to see your costs.")
        here = costs[current][self.VARIETIES.index(self.variety.get())]
        self.level_list.show([(v, cost, here, current) for v, cost in zip(self.VARIETIES, costs[current])])

    def _nearest_point(self, event):
        """The (group, variety) of the chart point closest to the pointer, if it is within reach."""
        if event.inaxes is not self.variety_ax or event.x is None:
            return None
        best = None
        for name, ys in self._variety_costs.items():
            for v, y in zip(self.VARIETIES, ys):
                if not math.isnan(y):
                    sx, sy = self.variety_ax.transData.transform((v, y))
                    dist = math.hypot(sx - event.x, sy - event.y)
                    if best is None or dist < best[0]:
                        best = (dist, name, v)
        return best[1:] if best and best[0] < px(16) else None

    def _variety_hover(self, event):
        self.variety_canvas.get_tk_widget().configure(cursor="hand2" if self._nearest_point(event) else "")

    def _variety_click(self, event):
        point = self._nearest_point(event)
        if point:
            self.use_setting(*point)

    def use_setting(self, group, variety):
        """Switch to a variety level, and to another group if a different group's line was clicked."""
        self.variety.set(variety)
        if group in d.PRESETS and group != self.group.get():
            self.group.set(group)
            self.group_chosen()                         # loads that group's limits, then solves
        else:
            self.solve()

    def _draw_level_row(self, cv, row, x0, y, x1, h):
        v, cost, here, _ = row
        cy, f = y + h / 2, UI.font
        current = v == self.variety.get()
        if current:
            UI.paint.rect(cv, x0 - px(10), y + px(2), x1 + px(10), y + h - px(2), px(8), ACCENT_SOFT)
        note = "your setting" if current else "more variety" if v < self.variety.get() else "less variety"
        cv.create_text(x0, cy - px(9), text=f"At most {v} servings", anchor="w", font=f["strong"],
                       fill=ACCENT_TEXT if current else TEXT)
        cv.create_text(x0, cy + px(10), text=note, anchor="w", font=f["small"], fill=MUTED)
        if math.isnan(cost):
            value, detail, color = "No menu", "limits can't be met", MUTED
        elif current or math.isnan(here):
            value, detail, color = f"₱{cost:.2f}", "per day", MUTED
        else:
            diff = cost - here
            value = f"₱{cost:.2f}"
            detail = "same cost" if abs(diff) < 0.005 else f"{'+' if diff > 0 else '−'}₱{abs(diff):.2f} a day"
            color = MUTED if abs(diff) < 0.005 else DANGER if diff > 0 else GOOD
        cv.create_text(x1, cy - px(9), text=value, anchor="e", font=f["strong"],
                       fill=ACCENT_TEXT if current else TEXT)
        cv.create_text(x1, cy + px(10), text=detail, anchor="e", font=f["small"], fill=color)


def main():
    if sys.platform == "win32":                       # sharp text on high-resolution Windows screens
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    DietApp().mainloop()


if __name__ == "__main__":
    main()
