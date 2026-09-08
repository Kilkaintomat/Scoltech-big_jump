"""Does the archived run reproduce, and is its k comparable across settings?

Uses the run's own seed (20270101) so the comparison is against the archived numbers rather than
against a different draw.
"""

import numpy as np

from onebigjump.simulation.kesten import simulate, xi_two_heuristics
from onebigjump.stats import hill, moment, sorted_positive_desc
from onebigjump.stats.gpd import gpd_from_order_statistics

SEED = 20270101
ARCHIVED = {  # p -> (k, hill, moment, gpd) straight out of figure1_metrics.json
    0.02: (3813, 0.2610, 0.1522, 0.1390),
    0.05: (12484, 0.3472, 0.3109, 0.2927),
}


def est(z, k):
    x = sorted_positive_desc(z)
    k = int(min(max(k, 20), x.size - 2))
    try:
        g = float(gpd_from_order_statistics(x, k).gamma)
    except Exception:
        g = float("nan")
    return hill(x, k), moment(x, k), g


print("=" * 88)
print("A. DOES THE ARCHIVED RUN REPRODUCE AT ITS OWN SEED AND k?")
print("=" * 88)
for p, (k, h0, m0, g0) in ARCHIVED.items():
    t = simulate(p=p, n_traces=3000, n_steps=64, burn_in=200, seed=SEED)
    h, m, g = est(t.z.ravel(), k)
    print("  p={:.2f} k={:<6} archived (hill {:.4f} moment {:.4f} gpd {:.4f})".format(
        p, k, h0, m0, g0))
    print("            recomputed (hill {:.4f} moment {:.4f} gpd {:.4f})  {}".format(
        h, m, g, "MATCH" if abs(m - m0) < 5e-3 else "DIFFERS"))

print()
print("=" * 88)
print("B. SENSITIVITY TO k AT p = 0.02  (true xi = {:.4f}, selector chose 1.99%)".format(
    xi_two_heuristics(0.02)))
print("=" * 88)
t = simulate(p=0.02, n_traces=3000, n_steps=64, burn_in=200, seed=SEED)
z = t.z.ravel()
print("{:>9} {:>8} {:>9} {:>9} {:>9}   {}".format("k/n", "k", "hill", "moment", "gpd", "note"))
for frac in (0.002, 0.005, 0.01, 0.0199, 0.05, 0.13, 0.20):
    h, m, g = est(z, round(frac * z.size))
    note = "<-- the selector's choice" if abs(frac - 0.0199) < 1e-6 else ""
    print("{:>9} {:>8} {:>9.4f} {:>9.4f} {:>9.4f}   {}".format(
        "{:.2%}".format(frac), round(frac * z.size), h, m, g, note))

print()
print("=" * 88)
print("C. IS THE SELECTED k COMPARABLE ACROSS SETTINGS?")
print("=" * 88)
print("  archived k/n by p: 5.00%, 1.99%, 6.50%, 12.79%, 12.79%, 19.95%")
print("  Each cell of Table 1 is therefore fitted at a different depth into the tail. A ten-fold")
print("  swing in k/n between neighbouring settings means the cells are not on a common footing,")
print("  and the bias each carries differs by cell -- see panel B for how much k alone moves the")
print("  answer at a single p.")
