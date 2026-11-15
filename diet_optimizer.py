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

# Daily (minimum, maximum) for each nutrient, in the order of NUTRIENTS. None means no limit.
PRESETS = {
    "Adult woman": [(1800, 2300), (50, None), (40, 70), (200, 300), (25, None),
                    (1000, None), (18, None), (75, None), (None, 2300)],
    "Adult man":   [(2200, 2800), (60, None), (50, 85), (250, 350), (30, None),
                    (1000, None), (8, None), (90, None), (None, 2300)],
    "Teen":        [(2000, 2600), (52, None), (45, 80), (230, 340), (26, None),
                    (1300, None), (15, None), (65, None), (None, 2300)],
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
# ---------------------------------------------------------------------------
def make_plots(p: Problem, s: Solution, folder="figures"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(folder, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
    teal, coral, purple, gray = "#1D9E75", "#D85A30", "#7F77DD", "#888780"

    # 1. Menu: what each food costs
    used = [j for j in np.argsort(s.x * p.c) if s.x[j] > 1e-6]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh([p.names[j] for j in used], [s.x[j] * p.c[j] for j in used], color=teal)
    for k, j in enumerate(used):
        ax.text(s.x[j] * p.c[j] + 0.4, k, f"{s.x[j]:.2f} x {p.servings[j]}", va="center", fontsize=8)
    ax.set_xlabel("Cost (PHP)")
    ax.set_title(f"Figure 1. Cheapest menu, total PHP {s.cost:.2f}")
    fig.tight_layout(); fig.savefig(f"{folder}/fig1_menu.png"); plt.close(fig)

    # 2. Nutrition check: each total as a percent of its limit
    totals = p.N @ s.x
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for i, ((name, unit), (lo, hi)) in enumerate(zip(NUTRIENTS, p.limits)):
        ref = lo if lo is not None else hi
        ax.barh(i, 100 * totals[i] / ref, color=teal if lo is not None else purple)
        ax.text(100 * totals[i] / ref + 2, i, f"{totals[i]:.0f} {unit}", va="center", fontsize=8)
        if lo is not None and hi is not None:
            ax.plot([100 * hi / ref] * 2, [i - 0.4, i + 0.4], color=coral, lw=2)
    ax.axvline(100, color="black", lw=1, ls="--")
    ax.set_yticks(range(len(NUTRIENTS)), [n for n, _ in NUTRIENTS])
    ax.invert_yaxis()
    ax.set_xlabel("Percent of the limit (dashed line = 100%, red tick = maximum)")
    ax.set_title("Figure 2. Every requirement is met (teal: minimums, purple: maximums)")
    fig.tight_layout(); fig.savefig(f"{folder}/fig2_nutrition.png"); plt.close(fig)

    # 3. What drives the cost
    drivers = sorted(((v, lab) for v, lab in zip(s.y, p.labels) if v > 1e-7 and lab[0] != "cap"),
                     reverse=True)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.barh([f"{name} ({kind})" for _, (kind, name, _) in drivers], [v for v, _ in drivers], color=coral)
    for k, (v, (_, _, unit)) in enumerate(drivers):
        ax.text(v, k, f"  PHP {v:.3f} per {unit}", va="center", fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Price of one more unit of the requirement (PHP)")
    ax.set_title("Figure 3. Requirements that push the cost up (from the mirror problem)")
    fig.tight_layout(); fig.savefig(f"{folder}/fig3_cost_drivers.png"); plt.close(fig)

    # 4. Solver progress: the guaranteed minimum rises each pivot
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(range(len(s.steps) + 1), [0] + [st.value for st in s.steps], "o-", color=purple)
    ax.axhline(s.cost, color=teal, ls="--", lw=1)
    ax.text(0.2, s.cost - 9, f"cheapest menu PHP {s.cost:.2f}", color=teal, fontsize=9)
    ax.set_xlabel("Pivot number")
    ax.set_ylabel("Guaranteed minimum (PHP)")
    ax.set_title("Figure 4. Each pivot raises the proven lower bound until it meets a real menu")
    fig.tight_layout(); fig.savefig(f"{folder}/fig4_solver_progress.png"); plt.close(fig)

    # 5. Variety versus cost for each group
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for preset, color in zip(PRESETS, (teal, purple, coral)):
        caps = range(2, 9)
        costs = [solve_diet(build_problem(preset, "anything", v)).cost for v in caps]
        ax.plot(caps, costs, "o-", color=color, label=preset)
    ax.set_xlabel("Most servings allowed of any one food")
    ax.set_ylabel("Cheapest day (PHP)")
    ax.set_title("Figure 5. More variety (a lower cap) costs a little more")
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(f"{folder}/fig5_variety.png"); plt.close(fig)

    # 6. The 2-food example: the region of valid menus and its corners
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    g = np.linspace(0, 14, 300)
    X, Y = np.meshgrid(g, g)
    E = EXAMPLE
    valid = (E["nutrition"][0, 0] * X + E["nutrition"][0, 1] * Y >= 1200) & \
            (E["nutrition"][1, 0] * X + E["nutrition"][1, 1] * Y >= 48)
    ax.contourf(X, Y, valid, levels=[0.5, 1], colors=[teal], alpha=0.25)
    ax.plot(g, 12 - 2 * g, color=coral, lw=2, label="200x + 100y = 1200 (calories)")
    ax.plot(g, 6 - g / 2, color=purple, lw=2, ls="--", label="4x + 8y = 48 (protein)")
    ax.plot(g, 8 - g, color=gray, lw=1, ls=":", label="10x + 10y = 80 (cost line)")
    for (cx, cy, txt) in ((0, 12, "A  PHP 120"), (4, 4, "B  PHP 80 (cheapest)"), (12, 0, "C  PHP 120")):
        ax.plot(cx, cy, "o", color="black", ms=6)
        ax.annotate(txt, (cx, cy), xytext=(8, 8), textcoords="offset points", fontsize=9)
    ax.set_xlim(0, 14); ax.set_ylim(0, 14)
    ax.set_xlabel("Cups of rice (x)"); ax.set_ylabel("Eggs (y)")
    ax.set_title("Figure 6. The cheapest valid menu is a corner")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    fig.tight_layout(); fig.savefig(f"{folder}/fig6_two_food_region.png"); plt.close(fig)

    print(f"Saved 6 figures in {folder}/")


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
