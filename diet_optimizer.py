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

Vectors and matrices are plain Python lists (a matrix is a list of rows).
Every operation on them is written out in this file: dot product, matrix-vector
product, transpose, row operations, 2 x 2 determinants and Cramer's rule.
No library does any of the math. Matplotlib only draws the figures, and SciPy
is used only by --test, as an outside check.

USAGE
-----
    python diet_optimizer.py                       adult woman, any food, variety 4
    python diet_optimizer.py --preset "Adult man" --diet plant-based --variety 3
    python diet_optimizer.py --price "Egg=10" --exclude "Beef"
    python diet_optimizer.py --example             2-food walkthrough with every row operation
    python diet_optimizer.py --plots               save the report figures into figures/
    python diet_optimizer.py --test                compare with SciPy on every setting
    python diet_optimizer.py --gui                 open the window (same as python diet_gui.py)

Prices: WFP retail market prices, Davao City, October 2026 (see DATA below).
Nutrition: USDA SR28, raw food. For coursework, not medical advice.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass, field
from fractions import Fraction

EPS = 1e-9          # tolerance for treating a floating-point number as zero

# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------
NUTRIENTS = [("Calories", "kcal"), ("Protein", "g"), ("Fat", "g"), ("Carbohydrates", "g"),
             ("Fiber", "g"), ("Calcium", "mg"), ("Iron", "mg"), ("Vitamin C", "mg"),
             ("Sodium", "mg")]

PLANT, MEAT_FISH, EGG_DAIRY = 0, 1, 2

# PRICES are real market prices: the World Food Programme's retail prices for Davao City, October 2026
# (data/wfp_food_prices_davao_city_2026-10.csv). They are per kilogram as bought (eggs: per piece), the
# way a market vendor quotes them. Every food below has a price in that file.
#
# NUTRITION is for raw food, per 100 g of the edible part, from the USDA National Nutrient Database for
# Standard Reference, Release 28 (SR28). A kilogram as bought includes peel, bones and seeds, so each food
# has an edible share: SR28's refuse figure, or for whole fish the edible-flesh yield in FAO Fisheries
# Technical Paper 309 (1989). Pork and beef count as boneless, since WFP lists the cuts with bones apart.
#
# A serving is 100 g as bought (egg: 1 egg). The menu x counts servings, and for one serving
#   price     = market price per kg  x  kg in a serving
#   nutrients = nutrients per 100 g of the edible part  x  edible grams in a serving / 100
PRICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                          "wfp_food_prices_davao_city_2026-10.csv")

# (name, WFP commodity, priced per "kg" or "piece", grams as bought in a serving, edible share,
#  own maximum servings a day, kind, SR28 number, nutrients per 100 g of the edible part)
#  nutrients:  kcal   protein  fat   carbs  fiber  calcium  iron  vitamin C  sodium
FOOD_DATA = [
    ("Rice (regular milled)", "Rice (regular, milled)", "kg", 100, 1.00, 4, PLANT, "20444",
     [365, 7.13, 0.66, 79.95, 1.3, 28, 0.8, 0, 5]),
    ("Corn (yellow, dried)", "Maize (yellow)", "kg", 100, 1.00, 4, PLANT, "20014",
     [365, 9.42, 4.74, 74.26, 7.3, 7, 2.71, 0, 35]),
    ("Potato", "Potatoes (Irish)", "kg", 100, 0.75, 4, PLANT, "11352",
     [77, 2.05, 0.09, 17.49, 2.1, 12, 0.81, 19.7, 6]),
    ("Mung beans (dried)", "Beans (mung)", "kg", 100, 1.00, 2, PLANT, "16080",
     [347, 23.86, 1.15, 62.62, 16.3, 132, 6.74, 4.8, 15]),
    ("Peanuts (shelled)", "Groundnuts (shelled)", "kg", 100, 1.00, 1, PLANT, "16087",
     [567, 25.8, 49.24, 16.13, 8.5, 92, 4.58, 0, 18]),
    ("Egg", "Eggs", "piece", 57, 0.88, 4, EGG_DAIRY, "01123",          # a large egg: 50 g without its shell
     [143, 12.56, 9.51, 0.72, 0, 56, 1.75, 0, 142]),
    ("Chicken (whole)", "Meat (chicken, whole)", "kg", 100, 0.69, 3, MEAT_FISH, "05001",
     [213, 18.33, 14.83, 0.13, 0, 11, 1.31, 2.6, 70]),
    ("Pork", "Meat (pork)", "kg", 100, 1.00, 2, MEAT_FISH, "10226",
     [177, 20.08, 10.14, 0, 0, 16, 0.74, 0.1, 54]),
    ("Beef", "Meat (beef)", "kg", 100, 1.00, 2, MEAT_FISH, "13795",
     [214, 20.01, 14.42, 0, 0, 17, 1.69, 0, 52]),
    ("Milkfish (bangus)", "Fish (milkfish)", "kg", 100, 0.61, 3, MEAT_FISH, "15053",
     [148, 20.53, 6.73, 0, 0, 51, 0.32, 0, 72]),
    ("Round scad (galunggong)", "Fish (roundscad)", "kg", 100, 0.52, 3, MEAT_FISH, "15050",   # jack mackerel:
     [158, 20.07, 7.89, 0, 0, 23, 1.16, 2.0, 86]),                     # same family, SR28 has no scad
    ("Tilapia", "Fish (tilapia)", "kg", 100, 0.37, 3, MEAT_FISH, "15261",
     [96, 20.08, 1.7, 0, 0, 10, 0.56, 0, 52]),
    ("Anchovies (dilis)", "Anchovies", "kg", 100, 0.62, 3, MEAT_FISH, "15001",
     [131, 20.35, 4.84, 0, 0, 147, 3.25, 0, 104]),
    ("Ampalaya (bitter gourd)", "Bitter melon", "kg", 100, 0.83, 3, PLANT, "11024",
     [17, 1.0, 0.17, 3.7, 2.8, 19, 0.43, 84, 5]),
    ("Cabbage", "Cabbage", "kg", 100, 0.80, 3, PLANT, "11109",
     [25, 1.28, 0.1, 5.8, 2.5, 40, 0.47, 36.6, 18]),
    ("Carrots", "Carrots", "kg", 100, 0.89, 3, PLANT, "11124",
     [41, 0.93, 0.24, 9.58, 2.8, 33, 0.3, 5.9, 69]),
    ("Eggplant", "Eggplants", "kg", 100, 0.81, 3, PLANT, "11209",
     [25, 0.98, 0.18, 5.88, 3.0, 9, 0.23, 2.2, 2]),
    ("Squash (kalabasa)", "Squashes", "kg", 100, 0.70, 3, PLANT, "11422",
     [26, 1.0, 0.1, 6.5, 0.5, 21, 0.8, 9.0, 1]),
    ("Upo (bottle gourd)", "Bottle gourd", "kg", 100, 0.70, 3, PLANT, "11218",
     [14, 0.62, 0.02, 3.39, 0.5, 26, 0.2, 10.1, 2]),
    ("String beans (sitaw)", "Beans (string)", "kg", 100, 0.95, 3, PLANT, "11199",   # SR28 lists no fiber
     [47, 2.8, 0.4, 8.35, 0, 50, 0.47, 18.8, 4]),
    ("Tomato", "Tomatoes", "kg", 100, 0.91, 3, PLANT, "11529",
     [18, 0.88, 0.2, 3.89, 1.2, 10, 0.27, 13.7, 5]),
    ("Banana (lakatan)", "Bananas (lakatan)", "kg", 100, 0.64, 4, PLANT, "09040",
     [89, 1.09, 0.33, 22.84, 2.6, 5, 0.26, 8.7, 1]),
    ("Banana (latundan)", "Bananas (latundan)", "kg", 100, 0.64, 4, PLANT, "09040",
     [89, 1.09, 0.33, 22.84, 2.6, 5, 0.26, 8.7, 1]),
    ("Mango (carabao)", "Mangoes (carabao)", "kg", 100, 0.71, 3, PLANT, "09176",
     [60, 0.82, 0.38, 14.98, 1.6, 11, 0.16, 36.4, 1]),
]

PRICE_UNIT = {f[0]: f[2] for f in FOOD_DATA}                      # "kg" or "piece"
SERVING_GRAMS = {f[0]: f[3] for f in FOOD_DATA}                   # grams as bought in one serving
PER_SERVING = {f[0]: f[3] / 1000 if f[2] == "kg" else 1.0 for f in FOOD_DATA}   # market units in a serving
COMMODITY = {f[0]: f[1] for f in FOOD_DATA}                       # the food's name in the WFP file


def read_prices(path=PRICE_FILE):
    """The WFP file's retail prices as {commodity: price in PHP}, with its market and date."""
    prices, places = {}, set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["pricetype"] == "Retail" and row["currency"] == "PHP":
                prices[row["commodity"]] = float(row["price"])
                places.add((row["market"], row["date"]))
    if len(places) != 1:
        raise ValueError(f"{path} should hold one market and one month, not {sorted(places)}")
    (market, date), = places
    return prices, market, date


def month_name(date):
    """'2026-10-15' -> 'October 2026'."""
    names = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December")
    year, month, _ = date.split("-")
    return f"{names[int(month) - 1]} {year}"


PRICES, MARKET, MONTH = read_prices()


def make_foods():
    """Each food as (name, serving, market price, own maximum servings, kind, nutrients in one serving)."""
    foods = []
    for name, commodity, unit, grams, edible, own_max, kind, _, per_100g in FOOD_DATA:
        if commodity not in PRICES:
            raise ValueError(f"{PRICE_FILE} has no price for {commodity} ({name})")
        serving = "1 egg" if unit == "piece" else f"{grams} g"
        foods.append((name, serving, PRICES[commodity], own_max, kind,
                      [v * grams * edible / 100 for v in per_100g]))
    return foods


FOODS = make_foods()


def amount(name, servings):
    """What to buy, in words: '358 g', '1.25 kg', '9.5 g' or '4 eggs'."""
    if PRICE_UNIT[name] == "piece":
        n = round(servings, 1)
        return f"{n:g} {name.lower()}{'' if n == 1 else 's'}"
    grams = servings * SERVING_GRAMS[name]
    return f"{grams / 1000:.2f} kg" if grams >= 1000 else f"{grams:.0f} g" if grams >= 10 else f"{grams:.1f} g"

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
# VECTORS AND MATRICES (plain Python lists, every operation written out)
# A vector is a list of numbers. A matrix is a list of rows, each a vector.
# ---------------------------------------------------------------------------
def dot(u, v):
    """Dot product  u . v = u1 v1 + u2 v2 + ... + un vn."""
    return sum(a * b for a, b in zip(u, v))


def mat_vec(A, x):
    """
    Matrix-vector product A x. Entry i is (row i of A) . x, so the result is the
    linear combination x1 (column 1) + x2 (column 2) + ... of A's columns.
    """
    return [dot(row, x) for row in A]


def transpose(A):
    """A^T: row i of A becomes column i."""
    return [list(column) for column in zip(*A)]


def scale(v, k):
    """
    Purpose: multiply a vector by a number (scalar multiplication).
    Math:    k v = (k v1, k v2, ..., k vn).
    """
    return [k * a for a in v]


def identity(n):
    """The n x n identity matrix I: 1 on the diagonal, 0 everywhere else."""
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def shape(A):
    """(number of rows, number of columns) of a matrix."""
    return len(A), len(A[0]) if A else 0


def det2(M):
    """Determinant of a 2 x 2 matrix [[a, b], [c, d]]:  ad - bc."""
    (a, b), (c, d) = M
    return a * d - b * c


def cramer2(M, rhs):
    """
    Solve the 2 x 2 system M v = rhs by Cramer's rule: v_i = det(M_i) / det(M),
    where M_i is M with column i replaced by rhs. Needs det(M) != 0.
    """
    (a, b), (c, d) = M
    e, f = rhs
    D = det2(M)
    # "+ 0.0" turns a -0.0 (from 0 divided by a negative determinant) into a plain 0.0
    return [det2([[e, b], [f, d]]) / D + 0.0, det2([[a, e], [c, f]]) / D + 0.0]


# ---------------------------------------------------------------------------
# BUILDING THE SYSTEM  G @ x >= h
# ---------------------------------------------------------------------------
@dataclass
class Problem:
    names: list            # foods allowed on this menu
    servings: list         # serving size of each food (100 g as bought, or 1 egg)
    c: list                # price of one serving of each food
    N: list                # nutrition matrix (9 rows), one column per food
    G: list                # every requirement as a row, so that G @ x >= h
    h: list
    labels: list           # (kind, name, unit) for each row of G
    limits: list           # the (min, max) pair for each nutrient


def build_problem(preset="Adult woman", diet="anything", variety=4, prices=None, exclude=(),
                  limits=None, own_max=None):
    """
    Purpose: turn the food list and a person's requirements into G @ x >= h.
    Math:    a minimum is  N_i . x >= lo,  a maximum is  -N_i . x >= -hi,
             and the variety cap is  -x_j >= -cap_j  (all the same ">=" form).
    Optional: `prices` replaces market prices (PHP per kg, or per egg), `limits` replaces the
              preset's (min, max) pairs, and `own_max` changes a food's own serving limit.
    """
    prices, own_max = prices or {}, own_max or {}
    limits = limits or PRESETS[preset]
    foods = [f for f in FOODS if f[4] not in DIETS[diet] and f[0] not in exclude]
    names = [f[0] for f in foods]
    c = [float(prices.get(f[0], f[2])) * PER_SERVING[f[0]] for f in foods]    # price of one serving
    # 9 x n: row i is nutrient i in every food, so column j is food j's nutrition label
    N = [[float(f[5][i]) for f in foods] for i in range(len(NUTRIENTS))]
    caps = [float(min(variety, own_max.get(f[0], f[3]))) for f in foods]

    rows, h, labels = [], [], []
    for i, (lo, hi) in enumerate(limits):
        name, unit = NUTRIENTS[i]
        if lo is not None:
            rows.append(list(N[i])); h.append(float(lo)); labels.append(("min", name, unit))
        if hi is not None:
            rows.append([-v for v in N[i]]); h.append(-float(hi)); labels.append(("max", name, unit))
    G = rows + [[-v for v in e] for e in identity(len(foods))]     # stack the rows of -I under them
    h = h + [-cap for cap in caps]
    labels += [("cap", name, "serving") for name in names]
    return Problem(names, [f[1] for f in foods], c, N, G, h, labels, list(limits))


# ---------------------------------------------------------------------------
# PLANNING SOME OF THE DAY'S MEALS (used by the window)
# Planning m of the day's M meals is the share f = m / M of the day. Every
# goal AND every serving cap is multiplied by f, so the system for the plan is
#     G x >= f h      (the same G, every right-hand side scaled by f).
# The solver then finds the cheapest menu for these smaller goals. Because
# N x and c . x are linear, that menu comes out as  x_plan = f x_day, and it
# costs  f (c . x_day). The solver still finds it on its own; the window
# never takes that shortcut, and seeing it happen is a check that it is right.
# ---------------------------------------------------------------------------
def meal_limits(limits, f):
    """
    Purpose: the goals for the share f of the day (for example f = 1/3 for 1 of 3 meals).
    Math:    each (min, max) pair is multiplied by f: the vector of minimums becomes
             f lo and the vector of maximums f hi. None (no limit) stays None.
             Maximums shrink too: one meal gets a third of the day's sodium allowance.
    """
    lows = scale([0.0 if lo is None else lo for lo, _ in limits], f)
    highs = scale([0.0 if hi is None else hi for _, hi in limits], f)
    return [(None if lo is None else a, None if hi is None else b)
            for (lo, hi), a, b in zip(limits, lows, highs)]


def meal_caps(own_max, f):
    """
    Purpose: each food's own daily maximum, for the share f of the day.
    Math:    the maximums form a vector, and it is scaled by f.
    The caps must shrink with the goals. With the day's caps, one meal could use the
    whole day's allowance of the cheapest food (₱40.97 instead of ₱50.46 for 1 of 3
    meals with the defaults), and three such meals in a row would break the daily cap.
    """
    names = [food[0] for food in FOODS]
    caps = scale([float(own_max.get(food[0], food[3])) for food in FOODS], f)     # f times the cap vector
    return dict(zip(names, caps))


@dataclass
class BudgetCheck:
    plan_budget: float     # the budget for one day of the planned meals
    left: float            # plan_budget - cost (negative means short)
    meal_budget: float     # plan_budget per planned meal
    meal_cost: float       # cost per planned meal
    meals_covered: float   # how many meals' goals the budget pays for
    day_budget: float      # plan_budget as a whole day (divided by f)
    fits: bool


def budget_check(cost, budget, period_days, planned, meals_a_day):
    """
    Purpose: compare a budget with the cheapest cost of the planned goals.
    Math:    plan budget  = budget / period_days     (period_days is 1, 7 or 30)
             left         = plan budget - cost
             per meal     = plan budget / planned,  cost / planned
             meals covered = plan budget / (cost per meal)
    The budget is NOT added to G x >= h as a row  -c . x >= -B. The solver already finds
    the cheapest menu that meets the goals, so that row could never make the menu cheaper;
    it could only turn "too expensive" into "no menu", which says less. When the budget is
    short, the mirror value h . y (= cost) is a guaranteed minimum: it proves that no menu
    meeting these goals costs less, so a smaller budget can't cover them at these settings.
    Only the cost is ever divided by, never the budget, so a budget of 0 is fine.
    """
    plan_budget = budget / period_days
    meal_cost = cost / planned
    return BudgetCheck(plan_budget=plan_budget, left=plan_budget - cost, meal_budget=plan_budget / planned,
                       meal_cost=meal_cost,
                       meals_covered=plan_budget / meal_cost if meal_cost > EPS else math.inf,
                       day_budget=plan_budget * meals_a_day / planned,
                       fits=plan_budget >= cost - EPS)


def reduced_costs(p: Problem, s: "Solution"):
    """
    Purpose: for each food, how much cheaper it would need to be to join the menu.
    Math:    c_j - (column j of G) . y. A food on the menu has 0, an unused food
             has a positive value: the price cut it needs before it pays off.
    """
    value = mat_vec(transpose(p.G), s.y)          # G^T y: each food's nutrients at the requirement prices
    return [cj - vj for cj, vj in zip(p.c, value)]


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
    ops, p = [], T[row][col]
    if abs(p - 1) > EPS:
        ops.append(f"{coef(1 / p)}R{row + 1} -> R{row + 1}")
    T[row] = [v / p for v in T[row]]                               # (1/p)R_row -> R_row
    for i in range(len(T)):
        k = -T[i][col]
        if i == row or k == 0:
            continue
        T[i] = [a + k * b for a, b in zip(T[i], T[row])]           # k*R_row + R_i -> R_i
        if abs(k) > EPS:
            ops.append(f"{coef(k)}R{row + 1} + R{i + 1} -> R{i + 1}")
    return ops


@dataclass
class Step:
    entering: int          # column that joins the basis
    leaving: int           # column that leaves the basis
    value: float           # objective value after this pivot
    ops: list              # row operations performed
    tableau: list = field(default=None, repr=False)


@dataclass
class SimplexResult:
    y: list                # the optimal point
    value: float           # the optimal objective value
    slack_row: list        # objective-row entries under the slack columns
    steps: list            # one Step per pivot


def simplex_max(c, A, b, keep_tableaus=False, start_steps=None):
    """
    Purpose: maximize c . y subject to A @ y <= b and y >= 0, where b >= 0.
    Math:    because b >= 0, y = 0 is a valid starting corner. Each slack
             variable turns an inequality into an equation:  A @ y + s = b.

             Tableau  [  A  | I | b ]    rows 1..m are the constraints
                      [ -c  | 0 | 0 ]    the last row is the objective
    """
    m, n = len(A), len(c)
    I = identity(m)
    T = [[float(v) for v in A[i]] + I[i] + [float(b[i])] for i in range(m)]   # [ A | I | b ]
    T.append([-float(v) for v in c] + [0.0] * (m + 1))                       # [ -c | 0 | 0 ]
    basis = list(range(n, n + m))          # start: only the slack variables are "in play"
    steps = []
    if start_steps is not None:
        start_steps.append([r[:] for r in T])

    while True:
        improving = [j for j in range(n + m) if T[m][j] < -EPS]
        if not improving:
            break                          # no neighbor is better: this corner is optimal
        col = improving[0]                 # Bland's rule (lowest index) so it never cycles
        rows = [i for i in range(m) if T[i][col] > EPS]
        if not rows:
            return None                    # the objective can grow forever (unbounded)
        ratios = [T[i][-1] / T[i][col] for i in rows]        # ratio test: how far we can move
        least = min(ratios)
        tied = [i for i, r in zip(rows, ratios) if r <= least + EPS]
        row = min(tied, key=lambda i: basis[i])              # Bland's rule for ties
        ops = pivot(T, row, col)
        steps.append(Step(col, basis[row], T[m][-1], ops, [r[:] for r in T] if keep_tableaus else None))
        basis[row] = col

    y = [0.0] * n
    for i, j in enumerate(basis):
        if j < n:
            y[j] = T[i][-1]
    return SimplexResult(y, T[m][-1], T[m][n:n + m], steps)


# ---------------------------------------------------------------------------
# SOLVING THE DIET PROBLEM
# ---------------------------------------------------------------------------
@dataclass
class Solution:
    x: list                # servings of each food (the menu)
    y: list                # price of each requirement (the mirror problem's answer)
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
    r = simplex_max(p.h, transpose(p.G), p.c)
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
    print(f"Prices: WFP, {MARKET}, {month_name(MONTH)}. A serving is 100 g as bought, or 1 egg.")
    print(rule)
    (n_rows, n_cols), (g_rows, g_cols) = shape(p.N), shape(p.G)
    print(f"Nutrition matrix N: {n_rows} nutrients x {n_cols} foods")
    print(f"Requirement system G @ x >= h: {g_rows} rows x {g_cols} foods")
    print(f"Mirror problem uses the transpose G^T: {g_cols} x {g_rows}")

    print(f"\nSOLVER STEPS ({len(s.steps)} pivots). Each pivot is one Gauss-Jordan step.")
    print("The mirror value is a guaranteed minimum cost. It rises until it meets a real menu.")
    for k, st in enumerate(s.steps, 1):
        print(f"  Pivot {k:2}: {describe(p, st.entering):<38} in   "
              f"guaranteed minimum PHP {st.value:7.2f}")

    print("\nCHEAPEST MENU (what to buy, as bought)")
    order = sorted(range(len(p.names)), key=lambda j: -s.x[j] * p.c[j])     # most expensive first
    for j in order:
        if s.x[j] > 1e-6:
            print(f"  {amount(p.names[j], s.x[j]):>9}  {p.names[j]:<36} PHP {s.x[j] * p.c[j]:7.2f}")
    print(f"  {'Total cost (c . x)':<47} PHP {dot(p.c, s.x):7.2f}")

    print("\nNUTRITION CHECK (N @ x)")
    totals = mat_vec(p.N, s.x)                           # matrix-vector product
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

    gap = abs(dot(p.c, s.x) - dot(p.h, s.y))
    worst = max(hi - gx for hi, gx in zip(p.h, mat_vec(p.G, s.x)))     # largest shortfall in G x >= h
    print("\nCHECKS")
    print(f"  Every requirement met (G @ x >= h): {'yes' if worst < 1e-6 else 'NO'}")
    print(f"  Menu cost c . x = PHP {dot(p.c, s.x):.4f}, mirror value h . y = PHP {dot(p.h, s.y):.4f}"
          f"  (difference {gap:.1e})")


# ---------------------------------------------------------------------------
# THE 2-FOOD EXAMPLE (small enough to show every row operation)
# ---------------------------------------------------------------------------
EXAMPLE = dict(foods=["Rice (cups)", "Eggs"], cost=[10.0, 10.0],
               nutrition=[[200.0, 100.0],               # calories per serving
                          [4.0, 8.0]],                  # protein (g) per serving
               need=[1200.0, 48.0])


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
             "rice = 0": ([1.0, 0.0], 0.0), "eggs = 0": ([0.0, 1.0], 0.0)}
    keys = list(lines)
    for a in range(4):
        for d in range(a + 1, 4):
            M = [lines[keys[a]][0], lines[keys[d]][0]]
            rhs = [lines[keys[a]][1], lines[keys[d]][1]]
            det = det2(M)                                  # ad - bc
            if abs(det) < EPS:
                print(f"  {keys[a]:>8} & {keys[d]:<8} det = 0, the lines never cross")
                continue
            pt = cramer2(M, rhs)                           # Cramer's rule
            valid = all(t >= need - 1e-9 for t, need in zip(mat_vec(A, pt), b)) and min(pt) >= -1e-9
            print(f"  {keys[a]:>8} & {keys[d]:<8} det = {det:7.1f}  corner ({pt[0]:5.2f}, {pt[1]:5.2f})  "
                  + (f"valid, costs PHP {dot(c, pt):6.2f}" if valid else "breaks a requirement"))

    # Part 2: simplex on the mirror problem, showing the tableau after every pivot
    print("\nPART 2: simplex on the mirror problem  max 1200a + 48b  s.t.  A^T @ (a, b) <= (10, 10)")
    tableaus = []
    r = simplex_max(b, transpose(A), c, keep_tableaus=True, start_steps=tableaus)
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
    used = [j for j in sorted(range(len(p.names)), key=lambda j: s.x[j] * p.c[j]) if s.x[j] > 1e-6]
    costs = [s.x[j] * p.c[j] for j in used]
    top = max(costs, default=1.0)
    ax.barh([p.names[j] for j in used], costs, color=TEAL, height=0.62)
    for k, j in enumerate(used):
        ax.text(costs[k] + top * 0.015, k, f"{amount(p.names[j], s.x[j])}   ₱{costs[k]:.2f}",
                va="center", fontsize=8.5, color=MUTED)
    ax.set_xlim(0, top * 1.4)
    ax.set_xlabel("Cost (₱)")


def draw_nutrition(ax, p: Problem, s: Solution):
    """Figure 2: each of the day's totals (N @ x) as a percent of its limit."""
    style_axes(ax, "x")
    totals = mat_vec(p.N, s.x)
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
            row.append(math.nan if s is None else s.cost)
        costs[name] = row
    return costs


def draw_variety(ax, costs, varieties=range(2, 9), mark=None, budget=None):
    """
    Figure 5: the cheapest day at each variety level, one line per group, named at its right end.
    `mark` = (group name, variety) rings one point. The window uses it for the current setting.
    `budget` (a daily amount) draws a dashed line. The window uses it; --plots leaves it out.
    """
    style_axes(ax, "y")
    xs = list(varieties)
    ends = []                                          # (label height, x, y, name, color)
    for name, ys in costs.items():
        color = GROUP_COLORS.get(name, INK)
        ax.plot(xs, ys, "o-", color=color, lw=2, ms=4.5)
        last = [i for i, y in enumerate(ys) if not math.isnan(y)]
        if last:
            ends.append([ys[last[-1]], xs[last[-1]], ys[last[-1]], name, color])
    values = [y for ys in costs.values() for y in ys if not math.isnan(y)]
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
        if not math.isnan(y):
            ax.plot(mark[1], y, "o", ms=13, mfc="none", mec=GROUP_COLORS.get(mark[0], INK), mew=2)
    if budget is not None:
        lo, hi = ax.get_ylim()
        pad = (hi - lo) * 0.06 or 1.0
        ax.set_ylim(min(lo, budget - pad), max(hi, budget + pad))     # keep the line on the chart
        ax.axhline(budget, color=INK, lw=1.2, ls=(0, (5, 3)))
        ax.annotate(f"your budget, as a whole day  ₱{budget:.2f}", xy=(xs[0] - 0.3, budget), xytext=(4, 4),
                    textcoords="offset points", fontsize=8.5, color=INK)
    ax.set_xticks(xs)
    ax.set_xlim(xs[0] - 0.3, xs[-1] + 0.3)
    ax.set_xlabel("Most servings allowed of any one food (1 serving = 100 g as bought, or 1 egg)")
    ax.set_ylabel("Cheapest day (₱)")


def draw_two_food(ax):
    """Figure 6: the 2-food example. The valid menus form a region with flat sides and the cheapest is a corner."""
    E = EXAMPLE
    A, b, c = E["nutrition"], E["need"], E["cost"]
    style_axes(ax, "both")
    top = 14.0                                         # the plot shows 0 to 14 on both axes
    best = cramer2(A, b)                               # B: where the two boundary lines cross
    corner_a = [0.0, max(b[i] / A[i][1] for i in range(2))]     # A: on the eggs axis
    corner_c = [max(b[i] / A[i][0] for i in range(2)), 0.0]     # C: on the rice axis
    # The valid region lies above both lines: bounded below by A, B, C, open to the upper right
    region = [corner_a, best, corner_c, [top, 0.0], [top, top], [0.0, top]]
    ax.fill([x for x, _ in region], [y for _, y in region], color=ZONE, lw=0)
    ends = [0.0, top]                                  # a straight line only needs its two ends
    for i, (color, style, what) in enumerate(((CORAL, "-", "calories"), (PURPLE, "--", "protein"))):
        ax.plot(ends, [(b[i] - A[i][0] * x) / A[i][1] for x in ends], color=color, lw=2.2, ls=style,
                label=f"{A[i][0]:g}x + {A[i][1]:g}y = {b[i]:g} ({what})")
    ax.plot(ends, [(dot(c, best) - c[0] * x) / c[1] for x in ends], color=MUTED, lw=1.2, ls=":",
            label=f"{c[0]:g}x + {c[1]:g}y = {dot(c, best):g} (cost line)")
    corners = (("A", corner_a, (10, 6), "left"), ("B", best, (10, 8), "left"), ("C", corner_c, (0, 12), "center"))
    for name, pt, offset, align in corners:
        cheapest = name == "B"
        ax.plot(*pt, "o", color=TEAL if cheapest else INK, ms=8 if cheapest else 6, clip_on=False, zorder=3)
        ax.annotate(f"{name}  ₱{dot(c, pt):g}" + ("  cheapest" if cheapest else ""), tuple(pt), xytext=offset,
                    textcoords="offset points", ha=align, fontsize=9, color=INK,
                    fontweight="bold" if cheapest else "normal")
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
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
    """Compare our simplex with SciPy's solver on every preset, eating style and variety level (84 settings)."""
    try:
        from scipy.optimize import linprog
    except ImportError:
        print("SciPy is not installed. Run: pip install scipy")
        return
    worst, solved, no_menu = 0.0, 0, 0
    for preset in PRESETS:
        for diet in DIETS:
            for variety in range(2, 9):
                p = build_problem(preset, diet, variety)
                ours = solve_diet(p)
                ref = linprog(p.c, A_ub=[[-v for v in row] for row in p.G], b_ub=[-v for v in p.h],
                              bounds=(0, None), method="highs")       # SciPy wants A_ub x <= b_ub
                if ours is None or ref.status != 0:
                    assert ours is None and ref.status == 2, (preset, diet, variety)
                    no_menu += 1                             # both agree that no menu exists
                    continue
                assert all(gx >= hi - 1e-6 for gx, hi in zip(mat_vec(p.G, ours.x), p.h)), \
                    "menu breaks a requirement"
                assert abs(dot(p.c, ours.x) - dot(p.h, ours.y)) < 1e-6, "costs of the two problems differ"
                worst = max(worst, abs(ours.cost - ref.fun))
                solved += 1
    print(f"Checked {solved + no_menu} settings against SciPy. Both found no menu in {no_menu}.")
    print(f"Largest cost difference: PHP {worst:.2e}")
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
                    help='change a price in PHP per kg (eggs: per egg), e.g. --price "Tilapia=240"')
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
    known = {f[0] for f in FOOD_DATA}
    for name in [*prices, *args.exclude]:
        if name not in known:
            print(f'Note: there is no food called "{name}", so it was ignored. Foods: ' + ", ".join(sorted(known)))
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
