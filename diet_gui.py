"""
diet_gui.py
===========
The Diet Optimizer window. It has the same screens as our web page, but every
answer comes from the Python solver in diet_optimizer.py.

Run:   python diet_gui.py          (or: python diet_optimizer.py --gui)

Tabs:
    Menu           the cheapest day of eating, with amounts and costs
    Nutrition      the totals N @ x checked against every limit
    Foods          turn foods on or off, edit prices and serving limits
    Limits         edit the minimum and maximum for each nutrient
    Why            which requirements push the cost up, and which foods just missed
    Solver steps   every simplex pivot and the guaranteed minimum after each one
    Guide          how to use the program and how the math works
"""

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402

import diet_optimizer as d  # noqa: E402

# Colors match the web page
BG, CARD, TEXT, MUTED, BORDER = "#fafaf7", "#f1efe8", "#2c2c2a", "#5f5e5a", "#d3d1c7"
ACCENT, ACCENT_BG, ACCENT_TEXT, WARN, BAR = "#0F6E56", "#e1f5ee", "#04342c", "#993c1d", "#5dcaa5"
PURPLE, CORAL = "#7F77DD", "#D85A30"

DIETS = {"Anything": "anything", "No meat or fish": "no-meat-fish", "Plant-based": "plant-based"}
GROUPS = list(d.PRESETS)
DEFAULTS = {f[0]: (f[2], f[3]) for f in d.FOODS}           # food name -> (price, own max)
KIND_OF = {f[0]: f[4] for f in d.FOODS}
SERVING_OF = {f[0]: f[1] for f in d.FOODS}

GUIDE = """QUICK START
1. Pick who the menu is for, an eating style and a variety level at the top.
2. Open Menu to see the cheapest day of eating. The cost at the top right updates as you change things.
3. Open Nutrition to confirm every target is met.
4. Press Copy menu to save it.

WHAT EACH TAB DOES
Menu: foods, amounts and costs.
Nutrition: totals against your limits.
Foods: turn foods on or off, search, and edit prices and serving limits.
Limits: edit minimums and maximums. Leave a box empty for no limit.
Why: which limits push the cost up, and how much cheaper an unused food would need to be.
Solver steps: every pivot the simplex method makes.

HOW THE MATH WORKS
1. Foods are vectors. Each food's nutrition label is a column of the matrix N.
2. A menu is a vector x of servings. The day's totals are the product N x, a linear combination of the food columns. The cost is the dot product c . x.
3. Every limit is a linear inequality. Together they form a region of valid menus with flat sides, and the cheapest menu is at a corner.
4. The simplex method moves from corner to corner. Each move (a pivot) is one Gauss-Jordan step: scale the pivot row, then clear its column with row operations.
5. The solver works on the mirror problem built from the transpose of the requirement matrix. It puts a price on every requirement, and the same final table also holds the menu.

WORDS YOU WILL SEE
Serving: one standard portion, such as 1 cup or 1 piece.
Requirement price: how much the daily cost changes if a limit moves by one unit.
Reduced cost: how much cheaper an unused food would need to be to join the menu.
Pivot: one move from a corner to a cheaper neighboring corner.

WHERE THE LIMITS COME FROM
Every group uses the Philippine Dietary Reference Intakes 2015 (FNRI-DOST). Adults are ages 19 to 29 and teens are 16 to 18.
Calories: at least the Recommended Energy Intake. Protein, calcium, iron and vitamin C: at least the Recommended Nutrient Intake.
Fat and carbohydrates: the recommended percent of calories, turned into grams.
Sodium: at least 500 mg and under 2,000 mg.
The PDRI says the 28 mg of iron for women and teen girls usually needs iron-rich or fortified foods or a supplement. That is why iron drives the cost for those groups.

Amounts like 2.3 cups are fine for the model. Round to the nearest half serving in practice.
Prices and nutrition values are rough estimates for coursework, not medical advice."""


def number(text, default=None):
    """Read a non-negative number from a text box, or return the default."""
    try:
        value = float(text)
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


def chart(parent, height=3.4):
    """Create an empty matplotlib chart inside a Tk frame."""
    fig = Figure(figsize=(5.4, height), dpi=100, facecolor=BG)
    ax = fig.add_subplot(111)
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.get_tk_widget().configure(bg=BG, highlightthickness=0)
    return fig, ax, canvas


def tidy(ax):
    ax.set_facecolor(BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=8, colors=TEXT)


class DietApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Diet optimizer")
        self.geometry("1180x800")
        self.minsize(980, 680)
        self.configure(bg=BG)
        self._fonts()
        self._style()

        self.group = tk.StringVar(value="Adult woman")
        self.diet = tk.StringVar(value="Anything")
        self.variety = tk.IntVar(value=4)
        self.on = {name: tk.BooleanVar(value=True) for name in DEFAULTS}
        self.price = {name: tk.StringVar(value=f"{p:g}") for name, (p, _) in DEFAULTS.items()}
        self.own_max = {name: tk.StringVar(value=f"{m:g}") for name, (_, m) in DEFAULTS.items()}
        self.limit_vars = [(tk.StringVar(), tk.StringVar()) for _ in d.NUTRIENTS]
        self._filling, self._pending, self.menu_text = False, None, ""
        self.last_group = "Adult woman"           # remembered when limits are customized

        self._header()
        self._setup_card()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        self._menu_tab()
        self._nutrition_tab()
        self._foods_tab()
        self._limits_tab()
        self._why_tab()
        self._steps_tab()
        self._guide_tab()

        self.fill_limits("Adult woman")
        for var in [*self.on.values(), *self.price.values(), *self.own_max.values()]:
            var.trace_add("write", self.schedule)
        for lo, hi in self.limit_vars:
            for var in (lo, hi):
                var.trace_add("write", self.limit_edited)
        self.solve()

    # ------------------------------------------------------------------ look
    def _fonts(self):
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(size=10)
        family = base.actual("family")
        self.f_title = tkfont.Font(family=family, size=15, weight="bold")
        self.f_bold = tkfont.Font(family=family, size=10, weight="bold")
        self.f_small = tkfont.Font(family=family, size=9)
        self.f_big = tkfont.Font(family=family, size=12, weight="bold")

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER)
        s.configure("Card.TFrame", background=CARD)
        s.configure("Card.TLabel", background=CARD, foreground=TEXT)
        s.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=self.f_small)
        s.configure("Muted.TLabel", foreground=MUTED)
        s.configure("Title.TLabel", font=self.f_title)
        s.configure("Pill.TLabel", background=ACCENT_BG, foreground=ACCENT, font=self.f_big, padding=(14, 4))
        s.configure("Warn.TLabel", foreground=WARN)
        s.configure("Value.TLabel", background=CARD, font=self.f_big)
        s.configure("Chip.Toolbutton", background=BG, foreground=TEXT, padding=(12, 5), relief="solid",
                    borderwidth=1)
        s.map("Chip.Toolbutton", background=[("selected", ACCENT_BG), ("active", "#ffffff")],
              foreground=[("selected", ACCENT_TEXT)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", padding=(14, 6),
                    font=self.f_bold)
        s.map("Accent.TButton", background=[("active", ACCENT_TEXT)])
        s.configure("TButton", padding=(12, 6))
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 7), background=CARD, foreground=MUTED)
        s.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACCENT)])
        s.configure("Treeview", rowheight=26, background="#ffffff", fieldbackground="#ffffff")
        s.configure("Treeview.Heading", font=self.f_bold, background=CARD)
        s.configure("Off.TLabel", foreground="#a8a69e")

    # ------------------------------------------------------------------ top of the window
    def _header(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=(12, 6))
        ttk.Label(bar, text="Diet optimizer", style="Title.TLabel").pack(side="left")
        self.pill = ttk.Label(bar, text="-", style="Pill.TLabel")
        self.pill.pack(side="right")

    def _setup_card(self):
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 10))
        card.pack(fill="x", padx=16)
        ttk.Label(card, text="Who is the menu for?", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
        row = ttk.Frame(card, style="Card.TFrame")
        row.grid(row=1, column=0, sticky="w", pady=(2, 8))
        for g in GROUPS:
            ttk.Radiobutton(row, text=g, value=g, variable=self.group, style="Chip.Toolbutton",
                            command=self.group_chosen).pack(side="left", padx=(0, 6))
        self.custom_tag = ttk.Label(row, text="Custom limits", style="CardMuted.TLabel")

        ttk.Label(card, text="Eating style", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(30, 0))
        row = ttk.Frame(card, style="Card.TFrame")
        row.grid(row=1, column=1, sticky="w", padx=(30, 0), pady=(2, 8))
        for name in DIETS:
            ttk.Radiobutton(row, text=name, value=name, variable=self.diet, style="Chip.Toolbutton",
                            command=self.solve).pack(side="left", padx=(0, 6))

        ttk.Label(card, text="Variety: most servings of any one food", style="CardMuted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        row = ttk.Frame(card, style="Card.TFrame")
        row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Button(row, text="−", width=3, command=lambda: self.change_variety(-1)).pack(side="left")
        ttk.Label(row, textvariable=self.variety, style="Value.TLabel", width=3, anchor="center").pack(side="left")
        ttk.Button(row, text="+", width=3, command=lambda: self.change_variety(1)).pack(side="left")
        ttk.Label(row, text="   Lower = more varied, usually costs a bit more", style="CardMuted.TLabel").pack(side="left")

        self.message = ttk.Label(self, text="", style="Warn.TLabel", wraplength=1100)
        self.message.pack(fill="x", padx=18, pady=(6, 0))

    # ------------------------------------------------------------------ tabs
    def _tab(self, title):
        frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(frame, text=title)
        return frame

    def _tree(self, parent, columns, widths, height=14):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for col, w in zip(columns, widths):
            tree.heading(col, text=col, anchor="w")
            tree.column(col, width=w, anchor="w", stretch=col == columns[0])
        return tree

    def _menu_tab(self):
        tab = self._tab("Menu")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.menu_sum = ttk.Label(left, text="", style="Muted.TLabel")
        self.menu_sum.pack(anchor="w", pady=(0, 6))
        self.menu_tree = self._tree(left, ("Food", "Amount", "Cost"), (220, 150, 90))
        self.menu_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(left)
        buttons.pack(anchor="w", pady=(10, 0))
        self.copy_btn = ttk.Button(buttons, text="Copy menu", style="Accent.TButton", command=self.copy_menu)
        self.copy_btn.pack(side="left")
        ttk.Button(buttons, text="Reset everything", command=self.reset).pack(side="left", padx=8)
        self.menu_fig, self.menu_ax, self.menu_canvas = chart(tab)
        self.menu_canvas.get_tk_widget().pack(side="right", fill="both", expand=True, padx=(12, 0))

    def _nutrition_tab(self):
        tab = self._tab("Nutrition")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.nut_sum = ttk.Label(left, text="", style="Muted.TLabel", wraplength=480)
        self.nut_sum.pack(anchor="w", pady=(0, 6))
        self.nut_tree = self._tree(left, ("Nutrient", "Total", "Need", "Status"), (110, 90, 110, 175), 10)
        self.nut_tree.pack(fill="both", expand=True)
        self.nut_fig, self.nut_ax, self.nut_canvas = chart(tab)
        self.nut_canvas.get_tk_widget().pack(side="right", fill="both", expand=True, padx=(12, 0))

    def _foods_tab(self):
        tab = self._tab("Foods")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Turn foods on or off and change prices to match your market.",
                  style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Turn all off", command=lambda: self.set_all(False)).pack(side="right")
        ttk.Button(top, text="Turn all on", command=lambda: self.set_all(True)).pack(side="right", padx=6)
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.filter_foods())
        ttk.Entry(top, textvariable=self.search, width=24).pack(side="right", padx=6)
        ttk.Label(top, text="Search", style="Muted.TLabel").pack(side="right")

        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True)
        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self._wheel(canvas)

        for col, text in enumerate(("Use", "Food", "Price (₱)", "Own max", "")):
            ttk.Label(inner, text=text, font=self.f_bold).grid(row=0, column=col, sticky="w", padx=6, pady=4)
        self.food_rows = {}
        for r, name in enumerate(DEFAULTS, start=1):
            widgets = [
                ttk.Checkbutton(inner, variable=self.on[name]),
                ttk.Label(inner, text=f"{name}  ({SERVING_OF[name]})"),
                ttk.Spinbox(inner, from_=0, to=500, increment=0.5, width=8, textvariable=self.price[name]),
                ttk.Spinbox(inner, from_=0, to=20, increment=0.5, width=6, textvariable=self.own_max[name]),
                ttk.Label(inner, text="", style="Muted.TLabel"),
            ]
            for col, w in enumerate(widgets):
                w.grid(row=r, column=col, sticky="w", padx=6, pady=2)
            self.food_rows[name] = (r, widgets)

    def _limits_tab(self):
        tab = self._tab("Limits")
        ttk.Label(tab, text="Leave a box empty for no limit. Editing a limit switches the group to custom.",
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        for col, text in enumerate(("Nutrient", "Unit", "Minimum", "Maximum")):
            ttk.Label(tab, text=text, font=self.f_bold).grid(row=1, column=col, sticky="w", padx=8, pady=4)
        for i, ((name, unit), (lo, hi)) in enumerate(zip(d.NUTRIENTS, self.limit_vars), start=2):
            ttk.Label(tab, text=name).grid(row=i, column=0, sticky="w", padx=8, pady=3)
            ttk.Label(tab, text=unit, style="Muted.TLabel").grid(row=i, column=1, sticky="w", padx=8)
            ttk.Entry(tab, textvariable=lo, width=10).grid(row=i, column=2, sticky="w", padx=8)
            ttk.Entry(tab, textvariable=hi, width=10).grid(row=i, column=3, sticky="w", padx=8)
        ttk.Button(tab, text="Reset limits to the chosen group", command=self.reset_limits).grid(
            row=len(d.NUTRIENTS) + 2, column=0, columnspan=3, sticky="w", padx=8, pady=12)

    def _why_tab(self):
        tab = self._tab("Why")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.why_text = tk.Text(left, wrap="word", bg=BG, fg=TEXT, relief="flat", height=20, width=56,
                                font=tkfont.nametofont("TkDefaultFont"), padx=4)
        self.why_text.tag_configure("h", font=self.f_bold, spacing1=8, spacing3=4)
        self.why_text.tag_configure("m", foreground=MUTED)
        self.why_text.pack(fill="both", expand=True)
        self.why_fig, self.why_ax, self.why_canvas = chart(tab)
        self.why_canvas.get_tk_widget().pack(side="right", fill="both", expand=True, padx=(12, 0))

    def _steps_tab(self):
        tab = self._tab("Solver steps")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.steps_sum = ttk.Label(left, text="", style="Muted.TLabel", wraplength=470, justify="left")
        self.steps_sum.pack(anchor="w", pady=(0, 6))
        self.steps_tree = self._tree(left, ("Pivot", "What joins the solution", "Proven minimum"),
                                     (50, 250, 130), 14)
        self.steps_tree.column("Pivot", stretch=False)
        self.steps_tree.column("What joins the solution", stretch=True)
        self.steps_tree.pack(fill="both", expand=True)
        self.steps_fig, self.steps_ax, self.steps_canvas = chart(tab)
        self.steps_canvas.get_tk_widget().pack(side="right", fill="both", expand=True, padx=(12, 0))

    def _guide_tab(self):
        tab = self._tab("Guide")
        text = tk.Text(tab, wrap="word", bg=BG, fg=TEXT, relief="flat", padx=6,
                       font=tkfont.nametofont("TkDefaultFont"))
        text.tag_configure("h", font=self.f_bold, spacing1=10, spacing3=4)
        for block in GUIDE.split("\n\n"):
            head, *body = block.split("\n")
            if head.isupper():
                text.insert("end", head.capitalize() + "\n", "h")
            else:
                body = [head] + body
            text.insert("end", "\n".join(body) + "\n")
        text.configure(state="disabled")
        bar = ttk.Scrollbar(tab, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

    def _wheel(self, canvas):
        """Scroll the foods list with the mouse wheel while the pointer is over it."""
        def scroll(event):
            step = -1 if (event.num == 4 or event.delta > 0) else 1
            canvas.yview_scroll(step * 2, "units")
        def bind(_):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.bind_all(seq, scroll)
        def unbind(_):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.unbind_all(seq)
        canvas.bind("<Enter>", bind)
        canvas.bind("<Leave>", unbind)

    # ------------------------------------------------------------------ actions
    def schedule(self, *_):
        """Re-solve shortly after the last edit, so typing a price stays smooth."""
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(250, self.solve)

    def fill_limits(self, group):
        self._filling = True
        for (lo, hi), (vlo, vhi) in zip(d.PRESETS[group], self.limit_vars):
            vlo.set("" if lo is None else f"{lo:g}")
            vhi.set("" if hi is None else f"{hi:g}")
        self._filling = False
        self.custom_tag.pack_forget()

    def group_chosen(self):
        self.last_group = self.group.get()
        self.fill_limits(self.last_group)
        self.solve()

    def limit_edited(self, *_):
        if not self._filling:
            self.group.set("")                       # no group button is selected any more
            self.custom_tag.pack(side="left", padx=8)
            self.schedule()

    def reset_limits(self):
        self.group.set(self.last_group)
        self.group_chosen()

    def change_variety(self, step):
        self.variety.set(max(2, min(8, self.variety.get() + step)))
        self.solve()

    def set_all(self, value):
        for var in self.on.values():
            var.set(value)

    def filter_foods(self):
        q = self.search.get().lower()
        for name, (r, widgets) in self.food_rows.items():
            for w in widgets:
                (w.grid if q in name.lower() else w.grid_remove)()

    def copy_menu(self):
        self.clipboard_clear()
        self.clipboard_append(self.menu_text)
        self.copy_btn.configure(text="Copied!")
        self.after(1500, lambda: self.copy_btn.configure(text="Copy menu"))

    def reset(self):
        self._filling = True
        for name, (p, m) in DEFAULTS.items():
            self.on[name].set(True)
            self.price[name].set(f"{p:g}")
            self.own_max[name].set(f"{m:g}")
        self._filling = False
        self.diet.set("Anything")
        self.variety.set(4)
        self.group.set("Adult woman")
        self.search.set("")
        self.group_chosen()
        self.notebook.select(0)

    # ------------------------------------------------------------------ solving
    def read_limits(self):
        limits = []
        for (name, _), (vlo, vhi) in zip(d.NUTRIENTS, self.limit_vars):
            pair = []
            for var in (vlo, vhi):
                text = var.get().strip()
                value = None if text == "" else number(text)
                if text != "" and value is None:
                    raise ValueError(f"The {name} limit must be a number.")
                pair.append(value)
            limits.append(tuple(pair))
        return limits

    def solve(self):
        self._pending = None
        diet = DIETS[self.diet.get()]
        excluded_kinds = d.DIETS[diet]
        for name, (_, widgets) in self.food_rows.items():
            blocked = KIND_OF[name] in excluded_kinds
            widgets[1].configure(style="Off.TLabel" if blocked or not self.on[name].get() else "TLabel")
            widgets[4].configure(text="not in this eating style" if blocked else "")
        try:
            limits = self.read_limits()
        except ValueError as err:
            return self.no_menu(str(err))

        prices = {n: number(v.get(), DEFAULTS[n][0]) for n, v in self.price.items()}
        own_max = {n: number(v.get(), 1e9) if v.get().strip() else 1e9 for n, v in self.own_max.items()}
        exclude = {n for n, v in self.on.items() if not v.get()}
        p = d.build_problem("Adult woman", diet, self.variety.get(), prices, exclude, limits, own_max)
        if not p.names:
            return self.no_menu("Every food is turned off. Turn some on in the Foods tab.")
        s = d.solve_diet(p)
        if s is None:
            caps = -p.h[-len(p.names):]
            best = p.N @ caps                           # the most of each nutrient we could ever get
            hints = [f"{name} can't reach {lo:g} {unit}" for (name, unit), (lo, _), b
                     in zip(d.NUTRIENTS, limits, best) if lo is not None and b < lo - 1e-9]
            return self.no_menu("No menu meets every limit" + (f" ({'. '.join(hints)})" if hints else "")
                                + ". Try more servings per food, “Anything”, or a lower minimum.")
        self.message.configure(text="")
        self.pill.configure(text=f"₱{s.cost:.2f} / day")
        self.show_menu(p, s)
        self.show_nutrition(p, s, limits)
        self.show_why(p, s)
        self.show_steps(p, s)

    def no_menu(self, text):
        self.pill.configure(text="No menu")
        self.message.configure(text=text)
        self.menu_text = ""
        for tree in (self.menu_tree, self.nut_tree, self.steps_tree):
            tree.delete(*tree.get_children())
        for label in (self.menu_sum, self.nut_sum, self.steps_sum):
            label.configure(text="")
        self.why_text.configure(state="normal")
        self.why_text.delete("1.0", "end")
        self.why_text.configure(state="disabled")
        for ax, canvas in ((self.menu_ax, self.menu_canvas), (self.nut_ax, self.nut_canvas),
                           (self.why_ax, self.why_canvas), (self.steps_ax, self.steps_canvas)):
            ax.clear()
            ax.axis("off")
            ax.text(0.5, 0.5, "No menu", ha="center", va="center", color=MUTED, fontsize=12)
            canvas.draw_idle()

    # ------------------------------------------------------------------ views
    def show_menu(self, p, s):
        costs = s.x * p.c
        items = [j for j in np.argsort(-costs) if s.x[j] > 1e-6]
        self.menu_tree.delete(*self.menu_tree.get_children())
        for j in items:
            self.menu_tree.insert("", "end", values=(p.names[j], f"{s.x[j]:.1f} × {p.servings[j]}",
                                                     f"₱{costs[j]:.2f}"))
        self.menu_sum.configure(text=f"{len(items)} foods, about ₱{s.cost / 3:.2f} per meal "
                                     "if split into three.")
        self.menu_text = f"Cheapest day: ₱{s.cost:.2f}\n" + "\n".join(
            f"- {p.names[j]}: {s.x[j]:.1f} × {p.servings[j]} (₱{costs[j]:.2f})" for j in items)

        ax = self.menu_ax
        ax.clear()
        tidy(ax)
        order = items[::-1]
        ax.barh([p.names[j] for j in order], [costs[j] for j in order], color=BAR)
        ax.set_xlabel("Cost of each food (₱)", fontsize=9)
        ax.set_title(f"Total ₱{s.cost:.2f} per day", fontsize=10, color=TEXT)
        self.menu_fig.tight_layout()
        self.menu_canvas.draw_idle()

    def show_nutrition(self, p, s, limits):
        totals = p.N @ s.x                                   # N @ x: the day's nutrient totals
        priced = {(k, n) for v, (k, n, _) in zip(s.y, p.labels) if v > 1e-7 and k != "cap"}
        self.nut_tree.delete(*self.nut_tree.get_children())
        for (name, unit), (lo, hi), t in zip(d.NUTRIENTS, limits, totals):
            need = (f"{lo:g} to {hi:g}" if lo is not None and hi is not None else
                    f"at least {lo:g}" if lo is not None else f"at most {hi:g}" if hi is not None else "no limit")
            status = "✓ met"
            if ("min", name) in priced or ("max", name) in priced:
                status = "✓ drives the cost"
            elif (lo is not None and abs(t - lo) < 1e-6) or (hi is not None and abs(t - hi) < 1e-6):
                status = "✓ at the limit"
            self.nut_tree.insert("", "end", values=(name, f"{t:.0f} {unit}", need, status))
        self.nut_sum.configure(text="Every limit is met. Rows marked “drives the cost” push the price "
                                    "up the most (see Why).")

        ax = self.nut_ax
        ax.clear()
        tidy(ax)
        names = [n for n, _ in d.NUTRIENTS]
        for i, ((lo, hi), t) in enumerate(zip(limits, totals)):
            ref = lo if lo else hi
            if not ref:
                continue
            ax.barh(i, 100 * t / ref, color=BAR if lo else PURPLE)
            if lo and hi:
                ax.plot([100 * hi / ref] * 2, [i - 0.4, i + 0.4], color=CORAL, lw=2)
        ax.axvline(100, color=TEXT, lw=1, ls="--")
        ax.set_yticks(range(len(names)), names)
        ax.invert_yaxis()
        ax.set_xlabel("Percent of the limit (red tick = maximum)", fontsize=9)
        ax.set_title("Teal: minimums   Purple: maximums", fontsize=10, color=TEXT)
        self.nut_fig.tight_layout()
        self.nut_canvas.draw_idle()

    def show_why(self, p, s):
        t = self.why_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        drivers = sorted(((v, lab) for v, lab in zip(s.y, p.labels) if v > 1e-7 and lab[0] != "cap"),
                         reverse=True)
        t.insert("end", "Limits that push the cost up\n", "h")
        if drivers:
            t.insert("end", "Each extra unit of the requirement changes the daily cost by about:\n", "m")
            for v, (kind, name, unit) in drivers:
                note = " (loosening this cap saves that much)" if kind == "max" else ""
                t.insert("end", f"• {name} {'minimum' if kind == 'min' else 'maximum'}: "
                                f"₱{v:.3f} per {unit}{note}\n")
        else:
            t.insert("end", "No limit is holding the cost up.\n", "m")

        rc = d.reduced_costs(p, s)                            # c_j - (column j of G) . y
        missed = sorted((rc[j], p.names[j], p.c[j]) for j in range(len(p.names)) if s.x[j] <= 1e-6)[:5]
        if missed:
            t.insert("end", "Foods that just missed out\n", "h")
            t.insert("end", "How much cheaper each would need to be to join the menu:\n", "m")
            for r, name, c in missed:
                t.insert("end", f"• {name} (now ₱{c:.2f}): ₱{r:.2f} cheaper\n")
        t.configure(state="disabled")

        ax = self.why_ax
        ax.clear()
        tidy(ax)
        if drivers:
            ax.barh([f"{n} ({k})" for _, (k, n, _) in drivers], [v for v, _ in drivers], color=CORAL)
            ax.invert_yaxis()
        ax.set_xlabel("₱ per extra unit of the requirement", fontsize=9)
        ax.set_title("Requirement prices from the mirror problem", fontsize=10, color=TEXT)
        self.why_fig.tight_layout()
        self.why_canvas.draw_idle()

    def show_steps(self, p, s):
        self.steps_sum.configure(text=(
            f"Nutrition matrix N is {p.N.shape[0]} × {p.N.shape[1]}. The requirement system "
            f"G x ≥ h is {p.G.shape[0]} × {p.G.shape[1]}, and the mirror problem uses its "
            f"transpose ({p.G.shape[1]} × {p.G.shape[0]}). The solver made {len(s.steps)} pivots. "
            "Each one is a Gauss-Jordan step that raises the guaranteed minimum cost."))
        self.steps_tree.delete(*self.steps_tree.get_children())
        for k, st in enumerate(s.steps, 1):
            self.steps_tree.insert("", "end", values=(k, d.describe(p, st.entering), f"₱{st.value:.2f}"))

        ax = self.steps_ax
        ax.clear()
        tidy(ax)
        ax.plot(range(len(s.steps) + 1), [0] + [st.value for st in s.steps], "o-", color=PURPLE)
        ax.axhline(s.cost, color=ACCENT, ls="--", lw=1)
        ax.text(0.1, s.cost * 0.92, f"cheapest menu ₱{s.cost:.2f}", color=ACCENT, fontsize=8)
        ax.set_xlabel("Pivot number", fontsize=9)
        ax.set_ylabel("Guaranteed minimum (₱)", fontsize=9)
        ax.set_title("Each pivot raises the proven minimum", fontsize=10, color=TEXT)
        self.steps_fig.tight_layout()
        self.steps_canvas.draw_idle()


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
