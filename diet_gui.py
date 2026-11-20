"""
diet_gui.py
===========
The Diet Optimizer window. Every answer comes from the Python solver in
diet_optimizer.py. This file only draws the screens.

Run:   python diet_gui.py          (or: python diet_optimizer.py --gui)

Layout:
    Left panel     who the menu is for, eating style, variety, and the meals and budget
                   (Alt+1 to Alt+3 set the meals a day)
    Top bar        page tabs, Reset all and Copy menu
    Summary tiles  cost of the planned meals, cost per meal, foods used, targets met
                   and the budget check (on every page)

Pages (Ctrl+1 to Ctrl+8 switch between them):
    Menu           the cheapest food for the planned meals, with amounts, costs, a shopping
                   checklist and what the budget can do
    Nutrition      the totals N @ x checked against every limit
    Foods          turn foods on or off, edit prices and daily maximums
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
# The project slides' colors, used sparingly: forest green for text and buttons, lime only for
# the active tab, a pale lime for selections, and plain white cards on an off-white page
FOREST, LIME, PALE = "#0F2B1D", "#CAE265", "#F0F5E1"
BG, SURFACE, SUNKEN, TRACK, HOVER = "#FAFBF7", "#FFFFFF", "#F1F3EC", "#F1F3EC", "#F6F8F1"
BORDER, BORDER_STRONG = "#E6E9E0", "#D2D7CA"
TEXT, TEXT_2, MUTED, SUBTLE = FOREST, "#2F4636", "#68746B", "#9AA49C"
ACCENT, ACCENT_HOVER, ACCENT_SOFT, ACCENT_TEXT = FOREST, "#1E4A2F", PALE, FOREST
GOOD, GOOD_ZONE = "#2E7D4F", "#E3EDC6"
PURPLE, CORAL, DANGER = "#7F77DD", "#E8913A", "#D9534F"
TONES = {                                    # badge colors: (background, text)
    "good": ("#E4EFC4", "#24603A"),
    "warn": ("#FCEBD2", "#A85A12"),
    "info": ("#E3EDE6", "#24452F"),
    "danger": ("#FBE3E1", "#B03A35"),
    "neutral": ("#EEF1E7", "#4A5A4D"),
}
PALETTE = [FOREST, "#9CC43D", "#2E7D4F", "#E3B341", "#7FA88A",
           "#C9D88F", "#5B8C6A", "#D9A066", "#B5C7A5", "#3E6B4B"]

DIETS = {"Anything": "anything", "No meat or fish": "no-meat-fish", "Plant-based": "plant-based"}
DIET_NOTES = {"Anything": "Every food", "No meat or fish": "Keeps eggs and dairy",
              "Plant-based": "Plants only"}
KIND_NAMES = {d.PLANT: "Plant", d.MEAT_FISH: "Meat or fish", d.EGG_DAIRY: "Egg or dairy"}
GROUPS = list(d.PRESETS)
FOOD_NAMES = [f[0] for f in d.FOODS]
KIND_OF = {f[0]: f[4] for f in d.FOODS}
OWN_MAX = {f[0]: f[3] for f in d.FOODS}
MARKET_PRICE = {f[0]: f[2] for f in d.FOODS}                 # WFP price per kg (eggs: per egg)
PRICE_SOURCE = f"{d.MARKET}, {d.month_name(d.MONTH)}"


def price_unit(name):
    """'/kg' or '/egg': the unit a market price is quoted in."""
    return "/egg" if d.PRICE_UNIT[name] == "piece" else "/kg"


def serving_unit(name):
    """What one serving is, for labels: '100 g', '1 g' or 'egg'."""
    return "egg" if d.PRICE_UNIT[name] == "piece" else f"{d.SERVING_GRAMS[name]} g"


def max_unit(name):
    """The unit next to a food's daily maximum: '× 100 g', 'g' or 'eggs'."""
    grams = d.SERVING_GRAMS[name]
    return "eggs" if d.PRICE_UNIT[name] == "piece" else "g" if grams == 1 else f"× {grams} g"

# (tab name, page title, one-line description)
PAGES = [
    ("Menu", "Cheapest menu",
     "The meals you're planning, for the settings on the left, most expensive food first."),
    ("Nutrition", "Nutrition check",
     "The totals N x, a linear combination of the food columns, against every goal for the meals "
     "you're planning."),
    ("Foods", "Foods and prices",
     "Turn foods on or off and set prices to match your market. The menu updates as you type."),
    ("Limits", "Nutrition limits",
     "The daily minimum and maximum for each nutrient. Leave a box empty for no limit."),
    ("Why", "What drives the cost",
     "Prices from the mirror problem (for the meals you're planning): how the cost reacts when a limit "
     "or a price moves."),
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
    ("dl", [("Menu", "foods, amounts and costs. Pick 1, 3 or 7 days to shop for, tick the circle when "
                     "you've bought a food, and click a food to edit its price."),
            ("Nutrition", "each total checked against its limits."),
            ("Foods", "turn foods on or off, search, and edit prices and daily maximums. −10% and +10% "
                      "change every price at once."),
            ("Limits", "edit minimums and maximums. Leave a box empty for no limit."),
            ("Why", "which limits push the cost up, and how much cheaper an unused food "
                    "would need to be."),
            ("Variety", "what a more varied menu costs, for every group. Click a point or a row to "
                        "use that setting."),
            ("Solver steps", "every pivot the simplex method makes."),
            ("Guide", "this page. The explorer on the right shows the method on a 2-food problem: step "
                      "through every pair of lines with the slider and see Cramer's rule worked out, slide the "
                      "cost line, change the prices, or click a menu to check it. Switch to “Our paper” to "
                      "show the paper's Figure 1.")]),
    ("h", "How the math works"),
    ("ol", ["Foods are vectors. Each food's nutrition label is a column of the matrix N.",
            "A menu is a vector x of servings (100 g as bought). The day's totals are the product N x, "
            "a linear combination of the food columns. The cost is the dot product c · x.",
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
    ("h", "Meals and budget"),
    ("ol", ["Planning m of the day's meals is the share f = m ÷ (meals a day) of the day. Planning 1 of 3 "
            "meals is f = ⅓. Every goal, minimums and maximums alike, and every serving cap is multiplied "
            "by f.",
            "The solver then finds the cheapest food that meets those smaller goals. The Menu, Nutrition, "
            "Why and Solver steps pages all show the planned meals.",
            "The answer comes out as f times the whole day's menu, x_plan = f · x_day, costing "
            "f · (c · x_day), because N x and c · x are linear. The solver still finds it on its own, "
            "which is a good check that it is right.",
            "The budget is checked against that cost. It is not added as a limit, so being on budget "
            "never means missing a goal. If the budget is short, the solver's guaranteed minimum h · y "
            "proves that nothing cheaper meets every goal."]),
    ("h", "Words you will see"),
    ("dl", [("Serving", "100 g of a food as bought, peel and bones included (egg: 1 egg)."),
            ("Edible share", "the part of a food you can eat. The nutrition counts only that part, so "
                             "100 g of whole tilapia gives 37 g of fish."),
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
    ("p", "With these market foods, calcium is the limit that drives the cost for every group: few "
          "of them are rich in it. The Why page shows the price of each limit."),
    ("h", "Where the prices and nutrition come from"),
    ("dl", [("Prices", f"World Food Programme retail prices for {PRICE_SOURCE}, per kg as bought "
                       "(eggs: each). Every food in the program is in that data."),
            ("Nutrition", "USDA SR28, raw food, per 100 g of the edible part. Edible shares come from "
                          "SR28, and for whole fish from the FAO (1989).")]),
    ("h", "Good to know"),
    ("p", "Amounts are what to buy, weighed as sold. At the market you can ask for “₱20 worth” "
          "and let the vendor weigh it: the menu works in any amount, not only whole servings."),
    ("p", "Raw food holds little sodium. With plants only, the 500 mg sodium minimum can't be met "
          "together with the other limits, so Plant-based shows no menu. Clear the sodium minimum on "
          "the Limits page to see one."),
    ("p", "Nutrition is for raw food. Cooking loses some vitamin C, and cooking fuel and oil are "
          "not counted. This is for coursework, not medical advice."),
    ("h", "Shortcuts"),
    ("dl", [("Ctrl+1 to Ctrl+8", "switch pages, in the order of the tabs."),
            ("Alt+1, Alt+2, Alt+3", "set the meals a day to 1, 2 or 3."),
            ("← and →", "move the Guide explorer's vertex slider one pair at a time when it has focus."),
            ("Esc", "clear the food search.")]),
]

# How the planned share of the day is written in labels
SHARE_TEXT = {(1, 2): "½", (1, 3): "⅓", (2, 3): "⅔"}
BUDGET_PERIODS = (("plan", "the meals I'm planning", 1), ("week", "a week", 7), ("month", "a month", 30))
PERIOD_DAYS = {key: days for key, _, days in BUDGET_PERIODS}


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
                 track=SUNKEN, chosen=SURFACE):
        self.options, self.variable, self.command = list(options), variable, command
        self.stretch, self.track, self.hot, self.pad, self.chosen = stretch, track, None, pad, chosen
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

    def set_options(self, options):
        """Replace the options (for example when the meals a day change)."""
        self.options, self.hot = list(options), None
        self.natural = [UI.font["strong"].measure(label) + 2 * self.pad for _, label in self.options]
        self.configure(width=sum(self.natural) + 2 * px(4))
        self.paint()

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
            if chosen:                                   # lime only for the page tabs, as on the slides
                UI.paint.rect(self, a, inset, b, h - inset, px(7), self.chosen,
                              BORDER if self.chosen == SURFACE else self.chosen)
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

    def __init__(self, parent, pad=18, fill=SURFACE, line=BORDER, radius=18):
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
        self.title = tk.Label(words, text=title, font=UI.font["h3"], fg=TEXT, bg=self.fill, anchor="w")
        self.title.pack(fill="x")
        self.subtitle = None
        if subtitle:
            self.subtitle = wrapping_label(words, subtitle, UI.font["small"], MUTED, self.fill)
            self.subtitle.pack(fill="x")
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
        self.footer_rows, self.click_x = 1, 0          # footer height in rows; x of the last click
        self.scroll_canvas = self
        self.bind("<Configure>", lambda e: self.redraw())
        if on_click:
            self.bind("<Motion>", lambda e: self._set_hover(self._index(e)))
            self.bind("<Leave>", lambda e: self._set_hover(None))
            self.bind("<Button-1>", self._click)

    def show(self, rows, footer=None, empty=None, footer_rows=1, keep_scroll=False):
        self.rows, self.footer, self.hover, self.footer_rows = rows, footer, None, footer_rows
        self.empty = empty or self.empty
        if not keep_scroll:
            self.yview_moveto(0)
        self.redraw()

    def _rh(self):
        n = len(self.rows) + (self.footer_rows if self.footer is not None else 0)
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
        self.click_x = self.canvasx(e.x)
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
            self.draw_footer(self, self.footer, pad, y, w - pad, rh * self.footer_rows)
            y += rh * self.footer_rows
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
        self.meals = tk.IntVar(value=3)              # meals eaten a day
        self.planned = tk.IntVar(value=3)            # how many of them are planned and bought for
        self.budget = tk.StringVar()                 # empty = no budget
        self.budget_period = tk.StringVar(value="plan")
        self.shop_days = tk.IntVar(value=1)          # the Menu page's "shop for" days
        self.bought = set()                          # foods ticked on the shopping checklist
        self.result = None                           # (problem, solution, planned limits, daily limits)
        self.budget_options = None                   # cached numbers for "What your budget can do"
        self._meals_before = 3
        self.on = {name: tk.BooleanVar(value=True) for name in FOOD_NAMES}
        self.price = {name: tk.StringVar(value=f"{MARKET_PRICE[name]:g}") for name in FOOD_NAMES}
        self.own_max = {name: tk.StringVar(value=f"{OWN_MAX[name]:g}") for name in FOOD_NAMES}
        self.limit_vars = [(tk.StringVar(), tk.StringVar()) for _ in d.NUTRIENTS]
        self.page = tk.StringVar(value="Menu")
        self.search = tk.StringVar()
        self.food_filter = tk.StringVar(value="all")
        self._filling, self._pending, self.menu_text = False, None, ""
        self._scaling = False                     # True while −10% / +10% rewrite the price boxes
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
        for m in (1, 2, 3):
            for mod in ("Alt", "Option"):              # Option is the Alt key on a Mac
                try:
                    self.bind(f"<{mod}-Key-{m}>", lambda e, m=m: self.set_meals(m))
                except tk.TclError:
                    pass
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel)
        self.bind("<Configure>", self._resized)

        self.fill_limits("Adult woman")
        for var in self.price.values():
            var.trace_add("write", lambda *_: self._price_typed())
        for var in self.own_max.values():
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
        self.budget.trace_add("write", lambda *_: self.show_budget())          # never re-solves
        self.budget_period.trace_add("write", lambda *_: self.show_budget())
        self._group_note()
        self._variety_note()
        self._meals_note()
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

        # Page titles use a heavy black face, like the project slides
        heavy = "Arial Black" if "Arial Black" in families else None

        def display(size):
            return tkfont.Font(self, family=heavy, size=size) if heavy else font(size, True)

        UI.font = dict(body=font(10), small=font(9), tiny=font(8), strong=font(10, True),
                       small_strong=font(9, True), label=font(8, True), h1=display(16),
                       h2=font(13, True), h3=font(11, True), kpi=font(21, True), brand=font(13, True),
                       mono=font(10, family=mono), mono_small=font(9, family=mono))
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
        # Sliders (Guide explorer): a thin light track and a dark-green handle
        s.configure("App.Horizontal.TScale", troughcolor=TRACK, background=ACCENT, bordercolor=TRACK,
                    lightcolor=ACCENT, darkcolor=ACCENT, troughrelief="flat", sliderrelief="flat",
                    sliderlength=px(16), sliderthickness=px(16), gripcount=0)
        s.map("App.Horizontal.TScale", background=[("active", ACCENT_HOVER)])
        s.map("Clean.Treeview", background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", ACCENT_TEXT)])

    def _icon(self):
        """The app mark: a plate with an egg on a lime tile, as on the slides. Window icon and left panel."""
        def mark(size):
            k = 4
            n = size * k
            img = Image.new("RGBA", (n, n), rgba(LIME, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((0, 0, n - 1, n - 1), radius=n * 0.26, fill=rgba(LIME))
            # plate rim, plate, egg white, yolk
            for frac, color in ((0.36, "#FFFFFF"), (0.30, "#F3F1E8"), (0.17, "#FFFFFF"), (0.085, "#F6B12D")):
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
        # The panel scrolls when it is taller than the window. The scrollbar column (14 px) sits
        # inside the right padding, so the content keeps its 248 px width.
        scroll = Scroll(side)
        scroll.pack(fill="both", expand=True, padx=(px(22), px(8)), pady=(px(22), px(18)))
        box = scroll.inner

        brand = tk.Frame(box, bg=SURFACE)
        brand.pack(fill="x")
        tk.Label(brand, image=self._mark, bg=SURFACE).pack(side="left", padx=(0, px(12)))
        names = tk.Frame(brand, bg=SURFACE)
        names.pack(side="left")
        tk.Label(names, text="Diet Optimizer", font=UI.font["brand"], fg=TEXT, bg=SURFACE).pack(anchor="w")
        tk.Label(names, text="Math 2138 · Linear Algebra", font=UI.font["small"], fg=MUTED,
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

        self._section(box, "Meals and budget")
        self._field_label(box, "Meals a day")
        Segmented(box, [(m, str(m)) for m in (1, 2, 3)], self.meals, command=self.meals_chosen,
                  stretch=True, height=34, pad=8, track=TRACK).pack(fill="x")
        self._field_label(box, "Plan for")
        self.plan_seg = Segmented(box, self._plan_options(), self.planned, command=self.planned_chosen,
                                  stretch=True, height=34, pad=8, track=TRACK)
        self.plan_seg.pack(fill="x")
        self.meals_info = tk.Label(box, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE,
                                   justify="left", anchor="w", wraplength=px(244))
        self.meals_info.pack(fill="x", pady=(px(8), 0))
        self.extras.append((self.meals_info, dict(fill="x", pady=(px(8), 0), after=self.plan_seg)))

        self._field_label(box, "Budget")
        cell = tk.Frame(box, bg=SURFACE)
        cell.pack(fill="x")
        tk.Label(cell, text="₱", font=UI.font["body"], fg=MUTED, bg=SURFACE).pack(side="left", padx=(0, px(4)))
        self.budget_entry = ttk.Entry(cell, textvariable=self.budget, width=10, font=UI.font["body"])
        self.budget_entry.pack(side="left")
        self._field_label(box, "Budget is for")
        # Radio rows rather than a segmented track: "the meals I'm planning" is too wide for
        # three options side by side in this panel.
        for key, label, _ in BUDGET_PERIODS:
            Choice(box, label, self.budget_period, key, radio=True).pack(fill="x", pady=(0, px(6)))
        self.budget_info = tk.Label(box, text="", font=UI.font["small"], fg=MUTED, bg=SURFACE,
                                    justify="left", anchor="w", wraplength=px(244))
        self.budget_info.pack(fill="x", pady=(px(2), px(16)))

        source = tk.Label(box, text=f"Prices: WFP market data, {PRICE_SOURCE}. Nutrition: USDA SR28, raw "
                                    "food. For coursework, not medical advice.", font=UI.font["tiny"], fg=SUBTLE,
                          bg=SURFACE, justify="left", wraplength=px(244))
        source.pack(side="bottom", anchor="w")
        self.extras.append((source, dict(side="bottom", anchor="w")))     # hidden on short windows

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
        v = self.variety.get()
        self.variety_info.configure(text=f"At most {v} servings of any one food: {v * 100} g as bought, "
                                         f"or {v} eggs.")

    def _field_label(self, parent, text):
        tk.Label(parent, text=text, font=UI.font["small_strong"], fg=TEXT_2, bg=SURFACE).pack(
            anchor="w", pady=(px(12), px(6)))

    # ------------------------------------------------------------------ meals: words for the plan
    def share(self):
        """f = planned meals ÷ meals a day, the share of the day being planned."""
        return self.planned.get() / self.meals.get()

    def whole_day(self):
        return self.planned.get() == self.meals.get()

    def plan_words(self):
        """'1 meal', '2 meals' or 'the whole day'."""
        k = self.planned.get()
        return "the whole day" if self.whole_day() else f"{k} meal{'s' if k > 1 else ''}"

    def share_text(self):
        """'⅓', '⅔' or '½'."""
        return SHARE_TEXT.get((self.planned.get(), self.meals.get()), f"{self.share():.2f}")

    def _plan_options(self):
        m = self.meals.get()
        return [(k, f"{k} meal{'s' if k > 1 else ''}") for k in range(1, m)] + [(m, "Whole day")]

    def _meals_note(self):
        if self.whole_day():
            text = "Planning the whole day: the full daily goals."
        else:
            text = (f"Planning {self.planned.get()} of {self.meals.get()} meals: every goal is "
                    f"{self.share_text()} of the day's.")
        self.meals_info.configure(text=text)

    def set_meals(self, m):
        """Alt+1, Alt+2, Alt+3."""
        self.meals.set(m)
        self.meals_chosen()

    def meals_chosen(self):
        m, before = self.meals.get(), self._meals_before
        self._meals_before = m
        if self.planned.get() == before or self.planned.get() > m:
            self.planned.set(m)               # "Whole day" stays the whole day; never plan more than m
        self.plan_seg.set_options(self._plan_options())
        self.planned_chosen()

    def planned_chosen(self):
        self._meals_note()
        self.solve()

    # ------------------------------------------------------------------ top of the main area
    def _topbar(self, main):
        bar = tk.Frame(main, bg=BG)
        bar.pack(fill="x")
        Segmented(bar, [(n, n) for n in self.page_names], self.page, pad=11, track=BG, chosen=LIME,  # nav, as on the slides
                  command=lambda: self.show_page(self.page.get())).pack(side="left")
        self.copy_btn = Button(bar, "Copy menu", self.copy_menu, kind="primary", height=38,
                               other_texts=("Copied ✓",))
        self.copy_btn.pack(side="right")
        Button(bar, "Reset all", self.reset, kind="ghost", height=38).pack(side="right", padx=(0, px(6)))

    def _tiles(self, main):
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x", pady=(px(20), 0))
        self.tile_row, self.tiles, self.tile_labels = row, {}, {}
        for i, (key, label) in enumerate((("cost", "Daily cost"), ("meal", "Per meal"),
                                          ("foods", "Foods on the menu"), ("targets", "Targets met"),
                                          ("budget", "Budget"))):
            row.columnconfigure(i, weight=1, uniform="tile")
            fill = SURFACE
            card = Card(row, pad=14)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else px(14), 0))
            self.tile_labels[key] = tk.Label(card.body, text=label.upper(), font=UI.font["label"], fg=MUTED,
                                             bg=fill)
            self.tile_labels[key].pack(anchor="w")
            value = tk.Label(card.body, text="–", font=UI.font["kpi"], fg=TEXT, bg=fill)
            value.pack(anchor="w", pady=(px(2), 0))
            if key == "budget":                      # a thin meter: cost against the budget
                self.budget_meter = tk.Canvas(card.body, bg=fill, highlightthickness=0, bd=0, width=1,
                                              height=px(10))
                self.budget_meter.pack(fill="x", pady=(px(2), px(2)))
                self.budget_meter.bind("<Configure>", lambda e: self._draw_meter())
            note = tk.Label(card.body, text="", font=UI.font["small"], fg=MUTED, bg=fill, justify="left")
            note.pack(anchor="w")
            self.extras.append((note, dict(anchor="w")))
            self.tiles[key] = (value, note)
        self._meter = None                           # (cost, budget) the meter shows
        row.bind("<Configure>", lambda e: self._fit_tiles())

    def _fit_tiles(self):
        """Five tiles share the row: use a smaller value font when the largest value would not fit."""
        width = self.tile_row.winfo_width()
        if width < 50:
            return
        room = (width - 4 * px(14)) / 5 - 2 * px(14) - px(4)
        texts = [value.cget("text") for value, _ in self.tiles.values()]
        font = next((UI.font[k] for k in ("kpi", "h1", "h2")
                     if max(UI.font[k].measure(t) for t in texts) <= room), UI.font["h3"])
        for value, note in self.tiles.values():
            if value.cget("font") != str(font):
                value.configure(font=font)
            note.configure(wraplength=max(int(room), 60))
        for label in self.tile_labels.values():
            label.configure(wraplength=max(int(room), 60))

    def _draw_meter(self):
        """Track, a fill for the cost and a tick at the budget, like the range bars on Nutrition."""
        cv = self.budget_meter
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or self._meter is None:
            return
        cost, budget = self._meter
        top = max(cost, budget) * 1.1 or 1.0
        t, cy = px(6), h / 2
        UI.paint.rect(cv, 0, cy - t / 2, w, cy + t / 2, t // 2, TRACK)
        fill_to = w * min(cost / top, 1)
        if fill_to >= t:
            UI.paint.rect(cv, 0, cy - t / 2, fill_to, cy + t / 2, t // 2, GOOD if budget >= cost - 1e-9 else CORAL)
        x = w * min(budget / top, 1)
        cv.create_line(x, 0, x, h, fill=TEXT_2, width=px(2))

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
        body, actions = self._page("Menu")
        tk.Label(actions, text="Shop for", font=UI.font["small"], fg=MUTED, bg=BG).pack(side="left",
                                                                                       padx=(0, px(8)))
        Segmented(actions, ((1, "1 day"), (3, "3 days"), (7, "7 days")), self.shop_days,
                  command=self.show_shopping, height=34, pad=12).pack(side="left")
        body.columnconfigure(0, weight=3, uniform="menu")
        body.columnconfigure(1, weight=2, uniform="menu")
        body.rowconfigure(0, weight=1)
        left = Card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        left.header("Today's foods", "Click a food to change its price. Tick the circle when you've bought it.")
        self.menu_card = left
        self.menu_list = self._rows(left.body, self._draw_menu_row, px(56), draw_footer=self._draw_menu_total,
                                    on_click=self._menu_click, fit=True, min_row=px(44))
        right = Card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.header("Where the money goes", "Each slice is one food's share of the cost.")
        self.menu_fig, self.menu_ax, self.menu_canvas = self._chart(right.body)
        self.donut_card = right

        # Shown only when the budget is short, in the chart's place: settings that fit, from
        # numbers already computed
        self.budget_card = Card(body)
        self.budget_card.header("What your budget can do", "Settings that fit your budget.")
        # Wrap the long subtitle to the card's width, not the label's own: in this 3:2 column pair the
        # label's own width feeds back into the column width and the window never settles.
        subtitle = self.budget_card.subtitle
        subtitle.unbind("<Configure>")
        self.budget_card.body.bind("<Configure>", lambda e: subtitle.configure(wraplength=max(e.width - px(12), 80)),
                                   add="+")
        self.options_box = tk.Frame(self.budget_card.body, bg=SURFACE)      # shown only when a setting fits
        self.budget_list = self._rows(self.options_box, self._draw_option_row, px(54),
                                      on_click=self.use_budget_option)
        # The nutrition the budget buys: the cheapest menu scaled down to the budget
        self.afford_title = tk.Label(self.budget_card.body, text="", font=UI.font["strong"], fg=TEXT, bg=SURFACE,
                                     anchor="w")
        self.afford_title.pack(fill="x", pady=(0, px(2)))
        self.afford_note = wrapping_label(self.budget_card.body, "", UI.font["small"], MUTED, SURFACE)
        self.afford_note.pack(fill="x", pady=(0, px(6)))
        self.extras.append((self.afford_note, dict(fill="x", pady=(0, px(6)), after=self.afford_title)))
        self.afford_list = self._rows(self.budget_card.body, self._draw_afford_row, px(46), fit=True,
                                      min_row=px(32))

    def _nutrition_page(self):
        body, _ = self._page("Nutrition")
        card = Card(body)
        card.pack(fill="both", expand=True)
        right = card.header("Daily totals", "Each dot is the day's total. It must sit inside the green range.")
        self.nut_card = card
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

    FOOD_COLUMNS = ((52, 0), (170, 1), (104, 0), (138, 0), (118, 0), (112, 0))   # (min width, weight)

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
        Button(tools, "+10%", lambda: self.scale_prices(1.1), height=34).pack(side="right", padx=(0, px(16)))
        Button(tools, "−10%", lambda: self.scale_prices(0.9), height=34).pack(side="right", padx=(0, px(8)))
        self.scale_note = wrapping_label(card.body, "Every price scaled by the same number: the cost scales "
                                                    "too, but the menu stays the same.",
                                         UI.font["small"], ACCENT_TEXT, SURFACE)
        self._scale_note_after = tools

        wrapping_label(card.body, f"Prices: World Food Programme retail prices, {PRICE_SOURCE}, per kg as "
                                  "bought (eggs: each). Under each food is its name in the WFP data.",
                       UI.font["small"], MUTED, SURFACE).pack(fill="x", pady=(0, px(14)))

        head = tk.Frame(card.body, bg=SURFACE)
        head.pack(fill="x", padx=(0, px(20)))
        self._columns(head)
        for col, text in enumerate(("Use", "Food", "Type", "Market price", "Most a day", "Today")):
            tk.Label(head, text=text.upper(), font=UI.font["label"], fg=MUTED, bg=SURFACE).grid(
                row=0, column=col, sticky="w", pady=(0, px(8)))
        tk.Frame(card.body, bg=BORDER, height=1).pack(fill="x")

        scroll = Scroll(card.body)
        scroll.pack(fill="both", expand=True)
        inner = scroll.inner
        inner.columnconfigure(0, weight=1)
        self.food_rows = {}
        for r, name in enumerate(FOOD_NAMES):
            row = tk.Frame(inner, bg=SURFACE)
            row.grid(row=r, column=0, sticky="ew")
            self._columns(row)
            Toggle(row, self.on[name]).grid(row=0, column=0, sticky="w", pady=px(11))
            words = tk.Frame(row, bg=SURFACE, cursor="hand2")
            words.grid(row=0, column=1, sticky="w")
            label = tk.Label(words, text=name, font=UI.font["strong"], fg=TEXT, bg=SURFACE, cursor="hand2")
            label.pack(anchor="w")
            note = tk.Label(words, text=f"WFP: {d.COMMODITY[name]}", font=UI.font["small"], fg=MUTED,
                            bg=SURFACE, cursor="hand2")
            note.pack(anchor="w")
            for w in (words, label, note):
                w.bind("<Button-1>", lambda e, n=name: self.on[n].set(not self.on[n].get()))
            Badge(row, KIND_NAMES[KIND_OF[name]]).grid(row=0, column=2, sticky="w")
            cell = tk.Frame(row, bg=SURFACE)
            cell.grid(row=0, column=3, sticky="w")
            tk.Label(cell, text="₱", font=UI.font["body"], fg=MUTED, bg=SURFACE).pack(side="left", padx=(0, px(4)))
            price = ttk.Entry(cell, textvariable=self.price[name], width=7, font=UI.font["body"])
            price.pack(side="left")
            tk.Label(cell, text=price_unit(name), font=UI.font["small"], fg=MUTED, bg=SURFACE).pack(
                side="left", padx=(px(4), 0))
            most = tk.Frame(row, bg=SURFACE)
            most.grid(row=0, column=4, sticky="w")
            own = ttk.Entry(most, textvariable=self.own_max[name], width=5, font=UI.font["body"])
            own.pack(side="left")
            tk.Label(most, text=max_unit(name), font=UI.font["small"], fg=MUTED, bg=SURFACE).pack(
                side="left", padx=(px(4), 0))
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
        self.limits_note = wrapping_label(card.body, "", UI.font["body"], TONES["info"][1], SURFACE)
        # The table scrolls, so every row stays reachable on a short window
        scroll = Scroll(card.body)
        scroll.pack(fill="both", expand=True)
        self._limits_table = scroll
        table = tk.Frame(scroll.inner, bg=SURFACE)
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
        caps.header("Variety caps that bind", "Foods held back by the variety level or their own daily maximum.")
        self.why_caps = self._rows(caps.body, self._draw_cap_row, px(52), fit=True, min_row=px(44),
                                on_click=lambda row: self.focus_food(row[1]))
        missed = Card(body)
        missed.grid(row=0, column=1, rowspan=2, sticky="nsew")
        missed.header("Foods that just missed out",
                      "Reduced costs: how much cheaper each food would need to be to join the menu. "
                      "Click one to edit its price.")
        self.why_missed = self._rows(missed.body, self._draw_missed_row, px(58), fit=True, min_row=px(46),
                                  on_click=lambda row: self.focus_food(row[2]))

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
        left.header("Cheapest day at each variety level (whole day)",
                    "One line per group, using your eating style, prices and foods. "
                    "Your setting is circled. Click any point to switch to it.")
        # Packed before the chart so that on a short window the chart shrinks, not this note
        note = wrapping_label(left.body, "This chart is figure 5 of the report. python diet_optimizer.py "
                                         "--plots saves it with the unedited market prices.",
                              UI.font["small"], SUBTLE, SURFACE)
        note.pack(side="bottom", fill="x", pady=(px(8), 0))
        self.extras.append((note, dict(side="bottom", fill="x", pady=(px(8), 0))))
        self.variety_fig, self.variety_ax, self.variety_canvas = self._chart(left.body)
        self.variety_canvas.mpl_connect("button_press_event", self._variety_click)
        self.variety_canvas.mpl_connect("motion_notify_event", self._variety_hover)
        self._variety_stale, self._variety_costs, self._variety_current = True, {}, None
        self._variety_redraw = False                 # the chart needs redrawing (the budget line moved)

        right = Card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.header("Your cost at each level", "Compared with your current setting. Click a row to switch to it.")
        self.level_list = self._rows(right.body, self._draw_level_row, px(54), fit=True, min_row=px(40),
                                     on_click=lambda row: self.use_setting(row[3], row[0]))

    def _guide_page(self):
        body, actions = self._page("Guide")
        body.columnconfigure(0, weight=1, uniform="guide")          # the explorer gets the wider column
        body.columnconfigure(1, weight=2, uniform="guide")
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

        self._explorer(body, actions)

    # ------------------------------------------------------------------ Guide explorer (the two-food example)
    EXAMPLES = (("round", "Round numbers"), ("paper", "Our paper (Figure 1)"))
    EXPLORER_TABS = (("vertices", "Vertices"), ("cost", "Cost line"), ("prices", "Prices"))

    def _label(self, parent, text="", font="small", fg=MUTED, wrap_to=None):
        """A label; with `wrap_to`, it wraps to that frame's width (never its own, which can loop)."""
        label = tk.Label(parent, text=text, font=UI.font[font], fg=fg, bg=SURFACE, anchor="w", justify="left")
        if wrap_to is not None:
            wrap_to.bind("<Configure>", lambda e: label.configure(wraplength=max(e.width - px(6), 80)), add="+")
        return label

    def _explorer(self, body, actions):
        """The two-food example as an explorer: every vertex, the cost line, prices and clicked menus."""
        self.ex_example = tk.StringVar(value="round")
        self.ex_tab = tk.StringVar(value="vertices")
        self.ex_pair = tk.DoubleVar(value=1)
        self.ex_cost = tk.DoubleVar(value=0)
        self.ex_rice = tk.DoubleVar(value=10)
        self.ex_egg = tk.DoubleVar(value=10)
        self.ex_point, self._play_job, self._ex_quiet = None, None, False
        self._paper = d.paper_example()

        tk.Label(actions, text="Example", font=UI.font["small"], fg=MUTED, bg=BG).pack(side="left", padx=(0, px(8)))
        Segmented(actions, self.EXAMPLES, self.ex_example, command=self.ex_reset, height=34, pad=12).pack(side="left")

        card = Card(body)
        card.grid(row=0, column=1, sticky="nsew")
        right = card.header("See it in two dimensions", "An illustration, not your menu: the same method on a "
                                                        "problem with only rice and eggs, small enough to draw.")
        self.ex_card, inner = card, card.body
        sub = card.subtitle                                # wrap to the card, not the label (see the budget card)
        sub.unbind("<Configure>")
        inner.bind("<Configure>", lambda e: sub.configure(wraplength=max(e.width - px(280), 80)), add="+")
        self.extras.append((sub, dict(fill="x")))
        # One control group at a time keeps the chart large: Vertices, Cost line or Prices
        Segmented(right, self.EXPLORER_TABS, self.ex_tab, command=self.ex_show_tab, height=32, pad=12,
                  track=TRACK).pack()

        # Packed bottom-up before the chart, so on a short window the chart shrinks, not the controls
        self.ex_note = self._label(inner, fg=SUBTLE, wrap_to=inner)
        self.ex_note.pack(side="bottom", fill="x", pady=(px(6), 0))
        self.ex_solver = self._label(inner, wrap_to=inner)
        self.ex_solver.pack(side="bottom", fill="x", pady=(px(2), 0))
        self.extras.append((self.ex_note, dict(side="bottom", fill="x", pady=(px(6), 0), before=self.ex_solver)))
        self.ex_click = self._label(inner, "Click anywhere on the chart to check that menu.", "small", MUTED,
                                    wrap_to=inner)
        self.ex_click.pack(side="bottom", fill="x", pady=(px(6), 0))

        panels = tk.Frame(inner, bg=SURFACE)
        panels.pack(side="bottom", fill="x", pady=(px(8), 0))
        self.ex_panels = {key: tk.Frame(panels, bg=SURFACE) for key, _ in self.EXPLORER_TABS}
        self._vertex_panel(self.ex_panels["vertices"], inner)
        self._cost_panel(self.ex_panels["cost"], inner)
        self._price_panel(self.ex_panels["prices"], inner)

        # The chart, with the worked step beside it on the Vertices tab (the window is short, not narrow)
        stage = tk.Frame(inner, bg=SURFACE)
        stage.pack(fill="both", expand=True)
        self.ex_side = tk.Frame(stage, bg=SURFACE)
        self.ex_steps = tk.Text(self.ex_side, width=34, height=1, wrap="word", bg=TRACK, fg=TEXT, relief="flat",
                                bd=0, highlightthickness=0, padx=px(10), pady=px(8), font=UI.font["mono_small"],
                                cursor="arrow", spacing1=px(2))
        self.ex_steps.tag_configure("bad", foreground=DANGER)
        self.ex_steps.tag_configure("good", foreground=GOOD)
        self.ex_steps.pack(fill="both", expand=True)
        self.ex_side.pack(side="right", fill="y", padx=(px(12), 0))
        self.ex_fig, self.ex_ax, self.ex_canvas = self._chart(stage)
        self.ex_canvas.mpl_connect("button_press_event", self.ex_clicked)
        self.ex_canvas.mpl_connect("motion_notify_event", lambda e: self.ex_canvas.get_tk_widget().configure(
            cursor="hand2" if e.inaxes is self.ex_ax else ""))
        self.ex_reset()

    def _scale(self, parent, var, start, end, command):
        scale = ttk.Scale(parent, from_=start, to=end, variable=var, orient="horizontal", style="App.Horizontal.TScale",
                          command=command)
        return scale

    def _vertex_panel(self, box, inner):
        head = tk.Frame(box, bg=SURFACE)
        head.pack(fill="x")
        self._label(head, "Which two lines meet?", "small_strong", TEXT_2).pack(side="left")
        self.ex_badge = Badge(head)
        self.ex_badge.pack(side="right")
        row = tk.Frame(box, bg=SURFACE)
        row.pack(fill="x", pady=(px(6), px(6)))
        Button(row, "‹", lambda: self.ex_step_pair(-1), height=30).pack(side="left")
        self.ex_pair_scale = self._scale(row, self.ex_pair, 1, 6, self.ex_pair_moved)
        self.ex_pair_scale.pack(side="left", fill="x", expand=True, padx=px(8))
        Button(row, "›", lambda: self.ex_step_pair(1), height=30).pack(side="left")
        self.ex_pair_text = self._label(row, "", "small", MUTED)
        self.ex_pair_text.pack(side="left", padx=(px(10), 0))
        for key, step in (("<Left>", -1), ("<Right>", 1)):
            self.ex_pair_scale.bind(key, lambda e, s=step: (self.ex_step_pair(s), "break")[1])

    def _cost_panel(self, box, inner):
        head = tk.Frame(box, bg=SURFACE)
        head.pack(fill="x")
        self._label(head, "Slide the cost line", "small_strong", TEXT_2).pack(side="left")
        self.ex_play_btn = Button(head, "▶ Play", self.ex_play, height=28, other_texts=("■ Stop",))
        self.ex_play_btn.pack(side="right")
        row = tk.Frame(box, bg=SURFACE)
        row.pack(fill="x", pady=(px(6), px(6)))
        self.ex_cost_scale = self._scale(row, self.ex_cost, 100, 0, self.ex_cost_moved)
        self.ex_cost_scale.pack(side="left", fill="x", expand=True)
        self.ex_cost_value = self._label(row, "", "strong", TEXT)
        self.ex_cost_value.pack(side="left", padx=(px(10), 0))
        self.ex_cost_text = self._label(box, wrap_to=inner)
        self.ex_cost_text.pack(fill="x")

    def _price_panel(self, box, inner):
        self.ex_price_scales, self.ex_price_values = [], []
        for name, var in (("Rice price", self.ex_rice), ("Egg price", self.ex_egg)):
            row = tk.Frame(box, bg=SURFACE)
            row.pack(fill="x", pady=(0, px(6)))
            self._label(row, name, "small_strong", TEXT_2).pack(side="left")
            value = self._label(row, "", "small", TEXT)
            value.pack(side="right")
            scale = self._scale(row, var, 0.5, 30, lambda _v: self.ex_prices_moved())
            scale.pack(side="left", fill="x", expand=True, padx=px(10))
            self.ex_price_scales.append(scale)
            self.ex_price_values.append(value)
        self.ex_price_text = self._label(box, "", "strong", TEXT, wrap_to=inner)
        self.ex_price_text.pack(fill="x")
        row = tk.Frame(box, bg=SURFACE)
        row.pack(fill="x", pady=(px(2), 0))
        self._label(row, "The shaded region doesn't move: prices don't change which menus are valid, only "
                         "which corner is cheapest.", wrap_to=inner).pack(side="left", fill="x", expand=True)
        link = self._label(row, "Reset prices", "small_strong", ACCENT)
        link.configure(cursor="hand2")
        link.pack(side="right", anchor="n", padx=(px(8), 0))
        link.bind("<Button-1>", lambda e: self.ex_reset_prices())

    # ---- explorer state
    def ex_E(self):
        return d.EXAMPLE if self.ex_example.get() == "round" else self._paper

    def ex_prices(self):
        return [self.ex_rice.get(), self.ex_egg.get()]

    def ex_cheapest(self):
        """The valid vertices with the lowest cost c . v (two when they tie), and that cost."""
        corners = d.two_food_corners(self.ex_E())
        costs = [d.dot(self.ex_prices(), pt) for _, pt in corners]
        low = min(costs)
        return [(name, pt) for (name, pt), cost in zip(corners, costs) if abs(cost - low) < 0.005], low

    def _corner_name(self, point):
        for name, pt in d.two_food_corners(self.ex_E()):
            if abs(pt[0] - point[0]) < 1e-6 and abs(pt[1] - point[1]) < 1e-6:
                return name
        return None

    def ex_reset(self):
        """A fresh start for the chosen example: pair 1, its prices, the cost line at its top, no clicked menu."""
        self.ex_stop()
        E = self.ex_E()
        self._ex_quiet = True
        for scale, var, price in zip(self.ex_price_scales, (self.ex_rice, self.ex_egg), E["cost"]):
            scale.configure(from_=0.5, to=3 * price)
            var.set(price)
        self.ex_pair.set(1)
        self._ex_quiet = False
        self.ex_point = None
        paper = self.ex_example.get() == "paper"
        self.ex_card.subtitle.configure(
            text="The paper's Section 4.5: the teen boy's real rice and eggs. Compare with Figure 1 and Table 1."
            if paper else "An illustration, not your menu: the same method on a problem with only rice and eggs, "
                          "small enough to draw.")
        unit = E["foods"][0].split("(")[-1].rstrip(")")
        self.ex_note.configure(
            text=f"Each point is a menu ({unit} of rice, eggs); the shaded region meets both needs. "
                 + ("This is Figure 1 of our paper." if paper else "This picture is figure 6 of the report.")
                 + f" Your real menu has {len(d.FOODS)} foods, so its region can't be drawn.")
        self.ex_click.configure(text="Click anywhere on the chart to check that menu.", fg=MUTED)
        self._set_cost_range(reset=True)
        self.ex_show_tab()

    def ex_reset_prices(self):
        self._ex_quiet = True
        for var, price in zip((self.ex_rice, self.ex_egg), self.ex_E()["cost"]):
            var.set(price)
        self._ex_quiet = False
        self.ex_prices_moved()

    def _set_cost_range(self, reset=False):
        """The cost slider runs from the highest vertex cost plus 20% down to 0."""
        top = max(v["cost"] for v in d.two_food_vertices(self.ex_E(), self.ex_prices()) if v["valid"]) * 1.2
        self._ex_quiet = True
        self.ex_cost_scale.configure(from_=top, to=0)
        if reset or self.ex_cost.get() > top:
            self.ex_cost.set(top)
        self._ex_quiet = False
        self._cost_top = top

    def ex_show_tab(self):
        for key, frame in self.ex_panels.items():
            frame.pack_forget()
        self.ex_panels[self.ex_tab.get()].pack(fill="x")
        if self.ex_tab.get() == "vertices":
            self.ex_side.pack(side="right", fill="y", padx=(px(12), 0), before=self.ex_canvas.get_tk_widget())
        else:
            self.ex_side.pack_forget()
        if self.ex_tab.get() != "cost":
            self.ex_stop()
        self.ex_update()

    # ---- drawing and readouts (no diet solve here: only the 2 x 2 math and a 2-food simplex)
    def ex_update(self):
        E, prices, tab = self.ex_E(), self.ex_prices(), self.ex_tab.get()
        pair = int(round(self.ex_pair.get())) - 1
        self.ex_ax.clear()
        d.draw_two_food(self.ex_ax, E, prices=prices, pair=pair if tab == "vertices" else None,
                        cost_level=self.ex_cost.get() if tab == "cost" else None, point=self.ex_point,
                        top=14 if E is d.EXAMPLE else None)
        self.ex_canvas.draw_idle()
        self._ex_steps(pair)
        self._ex_cost_text()
        self._ex_price_text()
        self._ex_solver_text()

    def _ex_steps(self, pair):
        """The worked step for one pair of lines: the system, det, Cramer's rule, the check and the cost."""
        E, prices = self.ex_E(), self.ex_prices()
        v = d.two_food_vertices(E, prices)[pair]
        rice_unit = E["foods"][0].split("(")[-1].rstrip(")")

        def num(x):                                     # 3010 -> "3,010", 71.7288 -> "71.73", -6.3 -> "−6.30"
            text = f"{x:,.0f}" if abs(x - round(x)) < 0.005 else f"{x:,.2f}"
            return text.replace("-", "−")

        def tot(x):                                     # totals as in the paper: 3,010 or 819.7
            return f"{x:,.0f}" if abs(x - round(x)) < 0.05 else f"{x:,.1f}"

        def price(x):
            return f"{round(x, 3):g}"

        (a, b), (c, e) = v["M"]
        lines = [(f"Lines: {v['lines'][0]} & {v['lines'][1]}", None)]
        width = max(len(num(t)) for t in (a, b, c, e))
        for (m0, m1), r in zip(v["M"], v["rhs"]):
            lines.append((f"  {num(m0):>{width}} x₁ + {num(m1):>{width}} x₂ = {num(r)}", None))
        if v["point"] is None:
            lines.append(("det = 0: the lines are parallel and never meet", "bad"))
            self.ex_badge.update_badge("No meeting point", "neutral")
        else:
            x1, x2 = v["point"]
            lines.append((f"det = {num(a)}({num(e)}) − {num(b)}({num(c)}) = {num(v['det'])}", None))
            lines.append((f"x₁ = det(A₁) ÷ det = {num(x1)} {rice_unit} of rice", None))
            lines.append((f"x₂ = det(A₂) ÷ det = {num(x2)} eggs", None))
            checks = [f"{tot(t)} {unit} ≥ {num(n)} {'✓' if t >= n - 1e-9 else '✗'}"
                      for t, n, unit in zip(v["totals"], E["need"], ("kcal", "g"))]
            if min(v["point"]) < -1e-9:
                checks.append("x ≥ 0 ✗")
            name = self._corner_name(v["point"])
            verdict = f"→ valid vertex {name}" if v["valid"] else "→ not a valid vertex"
            lines.append(("Check: " + "   ".join(checks) + "   " + verdict, "good" if v["valid"] else "bad"))
            lines.append((f"Cost: {price(prices[0])}({num(x1)}) + {price(prices[1])}({num(x2)}) = ₱{v['cost']:.2f}",
                          None))
            cheapest, _ = self.ex_cheapest()
            if v["valid"] and any(n == name for n, _ in cheapest):
                self.ex_badge.update_badge("Cheapest vertex", "info")
            elif v["valid"]:
                self.ex_badge.update_badge("Valid vertex", "good")
            else:
                self.ex_badge.update_badge("Outside the region", "danger")
        self.ex_steps.configure(state="normal")
        self.ex_steps.delete("1.0", "end")
        for i, (text, tag) in enumerate(lines):
            self.ex_steps.insert("end", text + ("\n" if i < len(lines) - 1 else ""), tag or ())
        self.ex_steps.configure(state="disabled")
        self.ex_pair_text.configure(text=f"{pair + 1} of 6")

    def _ex_cost_text(self):
        level = self.ex_cost.get()
        cheapest, low = self.ex_cheapest()
        self.ex_cost_value.configure(text=f"₱{level:.2f}")
        names = " and ".join(name for name, _ in cheapest)
        if abs(level - low) < 0.005:
            text, color = f"₱{low:.2f}: the line just touches the region at {names}. This is the cheapest menu.", GOOD
        elif level > low:
            text, color = (f"₱{level:.2f}: this line crosses the shaded region, so some valid menus cost this much. "
                           "Keep sliding down."), TEXT_2
        else:
            text, color = (f"₱{level:.2f}: the line misses the region. No menu that meets both needs is this "
                           "cheap."), DANGER
        self.ex_cost_text.configure(text=text, fg=color)

    def _ex_price_text(self):
        for value, var in zip(self.ex_price_values, (self.ex_rice, self.ex_egg)):
            value.configure(text=f"₱{var.get():.2f}")
        cheapest, low = self.ex_cheapest()
        if len(cheapest) == 2:
            (a, _), (b, _) = cheapest
            text = f"Tie: {a} and {b} at ₱{low:.2f}. Every point on the edge between them is cheapest."
        else:
            name, (x, y) = cheapest[0]
            text = f"Cheapest: {name} ({x:.2f}, {y:.2f}) at ₱{low:.2f}"
        self.ex_price_text.configure(text=text)

    def _ex_solver_text(self):
        """The 2-food simplex on the mirror problem must land on the cheapest vertex's cost."""
        E = self.ex_E()
        r = d.simplex_max(E["need"], d.transpose(E["nutrition"]), self.ex_prices())
        _, low = self.ex_cheapest()
        x = r.slack_row
        same = abs(r.value - low) < 1e-6
        self.ex_solver.configure(
            text=f"Simplex on the mirror problem ({len(r.steps)} pivot{'s' if len(r.steps) != 1 else ''}) also "
                 f"finds ₱{r.value:.2f} at "
                 f"({x[0]:.2f}, {x[1]:.2f})." if same else
            f"Simplex found ₱{r.value:.2f}, but the cheapest vertex is ₱{low:.2f}. That is a bug.",
            fg=MUTED if same else DANGER)

    # ---- control callbacks
    def ex_pair_moved(self, value):
        """Snap the vertex slider to whole numbers."""
        if self._ex_quiet:
            return
        k = int(round(float(value)))
        if abs(self.ex_pair.get() - k) > 1e-9:
            self._ex_quiet = True
            self.ex_pair.set(k)
            self._ex_quiet = False
        if getattr(self, "_pair_shown", None) != k:
            self._pair_shown = k
            self.ex_update()

    def ex_step_pair(self, step):
        self.ex_pair.set(max(1, min(6, int(round(self.ex_pair.get())) + step)))
        self._pair_shown = int(self.ex_pair.get())
        self.ex_update()

    def ex_cost_moved(self, value):
        if self._ex_quiet:
            return
        self.ex_stop()
        _, low = self.ex_cheapest()
        if abs(float(value) - low) <= 0.5:                 # snap to the touching point
            self._ex_quiet = True
            self.ex_cost.set(low)
            self._ex_quiet = False
        self.ex_update()

    def ex_prices_moved(self):
        if self._ex_quiet:
            return
        self._set_cost_range()
        self.ex_update()

    def ex_play(self):
        """▶ Play: slide the cost line from the top down to the cheapest cost in about 2 seconds."""
        if self._play_job:
            return self.ex_stop()
        top, (_, low) = self._cost_top, self.ex_cheapest()
        self.ex_play_btn.set_text("■ Stop")

        def step(i):
            self._ex_quiet = True
            self.ex_cost.set(top - (top - low) * i / 40)
            self._ex_quiet = False
            self.ex_update()
            self._play_job = self.after(50, step, i + 1) if i < 40 else None
            if i >= 40:
                self.ex_play_btn.set_text("▶ Play")

        step(0)

    def ex_stop(self):
        if self._play_job:
            self.after_cancel(self._play_job)
            self._play_job = None
        if hasattr(self, "ex_play_btn"):
            self.ex_play_btn.set_text("▶ Play")

    def ex_clicked(self, event):
        """A clicked menu: its totals A v, its cost c . v, and which need it breaks."""
        if event.inaxes is not self.ex_ax or event.xdata is None:
            return
        self.ex_check_point(max(0.0, round(event.xdata, 1)), max(0.0, round(event.ydata, 1)))

    def ex_check_point(self, x, y):
        E = self.ex_E()
        self.ex_point = (x, y)
        kcal, protein = d.mat_vec(E["nutrition"], [x, y])
        cost = d.dot(self.ex_prices(), [x, y])
        broken = [what for what, t, n in zip(("calorie", "protein"), (kcal, protein), E["need"]) if t < n - 1e-9]
        verdict = ("Meets both needs." if not broken else
                   f"Breaks the {' and '.join(broken)} need{'s' if len(broken) > 1 else ''}.")
        self.ex_click.configure(text=f"({x:.1f} rice, {y:.1f} eggs): {kcal:,.0f} kcal, {protein:.1f} g protein, "
                                     f"₱{cost:.2f}. {verdict}", fg=GOOD if not broken else DANGER)
        self.ex_update()

    # ------------------------------------------------------------------ list rows (drawn on canvases)
    def _draw_menu_row(self, cv, row, x0, y, x1, h):
        name, amount, cost, share, color, bought = row
        cy, f = y + h / 2, UI.font
        # The check circle on the left ticks a food off the shopping list
        if bought:
            UI.paint.circle(cv, x0 + px(9), cy, px(9), ACCENT)
            cv.create_text(x0 + px(9), cy, text="✓", font=f["small_strong"], fill="#FFFFFF")
        else:
            UI.paint.circle(cv, x0 + px(9), cy, px(9), SURFACE, BORDER_STRONG, width=1.4)
        UI.paint.circle(cv, x0 + px(32), cy, px(5), BORDER_STRONG if bought else color)
        ink, sub = (SUBTLE, SUBTLE) if bought else (TEXT, MUTED)
        cv.create_text(x0 + px(46), cy - px(9), text=name, anchor="w", font=f["strong"], fill=ink)
        cv.create_text(x0 + px(46), cy + px(10), text="Bought" if bought else amount, anchor="w",
                       font=f["small"], fill=sub)
        cv.create_text(x1, cy - px(9), text=f"₱{cost:.2f}", anchor="e", font=f["strong"], fill=ink)
        cv.create_text(x1, cy + px(10), text=f"{share:.0%} of the cost", anchor="e", font=f["small"], fill=sub)

    def _draw_menu_total(self, cv, footer, x0, y, x1, h):
        """The total, with the budget line above it and the checklist line below it when they apply."""
        label, total, budget_line, bought_line = footer
        f = UI.font
        lines = ([("budget", budget_line)] if budget_line else []) + [("total", None)] + \
                ([("bought", bought_line)] if bought_line else [])
        heights = {"budget": px(22), "total": px(30), "bought": px(22)}
        cy = y + (h - sum(heights[k] for k, _ in lines)) / 2
        for kind, content in lines:
            mid = cy + heights[kind] / 2
            if kind == "total":
                cv.create_text(x0, mid, text=label, anchor="w", font=f["strong"], fill=TEXT)
                cv.create_text(x1, mid, text=f"₱{total:.2f}", anchor="e", font=f["h3"], fill=ACCENT)
            else:
                text, color = content
                cv.create_text(x0, mid, text=text, anchor="w", font=f["small"], fill=color, width=x1 - x0)
            cy += heights[kind]

    def _menu_click(self, row):
        """The check circle ticks a food as bought. The rest of the row opens its price."""
        if self.menu_list.click_x < px(10) + px(24):
            self.bought.symmetric_difference_update({row[0]})
            self.show_shopping(keep_scroll=True)
        else:
            self.focus_food(row[0])

    def _draw_option_row(self, cv, row, x0, y, x1, h):
        _, _, title, detail, cost = row
        cv.create_text(x1, y + h / 2, text="›", anchor="e", font=UI.font["h2"], fill=SUBTLE)
        self._two_lines(cv, x0, x1 - px(22), y + h / 2, title, detail, f"₱{cost:.2f} ✓", "fits your budget",
                        GOOD)

    def _draw_nut_row(self, cv, row, x0, y, x1, h):
        name, unit, total, lo, hi, status, day = row
        cy, f = y + h / 2, UI.font
        cv.create_text(x0, cy - px(9), text=name, anchor="w", font=f["strong"], fill=TEXT)
        need = cv.create_text(x0, cy + px(10), text="need " + need_text(lo, hi, unit), anchor="w",
                              font=f["small"], fill=MUTED)
        if day:                                      # the daily figure the goal was divided from
            cv.create_text(cv.bbox(need)[2] + px(4), cy + px(10), text=f"(day: {day})", anchor="w",
                           font=f["small"], fill=SUBTLE)
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
        when = "a day" if self.whole_day() else f"for {self.plan_words()}"
        self._two_lines(cv, x0, x1, cy, f"{name} {bound}", f"Raising it by 1 {unit} {effect} {money(value)} {when}",
                        money(value), f"per {unit}", CORAL)

    def _draw_cap_row(self, cv, row, x0, y, x1, h):
        value, name, cap = row
        self._two_lines(cv, x0, x1, y + h / 2, name, f"Held at its cap of {d.amount(name, cap)}",
                        money(value), f"saved per extra {serving_unit(name)}", TEXT_2)

    def _draw_missed_row(self, cv, row, x0, y, x1, h):
        _, reduced, name, price = row                  # both in market units: per kg, or per egg
        cy, unit = y + h / 2, price_unit(name)
        below = price - reduced
        detail = (f"Now ₱{price:.2f}{unit} · joins below ₱{below:.2f}{unit}" if below > 0.005 else
                  f"Now ₱{price:.2f}{unit} · would not join even if free")
        cv.create_text(x1, cy, text="›", anchor="e", font=UI.font["h2"], fill=SUBTLE)
        self._two_lines(cv, x0, x1 - px(22), cy, name, detail, f"₱{reduced:.2f}{unit}", "price cut needed",
                        TONES["warn"][1])

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

    def _price_typed(self):
        if not self._scaling and not self._filling:
            self.scale_note.pack_forget()           # the note is only true right after −10% / +10%
        self.schedule()

    def scale_prices(self, k):
        """−10% and +10%: multiply the price vector c by 0.9 or 1.1 (scalar multiplication)."""
        names = [n for n in FOOD_NAMES if number(self.price[n].get()) is not None]
        values = d.scale([number(self.price[n].get()) for n in names], k)       # k c
        self._scaling = True
        for name, v in zip(names, values):
            self.price[name].set(f"{v:g}")
        self._scaling = False
        self.scale_note.pack(fill="x", pady=(0, px(14)), after=self._scale_note_after)

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
        for name in FOOD_NAMES:
            self.on[name].set(True)
            self.price[name].set(f"{MARKET_PRICE[name]:g}")
            self.own_max[name].set(f"{OWN_MAX[name]:g}")
        self._filling = False
        self.diet.set("Anything")
        self.variety.set(4)
        self.meals.set(3)
        self._meals_before = 3
        self.planned.set(3)
        self.plan_seg.set_options(self._plan_options())
        self._meals_note()
        self.budget.set("")
        self.budget_period.set("plan")
        self.shop_days.set(1)
        self.scale_note.pack_forget()
        self.ex_example.set("round")                 # the Guide explorer: round example, pair 1
        self.ex_tab.set("vertices")
        self.ex_reset()
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
        prices = {n: number(self.price[n].get(), p) for n, p in MARKET_PRICE.items()}   # per kg or per egg
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
        if all(KIND_OF[n] in excluded_kinds or n in exclude for n in FOOD_NAMES):
            return self.no_menu("Every food is turned off or left out by the eating style. "
                                "Turn some on in Foods, or pick another eating style.")

        # Planning m of M meals: every daily goal AND every serving cap is multiplied by f = m / M.
        # The variety level and the foods' own maximums are per day, so a meal's cap is f times the
        # day's. Without that, one meal could use the whole day's allowance of the cheapest food.
        f = self.share()
        plan_limits = d.meal_limits(limits, f)
        plan_own_max = d.meal_caps(own_max, f)
        p = d.build_problem("Adult woman", diet, self.variety.get() * f, prices, exclude, plan_limits, plan_own_max)
        s = d.solve_diet(p)                             # the real solve, aimed at the divided goals
        self.bought.clear()
        if s is None:
            caps = [-v for v in p.h[len(p.h) - len(p.names):]]      # the last rows of h are -cap
            best = d.mat_vec(p.N, caps)                 # the most of each nutrient we could ever get
            hints = [f"{name} can't reach {fmt(lo)} {unit}" for (name, unit), (lo, _), b
                     in zip(d.NUTRIENTS, plan_limits, best) if lo is not None and b < lo - 1e-9]
            why = f" ({'; '.join(hints)})" if hints else ": each limit can be met alone, but not all at once"
            tip = (" With plants only, the sodium minimum is the usual cause: clear it on the Limits page."
                   if diet == "plant-based" else "")
            return self.no_menu("No menu meets every limit" + why + ". Try a higher variety level, "
                                "“Anything”, more foods, or a lower minimum." + tip)
        self.banner.pack_forget()
        self.result = (p, s, plan_limits, limits)
        self.budget_options = self._budget_options(p, s, diet, prices, exclude, own_max, plan_limits,
                                                   plan_own_max, limits)
        self.show_plan_labels()
        self.show_tiles(p, s, plan_limits)
        self.show_menu(p, s)
        self.show_nutrition(p, s, plan_limits, limits)
        self.show_foods(p, s)
        self.show_why(p, s)
        self.show_steps(p, s)
        self.show_budget()

    def _budget_options(self, p, s, diet, prices, exclude, own_max, plan_limits, plan_own_max, limits):
        """
        The numbers behind "What your budget can do", worked out once per solve and cached, so
        typing a budget only compares numbers. Each one uses math the program already has:
          fewer meals    k meals cost k × (cost per meal): the menu scales with the goals
          variety        the existing variety_costs (one group: these limits) times f
          Anything       one more solve with the same divided goals and caps
        """
        f = self.share()
        meal_cost = s.cost / self.planned.get()
        fewer = [(k, k * meal_cost) for k in range(self.planned.get() - 1, 0, -1)]
        days = d.variety_costs(diet, prices, exclude, own_max, {"current": limits}, self.VARIETIES)["current"]
        variety = [(v, f * cost) for v, cost in zip(self.VARIETIES, days)
                   if v != self.variety.get() and not math.isnan(cost)]
        anything = None
        if diet != "anything":
            other = d.solve_diet(d.build_problem("Adult woman", "anything", self.variety.get() * f, prices, exclude,
                                                 plan_limits, plan_own_max))
            anything = other.cost if other else None
        return dict(fewer=fewer, variety=variety, anything=anything)

    def no_menu(self, text):
        self.banner_text.configure(text=text)
        self.banner.pack(fill="x", pady=(px(16), 0), before=self.stack)
        self.menu_text, self.prev_cost, self.in_menu = "", None, {}
        self.result, self.budget_options = None, None
        self.bought.clear()
        self.show_plan_labels()
        value, note = self.tiles["cost"]
        value.configure(text="No menu", fg=DANGER)
        note.configure(text="see the message below", fg=MUTED)
        for key in ("meal", "foods", "targets"):
            self.tiles[key][0].configure(text="–", fg=TEXT)
            self.tiles[key][1].configure(text="")
        self.show_budget()
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
    def show_plan_labels(self):
        """Titles that say what is being planned: the whole day, 1 meal or 2 meals."""
        whole, k, m, words = self.whole_day(), self.planned.get(), self.meals.get(), self.plan_words()
        self.tile_labels["cost"].configure(text="DAILY COST" if whole else f"COST OF {words.upper()}")
        self.menu_card.title.configure(text="Today's foods" if whole else f"Foods for {words}")
        split = "" if whole or k < 2 else f"For {words}. Split each amount in half for each meal. "
        self.menu_card.subtitle.configure(text=split + "Click a food to change its price. Tick the circle when "
                                                       "you've bought it.")
        self.nut_card.title.configure(text="Daily totals" if whole else f"Totals for {words}")
        self.nut_card.subtitle.configure(
            text="Each dot is the day's total. It must sit inside the green range." if whole else
            f"Goals for {k} of {m} meals ({self.share_text()} of each daily limit). Each dot is the total "
            "for these meals. It must sit inside the green range.")
        if whole:
            self.limits_note.pack_forget()
        else:
            self.limits_note.configure(text=f"These are daily limits. You're planning {k} of {m} meals, so the "
                                            f"solver uses {self.share_text()} of each.")
            self.limits_note.pack(fill="x", pady=(0, px(12)), before=self._limits_table)

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

        k, m = self.planned.get(), self.meals.get()
        self.tiles["meal"][0].configure(text=f"₱{s.cost / k:.2f}", fg=TEXT)
        self.tiles["meal"][1].configure(text=f"1 of {m} meals" if k == 1 and m > 1 else
                                        "1 meal a day" if k == 1 else f"each of {k} meals")
        used = sum(x > 1e-6 for x in s.x)
        self.tiles["foods"][0].configure(text=str(used), fg=TEXT)
        self.tiles["foods"][1].configure(text=f"out of {len(p.names)} available")

        totals = d.mat_vec(p.N, s.x)                         # N x: the totals, against the planned goals
        limited = [(t, lo, hi) for t, (lo, hi) in zip(totals, limits) if lo is not None or hi is not None]
        met = sum((lo is None or t >= lo - 1e-6) and (hi is None or t <= hi + 1e-6) for t, lo, hi in limited)
        drivers = sum(v > 1e-7 and lab[0] != "cap" for v, lab in zip(s.y, p.labels))
        self.tiles["targets"][0].configure(text=f"{met} of {len(limited)}",
                                           fg=GOOD if met == len(limited) else DANGER)
        self.tiles["targets"][1].configure(text=f"{drivers} limit{'s' if drivers != 1 else ''} drive the cost"
                                           if drivers else "none is holding the cost up")
        self._fit_tiles()

    def show_menu(self, p, s):
        costs = [x * c for x, c in zip(s.x, p.c)]           # what each food adds to c . x
        used = [j for j in sorted(range(len(costs)), key=lambda j: -costs[j]) if s.x[j] > 1e-6]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(used))]
        self.menu_order = list(zip(used, colors))           # the list and the slices share colors
        self.show_shopping()

        ax = self.menu_ax
        ax.clear()
        ax.set_axis_off()
        if s.cost > 1e-9:
            ax.pie([costs[j] for j in used], colors=colors, startangle=90, counterclock=False,
                   wedgeprops=dict(width=0.3, edgecolor=SURFACE, linewidth=2.5))
        ax.set_aspect("equal")
        ax.text(0, 0.08, f"₱{s.cost:.2f}", ha="center", va="center", fontsize=18, fontweight="semibold",
                color=TEXT)
        ax.text(0, -0.16, "per day" if self.whole_day() else f"for {self.plan_words()}", ha="center",
                va="center", fontsize=9.5, color=MUTED)
        self.menu_canvas.draw_idle()

    def show_shopping(self, keep_scroll=False):
        """The Menu list: the planned menu times the days to shop for, with the checklist and budget line."""
        if self.result is None:
            return
        p, s = self.result[:2]
        days = self.shop_days.get()
        x = d.scale(s.x, days)                              # what to buy for `days` days
        costs = [xj * cj for xj, cj in zip(x, p.c)]
        total = d.dot(p.c, x)                               # c . x for those days
        share = total if total > 1e-9 else 1.0
        rows = [(p.names[j], f"Buy {d.amount(p.names[j], x[j])}", costs[j], costs[j] / share, color,
                 p.names[j] in self.bought) for j, color in self.menu_order]
        words = "the day" if self.whole_day() else self.plan_words()
        label = f"Total for {words}" if days == 1 else \
            f"Total for {days} days" + ("" if self.whole_day() else f" of {self.plan_words()}")
        bought = sum(row[2] for row in rows if row[5])
        bought_line = (f"Bought ₱{bought:.2f} · still to buy ₱{total - bought:.2f}", ACCENT_TEXT) \
            if self.bought else None
        budget_line = self._budget_line(s.cost, days)
        self.menu_list.show(rows, footer=(label, total, budget_line, bought_line),
                            footer_rows=1 + bool(budget_line or bought_line), keep_scroll=keep_scroll)

    def _budget_line(self, cost, days):
        """'Budget ₱70.00 · this meal ₱68.48 · every goal met ✓', or how short it is."""
        check = self.budget_status()
        if check is None:
            return None
        noun = "this day" if self.whole_day() else "this meal" if self.planned.get() == 1 else \
            f"these {self.planned.get()} meals"
        budget, spend = check.plan_budget, cost
        if self.budget_period.get() == "week" and days == 7:     # compare the week's total with the week's budget
            budget, spend, noun = self.budget_value(), 7 * cost, "7 days"
        if budget >= spend - 1e-9:
            return f"Budget ₱{budget:.2f} · {noun} ₱{spend:.2f} · every goal met ✓", GOOD
        cheapest = "the cheapest day" if self.whole_day() else "the cheapest meal" if self.planned.get() == 1 \
            else f"the cheapest {self.planned.get()} meals"
        if noun == "7 days":
            cheapest = "the cheapest 7 days"
        meets, verb = ("meets", "is") if cheapest.endswith(("day", "meal")) else ("meet", "are")
        return (f"Budget ₱{budget:.2f} · {cheapest} that {meets} the goals {verb} ₱{spend:.2f} · "
                f"₱{spend - budget:.2f} short", DANGER)

    def show_nutrition(self, p, s, limits, daily):
        """`limits` are the goals that were solved (divided for the plan); `daily` the Limits page's."""
        totals = d.mat_vec(p.N, s.x)                         # N x: the totals for the planned meals
        priced = {(k, n) for v, (k, n, _) in zip(s.y, p.labels) if v > 1e-7 and k != "cap"}
        rows = []
        for (name, unit), (lo, hi), t, (dlo, dhi) in zip(d.NUTRIENTS, limits, totals, daily):
            day = None
            if not self.whole_day() and (dlo is not None or dhi is not None):
                day = f"{fmt(dlo)} to {fmt(dhi)}" if dlo is not None and dhi is not None else fmt(
                    dlo if dlo is not None else dhi)
            if (lo is not None and t < lo - 1e-6) or (hi is not None and t > hi + 1e-6):
                status = "missed"
            elif ("min", name) in priced or ("max", name) in priced:
                status = "drives"
            elif (lo is not None and abs(t - lo) < 1e-6) or (hi is not None and abs(t - hi) < 1e-6):
                status = "limit"
            else:
                status = "met"
            rows.append((name, unit, t, lo, hi, status, day))
        self.nut_list.show(rows)

    def _food_status(self, name, servings):
        """The badge in the Today column of the Foods page."""
        if servings > 1e-6:
            return f"{d.amount(name, servings)} in menu", "good"
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
        rc = d.reduced_costs(p, s)                            # c_j - (column j of G) . y, per serving
        per = [d.PER_SERVING[name] for name in p.names]       # back to market units: per kg, or per egg
        missed = sorted((rc[j] / max(p.c[j], 1e-9), rc[j] / per[j], p.names[j], p.c[j] / per[j])
                        for j in range(len(p.names)) if s.x[j] <= 1e-6)[:8]    # smallest cut in percent first
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

    # ------------------------------------------------------------------ budget (compares cached numbers only)
    def budget_value(self):
        """The budget box as a number, or None when it is empty or not a number of zero or more."""
        text = self.budget.get().strip()
        return None if text == "" else number(text)

    def budget_status(self):
        """d.budget_check for the current menu, or None with no menu or no budget."""
        budget = self.budget_value()
        if self.result is None or budget is None:
            return None
        return d.budget_check(self.result[1].cost, budget, PERIOD_DAYS[self.budget_period.get()],
                              self.planned.get(), self.meals.get())

    def show_budget(self):
        """Everything that follows the budget box. Typing in it never re-solves."""
        text, budget = self.budget.get().strip(), self.budget_value()
        self.budget_entry.configure(style="TEntry" if text == "" or budget is not None else "Invalid.TEntry")
        period, days = self.budget_period.get(), PERIOD_DAYS[self.budget_period.get()]
        per = "for the whole day" if self.whole_day() else f"for {self.plan_words()} a day"
        if text == "":
            self.budget_info.configure(text="Leave it empty for no budget.", fg=MUTED)
        elif budget is None:
            self.budget_info.configure(text="Type a number of zero or more, or leave it empty.", fg=DANGER)
        elif period == "plan":
            self.budget_info.configure(text=f"₱{budget:,.2f} {per}", fg=MUTED)
        else:
            span = "a week" if period == "week" else "a month (30 days)"
            day = "a day" if self.whole_day() else f"a day for {self.plan_words()}"
            self.budget_info.configure(text=f"₱{budget:,.2f} {span} = ₱{budget / days:,.2f} {day}", fg=MUTED)

        check = self.budget_status()
        value, note = self.tiles["budget"]
        if self.result is None:
            value.configure(text="–", fg=TEXT)
            note.configure(text="")
        elif check is None:
            value.configure(text="Not set", fg=MUTED)
            note.configure(text="enter one in the left panel", fg=MUTED)
        elif check.fits:
            value.configure(text=f"₱{check.left:.2f} left", fg=GOOD)
            note.configure(text=f"goals met for {self.plan_words()}", fg=MUTED)
        else:
            covers = check.meals_covered
            value.configure(text=f"₱{-check.left:.2f} short", fg=DANGER)
            note.configure(text=f"covers {covers:.1f} of a meal's goals" if covers < 1 else
                           f"covers {covers:.1f} meals", fg=MUTED)
        self._meter = (self.result[1].cost, check.plan_budget) if check else None
        self._draw_meter()
        self._fit_tiles()

        if self.result is not None:
            self.show_shopping(keep_scroll=True)
            self.menu_text = self._menu_text()
        self.show_budget_card(check)
        self._variety_redraw = True
        if self.page.get() == "Variety":
            self.after_idle(self.show_variety)

    def show_budget_card(self, check):
        """When the budget is short: the settings that fit, each one click away."""
        if check is None or check.fits or self.budget_options is None:
            self.budget_card.grid_remove()
            self.donut_card.grid()
            return
        opts, budget, k = self.budget_options, check.plan_budget, self.planned.get()
        rows = []
        instead = "the whole day" if self.whole_day() else str(k)
        for n, cost in opts["fewer"]:                      # n meals cost n × (cost per meal)
            if cost <= budget + 1e-9:
                rows.append(("meals", n, f"Plan {n} meal{'s' if n > 1 else ''} instead of {instead}",
                             f"{n} × ₱{check.meal_cost:.2f} a meal", cost))
        for v, cost in opts["variety"]:                    # most variety first
            if cost <= budget + 1e-9:
                rows.append(("variety", v, f"Variety {v}: at most {v} servings of any food",
                             "more variety" if v < self.variety.get() else "less variety", cost))
        if opts["anything"] is not None and opts["anything"] <= budget + 1e-9:
            rows.append(("diet", "Anything", "Eating style “Anything”", "every food, same goals",
                         opts["anything"]))

        s = self.result[1]
        minimum = d.dot(self.result[0].h, s.y)             # h . y, the mirror problem's value
        cheapest = ("day that meets" if self.whole_day() else
                    "meal that meets" if k == 1 else f"{k} meals that meet")
        for_part = "" if self.whole_day() else f" for {k} of {self.meals.get()} meals"
        verb = "is" if self.whole_day() or k == 1 else "are"
        if rows:
            self.budget_card.subtitle.configure(
                text=f"The solver's guaranteed minimum (h · y = ₱{minimum:.2f}) proves nothing cheaper meets "
                     f"these goals, but these settings fit ₱{budget:.2f}. Click one to switch.")
            self.budget_list.configure(height=len(rows) * px(54))
            self.options_box.pack(fill="x", pady=(0, px(12)), before=self.afford_title)
        else:
            self.budget_card.subtitle.configure(
                text=f"No setting fits ₱{budget:.2f}. The cheapest {cheapest} {self._whose()} goals{for_part} "
                     f"{verb} ₱{s.cost:.2f}, and the guaranteed minimum (h · y = ₱{minimum:.2f}) proves nothing "
                     "cheaper meets every goal. Raise the budget, lower a limit on Limits, or edit a price on Foods.")
            self.options_box.pack_forget()
        self.budget_list.show(rows)

        # What the budget buys: the cheapest menu times k = budget ÷ cost, whose totals are k (N x)
        p = self.result[0]
        share, x = d.budget_menu(s.x, s.cost, budget)
        totals = d.mat_vec(p.N, x)
        self.afford_title.configure(text=f"What ₱{budget:.2f} buys")
        self.afford_note.configure(text=f"The cheapest menu cut to {share:.0%} of every amount. Each nutrient "
                                        f"falls to {share:.0%} of the menu's total.")
        self.afford_list.show([(name, unit, t, lo, hi) for (name, unit), t, (lo, hi)
                               in zip(d.NUTRIENTS, totals, self.result[2]) if lo is not None or hi is not None])
        self.donut_card.grid_remove()
        self.budget_card.grid(row=0, column=1, sticky="nsew")

    def _draw_afford_row(self, cv, row, x0, y, x1, h):
        """One nutrient of what the budget buys, against its goal (the planned goals)."""
        name, unit, total, lo, hi = row
        ok = (lo is None or total >= lo - 1e-6) and (hi is None or total <= hi + 1e-6)
        ref = lo if lo else hi
        pct = f"{total / ref:.0%}" if ref else "–"
        self._two_lines(cv, x0, x1, y + h / 2, name, f"{fmt(total)} {unit} · need {need_text(lo, hi, unit)}",
                        pct, "of the goal" if lo else "of the maximum", GOOD if ok else DANGER)

    def _whose(self):
        """"a Teen boy's", "an Adult woman's" or "your custom"."""
        group = self.group.get()
        if not group:
            return "your custom"
        return f"{'an' if group[0] in 'AEIOU' else 'a'} {group}'s"

    def use_budget_option(self, row):
        kind, value = row[:2]
        if kind == "meals":
            self.planned.set(value)
            self.planned_chosen()
        elif kind == "variety":
            self.use_setting(self.group.get(), value)
        else:
            self.diet.set(value)
            self.solve()

    def _menu_text(self):
        """What Copy menu puts on the clipboard."""
        p, s, plan_limits, _ = self.result
        k, m = self.planned.get(), self.meals.get()
        group = self.group.get() or f"custom limits from {self.last_group}"
        if self.whole_day():
            what = "Cheapest day"
        else:
            what = f"Cheapest {'meal' if k == 1 else f'{k} meals'} ({k} of {m} a day)"
        lines = [f"{what}: ₱{s.cost:.2f} ({group}, {self.diet.get().lower()}, at most {self.variety.get()} "
                 f"servings of any food a day; {PRICE_SOURCE} prices)"]
        limited = [i for i, (lo, hi) in enumerate(plan_limits) if lo is not None or hi is not None]
        shown = [need_text(*plan_limits[i], d.NUTRIENTS[i][1]) + ("" if i == 0 else f" {d.NUTRIENTS[i][0].lower()}")
                 for i in (0, 1) if i in limited]                       # calories and protein
        others = len(limited) - len(shown)
        goals = " and ".join(shown) + (f", and {others} other limit{'s' if others != 1 else ''}" if others else "")
        if not shown:
            goals = f"all {others} limits"
        share = "" if self.whole_day() else f" ({self.share_text()} of the day's)"
        lines.append(f"Goals met{share}: {goals}")
        check = self.budget_status()
        if check:
            state = (f"₱{check.left:.2f} left, every goal met" if check.fits else
                     f"₱{-check.left:.2f} short of the cheapest menu that meets the goals")
            per = "the whole day" if self.whole_day() else f"{self.plan_words()} a day"
            lines.append(f"Budget: ₱{check.plan_budget:.2f} for {per}. {state}.")
        lines += [f"- {p.names[j]}: {d.amount(p.names[j], s.x[j])} (₱{s.x[j] * p.c[j]:.2f})"
                  for j, _ in self.menu_order]
        return "\n".join(lines)

    VARIETIES = range(2, 9)

    def show_variety(self):
        """
        The Variety page for the current eating style, prices and foods, always for the whole day
        (figure_inputs holds the daily limits). About 0.2 s (28 solves) when the inputs changed;
        a budget change only redraws the chart.
        """
        if not hasattr(self, "figure_inputs") or not (self._variety_stale or self._variety_redraw):
            return
        if self._variety_stale:
            self._variety_stale = False
            diet, prices, exclude, own_max, limits = self.figure_inputs
            groups, current = dict(d.PRESETS), self.group.get()
            if not current and limits is not None:          # custom limits get their own line
                groups["Your limits"] = limits
                current = "Your limits"
            self._variety_costs = d.variety_costs(diet, prices, exclude, own_max, groups, self.VARIETIES)
            self._variety_current = current
        self._variety_redraw = False
        costs, current = self._variety_costs, self._variety_current
        check = self.budget_status()
        self.variety_ax.clear()
        d.draw_variety(self.variety_ax, costs, self.VARIETIES,
                       mark=(current, self.variety.get()) if current else None,
                       budget=check.day_budget if check else None)     # budget for the plan ÷ f
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
        cv.create_text(x0, cy - px(9), text=f"At most {v} servings ({v * 100} g)", anchor="w", font=f["strong"],
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
