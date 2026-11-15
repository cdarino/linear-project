# Diet Optimizer

Finds the cheapest day of eating that still meets every nutrition target: calories, protein, fiber, calcium, iron and vitamin C, with lower and upper limits on fat, carbohydrates and sodium. You pick who the menu is for, an eating style and how much variety you want. The program returns the menu, its cost and a check that every target is met.

For an adult woman with the sample prices, the cheapest day costs **₱156.66**.

This is the final project for Math 2138 (Linear Algebra). The menu is found by a simplex solver written from scratch with Gauss-Jordan row operations (see [How it works](#how-it-works)).

## What you need

- **Python 3.9 or newer, with Tkinter.** Tkinter draws the app window.
- **NumPy** and **Matplotlib.** Matplotlib also installs Pillow, which the window uses.
- **SciPy** (optional). Only needed for the self-test (`--test`).

Developed and tested with Python 3.13, NumPy 2.1 and Matplotlib 3.11 on Windows 10.

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
pip install numpy matplotlib
pip install scipy          # optional, for --test
```

**4. Check that everything works.**

```bash
python diet_optimizer.py --test
```

You should see `Checked 84 settings against SciPy` and `All tests passed.` If you skipped SciPy, run `python diet_optimizer.py` instead. The menu it prints should end with a total of `PHP 156.66`.

## Run the app

```bash
python diet_gui.py
```

`python diet_optimizer.py --gui` opens the same window.

Use the **left panel** to choose who the menu is for, the eating style and the variety level (the most servings of any one food). The tiles at the top always show the daily cost, the cost per meal, how many foods are used and how many targets are met. **Copy menu** copies the menu as text, and **Reset all** restores every default.

| Tab | What it shows |
|---|---|
| Menu | The cheapest day: foods, amounts and costs. Click a food to edit its price. |
| Nutrition | Each day's total against its minimum and maximum. |
| Foods | Turn foods on or off, search, and edit prices and serving limits. |
| Limits | Edit the minimum and maximum for each nutrient. Leave a box empty for no limit. |
| Why | Which limits push the cost up, and how much cheaper an unused food would need to be. |
| Solver steps | Every pivot of the simplex method (figure 4). |
| Figures | Figure 5 (variety versus cost, following your settings) and figure 6 (the 2-food example). |
| Guide | How to use the program and how the math works. |

Press **Ctrl+1** to **Ctrl+8** to switch tabs.

## Run from the command line

With no options, the program solves for an adult woman eating anything, with at most 4 servings of any one food. It prints the solver steps, the menu, the nutrition check, what drives the cost and a final check.

```bash
python diet_optimizer.py
```

| Option | What it does |
|---|---|
| `--preset "Adult man"` | Who the menu is for: `"Adult woman"`, `"Adult man"`, `"Teen girl"` or `"Teen boy"` |
| `--diet plant-based` | Eating style: `anything`, `no-meat-fish` or `plant-based` |
| `--variety 3` | Most servings of any one food (2 to 8) |
| `--price "Egg=10"` | Change a price in pesos. Repeat it for more foods. |
| `--exclude "Instant noodles"` | Leave a food out. Repeat it for more foods. |
| `--example` | The 2-food walkthrough, showing every row operation |
| `--plots` | Save the report figures into `figures/` |
| `--test` | Compare the solver with SciPy on every setting |
| `--gui` | Open the app window |

Options can be combined:

```bash
python diet_optimizer.py --preset "Teen girl" --diet no-meat-fish --variety 3 --price "Egg=10"
```

Food names must match exactly, including the brackets (for example `"White rice (cooked)"`). A name that doesn't match is ignored without a warning. The full list is on the app's Foods tab and in `FOODS` near the top of `diet_optimizer.py`.

## Report figures

```bash
python diet_optimizer.py --plots
```

This saves six images into `figures/` and **overwrites** the ones already there.

- Figures 1 to 4 (menu, nutrition check, cost drivers, solver progress) follow the `--preset`, `--diet`, `--variety`, `--price` and `--exclude` options.
- Figure 5 (variety versus cost) always uses the default prices and every group.
- Figure 6 is the fixed 2-food example.

The figures in the repository were made with the defaults. To recreate them exactly, run `--plots` with no other options.

## Project files

| File | What it holds |
|---|---|
| `diet_optimizer.py` | The food data, the requirements, the simplex solver, the command line and the figure code |
| `diet_gui.py` | The app window (Tkinter). Every number in it comes from `diet_optimizer.py`. |
| `figures/` | The six report figures |

## How it works

1. **Foods are vectors.** Each food's nutrition label is a column of the matrix **N** (9 nutrients × 25 foods). A menu is a vector **x** of servings. The day's totals are **N x**, a linear combination of the food columns, and the cost is the dot product **c · x**.
2. **Limits are linear inequalities.** Every minimum, maximum and serving cap becomes one row of the system **G x ≥ h** (37 × 25 for an adult woman). Together the rows cut out a region of valid menus with flat sides, and the cheapest menu is at one of its corners.
3. **The solver moves from corner to corner.** It runs the simplex method on the mirror (dual) problem built from the transpose **Gᵀ**. Each move, called a pivot, is one Gauss-Jordan step: scale the pivot row, then clear its column with row operations.
4. **One table gives both answers.** The final table holds the cheapest menu and a price for every requirement. For an adult woman, each extra milligram of iron required adds about ₱5.34 to the day.

`python diet_optimizer.py --example` shows every step on a 2-food problem small enough to follow by hand. The app's Guide tab explains the same ideas.

## Where the numbers come from

The nutrition targets follow the **Philippine Dietary Reference Intakes 2015** (FNRI-DOST). Adults are ages 19 to 29 and teens are 16 to 18. Prices and nutrition values are rough estimates for coursework, not medical advice.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognized (Windows) | Use the Python launcher instead: `py diet_gui.py`, `py -m venv .venv`, `py -m pip install numpy matplotlib`. |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Or skip activation and run `.venv\Scripts\python diet_gui.py`. |
| `No module named 'tkinter'` | On Linux, install Tk (see [What you need](#what-you-need)). On Windows, rerun the Python installer, choose **Modify**, and tick **tcl/tk and IDLE**. |
| `No module named 'numpy'` or `'matplotlib'` | The packages are in a different Python than the one you're running. Activate the virtual environment, or install with `python -m pip install numpy matplotlib`. |
| `SciPy is not installed` | Only `--test` needs it: `pip install scipy`. |
| The window looks slightly different on macOS or Linux | It was designed on Windows with the Segoe UI font. Elsewhere it uses your system font, so spacing can differ a little. |
