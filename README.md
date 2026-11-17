# Diet Optimizer

Finds the cheapest day of eating that still meets every nutrition target: calories, protein, fiber, calcium, iron and vitamin C, with lower and upper limits on fat, carbohydrates and sodium. You pick who the menu is for, an eating style and how much variety you want. The program returns a shopping list (what to buy, in grams, and what it costs), and a check that every target is met.

Prices are real retail market prices from the World Food Programme for Davao City, October 2026. The cheapest day for an adult woman costs **₱151.38**.

This is the final project for Math 2138 (Linear Algebra). The menu is found by a simplex solver written from scratch with Gauss-Jordan row operations (see [How it works](#how-it-works)).

## What you need

- **Python 3.9 or newer, with Tkinter.** Tkinter draws the app window.
- **Matplotlib.** Draws the charts. It also installs Pillow, which the window uses.
- **SciPy** (optional). Only needed for the self-test (`--test`).

The math itself uses no library. Vectors and matrices are plain Python lists, and every operation on them is written out in `diet_optimizer.py`. (Matplotlib installs NumPy for its own use, but the project's code never calls it.)

Developed and tested with Python 3.13 and Matplotlib 3.11 on Windows 10.

Tkinter comes with the python.org installers for Windows and macOS. On Linux, install it separately:

```bash
sudo apt install python3-tk        # Debian, Ubuntu
sudo dnf install python3-tkinter   # Fedora
```

To check that Tkinter works, run `python -m tkinter`. A small test window should open.

## Set up

**1. Get the code.** Clone the repository, or download it as a ZIP and unzip it.

```bash
git clone https://github.com/cdarino/linear-project.git
cd linear-project
```

**2. Create a virtual environment.** This is optional but recommended, because it keeps the packages separate from the rest of your system.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`. Run the activate command again each time you open a new terminal.

**3. Install the packages.**

```bash
pip install matplotlib
pip install scipy          # optional, for --test
```

**4. Check that everything works.**

```bash
python diet_optimizer.py --test
```

You should see `Checked 84 settings against SciPy` and `All tests passed.` If you skipped SciPy, run `python diet_optimizer.py` instead. The menu it prints should end with a total of `PHP 151.38`.

## Run the app

```bash
python diet_gui.py
```

`python diet_optimizer.py --gui` opens the same window.

Use the **left panel** to choose who the menu is for, the eating style and the variety level (the most servings of any one food). The tiles at the top always show the daily cost, the cost per meal, how many foods are used and how many targets are met. **Copy menu** copies the menu as text, and **Reset all** restores every default.

| Tab | What it shows |
|---|---|
| Menu | The cheapest day as a shopping list: how much of each food to buy and what it costs. Click a food to edit its price. |
| Nutrition | Each day's total against its minimum and maximum. |
| Foods | Turn foods on or off, search, and edit prices (per kg, or per egg) and each food's daily maximum. |
| Limits | Edit the minimum and maximum for each nutrient. Leave a box empty for no limit. |
| Why | Which limits push the cost up, and how much cheaper an unused food would need to be. |
| Variety | What a more varied menu costs, for every group and at every level. Click a point or a row to switch to that setting. This is report figure 5, drawn for your current settings. |
| Solver steps | Every pivot of the simplex method, and the guaranteed minimum after each one (report figure 4). |
| Guide | How to use the program and how the math works, with the 2-food example drawn in two dimensions (report figure 6). |

Press **Ctrl+1** to **Ctrl+8** to switch tabs.

## Run from the command line

With no options, the program solves for an adult woman eating anything, with at most 4 servings of any one food, at Davao City prices for October 2026. It prints the solver steps, the menu, the nutrition check, what drives the cost and a final check.

```bash
python diet_optimizer.py
```

| Option | What it does |
|---|---|
| `--preset "Adult man"` | Who the menu is for: `"Adult woman"`, `"Adult man"`, `"Teen girl"` or `"Teen boy"` |
| `--diet plant-based` | Eating style: `anything`, `no-meat-fish` or `plant-based` |
| `--variety 3` | Most servings of any one food (2 to 8). A serving is 100 g as bought, or 1 egg. |
| `--price "Tilapia=240"` | Change a price in pesos per kg (eggs: per egg). Repeat it for more foods. |
| `--exclude "Beef"` | Leave a food out. Repeat it for more foods. |
| `--example` | The 2-food walkthrough, showing every row operation |
| `--plots` | Save the report figures into `figures/` |
| `--test` | Compare the solver with SciPy on every setting |
| `--gui` | Open the app window |

Options can be combined:

```bash
python diet_optimizer.py --preset "Teen girl" --diet no-meat-fish --variety 3 --price "Egg=10"
```

Food names must match exactly, including the brackets (for example `"Mung beans (dried)"`). If a name doesn't match, the program says so and lists every food. The full list is also on the app's Foods tab and in `FOOD_DATA` near the top of `diet_optimizer.py`.

## Report figures

```bash
python diet_optimizer.py --plots
```

This saves six images into `figures/` and **overwrites** the ones already there.

- Figures 1 to 4 (menu, nutrition check, cost drivers, solver progress) follow the `--preset`, `--diet`, `--variety`, `--price` and `--exclude` options.
- Figure 5 (variety versus cost) always uses the unedited market prices and every group.
- Figure 6 is the fixed 2-food example.

The figures in the repository were made with the defaults. To recreate them exactly, run `--plots` with no other options.

## Project files

| File | What it holds |
|---|---|
| `diet_optimizer.py` | The food data, the requirements, the vector and matrix operations, the simplex solver, the command line and the figure code |
| `diet_gui.py` | The app window (Tkinter). Every number in it comes from `diet_optimizer.py`. |
| `data/wfp_food_prices_davao_city_2026-10.csv` | The WFP market prices for Davao City, October 2026, read with Python's built-in `csv` module |
| `figures/` | The six report figures |

## How it works

1. **Foods are vectors.** Each food's nutrition is a column of the matrix **N** (9 nutrients × 24 foods). A menu is a vector **x** of servings (100 g as bought). The day's totals are **N x**, a linear combination of the food columns, and the cost is the dot product **c · x**.
2. **Limits are linear inequalities.** Every minimum, maximum and serving cap becomes one row of the system **G x ≥ h** (36 × 24 for an adult woman). Together the rows cut out a region of valid menus with flat sides, and the cheapest menu is at one of its corners.
3. **The solver moves from corner to corner.** It runs the simplex method on the mirror (dual) problem built from the transpose **Gᵀ**. Each move, called a pivot, is one Gauss-Jordan step: scale the pivot row, then clear its column with row operations.
4. **One table gives both answers.** The final table holds the cheapest menu and a price for every requirement. For an adult woman, each extra milligram of calcium required adds about ₱0.19 to the day, so the 750 mg minimum accounts for about ₱142 of the ₱151.38.

Market prices are per kg, but the model counts servings of 100 g. Converting is a change of units: the price of a serving is the price per kg × 0.1. Scaling a food's column of **N** and its price by the same number gives the same menu in different units, so the solver works in servings and the app shows kilograms and pesos.

Every operation above is written out in plain Python near the top of `diet_optimizer.py`: the dot product, the matrix-vector product, the transpose, the row operations, and 2 × 2 determinants with Cramer's rule.

`python diet_optimizer.py --example` shows every step on a 2-food problem small enough to follow by hand. The app's Guide tab explains the same ideas.

## Where the numbers come from

| What | Source |
|---|---|
| Nutrition targets | **Philippine Dietary Reference Intakes 2015** (FNRI-DOST). Adults are ages 19 to 29 and teens are 16 to 18. |
| Prices | **World Food Programme** retail market prices for Davao City, October 2026 (`data/`). Per kg as bought; eggs per piece. Every food in the program has a price there. |
| Nutrition | **USDA National Nutrient Database for Standard Reference, Release 28** (SR28): raw food, per 100 g of the edible part. The SR28 food number for each food is in `FOOD_DATA`. |
| Edible share | SR28's refuse figures (peel, bones, seeds). For whole fish, the edible-flesh yields in **FAO Fisheries Technical Paper 309** (1989): milkfish 61%, round scad 52%, anchovies 62%, tilapia 37%. |

### Assumptions and limits

- **Only foods in the WFP data.** Foods WFP doesn't price in Davao City, such as tofu, malunggay and kangkong, are left out. So are the other two rice grades (same nutrition, higher price), cuts with bones, shrimp (no edible share for whole shrimp), coconut (unclear what is sold per kg), and garlic, ginger, onions and calamansi (seasonings). That leaves 24 foods.
- **Plant-based has no menu.** Raw plant foods hold little sodium, so the 500 mg sodium minimum can't be met together with the other limits. No meat or fish also has no menu at variety 2. In all, 32 of the 84 settings have no menu. Without the sodium minimum, plant-based menus exist for adults and teen boys (₱184.02 a day for an adult woman at variety 4), but still not for teen girls.
- **Close matches.** SR28 has no round scad, so it uses jack mackerel (same family). Pork and beef count as boneless, because WFP lists the cuts with bones separately. SR28 has no fiber value for string beans, so they count as 0 g.
- **Raw food.** Cooking loses some vitamin C, and fuel, oil and seasoning (including salt) aren't counted. The amounts are what to buy, so the optimizer suits someone who shops and cooks their own meals.

This is coursework, not medical advice.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognized (Windows) | Use the Python launcher instead: `py diet_gui.py`, `py -m venv .venv`, `py -m pip install matplotlib`. |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Or skip activation and run `.venv\Scripts\python diet_gui.py`. |
| `No module named 'tkinter'` | On Linux, install Tk (see [What you need](#what-you-need)). On Windows, rerun the Python installer, choose **Modify**, and tick **tcl/tk and IDLE**. |
| `No module named 'matplotlib'` | It's installed in a different Python than the one you're running. Activate the virtual environment, or install with `python -m pip install matplotlib`. |
| `SciPy is not installed` | Only `--test` needs it: `pip install scipy`. |
| The window looks slightly different on macOS or Linux | It was designed on Windows with the Segoe UI font. Elsewhere it uses your system font, so spacing can differ a little. |
