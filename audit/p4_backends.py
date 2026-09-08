"""P4 across backends and against its null, recomputed from the CSVs.

Reports the signed shape (`moment`, which can be negative) as well as Hill, because the paper's
order parameter is xi = max(gamma, 0) and clipping hides the sign that says whether the tail is
heavy at all.
"""

import csv
import glob
import pathlib

import numpy as np
from scipy.stats import spearmanr

ROOT = pathlib.Path(".")


def load(p):
    rows = list(csv.DictReader(open(p)))
    out = {}
    for k in rows[0]:
        out[k] = np.array(
            [float(r[k]) if r[k] not in ("", "nan", "None") else np.nan for r in rows]
        )
    return out


SETS = [
    ("MPS   (local)", "results/full/grokking/p4_grokking_seed*.csv"),
    ("CUDA  (A100) ", "results/full/grokking_cuda/p4_grokking_seed*.csv"),
    ("CPU   (fp32) ", "results/full/grokking_cpu/p4_grokking_seed*.csv"),
    ("NULL  (shuf) ", "results/full/grokking_null/p4_grokking_seed*.csv"),
]

hdr = "{:<14} {:>4} {:>8} {:>9} {:>9} {:>9} {:>9} {:>9} {:>9}"
print(hdr.format("run", "seed", "grok@", "hill_1st", "hill_last", "rho_hill", "mom_1st",
                 "mom_last", "rho_mom"))
print("-" * 100)
summary = {}
for label, pat in SETS:
    rhos_h, rhos_m = [], []
    for f in sorted(glob.glob(pat)):
        d = load(f)
        st, h, te = d["step"], d["hill"], d["test_acc"]
        m = d["moment"]
        lo, hi = np.nanmin(te), np.nanmax(te)
        grok = st[np.argmax(te >= (lo + hi) / 2)] if hi - lo > 0.1 else np.nan
        okh = np.isfinite(h)
        okm = np.isfinite(m)
        rh = spearmanr(st[okh], h[okh]).statistic
        rm = spearmanr(st[okm], m[okm]).statistic
        rhos_h.append(rh)
        rhos_m.append(rm)
        seed = f.split("seed")[1][0]
        print(hdr.format(label, seed, f"{grok:.0f}" if np.isfinite(grok) else "none",
                         f"{h[0]:.4f}", f"{h[-1]:.4f}", f"{rh:+.3f}",
                         f"{m[0]:+.4f}", f"{m[-1]:+.4f}", f"{rm:+.3f}"))
    if rhos_h:
        summary[label] = (np.mean(rhos_h), np.mean(rhos_m))
    print()

print("=" * 100)
print("mean Spearman(step, .) per run set")
for label, (rh, rm) in summary.items():
    print("  {}  hill {:+.3f}   moment(signed) {:+.3f}".format(label, rh, rm))

print()
print("=" * 100)
print("Is the signed shape ever positive? (xi = max(gamma,0) hides this)")
for label, pat in SETS:
    for f in sorted(glob.glob(pat)):
        d = load(f)
        m = d["moment"][np.isfinite(d["moment"])]
        g = d["gpd"][np.isfinite(d["gpd"])]
        print("  {} seed{}  moment: {:.1f}% >0  min {:+.3f} max {:+.3f} | gpd: {:.1f}% >0".format(
            label, f.split("seed")[1][0], 100 * (m > 0).mean(), m.min(), m.max(),
            100 * (g > 0).mean()))
