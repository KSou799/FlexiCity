import tkinter as tk
from tkinter import ttk, messagebox
import math

from flexicity_model import (
    NUM_HOURS, PRICE_PER_HOUR,
    default_assets, validate_asset, simulate, optimise,
)

# ========================================
# FLEXI CITY - SMART ELECTRICITY LOAD SHIFTING SIMULATOR
# ========================================
# Competition: Urban Circular Hack Helsinki 2025
# Topic: Preparing cities for the increasing demand in electricity
#
# WHAT THIS DOES
#   Simulates a city of 24 flexible electricity loads (EVs, heat pumps,
#   HVAC, fridges, chargers, etc.) and compares two schedules:
#     BEFORE  Each load runs from its usual start hour
#             (no coordination - "plug in when I get home" behaviour)
#     AFTER   The shiftable part of each load is moved to hours with a low
#             weighted combination of grid load and electricity price
#   Reports peak demand, daily cost and CO2 emissions for both.
#
# The model itself is in flexicity_model.py. This file is the tkinter app.
#
# OPTIMIZER
#   - Exhaustive 1% grid search over (flex%, priority%), 10,201 schedules
#   - Four objectives: peak, cost, CO2, all three (none may get worse)

ASSETS = default_assets()

result = simulate(ASSETS, 1.0, 0.5)
before_load = result.before_load
after_load = result.after_load


def recalculate_schedules():
    """Run the model with the current slider settings."""
    global result, before_load, after_load
    result = simulate(ASSETS, flex_var.get() / 100.0, priority_var.get() / 100.0)
    before_load = result.before_load
    after_load = result.after_load


# -------- UI --------

root = tk.Tk()
root.title("FlexiCity - Peak, Price & CO2 Demo (24h)")
root.geometry("1450x900")

APP_FONT = "Segoe UI"
COLOR_SAVING = "#2ca02c"
COLOR_RESET = "#c62828"
COLOR_GRID = "#e8e8e8"
COLOR_BEFORE_LINE = "#d62728"
COLOR_AFTER_LINE = "#1f77b4"
COLOR_PRICE_LINE = "#6b6b6b"

style = ttk.Style()
style.configure("TLabel", font=(APP_FONT, 9))
style.configure("TLabelframe.Label", font=(APP_FONT, 10, "bold"))
style.configure("StatValue.TLabel", font=(APP_FONT, 9, "bold"))
style.configure("Saving.TLabel", font=(APP_FONT, 9, "bold"), foreground=COLOR_SAVING)
style.configure("Loss.TLabel", font=(APP_FONT, 9, "bold"), foreground=COLOR_RESET)
style.configure("TButton", font=(APP_FONT, 9))
style.configure("Optimize.TButton", font=(APP_FONT, 9, "bold"))
style.configure("Reset.TButton", font=(APP_FONT, 9, "bold"), foreground=COLOR_RESET)
style.configure("TCheckbutton", font=(APP_FONT, 9))
style.configure("TEntry", font=(APP_FONT, 9))

root.after_id_flex = None
root.after_id_priority = None
root.after_id_redraw = None

mainframe = ttk.Frame(root, padding=10)
mainframe.grid(row=0, column=0, sticky="nsew")
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

left_frame = ttk.Frame(mainframe)
left_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 15))

right_frame = ttk.Frame(mainframe)
right_frame.grid(row=0, column=1, sticky="nsew")
mainframe.columnconfigure(1, weight=1)
mainframe.rowconfigure(0, weight=1)

# --- Stats ---
stats_frame = ttk.LabelFrame(left_frame, text="Peak, cost & CO2")
stats_frame.grid(row=0, column=0, sticky="new", pady=(0, 5))

peak_before_var = tk.StringVar()
peak_after_var = tk.StringVar()
reduction_var = tk.StringVar()
cost_before_var = tk.StringVar()
cost_after_var = tk.StringVar()
saving_cost_var = tk.StringVar()
co2_var = tk.StringVar()

ttk.Label(stats_frame, text="Peak BEFORE").grid(row=0, column=0, sticky="w", padx=(0, 10))
ttk.Label(stats_frame, textvariable=peak_before_var, style="StatValue.TLabel").grid(row=0, column=1, sticky="w")
ttk.Label(stats_frame, text="Peak AFTER").grid(row=1, column=0, sticky="w", padx=(0, 10))
ttk.Label(stats_frame, textvariable=peak_after_var, style="StatValue.TLabel").grid(row=1, column=1, sticky="w")
ttk.Label(stats_frame, text="Peak reduction").grid(row=2, column=0, sticky="w", padx=(0, 10))
reduction_label = ttk.Label(stats_frame, textvariable=reduction_var, style="Saving.TLabel")
reduction_label.grid(row=2, column=1, sticky="w")
ttk.Separator(stats_frame, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)
ttk.Label(stats_frame, text="Cost BEFORE (flex assets)").grid(row=4, column=0, sticky="w", padx=(0, 10))
ttk.Label(stats_frame, textvariable=cost_before_var, style="StatValue.TLabel").grid(row=4, column=1, sticky="w")
ttk.Label(stats_frame, text="Cost AFTER (flex assets)").grid(row=5, column=0, sticky="w", padx=(0, 10))
ttk.Label(stats_frame, textvariable=cost_after_var, style="StatValue.TLabel").grid(row=5, column=1, sticky="w")
ttk.Label(stats_frame, text="Saving").grid(row=6, column=0, sticky="w", padx=(0, 10))
saving_cost_label = ttk.Label(stats_frame, textvariable=saving_cost_var, style="Saving.TLabel")
saving_cost_label.grid(row=6, column=1, sticky="w")
ttk.Separator(stats_frame, orient="horizontal").grid(row=7, column=0, columnspan=2, sticky="ew", pady=2)
ttk.Label(stats_frame, text="CO2 saving (flex assets)").grid(row=8, column=0, sticky="w", padx=(0, 10))
co2_label = ttk.Label(stats_frame, textvariable=co2_var, style="Saving.TLabel")
co2_label.grid(row=8, column=1, sticky="w")

# --- Add ---
input_frame = ttk.LabelFrame(left_frame, text="Add flexible load")
input_frame.grid(row=1, column=0, sticky="new", pady=(5, 0))

ttk.Label(input_frame, text="Owner / Name:").grid(row=0, column=0, sticky="w")
entry_owner = ttk.Entry(input_frame, width=25)
entry_owner.grid(row=0, column=1, sticky="w")

ttk.Label(input_frame, text="Appliance:").grid(row=1, column=0, sticky="w")
entry_appliance = ttk.Entry(input_frame, width=25)
entry_appliance.grid(row=1, column=1, sticky="w")

ttk.Label(input_frame, text="Power (kW):").grid(row=2, column=0, sticky="w")
entry_power = ttk.Entry(input_frame, width=10)
entry_power.grid(row=2, column=1, sticky="w")

ttk.Label(input_frame, text="Duration (h):").grid(row=3, column=0, sticky="w")
entry_duration = ttk.Entry(input_frame, width=10)
entry_duration.grid(row=3, column=1, sticky="w")

ttk.Label(input_frame, text="Start hour (0-23):").grid(row=4, column=0, sticky="w")
entry_start = ttk.Entry(input_frame, width=10)
entry_start.grid(row=4, column=1, sticky="w")

ttk.Label(input_frame, text="End hour (0-24):").grid(row=5, column=0, sticky="w")
entry_end = ttk.Entry(input_frame, width=10)
entry_end.grid(row=5, column=1, sticky="w")

var_variable = tk.BooleanVar(value=True)
ttk.Checkbutton(
    input_frame, text="Variable (can be split into separate hours)",
    variable=var_variable
).grid(row=6, column=0, columnspan=2, sticky="w", pady=(5, 0))

var_enabled = tk.BooleanVar(value=True)
ttk.Checkbutton(
    input_frame, text="Enabled (included in simulation)",
    variable=var_enabled
).grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 0))

ttk.Label(input_frame, text="Flexibility (0-1):").grid(row=8, column=0, sticky="w")
entry_flex = ttk.Entry(input_frame, width=10)
entry_flex.insert(0, "1.0")
entry_flex.grid(row=8, column=1, sticky="w")


def read_form_values():
    owner = entry_owner.get().strip() or "Custom house"
    appliance = entry_appliance.get().strip() or "Appliance"
    try:
        power = float(entry_power.get())
        duration = int(entry_duration.get())
        start = int(entry_start.get())
        end = int(entry_end.get())
        flex_factor = float(entry_flex.get())
    except ValueError:
        raise ValueError("Power and flexibility must be numbers, duration and hours whole numbers")

    asset = {
        "owner": owner, "appliance": appliance,
        "power_kW": power, "duration_h": duration,
        "start_hour": start, "end_hour": end,
        "variable": var_variable.get(), "enabled": var_enabled.get(),
        "flex_factor": flex_factor,
    }
    validate_asset(asset)
    return asset


def clear_form():
    entry_owner.delete(0, tk.END)
    entry_appliance.delete(0, tk.END)
    entry_power.delete(0, tk.END)
    entry_duration.delete(0, tk.END)
    entry_start.delete(0, tk.END)
    entry_end.delete(0, tk.END)
    entry_flex.delete(0, tk.END)
    entry_flex.insert(0, "1.0")
    var_variable.set(True)
    var_enabled.set(True)


def add_asset():
    try:
        ASSETS.append(read_form_values())
        recalculate_schedules()
        update_stats_and_graph()
        clear_form()
    except ValueError as e:
        messagebox.showerror("Invalid input", str(e))


ttk.Button(input_frame, text="Add new", command=add_asset)\
    .grid(row=9, column=0, columnspan=2, pady=(5, 0), sticky="ew")

# --- Sliders ---
priority_frame = ttk.LabelFrame(left_frame, text="Priority: grid vs price")
priority_frame.grid(row=2, column=0, sticky="new", pady=(5, 0))

priority_var = tk.DoubleVar(value=50.0)
ttk.Label(priority_frame, text="Grid  <-  focus  ->  Price").grid(row=0, column=0, sticky="w")

priority_value_label = ttk.Label(priority_frame, text="Grid 50% / Price 50%")
priority_value_label.grid(row=2, column=0, sticky="w")


def on_priority_change(v=None):
    price_w = priority_var.get() / 100.0
    grid_w = 1.0 - price_w
    priority_value_label.config(text=f"Grid {grid_w*100:.0f}% / Price {price_w*100:.0f}%")
    recalculate_schedules()
    update_stats_and_graph()


def on_priority_change_debounced(v):
    if root.after_id_priority:
        root.after_cancel(root.after_id_priority)
    root.after_id_priority = root.after(200, on_priority_change)


scale_priority = ttk.Scale(
    priority_frame, from_=0, to=100, orient="horizontal",
    variable=priority_var, command=on_priority_change_debounced
)
scale_priority.grid(row=1, column=0, sticky="ew")
priority_frame.columnconfigure(0, weight=1)

flex_frame = ttk.LabelFrame(left_frame, text="Flex participation")
flex_frame.grid(row=3, column=0, sticky="new", pady=(5, 0))

flex_var = tk.DoubleVar(value=100.0)
flex_value_label = ttk.Label(flex_frame, text="Flexible users: 100%")
flex_value_label.grid(row=0, column=0, columnspan=2, sticky="w")


def on_flex_change(v=None):
    flex_value_label.config(text=f"Flexible users: {flex_var.get():.0f}%")
    recalculate_schedules()
    update_stats_and_graph()


def on_flex_change_debounced(v):
    if root.after_id_flex:
        root.after_cancel(root.after_id_flex)
    root.after_id_flex = root.after(200, on_flex_change)


scale_flex = ttk.Scale(
    flex_frame, from_=0, to=100, orient="horizontal",
    variable=flex_var, command=on_flex_change_debounced
)
scale_flex.grid(row=1, column=0, columnspan=2, sticky="ew")
flex_frame.columnconfigure(0, weight=1)
flex_frame.columnconfigure(1, weight=1)


def _cancel_pending_slider_callbacks():
    """Drop any deferred recalcs queued by var.set() on the ttk.Scales.
    Without this, an explicit synchronous recalc is followed ~200ms later
    by a duplicate recalc + redraw kicked off by the slider's command."""
    if root.after_id_flex:
        root.after_cancel(root.after_id_flex)
        root.after_id_flex = None
    if root.after_id_priority:
        root.after_cancel(root.after_id_priority)
        root.after_id_priority = None


def apply_optimization_result(best_flex, best_priority):
    """Push optimal sliders back to UI and refresh everything once."""
    flex_var.set(best_flex)
    priority_var.set(best_priority)
    flex_value_label.config(text=f"Flexible users: {best_flex:.0f}%")
    price_w = best_priority / 100.0
    grid_w = 1.0 - price_w
    priority_value_label.config(text=f"Grid {grid_w*100:.0f}% / Price {price_w*100:.0f}%")
    _cancel_pending_slider_callbacks()
    recalculate_schedules()
    update_stats_and_graph()


# ---- OPTIMIZER ----

def run_optimiser(objective):
    """Grid search in the model (no slider changes while it runs)."""
    root.config(cursor="watch")  # "wait" only exists on Windows
    root.update_idletasks()
    try:
        return optimise(ASSETS, objective)
    finally:
        root.config(cursor="")


def _change(pct):
    """'12.3% lower' or '4.5% higher' from a saving percentage."""
    return f"{abs(pct):.1f}% {'lower' if pct >= 0 else 'higher'}"


def _summary(r, flex, priority):
    return (f"Peak: {r.peak_before:.1f} -> {r.peak_after:.1f} kW ({_change(r.peak_reduction_pct)})\n"
            f"Cost: {r.cost_before:.2f} -> {r.cost_after:.2f} EUR ({_change(r.cost_saving_pct)})\n"
            f"CO2: {r.co2_before:.1f} -> {r.co2_after:.1f} kg/day ({_change(r.co2_saving_pct)})\n"
            f"Flex: {flex}% | Grid/Price: {100-priority}%/{priority}%\n"
            f"Cost and CO2 cover the flexible loads only.")


def find_optimal_settings_fast():
    """Minimize peak demand, ties broken by cost."""
    flex, priority, r = run_optimiser("peak")
    apply_optimization_result(flex, priority)
    messagebox.showinfo("Peak optimization", _summary(r, flex, priority))


def find_optimal_settings_cost():
    """Minimize the daily cost of the flexible loads, ties broken by peak."""
    flex, priority, r = run_optimiser("cost")
    apply_optimization_result(flex, priority)
    messagebox.showinfo("Cost optimization", _summary(r, flex, priority))


def find_optimal_settings_co2():
    """Minimize the daily CO2 of the flexible loads, ties broken by cost."""
    flex, priority, r = run_optimiser("co2")
    apply_optimization_result(flex, priority)
    messagebox.showinfo("CO2 optimization", _summary(r, flex, priority))


def find_optimal_settings_multi():
    """
    Find the (flex, priority) where peak, cost and CO2 all improve on the
    uncoordinated schedule, and their average (each scaled so 1.0 = no
    improvement) is lowest. Settings where any of them gets worse are
    rejected: an equal-weighted average would otherwise accept a cost
    increase for a large peak cut.

    If no setting improves all of them, the sliders are left where they are.
    """
    out = run_optimiser("all")
    if out is None:
        messagebox.showinfo(
            "Multi-objective optimization",
            "No (flex, priority) setting improves peak, cost and CO2 at once.\n"
            "Asset windows may be too tight to give the scheduler room to move.\n"
            "Try 'Optimize peak' or 'Optimize cost' for single-metric tuning."
        )
        return
    flex, priority, r = out
    apply_optimization_result(flex, priority)
    messagebox.showinfo("Multi-objective optimization", _summary(r, flex, priority))


def reset_to_defaults():
    """Restore ASSETS list, sliders, and the input form to startup state."""
    ASSETS.clear()
    ASSETS.extend(default_assets())
    flex_var.set(100.0)
    priority_var.set(50.0)
    flex_value_label.config(text="Flexible users: 100%")
    priority_value_label.config(text="Grid 50% / Price 50%")
    clear_form()
    _cancel_pending_slider_callbacks()
    recalculate_schedules()
    update_stats_and_graph()


optimize_frame = ttk.LabelFrame(left_frame, text="Optimize")
optimize_frame.grid(row=4, column=0, sticky="new", pady=(5, 0))
optimize_frame.columnconfigure(0, weight=1)

ttk.Button(optimize_frame, text="Optimize peak",
           command=find_optimal_settings_fast, style="Optimize.TButton")\
    .grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
ttk.Button(optimize_frame, text="Optimize cost",
           command=find_optimal_settings_cost, style="Optimize.TButton")\
    .grid(row=1, column=0, sticky="ew", padx=4, pady=2)
ttk.Button(optimize_frame, text="Optimize CO2",
           command=find_optimal_settings_co2, style="Optimize.TButton")\
    .grid(row=2, column=0, sticky="ew", padx=4, pady=2)
ttk.Button(optimize_frame, text="Optimize all (peak + cost + CO2)",
           command=find_optimal_settings_multi, style="Optimize.TButton")\
    .grid(row=3, column=0, sticky="ew", padx=4, pady=(2, 4))

ttk.Button(left_frame, text="Reset to defaults",
           command=reset_to_defaults, style="Reset.TButton")\
    .grid(row=5, column=0, sticky="ew", pady=(5, 0))

# --- Graphs ---
before_frame = ttk.LabelFrame(right_frame, text="Before - uncoordinated")
before_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 5))

after_frame = ttk.LabelFrame(right_frame, text="After - smart scheduling")
after_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 5))

bottom_frame = ttk.Frame(right_frame)
bottom_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(5, 0))

right_frame.rowconfigure(0, weight=1)
right_frame.rowconfigure(1, weight=1)
right_frame.rowconfigure(2, weight=1)
right_frame.columnconfigure(0, weight=1)
right_frame.columnconfigure(1, weight=1)

bottom_frame.rowconfigure(0, weight=1)
bottom_frame.columnconfigure(0, weight=3)
bottom_frame.columnconfigure(1, weight=2)

combined_frame = ttk.LabelFrame(bottom_frame, text="Comparison")
combined_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

price_frame = ttk.LabelFrame(bottom_frame, text="Price curve (cents/kWh)")
price_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

canvas_before = tk.Canvas(before_frame, width=700, height=220, bg="white")
canvas_before.grid(row=0, column=0, sticky="nsew")
before_frame.rowconfigure(0, weight=1)
before_frame.columnconfigure(0, weight=1)

canvas_after = tk.Canvas(after_frame, width=700, height=220, bg="white")
canvas_after.grid(row=0, column=0, sticky="nsew")
after_frame.rowconfigure(0, weight=1)
after_frame.columnconfigure(0, weight=1)

canvas_combined = tk.Canvas(combined_frame, width=700, height=220, bg="white")
canvas_combined.grid(row=0, column=0, sticky="nsew")
combined_frame.rowconfigure(0, weight=1)
combined_frame.columnconfigure(0, weight=1)

canvas_price = tk.Canvas(price_frame, width=500, height=220, bg="white")
canvas_price.grid(row=0, column=0, sticky="nsew")
price_frame.rowconfigure(0, weight=1)
price_frame.columnconfigure(0, weight=1)


def _canvas_size(canvas):
    """Actual rendered size (winfo_*) falls back to configured size at start-up."""
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w < 50:
        w = int(canvas["width"])
    if h < 50:
        h = int(canvas["height"])
    return w, h


def get_y_scaling_params():
    """Y-axis upper bound and tick step in kW. Steps of 25, or 50 once the
    peak passes 350 kW, so the labels do not crowd."""
    max_val_data = max(max(before_load), max(after_load))
    step = 25 if max_val_data <= 350 else 50
    if max_val_data <= 0:
        return step, step
    return max(step, step * math.ceil(max_val_data / step)), step


def _draw_axes(canvas, title, y_min, y_max, step, y_label_anchor="center"):
    """Clear the canvas and draw what all four charts share: grid, axes,
    title, hour ticks 0 to 24 and value ticks from y_min to y_max.

    Returns a function that turns (hour index 0 to 24, value) into canvas
    x, y, or None when the canvas is too small to draw on.
    """
    canvas.delete("all")
    w, h = _canvas_size(canvas)
    margin = 40
    usable_height = h - 2 * margin
    if usable_height <= 0:
        return None
    x_step = (w - 2 * margin) / 24.0

    def to_xy(k, val):
        return (margin + k * x_step,
                h - margin - ((val - y_min) / (y_max - y_min)) * usable_height)

    for y_val in range(y_min + step, y_max + 1, step):
        y = to_xy(0, y_val)[1]
        canvas.create_line(margin, y, w - margin, y, fill=COLOR_GRID)

    canvas.create_line(margin, h - margin, w - margin, h - margin)
    canvas.create_line(margin, margin, margin, h - margin)
    canvas.create_text(w / 2, margin / 2, text=title, font=(APP_FONT, 11, "bold"))

    for hour_label in range(0, 25):
        x = margin + hour_label * x_step
        canvas.create_line(x, h - margin, x, h - margin + 5)
        canvas.create_text(x, h - margin + 15, text=str(hour_label), font=(APP_FONT, 8))

    for y_val in range(y_min, y_max + 1, step):
        y = to_xy(0, y_val)[1]
        canvas.create_line(margin - 5, y, margin, y)
        if y_label_anchor == "e":
            canvas.create_text(margin - 10, y, text=str(y_val),
                               font=(APP_FONT, 8), anchor="e")
        else:
            canvas.create_text(margin - 30, y, text=str(y_val), font=(APP_FONT, 8))

    return to_xy


def _hourly_points(to_xy, values):
    """Canvas points for 24 hourly values, with hour 24 repeating hour 0."""
    pts = []
    for k in range(0, 25):
        pts.extend(to_xy(k, values[k % NUM_HOURS]))
    return pts


def draw_single_graph(canvas, load, title, line_color=COLOR_BEFORE_LINE):
    max_tick, step = get_y_scaling_params()
    to_xy = _draw_axes(canvas, title, 0, max_tick, step)
    if to_xy is None:
        return
    canvas.create_line(*_hourly_points(to_xy, load), fill=line_color, width=2)


def draw_combined_graph():
    canvas = canvas_combined
    max_tick, step = get_y_scaling_params()
    to_xy = _draw_axes(canvas, "Comparison", 0, max_tick, step)
    if to_xy is None:
        return

    canvas.create_line(*_hourly_points(to_xy, before_load), fill=COLOR_BEFORE_LINE, width=2)
    canvas.create_line(*_hourly_points(to_xy, after_load), fill=COLOR_AFTER_LINE, width=2,
                       dash=(4, 2))

    w, _ = _canvas_size(canvas)
    legend_y1 = 40 / 2
    legend_y2 = legend_y1 + 20
    legend_x_line = w - 200
    legend_x_text = legend_x_line + 40

    canvas.create_line(legend_x_line, legend_y1, legend_x_line + 30, legend_y1,
                       fill=COLOR_BEFORE_LINE, width=2)
    canvas.create_text(legend_x_text, legend_y1, text="Before",
                       anchor="w", font=(APP_FONT, 9))
    canvas.create_line(legend_x_line, legend_y2, legend_x_line + 30, legend_y2,
                       fill=COLOR_AFTER_LINE, width=2, dash=(4, 2))
    canvas.create_text(legend_x_text, legend_y2, text="After",
                       anchor="w", font=(APP_FONT, 9))


def draw_price_graph():
    """Price axis in steps of 5 c/kWh: 0 to 25 for this day, wider if the
    prices are higher or negative, so no price is cut off."""
    step = 5
    y_min = min(0, step * math.floor(min(PRICE_PER_HOUR) / step))
    y_max = max(25, step * math.ceil(max(PRICE_PER_HOUR) / step))
    to_xy = _draw_axes(canvas_price, "Price (cents/kWh)", y_min, y_max, step,
                       y_label_anchor="e")
    if to_xy is None:
        return
    canvas_price.create_line(*_hourly_points(to_xy, PRICE_PER_HOUR),
                             fill=COLOR_PRICE_LINE, width=2)


def draw_graphs():
    draw_single_graph(canvas_before, before_load,
                      "Total demand BEFORE flexibility (kW)", COLOR_BEFORE_LINE)
    draw_single_graph(canvas_after, after_load,
                      "Total demand AFTER flexibility (kW)", COLOR_AFTER_LINE)
    draw_combined_graph()
    draw_price_graph()


def update_stats_and_graph():
    r = result
    peak_before_var.set(f"{r.peak_before:.1f} kW")
    peak_after_var.set(f"{r.peak_after:.1f} kW")
    reduction_var.set(f"{r.peak_before - r.peak_after:.1f} kW ({r.peak_reduction_pct:.1f}%)")

    cost_before_var.set(f"{r.cost_before:.2f} EUR")
    cost_after_var.set(f"{r.cost_after:.2f} EUR")
    saving_cost_var.set(f"{r.cost_before - r.cost_after:.2f} EUR ({r.cost_saving_pct:.1f}%)")

    # Same basis as cost: the flexible loads only, so the two percentages are
    # comparable. The base load cannot move, so including it would only dilute
    # the saving. One modelled day is not extrapolated to a year.
    co2_var.set(f"{r.co2_before - r.co2_after:.1f} kg/day ({r.co2_saving_pct:.1f}%)")

    # green when the metric improves, red when it gets worse
    for label, pct in ((reduction_label, r.peak_reduction_pct),
                       (saving_cost_label, r.cost_saving_pct),
                       (co2_label, r.co2_saving_pct)):
        label.configure(style="Saving.TLabel" if pct >= 0 else "Loss.TLabel")

    draw_graphs()


# Redraw graphs when canvases are resized.
# Debounced because each of the 4 canvases fires <Configure> on every
# window resize tick - without coalescing we'd redraw ~16 times per tick.
def _on_canvas_configure(event):
    if root.after_id_redraw:
        root.after_cancel(root.after_id_redraw)
    root.after_id_redraw = root.after(50, draw_graphs)


for c in (canvas_before, canvas_after, canvas_combined, canvas_price):
    c.bind("<Configure>", _on_canvas_configure)


recalculate_schedules()
update_stats_and_graph()

if __name__ == "__main__":
    root.mainloop()
