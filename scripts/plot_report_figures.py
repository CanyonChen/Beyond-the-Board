"""Render report and slide figures from verified outputs. Run from any directory."""

import csv
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/processed/clock_audit.json"
COMPARISON = ROOT / "results/model_comparison"
VERIFIED = COMPARISON / "verified_180_0"
OUTPUT = COMPARISON / "report_figures"

INK = "#1D1D1F"
ACCENT = "#BF165E"
GRAY = "#555D61"
GRID = "#D5DADA"
STYLE = {
    "font.family": "DejaVu Sans", "font.size": 11, "axes.labelsize": 11,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": GRAY, "ytick.color": INK,
    "axes.edgecolor": GRAY, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.axisbelow": True, "ytick.major.size": 0,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "svg.fonttype": "none", "svg.hashsalt": "beyond-the-board",
    "pdf.fonttype": 42,
}


def read_rows(source):
    with source.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def grid(ax):
    ax.grid(axis="x", color=GRID, linewidth=0.65)
    ax.tick_params(axis="x", length=3, pad=4)
    ax.tick_params(axis="y", pad=6)


def percent(value):
    return "100%" if value == 100 else f"{value:.2f}%"


def clock_alignment():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    offsets = audit["json_vs_rounded_pgn_by_index_offset"]
    archived = audit["archived_clk_opponent"]
    positions = [1, 0]
    total = archived["archived_labeled_plies_with_clocks"]
    panels = [
        ("Agreement with PGN clocks", "Readings within ±0.5 s",
         [("Corrected index", offsets["0"]["within_pgn_rounding"], offsets["0"]["n"]),
          ("Archived index", offsets["1"]["within_pgn_rounding"], offsets["1"]["n"])]),
        ("Archived opponent clock", "Labelled moves with an exact match",
         [("Mover after move", archived["agrees_with_movers_current_post_move_clock"], total),
          ("Opponent before move", archived["agrees_with_opponents_correct_turn_start_clock"], total)]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 2.7), layout="constrained")
    descriptions = []
    for ax, (title, xlabel, observations) in zip(axes, panels):
        labels, counts, sizes = zip(*observations)
        values = [100 * n / d for n, d in zip(counts, sizes)]
        ax.set_title(title, fontsize=11, pad=10)
        ax.barh(positions, values, height=0.38, color=[ACCENT, GRAY])
        ax.set(yticks=positions, yticklabels=labels, xlim=(0, 100), ylim=(-0.58, 1.58),
               xticks=[0, 50, 100], xlabel=xlabel)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
        grid(ax)
        for y, value in zip(positions, values):
            inside = value > 80
            ax.annotate(percent(value), (value, y), xytext=(-5 if inside else 5, 0),
                        textcoords="offset points", va="center", ha="right" if inside else "left",
                        weight="bold", color="white" if inside else INK, fontsize=10.5)
        text = [f"{label}: {n:,}/{d:,} ({percent(value)})"
                for (label, n, d), value in zip(observations, values)]
        descriptions.append(f"{title}. " + "; ".join(text) + ".")
    alt = " ".join(descriptions) + " The exact-match outcomes in the second panel can overlap."
    return fig, "Clock alignment in the archived move data", alt, [AUDIT]


def feature_gains():
    source = VERIFIED / "paired_log_loss.csv"
    paired = {r["contrast"]: r for r in read_rows(source) if r["split"] == "published_test"}
    contrasts = [("Add both clocks", "clocks_minus_no_time"),
                 ("Then add recent time use", "history_minus_clocks"),
                 ("Both additions vs baseline", "full_minus_no_time")]
    fig, ax = plt.subplots(figsize=(8.2, 2.65), layout="constrained")
    notes = []
    for y, (label, contrast) in zip([2, 1, 0], contrasts):
        row = paired[contrast]
        # Source differences are augmented minus reference; reverse the sign and endpoint order.
        estimate = -float(row["delta_log_loss"])
        lower = -float(row["upper_95"])
        upper = -float(row["lower_95"])
        ax.errorbar(estimate, y, xerr=[[estimate-lower], [upper-estimate]],
                    fmt="D" if y == 0 else "o", ms=6.5, capsize=4, capthick=1.3,
                    color=GRAY if y == 1 else ACCENT, elinewidth=1.7)
        notes.append(f"{label}: {estimate:.6f} [{lower:.6f}, {upper:.6f}].")
        ax.annotate(f"{estimate:.6f}", (estimate, y), xytext=(0, 9), textcoords="offset points",
                    ha="center", weight="bold", fontsize=10.5)
    ax.axvline(0, color=GRAY, linestyle="--", lw=1)
    ax.set(yticks=[2, 1, 0], yticklabels=[label for label, _ in contrasts],
           xlim=(-0.00008, 0.0016), ylim=(-0.55, 2.75),
           xticks=[0, .0004, .0008, .0012, .0016],
           xlabel="Reduction in mean log loss (larger is better)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: "0" if x == 0 else f"{x:.4f}"))
    grid(ax)
    alt = ("Final-week histogram gradient boosting with the zero-risk rule. "
           + " ".join(notes) + " Intervals are paired 95% percentiles from "
           + f"{int(paired['full_minus_no_time']['bootstrap_resamples']):,} whole-game resamples.")
    return fig, "Incremental predictive value of clock information", alt, [source]


def model_comparison():
    sources = [VERIFIED / "validation_means.csv", VERIFIED / "published_test_metrics.csv"]
    families = [("Training prevalence", "prevalence"), ("Logistic regression", "logistic"),
                ("XGBoost", "xgb"), ("Histogram boosting", "hgb")]
    titles = ["Development · three-window mean", "Final week · 24–30 September"]
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(8.8, 3.0), layout="constrained")
    notes = []
    for i, (ax, title, path) in enumerate(zip(axes, titles, sources)):
        rows = {(r["family"], r["inputs"], r["gate"]): r for r in read_rows(path)}
        panel = []
        for y, (label, family) in enumerate(families):
            variant = ("constant", "False") if family == "prevalence" else ("clocks_and_history", "True")
            value = float(rows[family, *variant]["log_loss"])
            mark_color = ACCENT if family == "hgb" else GRAY
            ax.plot(value, y, marker="o" if i == 0 else "s", ms=7,
                    color=mark_color, linestyle="none",
                    markerfacecolor=mark_color if i == 0 else "white", markeredgewidth=1.7)
            ax.annotate(f"{value:.6f}", (value, y), xytext=(0, 7),
                        textcoords="offset points", ha="center", fontsize=9)
            panel.append(f"{label} {value:.6f}")
        ax.set(yticks=range(len(families)), yticklabels=[label for label, _ in families],
               xlim=(.226, .300), ylim=(3.45, -.7), xticks=[.23,.25,.27,.29],
               xlabel="Mean log loss (lower is better)")
        ax.set_title(title, pad=8, fontsize=11.5)
        grid(ax)
        notes.append(title + ". " + ", ".join(panel) + ".")
    alt = (" ".join(notes) + " All three fitted models use full inputs and the zero-risk rule. "
           "The prevalence baseline predicts the training event rate. The final week was previously evaluated.")
    return fig, "Predictive performance on the verified cohort", alt, sources


def phase_error_rates():
    source = COMPARISON / "clock_subgroups.csv"
    rows = {(r["dimension"], r["group"]):r for r in read_rows(source)}
    phases = ["opening", "middlegame", "endgame"]
    population = rows["all", "all"]
    fig, ax = plt.subplots(figsize=(7.6, 2.65), layout="constrained")
    labels, notes = [], []
    for y, phase in zip([2,1,0], phases):
        row = rows["phase", phase]
        errors, moves = int(row["events"]), int(row["moves"])
        rate = 100 * errors / moves
        labels.append(f"{phase.capitalize()}\n{errors:,} / {moves:,}")
        notes.append(f"{phase.capitalize()}: {errors:,} serious errors in {moves:,} moves ({rate:.2f}%).")
        ax.barh(y, rate, color=ACCENT if phase == "middlegame" else GRAY, height=0.38)
        ax.annotate(f"{rate:.2f}%", (rate, y), xytext=(5,0), textcoords="offset points",
                    va="center", fontsize=11, color=INK, weight="bold")
    overall_rate = 100 * int(population["events"]) / int(population["moves"])
    ax.axvline(overall_rate, linestyle="--", linewidth=1.25, color=GRAY)
    ax.text(overall_rate, 2.55, f"Overall {overall_rate:.2f}%", ha="center", va="bottom",
            fontsize=10, color=GRAY, bbox={"facecolor":"white", "edgecolor":"none", "pad":2})
    ax.set(yticks=[2,1,0], yticklabels=labels, xticks=[0,3,6,9,12],
           xlim=(0,13.2), ylim=(-.55, 3), xlabel="Observed serious-error rate (% of moves)")
    grid(ax)
    alt = (" ".join(notes) + f" Overall: {int(population['events']):,} serious errors in "
           f"{int(population['moves']):,} moves ({overall_rate:.2f}%), 24–30 September.")
    return fig, "Observed final-week serious-error rates by game phase", alt, [source]


def export(stem, fig, title, description, sources):
    pdf = OUTPUT / f"{stem}.pdf"
    svg = OUTPUT / f"{stem}.svg"
    fig.savefig(pdf, metadata={"Title": title, "Subject": description, "CreationDate": None})
    fig.savefig(svg, metadata={"Title": title, "Description": description, "Date": None})
    # Expose a short name and long description to assistive technology when the SVG is inline.
    text = svg.read_text(encoding="utf-8")
    text = text.replace("<svg ", f'<svg role="img" aria-labelledby="{stem}-title {stem}-desc" ', 1)
    text = text.replace(f"<title>{escape(title)}</title>",
                        f'<title id="{stem}-title">{escape(title)}</title>\n'
                        f'<desc id="{stem}-desc">{escape(description)}</desc>', 1)
    svg.write_text(text, encoding="utf-8")
    width, height = fig.get_size_inches()
    plt.close(fig)
    return {
        "title": title, "description": description, "size_mm": [round(width*25.4, 1), round(height*25.4, 1)],
        "sources": {s.relative_to(ROOT).as_posix(): hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {"matplotlib": mpl.__version__,
                "palette": {"accent": ACCENT, "ink": INK, "muted": GRAY, "line": GRID},
                "figures": {}}
    with mpl.rc_context(STYLE):
        for draw in (clock_alignment, feature_gains, model_comparison, phase_error_rates):
            manifest["figures"][draw.__name__] = export(draw.__name__, *draw())
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")


if __name__ == "__main__":
    main()

