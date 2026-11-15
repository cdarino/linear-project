"""
diet_optimizer.py
=================
Math 2138 (Linear Algebra) final project: the Diet Optimizer.

Finds the cheapest day of eating that still meets every nutrition requirement.

THE MODEL
---------
    N   (9 x n)  nutrition matrix. Column j is food j's nutrition label as a vector.
    x   (n)      servings of each food. This is the menu we solve for.
    c   (n)      price of one serving of each food.

    N @ x        the day's nutrient totals, a linear combination of the food columns
    c . x        the day's cost, a dot product

    minimize    c . x
    subject to  lo <= N @ x <= hi     (nutrition requirements)
                0  <=  x    <= cap    (no negative servings, and a variety limit)

Every requirement is rewritten in the form "row . x >= number", and the rows
stack into one system of inequalities  G @ x >= h.

HOW IT IS SOLVED
----------------
The valid menus form a region with flat sides, and the cheapest menu is at a
corner. The simplex method moves from corner to corner, always to a cheaper
one, until no neighbor is cheaper. Each move ("pivot") is one round of
Gauss-Jordan elimination on a table of numbers called the tableau: scale the
pivot row so the pivot is 1, then add multiples of it to clear its column.

The solver works on the MIRROR (dual) problem, built from the transpose G^T:

    maximize   h . y      subject to   G^T @ y <= c,   y >= 0

Here y holds a price for each requirement. "Every price is zero" is already a
valid corner, so simplex can start right away. When it stops, the same final
tableau also holds the cheapest menu x, and both problems reach the same value
(c . x = h . y). The prices y show which requirements push the cost up.

USAGE
-----
    python diet_optimizer.py                       adult woman, any food, variety 4
    python diet_optimizer.py --preset "Adult man" --diet plant-based --variety 3
    python diet_optimizer.py --price "Egg=10" --exclude "Instant noodles"
    python diet_optimizer.py --example             2-food walkthrough with every row operation
    python diet_optimizer.py --plots               save the report figures into figures/
    python diet_optimizer.py --test                compare with SciPy on every setting
    python diet_optimizer.py --gui                 open the window (same as python diet_gui.py)

Prices and nutrition values are rough estimates for coursework, not medical advice.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

EPS = 1e-9          # tolerance for treating a floating-point number as zero

# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
NUTRIENTS = [("Calories", "kcal"), ("Protein", "g"), ("Fat", "g"), ("Carbohydrates", "g"),
             ("Fiber", "g"), ("Calcium", "mg"), ("Iron", "mg"), ("Vitamin C", "mg"),
             ("Sodium", "mg")]

PLANT, MEAT_FISH, EGG_DAIRY = 0, 1, 2

# (name, serving size, price in PHP, own maximum servings, kind, nutrition vector)
# The nutrition vector follows the order of NUTRIENTS above.
FOODS = [
    ("White rice (cooked)", "1 cup", 12, 6, PLANT, [205, 4.3, 0.4, 44.5, 0.6, 16, 0.5, 0, 2]),
    ("Egg", "1 large", 9, 4, EGG_DAIRY, [72, 6.3, 4.8, 0.4, 0, 28, 0.9, 0, 71]),
    ("Chicken breast", "100 g cooked", 40, 3, MEAT_FISH, [165, 31, 3.6, 0, 0, 15, 1, 0, 74]),
    ("Tilapia", "100 g cooked", 30, 3, MEAT_FISH, [128, 26, 2.7, 0, 0, 14, 0.7, 0, 56]),
    ("Tofu (firm)", "100 g", 15, 4, PLANT, [80, 8, 4.8, 1.9, 0.3, 350, 2.7, 0, 7]),
    ("Mung beans (cooked)", "1 cup", 15, 3, PLANT, [212, 14.2, 0.8, 38.7, 15.4, 55, 2.8, 1, 4]),
    ("Sardines in tomato sauce", "1 small can", 25, 2, MEAT_FISH, [150, 17, 8, 1, 0, 300, 2.5, 0, 400]),
    ("Saba banana", "1 piece", 6, 6, PLANT, [110, 1.1, 0.2, 28, 2.6, 7, 0.4, 9, 1]),
    ("Kangkong (cooked)", "1 cup", 10, 3, PLANT, [20, 2.6, 0.2, 3.1, 2.1, 77, 1.7, 25, 60]),
    ("Malunggay leaves", "1 cup", 5, 3, PLANT, [13, 1.9, 0.2, 2, 0.8, 40, 0.8, 11, 3]),
    ("Carrot", "1 medium", 5, 3, PLANT, [25, 0.6, 0.1, 6, 1.7, 20, 0.2, 3.6, 42]),
    ("Cabbage (cooked)", "1 cup", 8, 3, PLANT, [33, 1.6, 0.1, 7.5, 2.8, 72, 0.3, 56, 30]),
    ("Camote (sweet potato)", "1 medium", 10, 4, PLANT, [112, 2, 0.1, 26, 3.9, 39, 0.8, 22, 72]),
    ("Pandesal", "1 piece", 4, 8, PLANT, [90, 3, 1.5, 17, 0.7, 10, 0.8, 0, 150]),
    ("Oatmeal (cooked)", "1 cup", 10, 3, PLANT, [150, 5, 2.5, 27, 4, 20, 1.7, 0, 5]),
    ("Milk", "1 cup", 20, 4, EGG_DAIRY, [150, 8, 8, 12, 0, 300, 0.1, 0, 105]),
    ("Peanut butter", "1 tbsp", 6, 3, PLANT, [94, 4, 8, 3, 1, 7, 0.3, 0, 70]),
    ("Cooking oil", "1 tbsp", 3, 3, PLANT, [120, 0, 14, 0, 0, 0, 0, 0, 0]),
    ("Peanuts (roasted)", "30 g", 10, 3, PLANT, [170, 7, 14, 5, 2.4, 20, 0.7, 0, 5]),
    ("Tomato", "1 medium", 6, 3, PLANT, [22, 1.1, 0.2, 4.8, 1.5, 12, 0.3, 17, 6]),
    ("Potato (boiled)", "1 medium", 10, 3, PLANT, [130, 3, 0.2, 30, 2.5, 15, 0.8, 10, 10]),
    ("Papaya", "1 cup", 12, 3, PLANT, [60, 0.7, 0.4, 15, 2.5, 30, 0.3, 88, 12]),
    ("Mango", "1 cup", 25, 2, PLANT, [99, 1.4, 0.6, 25, 2.6, 18, 0.3, 60, 2]),
    ("Ampalaya (cooked)", "1 cup", 10, 3, PLANT, [24, 1, 0.2, 5, 2.5, 20, 0.7, 13, 6]),
    ("Instant noodles", "1 pack", 10, 3, PLANT, [270, 6, 11, 38, 1, 20, 1.5, 0, 1000]),
]

# Daily requirements from the Philippine Dietary Reference Intakes 2015 (FNRI-DOST).
# Adults are the 19-29 group and teens are the 16-18 group.
#   Calories   at least the Recommended Energy Intake (REI)
#   Protein    at least the Recommended Nutrient Intake (RNI)
#   Fat, carbs the Acceptable Macronutrient Distribution Range (AMDR), a percent of the REI.
#              Grams = REI x percent / (9 kcal per g of fat, or 4 kcal per g of carbs)
#   Fiber      at least the low end of the PDRI range
#   Calcium, iron, vitamin C   at least the RNI. The PDRI notes that the 28 mg of iron
#              for women and teen girls "cannot be met by usual diet alone".
#   Sodium     at least the Adequate Intake of 500 mg, and under 2,000 mg as the PDRI
#              recommends for adults (from the WHO). We use the same cap for teens.
def pdri(rei, protein, fat_pct, carb_pct, fiber, calcium, iron, vitamin_c):
    """Turn one PDRI group's values into (minimum, maximum) pairs in the order of NUTRIENTS."""
    fat = tuple(round(rei * pct / 100 / 9) for pct in fat_pct)
    carbs = tuple(round(rei * pct / 100 / 4) for pct in carb_pct)
    return [(rei, None), (protein, None), fat, carbs, (fiber, None),
            (calcium, None), (iron, None), (vitamin_c, None), (500, 2000)]


# Daily (minimum, maximum) for each nutrient, in the order of NUTRIENTS. None means no limit.
#                          REI   protein  fat %     carbs %   fiber calcium iron vit C
PRESETS = {
    "Adult woman": pdri(1930, 62, (15, 30), (55, 75), 20, 750, 28, 60),
    "Adult man":   pdri(2530, 71, (15, 30), (55, 75), 20, 750, 12, 70),
    "Teen girl":   pdri(2280, 61, (15, 30), (55, 79), 21, 1000, 28, 60),
    "Teen boy":    pdri(3010, 72, (15, 30), (55, 79), 21, 1000, 14, 70),
}

# Which kinds of food each eating style leaves out
DIETS = {"anything": set(), "no-meat-fish": {MEAT_FISH}, "plant-based": {MEAT_FISH, EGG_DAIRY}}


# ---------------------------------------------------------------------------
# BUILDING THE SYSTEM  G @ x >= h
# ---------------------------------------------------------------------------
@dataclass
class Problem:
    names: list            # foods allowed on this menu
    servings: list         # serving size of each food
    c: np.ndarray          # price of one serving of each food
    N: np.ndarray          # nutrition matrix, one column per food
    G: np.ndarray          # every requirement as a row, so that G @ x >= h
    h: np.ndarray
    labels: list           # (kind, name, unit) for each row of G
    limits: list           # the (min, max) pair for each nutrient


def build_problem(preset="Adult woman", diet="anything", variety=4, prices=None, exclude=(),
                  limits=None, own_max=None):
    """
    Purpose: turn the food list and a person's requirements into G @ x >= h.
    Math:    a minimum is  N_i . x >= lo,  a maximum is  -N_i . x >= -hi,
             and the variety cap is  -x_j >= -cap_j  (all the same ">=" form).
    Optional: `limits` replaces the preset's (min, max) pairs, and `own_max`
              changes a food's own serving limit (both used by the GUI).
    """
    prices, own_max = prices or {}, own_max or {}
    limits = limits or PRESETS[preset]
    foods = [f for f in FOODS if f[4] not in DIETS[diet] and f[0] not in exclude]
    names = [f[0] for f in foods]
    c = np.array([prices.get(f[0], f[2]) for f in foods], dtype=float)
    N = np.array([f[5] for f in foods], dtype=float).reshape(-1, 9).T    # 9 x n, columns are foods
    caps = np.minimum(variety, [own_max.get(f[0], f[3]) for f in foods]).astype(float)

    rows, h, labels = [], [], []
    for i, (lo, hi) in enumerate(limits):
        name, unit = NUTRIENTS[i]
        if lo is not None:
            rows.append(N[i]); h.append(lo); labels.append(("min", name, unit))
        if hi is not None:
            rows.append(-N[i]); h.append(-hi); labels.append(("max", name, unit))
    G = np.vstack([np.array(rows, dtype=float).reshape(-1, len(foods)), -np.eye(len(foods))])
    h = np.concatenate([np.array(h, dtype=float), -caps])
    labels += [("cap", name, "serving") for name in names]
    return Problem(names, [f[1] for f in foods], c, N, G, h, labels, list(limits))


def reduced_costs(p: Problem, s: "Solution"):
    """
    Purpose: for each food, how much cheaper it would need to be to join the menu.
    Math:    c_j - (column j of G) . y. A food on the menu has 0, an unused food
             has a positive value: the price cut it needs before it pays off.
    """
    return p.c - p.G.T @ s.y


# ---------------------------------------------------------------------------
# THE SIMPLEX METHOD (written from scratch, using only row operations)
# ---------------------------------------------------------------------------
def frac(x) -> str:
    """Show a number the way you'd write it by hand: 3, -1/50, 0.0123."""
    f = Fraction(float(x)).limit_denominator(1000)
    return str(f) if abs(float(f) - x) < 1e-9 else f"{x:.4g}"


def coef(x) -> str:
    """A coefficient in a row-operation label, e.g. -100 or (1/200)."""
    t = frac(x)
    return f"({t})" if "/" in t or "." in t else t


def pivot(T, row, col):
    """
    Purpose: one simplex move, done as one Gauss-Jordan step on the tableau T.
    Math:    (1/p)R_row -> R_row, then  k*R_row + R_i -> R_i  for every other row,
             which turns column `col` into a unit column.
    Returns the row operations in class notation, for the intermediate results.
    """
    ops, p = [], T[row, col]
    if abs(p - 1) > EPS:
        ops.append(f"{coef(1 / p)}R{row + 1} -> R{row + 1}")
    T[row] /= p
    factors = -T[:, col]
    factors[row] = 0
    T += np.outer(factors, T[row])                 # every elimination at once
    ops += [f"{coef(k)}R{row + 1} + R{i + 1} -> R{i + 1}"
            for i, k in enumerate(factors) if abs(k) > EPS]
    return ops


@dataclass
class Step:
    entering: int          # column that joins the basis
    leaving: int           # column that leaves the basis
    value: float           # objective value after this pivot
    ops: list              # row operations performed
    tableau: np.ndarray = field(default=None, repr=False)


@dataclass
class SimplexResult:
    y: np.ndarray          # the optimal point
    value: float           # the optimal objective value
    slack_row: np.ndarray  # objective-row entries under the slack columns
    steps: list            # one Step per pivot


def simplex_max(c, A, b, keep_tableaus=False, start_steps=None):
    """
    Purpose: maximize c . y subject to A @ y <= b and y >= 0, where b >= 0.
    Math:    because b >= 0, y = 0 is a valid starting corner. Each slack
             variable turns an inequality into an equation:  A @ y + s = b.

             Tableau  [  A  | I | b ]    rows 1..m are the constraints
                      [ -c  | 0 | 0 ]    the last row is the objective
    """
    m, n = A.shape
    T = np.zeros((m + 1, n + m + 1))
    T[:m, :n], T[:m, n:n + m], T[:m, -1] = A, np.eye(m), b
    T[m, :n] = -c
    basis = list(range(n, n + m))          # start: only the slack variables are "in play"
    steps = []
    if start_steps is not None:
        start_steps.append(T.copy())

    while True:
        improving = np.flatnonzero(T[m, :-1] < -EPS)
        if improving.size == 0:
            break                          # no neighbor is better: this corner is optimal
        col = improving[0]                 # Bland's rule (lowest index) so it never cycles
        rows = np.flatnonzero(T[:m, col] > EPS)
        if rows.size == 0:
            return None                    # the objective can grow forever (unbounded)
        ratios = T[rows, -1] / T[rows, col]                  # ratio test: how far we can move
        tied = rows[ratios <= ratios.min() + EPS]
        row = min(tied, key=lambda i: basis[i])              # Bland's rule for ties
        ops = pivot(T, row, col)
        steps.append(Step(col, basis[row], T[m, -1], ops, T.copy() if keep_tableaus else None))
        basis[row] = col

    y = np.zeros(n)
    for i, j in enumerate(basis):
        if j < n:
            y[j] = T[i, -1]
    return SimplexResult(y, T[m, -1], T[m, n:n + m].copy(), steps)


# ---------------------------------------------------------------------------
# SOLVING THE DIET PROBLEM
# ---------------------------------------------------------------------------
@dataclass
class Solution:
    x: np.ndarray          # servings of each food (the menu)
    y: np.ndarray          # price of each requirement (the mirror problem's answer)
    cost: float
    steps: list


def solve_diet(p: Problem):
    """
    Purpose: find the cheapest menu.
    Math:    solve the mirror problem   max h . y   s.t.  G^T @ y <= c,  y >= 0.
             Prices c are never negative, so y = 0 is a valid start.
             The menu x is read from the final objective row, under the slack
             columns (one slack per food), and its cost equals h . y.
    Returns None when no menu can meet every requirement (the mirror is unbounded).
    """
    r = simplex_max(p.h, p.G.T, p.c)
    if r is None:
        return None
    return Solution(x=r.slack_row, y=r.y, cost=r.value, steps=r.steps)


def describe(p: Problem, column: int) -> str:
    """Name a tableau column of the mirror problem."""
    rows = len(p.labels)
    if column < rows:
        kind, name, _ = p.labels[column]
        return f"price of {name} ({'variety cap' if kind == 'cap' else kind})"
    return f"slack of {p.names[column - rows]}"


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------
def report(p: Problem, s: Solution, preset, diet, variety):
    rule = "-" * 72
    print(rule)
    print(f"DIET OPTIMIZER   {preset}, {diet}, at most {variety} servings of any food")
    print(rule)
    print(f"Nutrition matrix N: {p.N.shape[0]} nutrients x {p.N.shape[1]} foods")
    print(f"Requirement system G @ x >= h: {p.G.shape[0]} rows x {p.G.shape[1]} foods")
    print(f"Mirror problem uses the transpose G^T: {p.G.T.shape[0]} x {p.G.T.shape[1]}")

    print(f"\nSOLVER STEPS ({len(s.steps)} pivots). Each pivot is one Gauss-Jordan step.")
    print("The mirror value is a guaranteed minimum cost. It rises until it meets a real menu.")
    for k, st in enumerate(s.steps, 1):
        print(f"  Pivot {k:2}: {describe(p, st.entering):<38} in   "
              f"guaranteed minimum PHP {st.value:7.2f}")

    print("\nCHEAPEST MENU")
    order = np.argsort(-(s.x * p.c))
    for j in order:
        if s.x[j] > 1e-6:
            print(f"  {s.x[j]:5.2f} x {p.servings[j]:<13} {p.names[j]:<26} PHP {s.x[j] * p.c[j]:7.2f}")
    print(f"  {'Total cost (c . x)':<48} PHP {p.c @ s.x:7.2f}")

    print("\nNUTRITION CHECK (N @ x)")
    totals = p.N @ s.x                                   # matrix-vector product
    for i, ((name, unit), (lo, hi)) in enumerate(zip(NUTRIENTS, p.limits)):
        need = " to ".join(str(v) for v in (lo, hi) if v is not None) if lo and hi else \
            (f"at least {lo}" if lo is not None else f"at most {hi}")
        tight = (lo is not None and abs(totals[i] - lo) < 1e-6) or \
                (hi is not None and abs(totals[i] - hi) < 1e-6)
        print(f"  {name:<14} {totals[i]:9.1f} {unit:<5} need {need:<16} "
              f"{'OK, exactly at the limit' if tight else 'OK'}")

    print("\nWHAT DRIVES THE COST (prices from the mirror problem)")
    drivers = sorted(((v, lab) for v, lab in zip(s.y, p.labels) if v > 1e-7), reverse=True)
    for v, (kind, name, unit) in drivers:
        if kind == "min":
            print(f"  {name} minimum: each extra {unit} required adds PHP {v:.4f}")
        elif kind == "max":
            print(f"  {name} maximum: each extra {unit} allowed saves PHP {v:.4f}")
        else:
            print(f"  {name} variety cap: one more serving allowed saves PHP {v:.4f}")

    gap = abs(p.c @ s.x - p.h @ s.y)
    worst = (p.h - p.G @ s.x).max()
    print("\nCHECKS")
    print(f"  Every requirement met (G @ x >= h): {'yes' if worst < 1e-6 else 'NO'}")
    print(f"  Menu cost c . x = PHP {p.c @ s.x:.4f}, mirror value h . y = PHP {p.h @ s.y:.4f}"
          f"  (difference {gap:.1e})")


# ---------------------------------------------------------------------------
# THE 2-FOOD EXAMPLE (small enough to show every row operation)
# ---------------------------------------------------------------------------
EXAMPLE = dict(foods=["Rice (cups)", "Eggs"], cost=np.array([10.0, 10.0]),
               nutrition=np.array([[200.0, 100.0],      # calories per serving
                                   [4.0, 8.0]]),        # protein (g) per serving
               need=np.array([1200.0, 48.0]))


def print_tableau(T, header):
    print("           " + "".join(f"{h:>10}" for h in header))
    for i, row in enumerate(T):
        name = f"R{i + 1}" + (" obj" if i == len(T) - 1 else "")      # last row is the objective
        print(f"   {name:>7} " + "".join(f"{frac(v):>10}" for v in row))


def example():
    E = EXAMPLE
    A, b, c = E["nutrition"], E["need"], E["cost"]
    print("2-FOOD EXAMPLE: rice (200 kcal, 4 g protein, PHP 10) and eggs (100 kcal, 8 g, PHP 10)")
    print("Need at least 1200 kcal and 48 g protein. Minimize 10x + 10y.\n")

    # Part 1: every corner is the solution of a 2 x 2 linear system
    print("PART 1: corners are where two boundary lines meet (solve a 2 x 2 system)")
    lines = {"calories": (A[0], b[0]), "protein": (A[1], b[1]),
             "rice = 0": (np.array([1.0, 0]), 0.0), "eggs = 0": (np.array([0, 1.0]), 0.0)}
    keys = list(lines)
    for a in range(4):
        for d in range(a + 1, 4):
            M = np.array([lines[keys[a]][0], lines[keys[d]][0]])
            rhs = np.array([lines[keys[a]][1], lines[keys[d]][1]])
            det = np.linalg.det(M)
            if abs(det) < EPS:
                print(f"  {keys[a]:>8} & {keys[d]:<8} det = 0, the lines never cross")
                continue
            pt = np.linalg.solve(M, rhs)
            valid = np.all(A @ pt >= b - 1e-9) and np.all(pt >= -1e-9)
            print(f"  {keys[a]:>8} & {keys[d]:<8} det = {det:7.1f}  corner ({pt[0]:5.2f}, {pt[1]:5.2f})  "
                  + (f"valid, costs PHP {c @ pt:6.2f}" if valid else "breaks a requirement"))

    # Part 2: simplex on the mirror problem, showing the tableau after every pivot
    print("\nPART 2: simplex on the mirror problem  max 1200a + 48b  s.t.  A^T @ (a, b) <= (10, 10)")
    tableaus = []
    r = simplex_max(b, A.T, c, keep_tableaus=True, start_steps=tableaus)
    header = ["a", "b", "s_rice", "s_egg", "value"]
    print("\n  Starting tableau (every price is zero):")
    print_tableau(tableaus[0], header)
    for k, st in enumerate(r.steps, 1):
        print(f"\n  Pivot {k}: " + ",   ".join(st.ops))
        print_tableau(st.tableau, header)
    x = r.slack_row
    print(f"\n  Menu from the objective row under the slack columns: rice = {frac(x[0])}, eggs = {frac(x[1])}")
    print(f"  Cheapest cost = PHP {r.value:.2f}")
    print(f"  Prices: each extra kcal costs PHP {r.y[0]:.4f}, each extra gram of protein PHP {r.y[1]:.4f}")


# ---------------------------------------------------------------------------
# FIGURES FOR THE REPORT (matplotlib)
# Each draw_* function draws one figure onto a given set of axes. make_plots
# saves all six, and the window shows figures 4, 5 and 6 with the same
# functions, so the screen and the report always match.
# ---------------------------------------------------------------------------
TEAL, PURPLE, CORAL, AMBER = "#1D9E75", "#7F77DD", "#D85A30", "#E3A008"
INK, MUTED, GRID, ZONE = "#101828", "#667085", "#E4E7EC", "#CDEEDF"
GROUP_COLORS = dict(zip(PRESETS, (TEAL, PURPLE, CORAL, AMBER)))


def figure_style():
    """Matplotlib settings shared by the saved figures and the window's charts."""
    from matplotlib import font_manager
    installed = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [f for f in ("Segoe UI", "Helvetica Neue", "Arial") if f in installed] + ["DejaVu Sans"]
    return {"font.family": "sans-serif", "font.sans-serif": fonts,
            "axes.titlelocation": "left", "axes.titlesize": 11.5, "axes.titlepad": 12,
            "axes.titlecolor": INK, "axes.labelsize": 9.5}


def style_axes(ax, grid="x"):
    """No box, light grid lines along `grid` ("x", "y", "both" or None), quiet labels."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D0D5DD")
    ax.tick_params(colors=MUTED, labelsize=8.5, length=0, pad=6)
    ax.xaxis.label.set_color("#344054")
    ax.yaxis.label.set_color("#344054")
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def draw_menu(ax, p: Problem, s: Solution):
    """Figure 1: what each food on the menu costs."""
    style_axes(ax, "x")
    used = [j for j in np.argsort(s.x * p.c) if s.x[j] > 1e-6]
    costs = [s.x[j] * p.c[j] for j in used]
    top = max(costs, default=1.0)
    ax.barh([p.names[j] for j in used], costs, color=TEAL, height=0.62)
    for k, j in enumerate(used):
        ax.text(costs[k] + top * 0.015, k, f"{s.x[j]:.2f} × {p.servings[j]}   ₱{costs[k]:.2f}",
                va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(0, top * 1.4)
    ax.set_xlabel("Cost (₱)")


def draw_nutrition(ax, p: Problem, s: Solution):
    """Figure 2: each of the day's totals (N @ x) as a percent of its limit."""
    style_axes(ax, "x")
    totals = p.N @ s.x
    right = 100.0
    for i, ((name, unit), (lo, hi)) in enumerate(zip(NUTRIENTS, p.limits)):
        ref = lo if lo is not None else hi
        if not ref:
            continue
        pct = 100 * totals[i] / ref
        label_x = pct + 4
        ax.barh(i, pct, color=TEAL if lo is not None else PURPLE, height=0.62)
        if lo is not None and hi is not None:
            tick = 100 * hi / ref
            ax.plot([tick] * 2, [i - 0.38, i + 0.38], color=CORAL, lw=2.2, solid_capstyle="butt")
            if 0 <= tick - pct < 45:                     # the tick sits where the label would go
                label_x = tick + 4
            right = max(right, tick)
        ax.text(label_x, i, f"{totals[i]:,.0f} {unit}", va="center", fontsize=8.5, color=MUTED)
        right = max(right, pct)
    ax.axvline(100, color=INK, lw=1, ls=(0, (4, 3)))
    ax.set_yticks(range(len(NUTRIENTS)), [n for n, _ in NUTRIENTS])
    ax.invert_yaxis()
    ax.set_xlim(0, right * 1.15)
    ax.set_xlabel("Percent of the limit (dashed line = 100%, red tick = maximum)")


def draw_cost_drivers(ax, p: Problem, s: Solution):
    """Figure 3: the price of each requirement that pushes the cost up (from the mirror problem)."""
    style_axes(ax, "x")
    drivers = sorted(((v, lab) for v, lab in zip(s.y, p.labels) if v > 1e-7 and lab[0] != "cap"),
                     key=lambda t: -t[0])
    ax.barh([f"{name} ({kind})" for _, (kind, name, _) in drivers], [v for v, _ in drivers],
            color=CORAL, height=0.55)
    for k, (v, (_, _, unit)) in enumerate(drivers):
        ax.text(v, k, f"  ₱{v:.3f} per {unit}", va="center", fontsize=8.5, color=MUTED)
    ax.invert_yaxis()
    ax.set_xlim(0, max((v for v, _ in drivers), default=1.0) * 1.4)
    ax.set_xlabel("Price of one more unit of the requirement (₱)")


def draw_solver_progress(ax, s: Solution, line=TEAL):
    """Figure 4: the guaranteed minimum after each pivot rises until it meets a real menu."""
    from matplotlib.ticker import MaxNLocator
    style_axes(ax, "y")
    xs = range(len(s.steps) + 1)
    ys = [0] + [st.value for st in s.steps]
    ax.fill_between(xs, ys, color=PURPLE, alpha=0.10, linewidth=0)
    ax.plot(xs, ys, "o-", color=PURPLE, lw=2, ms=3.5)
    ax.axhline(s.cost, color=line, lw=1.2, ls=(0, (4, 3)))
    ax.annotate(f"cheapest menu ₱{s.cost:.2f}", xy=(0, s.cost), xytext=(2, 6),
                textcoords="offset points", color=line, fontsize=9)
    ax.set_xlim(0, max(len(s.steps), 1))
    ax.set_ylim(0, max(s.cost, 1e-9) * 1.15)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Pivot number")
    ax.set_ylabel("Guaranteed minimum (₱)")


def variety_costs(diet="anything", prices=None, exclude=(), own_max=None, groups=None,
                  varieties=range(2, 9)):
    """
    Purpose: the cheapest day for each group at each variety level (the data of figure 5).
    `groups` maps a name to its (min, max) limits and defaults to the four presets.
    A setting with no valid menu gives nan, which leaves a gap in its line.
    """
    groups = groups or PRESETS
    any_food = any(f[4] not in DIETS[diet] and f[0] not in exclude for f in FOODS)
    costs = {}
    for name, limits in groups.items():
        row = []
        for v in varieties:
            s = solve_diet(build_problem(diet=diet, variety=v, prices=prices, exclude=exclude,
                                         limits=limits, own_max=own_max)) if any_food else None
            row.append(np.nan if s is None else s.cost)
        costs[name] = row
    return costs


def draw_variety(ax, costs, varieties=range(2, 9), mark=None):
    """
    Figure 5: the cheapest day at each variety level, one line per group, named at its right end.
    `mark` = (group name, variety) rings one point. The window uses it for the current setting.
    """
    style_axes(ax, "y")
    xs = list(varieties)
    ends = []                                          # (label height, x, y, name, color)
    for name, ys in costs.items():
        color = GROUP_COLORS.get(name, INK)
        ax.plot(xs, ys, "o-", color=color, lw=2, ms=4.5)
        last = [i for i, y in enumerate(ys) if not np.isnan(y)]
        if last:
            ends.append([ys[last[-1]], xs[last[-1]], ys[last[-1]], name, color])
    values = [y for ys in costs.values() for y in ys if not np.isnan(y)]
    if values:
        lo, hi = min(values), max(values)
        gap = (hi - lo) * 0.08 or 1.0
        ends.sort()
        for k in range(1, len(ends)):                  # push labels apart so they never overlap
            ends[k][0] = max(ends[k][0], ends[k - 1][0] + gap)
        for label_y, x, y, name, color in ends:
            ax.annotate(f"{name}  ₱{y:.0f}", xy=(x, y), xytext=(x + 0.3, label_y), textcoords="data",
                        va="center", fontsize=8.5, color=color)
        ax.set_ylim(lo - gap, max(hi, ends[-1][0]) + gap)
    if mark and mark[0] in costs and mark[1] in xs:
        y = costs[mark[0]][xs.index(mark[1])]
        if not np.isnan(y):
            ax.plot(mark[1], y, "o", ms=13, mfc="none", mec=GROUP_COLORS.get(mark[0], INK), mew=2)
    ax.set_xticks(xs)
    ax.set_xlim(xs[0] - 0.3, xs[-1] + 0.3)
    ax.set_xlabel("Most servings allowed of any one food")
    ax.set_ylabel("Cheapest day (₱)")


def draw_two_food(ax):
    """Figure 6: the 2-food example. The valid menus form a region with flat sides and the cheapest is a corner."""
    E = EXAMPLE
    A, b, c = E["nutrition"], E["need"], E["cost"]
    style_axes(ax, "both")
    g = np.linspace(0, 14, 400)
    X, Y = np.meshgrid(g, g)
    valid = (A[0, 0] * X + A[0, 1] * Y >= b[0]) & (A[1, 0] * X + A[1, 1] * Y >= b[1])
    ax.contourf(X, Y, valid, levels=[0.5, 1], colors=[ZONE])
    best = np.linalg.solve(A, b)                       # B: where the two boundary lines cross
    for i, (color, style, what) in enumerate(((CORAL, "-", "calories"), (PURPLE, "--", "protein"))):
        ax.plot(g, (b[i] - A[i, 0] * g) / A[i, 1], color=color, lw=2.2, ls=style,
                label=f"{A[i, 0]:g}x + {A[i, 1]:g}y = {b[i]:g} ({what})")
    ax.plot(g, (c @ best - c[0] * g) / c[1], color=MUTED, lw=1.2, ls=":",
            label=f"{c[0]:g}x + {c[1]:g}y = {c @ best:g} (cost line)")
    corners = (("A", np.array([0, max(b / A[:, 1])]), (10, 6), "left"),      # on the eggs axis
               ("B", best, (10, 8), "left"),
               ("C", np.array([max(b / A[:, 0]), 0]), (0, 12), "center"))    # on the rice axis
    for name, pt, offset, align in corners:
        cheapest = name == "B"
        ax.plot(*pt, "o", color=TEAL if cheapest else INK, ms=8 if cheapest else 6, clip_on=False, zorder=3)
        ax.annotate(f"{name}  ₱{c @ pt:g}" + ("  cheapest" if cheapest else ""), pt, xytext=offset,
                    textcoords="offset points", ha=align, fontsize=9, color=INK,
                    fontweight="bold" if cheapest else "normal")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 14)
    ax.set_xlabel("Cups of rice (x)")
    ax.set_ylabel("Eggs (y)")
    ax.legend(fontsize=8, loc="upper right", framealpha=0.92, edgecolor="none")


def make_plots(p: Problem, s: Solution, folder="figures"):
    """Save figures 1 to 6 as PNG files (uses Matplotlib's Figure directly, so no window opens)."""
    import matplotlib
    from matplotlib.figure import Figure

    os.makedirs(folder, exist_ok=True)
    figures = [
        ("fig1_menu.png", (7, 3.6), f"Figure 1. Cheapest menu, total ₱{s.cost:.2f}",
         lambda ax: draw_menu(ax, p, s)),
        ("fig2_nutrition.png", (7, 3.8), "Figure 2. Every requirement is met (purple bars are maximum-only limits)",
         lambda ax: draw_nutrition(ax, p, s)),
        ("fig3_cost_drivers.png", (7, 2.8), "Figure 3. Requirements that push the cost up (from the mirror problem)",
         lambda ax: draw_cost_drivers(ax, p, s)),
        ("fig4_solver_progress.png", (7, 3.2),
         "Figure 4. Each pivot raises the proven lower bound until it meets a real menu",
         lambda ax: draw_solver_progress(ax, s)),
        ("fig5_variety.png", (7, 3.4), "Figure 5. More variety (a lower cap) costs more",
         lambda ax: draw_variety(ax, variety_costs())),
        ("fig6_two_food_region.png", (5.8, 4.8), "Figure 6. The cheapest valid menu is a corner", draw_two_food),
    ]
    with matplotlib.rc_context(figure_style()):
        for name, size, title, draw in figures:
            fig = Figure(figsize=size, layout="constrained")
            ax = fig.add_subplot()
            draw(ax)
            ax.set_title(title)
            fig.savefig(os.path.join(folder, name), dpi=150, facecolor="white", bbox_inches="tight",
                        pad_inches=0.12)
    print(f"Saved {len(figures)} figures in {folder}/")


# ---------------------------------------------------------------------------
# TESTING AGAINST SCIPY
# ---------------------------------------------------------------------------
def test():
    """Compare our simplex with SciPy's solver on every preset, diet and variety setting."""
    try:
        from scipy.optimize import linprog
    except ImportError:
        print("SciPy is not installed. Run: pip install scipy")
        return
    worst, count = 0.0, 0
    for preset in PRESETS:
        for diet in DIETS:
            for variety in range(2, 9):
                p = build_problem(preset, diet, variety)
                ours = solve_diet(p)
                ref = linprog(p.c, A_ub=-p.G, b_ub=-p.h, bounds=(0, None), method="highs")
                if ours is None or ref.status != 0:
                    assert ours is None and ref.status == 2, (preset, diet, variety)
                    continue
                assert (p.G @ ours.x >= p.h - 1e-6).all(), "menu breaks a requirement"
                assert abs(p.c @ ours.x - p.h @ ours.y) < 1e-6, "costs of the two problems differ"
                worst = max(worst, abs(ours.cost - ref.fun))
                count += 1
    print(f"Checked {count} settings against SciPy. Largest cost difference: PHP {worst:.2e}")
    assert worst < 1e-6
    print("All tests passed.")


# ---------------------------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------------------------
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Find the cheapest day of eating that meets every nutrition target.")
    ap.add_argument("--preset", default="Adult woman", choices=list(PRESETS))
    ap.add_argument("--diet", default="anything", choices=list(DIETS))
    ap.add_argument("--variety", type=int, default=4, help="most servings of any one food (2 to 8)")
    ap.add_argument("--price", action="append", default=[], metavar="FOOD=PRICE",
                    help='change a price, e.g. --price "Egg=10"')
    ap.add_argument("--exclude", action="append", default=[], metavar="FOOD", help="leave a food out")
    ap.add_argument("--example", action="store_true", help="2-food walkthrough with every row operation")
    ap.add_argument("--plots", action="store_true", help="save the report figures into figures/")
    ap.add_argument("--test", action="store_true", help="compare with SciPy on every setting")
    ap.add_argument("--gui", action="store_true", help="open the Diet Optimizer window")
    args = ap.parse_args()

    if args.gui:
        import diet_gui
        return diet_gui.main()
    if args.example:
        return example()
    if args.test:
        return test()

    prices = {k.strip(): float(v) for k, v in (item.rsplit("=", 1) for item in args.price)}
    p = build_problem(args.preset, args.diet, args.variety, prices, set(args.exclude))
    s = solve_diet(p)
    if s is None:
        print("No menu meets every requirement. Try a higher variety cap or another eating style.")
        return
    report(p, s, args.preset, args.diet, args.variety)
    if args.plots:
        make_plots(p, s)


if __name__ == "__main__":
    main()
