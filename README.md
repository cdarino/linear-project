# Diet Optimizer

Finds the cheapest day of eating that still meets every nutrition target: calories, protein, fiber, calcium, iron and vitamin C, with lower and upper limits on fat, carbohydrates and sodium. You pick who the menu is for, an eating style and how much variety you want. The program returns a shopping list (what to buy, in grams, and what it costs), and a check that every target is met.

Prices are real retail market prices from the World Food Programme for Davao City, October 2026. The cheapest day for an adult woman costs **₱151.38**.

This is the final project for Math 2138 (Linear Algebra). The menu is found by a simplex solver written from scratch with Gauss-Jordan row operations (see [How it works](#how-it-works)).

## How to open the app (Windows, in VS Code)

You'll type three short commands into VS Code's **terminal**, a panel at the bottom of VS Code where you give your computer instructions. For each command below: copy it, click inside the terminal, paste with **Ctrl+V**, then press **Enter**.

The first time takes about 10 minutes. After that, opening the app takes one command.

### Step 1: Download the project

1. Go to this project's page on GitHub.
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder. Right-click **linear-project-main.zip** and choose **Extract All**, then **Extract**.

### Step 2: Open the project folder in VS Code

1. In VS Code, click **File → Open Folder...**
2. Go to the folder you just extracted and keep double-clicking into folders until you see **diet_gui.py** inside. (There is often a `linear-project-main` folder inside another `linear-project-main` folder; you want the inner one.)
3. Click **Select Folder**. If VS Code asks whether you trust the authors, click **Yes, I trust the authors**.

**Check:** the **Explorer** panel on the left should list `data`, `figures`, `diet_gui.py`, `diet_optimizer.py` and `README.md`. If it shows only one `linear-project-main` folder, you opened one level too high: do Step 2 again and pick the folder inside it.

### Step 3: Open the terminal and check Python

Click **Terminal → New Terminal** at the top of VS Code. A panel opens at the bottom. Type:

```bat
py --version
```

- If you see something like `Python 3.13.0`, you have Python. Go to Step 4.
- If you see an error saying `py` is not recognized, install Python:
  1. Go to [python.org/downloads](https://www.python.org/downloads/) and click the yellow **Download Python** button.
  2. Open the file you downloaded. On the first screen, tick **Add python.exe to PATH** at the bottom, then click **Install Now**.
  3. When it says the setup was successful, **close VS Code completely and open it again**. VS Code only notices new programs after a restart. Then open a new terminal and type `py --version` again.

### Step 4: Install Matplotlib (first time only)

Matplotlib is an add-on the app uses to draw its charts.

```bat
py -m pip install matplotlib
```

Wait until it finishes and you can type again. Near the end you should see `Successfully installed`, or `Requirement already satisfied` if you already had it. Both are fine. A notice that "a new release of pip is available" is not an error; you can ignore it.

### Step 5: Open the app

```bat
py diet_gui.py
```

A window called **Diet Optimizer** opens, showing a daily cost of **₱151.38**. Keep VS Code open while you use the app. To close the app, close its window.

**Next time:** open VS Code (it usually reopens the project folder by itself), click **Terminal → New Terminal**, and type `py diet_gui.py`.

### If something goes wrong

| What you see | What to do |
|---|---|
| `py` is not recognized | Python isn't installed yet, or VS Code was already open when you installed it. Do Step 3 again, including closing and reopening VS Code. If `python --version` shows a version, type `python` instead of `py` in every command. |
| Typing `python` opens the Microsoft Store | Close the Store. Type `py` instead, as in the steps above. |
| `can't open file ... diet_gui.py` | VS Code has the wrong folder open. Do Step 2 again and check that the Explorer panel lists `diet_gui.py` directly. |
| `No module named 'matplotlib'` or `No module named 'PIL'` | Do Step 4 again. If you start the app with `python` instead of `py`, install with `python -m pip install matplotlib`. |
| `No module named 'tkinter'` | Open the Python installer again, choose **Modify**, tick **tcl/tk and IDLE**, and finish. |
| An error that mentions `wfp_food_prices_davao_city_2026-10.csv` | The `data` folder is missing. Extract the whole ZIP (Step 1) instead of opening files from inside it. |
| You clicked the ▷ (Run) button at the top right and got an error | That button can use a different Python than the terminal. Type `py diet_gui.py` in the terminal instead (Step 5). |
| The terminal panel is gone | Click **Terminal → New Terminal** again. |

### On a Mac or Linux

Follow the same steps in VS Code, but type `python3` where they say `py`:

```bash
python3 -m pip install matplotlib
python3 diet_gui.py
```

On a Mac, install Python from [python.org/downloads](https://www.python.org/downloads/) even if `python3` already works. The `python3` that comes with Apple's Command Line Tools (version 3.9) uses an old window toolkit, Tk 8.5, and the app freezes with it: no window, or a blank one, while the terminal stays busy. To check, run `python3 -c "import tkinter; print(tkinter.TkVersion)"`. It should print `8.6` or higher. After installing, close and reopen VS Code so that `python3` finds the new Python.

On Linux, install the window toolkit first: `sudo apt install python3-tk` (Debian or Ubuntu) or `sudo dnf install python3-tkinter` (Fedora). If pip refuses with `externally-managed-environment`, see [If pip refuses to install](#if-pip-refuses-to-install-mac-or-linux) at the end of this page. The window was designed on Windows, so its spacing can look slightly different.

## Using the app

Use the **left panel** to choose who the menu is for, the eating style and the variety level (the most servings of any one food). **Copy menu** copies the menu as text, and **Reset all** restores every default.

### Meals and budget

The **Meals and budget** section at the bottom of the left panel (scroll down on a small window) lets you plan only some of the day's meals:

- **Meals a day**: 1, 2 or 3. **Plan for**: how many of those meals you are buying for, or the whole day. Planning 1 of 3 meals divides every daily goal by 3 (maximums too: one meal gets a third of the day's sodium allowance), and every serving cap with it. The solver then finds the cheapest food that meets those goals. The note under the controls says which share of the day you are planning.
- **Budget**: what you can spend on the meals you are planning. Leave it empty for no budget. **Budget is for** sets whether that amount covers one day of those meals, a week (7 days) or a month (30 days). The note under it shows the amount that is compared, for example "₱490.00 a week = ₱70.00 a day for 1 meal".

The goals always come first: the budget is checked against the cheapest menu that meets them, so being within budget never means missing a goal.

### The tiles

The tiles at the top show, on every page:

| Tile | What it shows |
|---|---|
| Daily cost (or Cost of 1 meal, Cost of 2 meals) | The cheapest cost of the meals you are planning |
| Per meal | That cost divided by the number of planned meals |
| Foods on the menu | How many foods are used |
| Targets met | How many goals are met, counted against the divided goals |
| Budget | "Not set" with no budget. Otherwise how much is left (green) or how much is short (red), with a thin meter for the cost against the budget. When short, it says how many meals' goals the budget covers. |

### The pages

| Tab | What it shows |
|---|---|
| Menu | The cheapest food for the planned meals as a shopping list: how much of each food to buy and what it costs. **Shop for** 1, 3 or 7 days multiplies the list. Tick the circle at the left of a row when you've bought it, and the footer shows what is bought and what is still to buy. Click the rest of a row to edit the food's price. With a budget, a line above the total compares it with the cost. When the budget is short, **What your budget can do** lists settings that fit (fewer meals, another variety level, or the "Anything" eating style); click one to switch. |
| Nutrition | Each total against its goals. When you plan part of the day, each row also shows the daily figure, for example "need at least 1,003 kcal (day: 3,010)". |
| Foods | Turn foods on or off, search, and edit prices (per kg, or per egg) and each food's daily maximum. **−10%** and **+10%** change every price at once: the cost changes by the same percent, but the menu stays the same. |
| Limits | Edit the daily minimum and maximum for each nutrient. Leave a box empty for no limit. When you plan part of the day, the solver uses the same share of each. |
| Why | Which limits push the cost up, and how much cheaper an unused food would need to be, for the meals you are planning. |
| Variety | What a more varied menu costs for the whole day, for every group and at every level. Click a point or a row to switch to that setting. With a budget, a dashed line shows it as a whole-day amount. This is report figure 5, drawn for your current settings. |
| Solver steps | Every pivot of the simplex method, and the guaranteed minimum after each one (report figure 4). |
| Guide | How to use the program and how the math works, with the 2-food example drawn in two dimensions (report figure 6). |

**The Guide explorer.** The 2-food chart on the Guide page is interactive. **Example** (top right) switches between the round-number example and **Our paper (Figure 1)**, the teen boy's real rice and eggs from Section 4.5. On the **Vertices** tab, the slider (or ‹ ›, or the arrow keys) steps through all six pairs of boundary lines in the order of Table 1. Each step shows the 2 × 2 system, its determinant, Cramer's rule, the check against both needs and the cost, with a badge that says whether the point is a valid vertex, the cheapest one, or outside the region. On **Cost line**, slide the dotted line down (or press **▶ Play**) until it just touches the region at the cheapest corner. On **Prices**, change the rice and egg prices to see the cheapest corner jump while the region stays put. Click anywhere on the chart to check that menu. The last line confirms that the simplex solver finds the same cheapest cost.

Press **Ctrl+1** to **Ctrl+8** to switch tabs, and **Alt+1** to **Alt+3** to set the meals a day.

## Run from the command line

The examples below say `python`. On Windows, type `py` instead; on macOS or Linux, `python3`.

With no options, the program solves for an adult woman eating anything, with at most 4 servings of any one food, at Davao City prices for October 2026. It prints the solver steps, the menu, the nutrition check, what drives the cost and a final check. The menu should end with a total of `PHP 151.38`.

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
| `--test` | Compare the solver with SciPy on every setting (see [below](#check-the-solver-against-scipy)) |
| `--gui` | Open the app window, the same as `python diet_gui.py` |

Options can be combined:

```bash
python diet_optimizer.py --preset "Teen girl" --diet no-meat-fish --variety 3 --price "Egg=10"
```

Food names must match exactly, including the brackets (for example `"Mung beans (dried)"`). If a name doesn't match, the program says so and lists every food. The full list is also on the app's Foods tab and in `FOOD_DATA` near the top of `diet_optimizer.py`.

## Check the solver against SciPy

This is optional, and the only part of the project that uses SciPy. It solves 84 settings with our solver and with SciPy's, and checks that they agree.

```bash
python -m pip install scipy
python diet_optimizer.py --test
```

You should see `Checked 84 settings against SciPy. Both found no menu in 32.` and `All tests passed.`

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

The math uses no library. Vectors and matrices are plain Python lists, and every operation on them is written out near the top of `diet_optimizer.py`: the dot product, the matrix-vector product, the transpose, the row operations, and 2 × 2 determinants with Cramer's rule. Matplotlib only draws charts. (Installing it also installs NumPy for Matplotlib's own use, but the project's code never calls NumPy.)

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

## If pip refuses to install (Mac or Linux)

Windows users can skip this. Some Mac and Linux setups won't let pip add packages to the system's Python, and they show `externally-managed-environment`. The fix is to make a private copy of Python inside the project folder (called a virtual environment) and install Matplotlib there:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install matplotlib
python diet_gui.py
```

Next time, run `source .venv/bin/activate` from the project folder before `python diet_gui.py`.

Developed and tested with Python 3.13 and Matplotlib 3.11 on Windows 10.
