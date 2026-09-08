"""Is P4's reported quantity the paper's order parameter?

The paper's order parameter is xi = max(gamma, 0), where gamma is the signed EVT shape. Hill is a
mean of log-ratios of upper order statistics and is >= 0 by construction: it cannot represent a
light tail at all. This asks which of the two P4 actually moves.
"""

import csv
import glob

import numpy as np
from scipy.stats import spearmanr

SETS = [
    ("MPS", "results/full/grokking/p4_grokking_seed*.csv"),
    ("CUDA", "results/full/grokking_cuda/p4_grokking_seed*.csv"),
    ("CPU", "results/full/grokking_cpu/p4_grokking_seed*.csv"),
    ("NULL", "results/full/grokking_null/p4_grokking_seed*.csv"),
]


def load(p):
    rows = list(csv.DictReader(open(p)))
    return {
        k: np.array([float(r[k]) if r[k] not in ("", "nan", "None") else np.nan for r in rows])
        for k in rows[0]
    }


print("xi = max(moment, 0), the paper's order parameter, versus Hill which P4 actually reports")
print()
f = "{:<6} {:>4} {:>10} {:>10} {:>12} {:>12} {:>11}"
print(f.format("run", "seed", "hill_mean", "rho_hill", "xi>0 frac", "xi_mean", "rho_xi"))
print("-" * 74)
for label, pat in SETS:
    for p in sorted(glob.glob(pat)):
        d = load(p)
        st, h, m = d["step"], d["hill"], d["moment"]
        xi = np.maximum(m, 0.0)
        ok = np.isfinite(h)
        rho_h = spearmanr(st[ok], h[ok]).statistic
        okx = np.isfinite(xi)
        # A constant vector has no rank correlation; say so rather than print a NaN as a number.
        rho_x = spearmanr(st[okx], xi[okx]).statistic if np.ptp(xi[okx]) > 0 else np.nan
        seed = p.split("seed")[1][0]
        print(f.format(label, seed, "{:.4f}".format(np.nanmean(h)), "{:+.3f}".format(rho_h),
                       "{:.1%}".format(np.nanmean(xi > 0)), "{:.5f}".format(np.nanmean(xi)),
                       "{:+.3f}".format(rho_x) if np.isfinite(rho_x) else "undefined"))
    print()

print("=" * 74)
print("Reading: if xi is 0 at essentially every checkpoint, the order parameter does not move,")
print("and whatever P4 reports moving is Hill -- a different statistic that cannot be negative.")
