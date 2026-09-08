"""Why does the estimate undershoot at p = 0.02, and what is really true at p = 0?

The previous report attributed the p=0.02 undershoot to 64-step traces holding too few shocks.
That explanation is testable and is tested here, against the alternatives it was never compared
with: the choice of k, and the total number of steps rather than their arrangement.
"""

import numpy as np

from onebigjump.simulation.kesten import simulate, xi_two_heuristics
from onebigjump.stats import hill, moment, sorted_positive_desc
from onebigjump.stats.gpd import gpd_from_order_statistics


def est(z, k):
    x = sorted_positive_desc(z)
    k = int(min(max(k, 20), x.size - 2))
    try:
        g = float(gpd_from_order_statistics(x, k).gamma)
    except Exception:
        g = float("nan")
    return hill(x, k), moment(x, k), g


print("=" * 92)
print("1. THE k GRID at p = 0.02   (true xi = {:.4f})".format(xi_two_heuristics(0.02)))
print("=" * 92)
tr = simulate(p=0.02, n_traces=3000, n_steps=64, seed=11)
z = tr.z.ravel()
n = z.size
print("pooled n = {}".format(n))
print("{:>10} {:>9} {:>9} {:>9} {:>9}".format("k", "k/n", "hill", "moment", "gpd"))
for frac in (0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.065, 0.10, 0.25):
    h, m, g = est(z, round(frac * n))
    print("{:>10} {:>9} {:>9.4f} {:>9.4f} {:>9.4f}".format(round(frac * n),
          "{:.3%}".format(frac), h, m, g))
print()
print("The run in results/ used the double bootstrap, which chose k = 12484 (6.5% of n).")

print()
print("=" * 92)
print("2. IS IT TRACE LENGTH, OR TOTAL STEPS?  same total steps, different arrangement, p = 0.02")
print("=" * 92)
print("{:>8} {:>8} {:>10} {:>9} {:>9} {:>9}".format("traces", "steps", "total", "hill", "moment",
                                                    "gpd"))
TOTAL = 192000
for ell in (16, 64, 256, 1024):
    m_tr = TOTAL // ell
    t = simulate(p=0.02, n_traces=m_tr, n_steps=ell, seed=11)
    zz = t.z.ravel()
    h, mm, g = est(zz, round(0.002 * zz.size))
    print("{:>8} {:>8} {:>10} {:>9.4f} {:>9.4f} {:>9.4f}".format(m_tr, ell, zz.size, h, mm, g))
print("(k fixed at 0.2% of n so the comparison is about the data, not about k)")

print()
print("=" * 92)
print("3. BURN-IN: does the transient matter?   p = 0.02, k = 0.2% of n")
print("=" * 92)
for burn in (0, 10, 200, 2000):
    t = simulate(p=0.02, n_traces=3000, n_steps=64, seed=11, burn_in=burn)
    zz = t.z.ravel()
    h, mm, g = est(zz, round(0.002 * zz.size))
    print("  burn_in={:>5}   hill {:.4f}  moment {:.4f}  gpd {:.4f}".format(burn, h, mm, g))

print()
print("=" * 92)
print("4. p = 0: what IS the true tail?")
print("=" * 92)
print("At p=0 the multiplier is rho=0.7 deterministic and B_t is Gaussian, so E_t is a stationary")
print("Gaussian AR(1), its increments are Gaussian, and Z_t = ||increment|| in R^8 is chi-")
print("distributed. A chi distribution has UNBOUNDED support and a Gaussian upper tail: it lies in")
print("the Gumbel domain, where the true EVT shape is gamma = 0 exactly -- not gamma < 0, which")
print("would mean a bounded endpoint.")
print()
t0 = simulate(p=0.0, n_traces=3000, n_steps=64, seed=11)
z0 = t0.z.ravel()
print("  max observed Z_t = {:.3f}   (a bounded law would show a hard ceiling)".format(z0.max()))
print("{:>10} {:>9} {:>9} {:>9}".format("k/n", "hill", "moment", "gpd"))
for frac in (0.001, 0.005, 0.02, 0.05, 0.25):
    h, m, g = est(z0, round(frac * z0.size))
    print("{:>10} {:>9.4f} {:>9.4f} {:>9.4f}".format("{:.2%}".format(frac), h, m, g))
print()
print("Negative estimates here are finite-sample bias in the Gumbel domain, not evidence of a")
print("bounded tail. Reporting them as 'correctly negative, i.e. bounded' misreads the model.")

print()
print("=" * 92)
print("5. SEED SPREAD at the run's own k fraction (6.5%), p = 0.02 and p = 0.05")
print("=" * 92)
for p in (0.02, 0.05):
    hs, ms, gs = [], [], []
    for s in range(6):
        t = simulate(p=p, n_traces=3000, n_steps=64, seed=100 + s)
        zz = t.z.ravel()
        h, m, g = est(zz, round(0.065 * zz.size))
        hs.append(h); ms.append(m); gs.append(g)
    print("  p={:.2f} true xi={:.4f} | hill {:.4f}+-{:.4f}  moment {:.4f}+-{:.4f}  gpd {:.4f}+-{:.4f}".format(
        p, xi_two_heuristics(p), np.mean(hs), np.std(hs), np.mean(ms), np.std(ms),
        np.mean(gs), np.std(gs)))
print()
print("A spread far smaller than the gap to the truth means the undershoot is bias, not noise.")
