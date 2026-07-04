#!/usr/bin/env python3
"""checker_cause_analysis.py -- WHY does dark16 beat dark50? + Bayes risk.

Companion to checker_stat_sweep.py: consumes the same per-frame stats CSV
(regenerate with `checker_stat_sweep.py --compute --csv PATH`) and answers
the cause questions behind the 2026-07-03 sweep result:
  0. photometry of the pseudo-RAW (linear-light vs sRGB mosaic, empirical)
  1. class-conditional distributions / overlap coefficient
  2. 8-bit band-mass decomposition (which pixel bands carry the signal)
  3. operating-point error flips dark50@0.80 -> dark16@0.62
  4. Bayes risk with measured mAP costs (C_miss=0.1118, C_FA=0.0387,
     map_ablation_{exdark,coco}_yolov8n.csv; see theory report SS1.2)
  5. decomposition of the J improvement (subset / ratio / statistic effects)

Usage: python3 checker_cause_analysis.py [--csv PATH]
"""
import argparse
import csv
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve()
for p in [REPO] + list(REPO.parents):
    if (p / "data" / "coco_val").is_dir():
        REPO = p
        break
else:
    REPO = Path("/home/mini/workspace/dfxisp")

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--csv", default=str(Path(__file__).parent / "frame_stats.csv"))
CSV = Path(ap.parse_args().csv)

# ---------------------------------------------------------------- load csv --
with CSV.open() as f:
    rows = list(csv.DictReader(f))
D = {}
for k in rows[0]:
    if k in ("dataset", "stem"):
        D[k] = np.array([r[k] for r in rows])
    else:
        D[k] = np.array([float(r[k]) for r in rows])
y = D["label"]
pos, neg = y == 1, y == 0  # ExDark, COCO


def auc(scores):
    """Mann-Whitney AUC with tie correction, darkness-increasing scores."""
    p, n = scores[pos], scores[neg]
    allv = np.concatenate([p, n])
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt)
    ranks = (csum[inv] + (csum - cnt)[inv] + 1) / 2.0
    return (ranks[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))


# ------------------------------------------------- 0. what IS the raw data --
# Empirically identify the pseudo-RAW photometry: is raw16>>8 the sRGB 8-bit
# value mosaicked directly, or an inverse-gamma (linearized) value?
print("## 0. pseudo-RAW photometry check")
from PIL import Image  # noqa: E402
for ds in ("coco_val", "exdark_val"):
    raw_dir = REPO / "data" / ds / "raw_bin"
    img_dir = REPO / "data" / ds / "images"
    bp = sorted(raw_dir.glob("*.bin"))[0]
    src = None
    for p in img_dir.glob(f"{bp.stem}.*"):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            src = p
            break
    with Image.open(src) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float64)
    h, w = rgb.shape[:2]
    h -= h % 2; w -= w % 2
    rgb = rgb[:h, :w]
    a = np.fromfile(bp, dtype="<u2").reshape(h, w).astype(np.float64)
    v8 = a / 256.0
    # RGGB mosaic of the sRGB image
    mos = np.empty((h, w))
    mos[0::2, 0::2] = rgb[0::2, 0::2, 0]
    mos[0::2, 1::2] = rgb[0::2, 1::2, 1]
    mos[1::2, 0::2] = rgb[1::2, 0::2, 1]
    mos[1::2, 1::2] = rgb[1::2, 1::2, 2]
    lin = 255.0 * (mos / 255.0) ** 2.2  # inverse-gamma hypothesis
    err_direct = np.abs(v8 - mos).mean()
    err_lin = np.abs(v8 - lin).mean()
    print(f"  {ds} {bp.stem}: MAE(raw>>8 vs sRGB mosaic)={err_direct:.3f}  "
          f"MAE(vs inverse-gamma 2.2)={err_lin:.3f}")

# --------------------------------------- 1. class-conditional distributions --
print("\n## 1. class-conditional distribution / valley (bin=0.02)")
for name in ("dark16", "dark50"):
    s = D[name]
    bins = np.arange(0, 1.02, 0.02)
    hp, _ = np.histogram(s[pos], bins=bins, density=True)
    hn, _ = np.histogram(s[neg], bins=bins, density=True)
    ovl = np.minimum(hp, hn).sum() * 0.02  # overlap coefficient
    print(f"  {name}: overlap coeff={ovl:.4f} (Bayes err proxy {ovl/2:.4f})")
    # mass of each class in decision-boundary neighborhoods
    t = {"dark16": 0.615, "dark50": 0.822}[name]
    for w_ in (0.05, 0.10):
        mp = ((s[pos] > t - w_) & (s[pos] <= t + w_)).mean()
        mn = ((s[neg] > t - w_) & (s[neg] <= t + w_)).mean()
        print(f"    |s-t*|<={w_:.2f}: ExDark {mp*100:.1f}%  COCO {mn*100:.1f}%")

# where does COCO sit on each axis? quartiles
for name in ("dark16", "dark50"):
    s = D[name]
    qp = np.percentile(s[pos], [25, 50, 75, 90])
    qn = np.percentile(s[neg], [25, 50, 75, 90])
    print(f"  {name} quartiles(25/50/75/90): ExDark {np.round(qp,3)}  "
          f"COCO {np.round(qn,3)}")

# ------------------------------------------------ 2. band decomposition -----
print("\n## 2. 8-bit band mass per class + per-band AUC")
bands = [("[0,16)", D["dark16"]),
         ("[16,24)", D["dark24"] - D["dark16"]),
         ("[24,32)", D["dark32"] - D["dark24"]),
         ("[32,48)", D["dark48"] - D["dark32"]),
         ("[48,50)", D["dark50"] - D["dark48"]),
         ("[50,64)", D["dark64"] - D["dark50"]),
         ("[16,50)", D["dark50"] - D["dark16"])]
print("| band | ExDark mean mass | COCO mean mass | AUC(band ratio) |")
for nm, v in bands:
    print(f"| {nm} | {v[pos].mean():.3f} | {v[neg].mean():.3f} | "
          f"{auc(v):.3f} |")

# correlation: does the [16,50) mass explain dark50's errors?
b1650 = D["dark50"] - D["dark16"]
err50 = ((D["dark50"] > 0.80) != y.astype(bool))
print(f"\n  [16,50) mass: err-frames(dark50@0.80) mean={b1650[err50].mean():.3f} "
      f"vs correct-frames mean={b1650[~err50].mean():.3f}")

# ---------------------------------------------------- 3. error flip table ---
print("\n## 3. operating-point error flips: dark50>0.80 -> dark16>0.62")
old = D["dark50"] > 0.80
new = D["dark16"] > 0.62
for cls, mask, want in (("ExDark(miss)", pos, True), ("COCO(FT)", neg, False)):
    o_err = (old != want) & mask
    n_err = (new != want) & mask
    fixed = o_err & ~n_err
    broke = ~o_err & n_err
    both = o_err & n_err
    print(f"  {cls}: old errors={o_err.sum()}  new errors={n_err.sum()}  "
          f"fixed={fixed.sum()}  newly-broken={broke.sum()}  persistent={both.sum()}")
    for tag, m in (("fixed", fixed), ("newly-broken", broke)):
        if m.sum():
            print(f"    {tag} frames: [16,50) mass mean={b1650[m].mean():.3f}, "
                  f"dark16 mean={D['dark16'][m].mean():.3f}, "
                  f"dark50 mean={D['dark50'][m].mean():.3f}")
            ex = D["stem"][m][:4]
            print(f"    examples: {', '.join(ex)}")

# persistent-error characterization (what NO dark-ratio threshold can fix)
print(f"\n  persistent ExDark misses n={(pos & ~old & ~new).sum()}: "
      f"dark16 median={np.median(D['dark16'][pos & ~old & ~new]):.3f}, "
      f"mean8 median={np.median(D['mean8'][pos & ~old & ~new]):.1f}")
print(f"  persistent COCO FTs n={(neg & old & new).sum()}: "
      f"dark16 median={np.median(D['dark16'][neg & old & new]):.3f}, "
      f"mean8 median={np.median(D['mean8'][neg & old & new]):.1f}")

# ---------------------------------------------------- 4. Bayes risk ---------
print("\n## 4. Bayes risk with measured costs (C_miss=0.1118, C_FA=0.0387)")
CM, CF = 0.1118, 0.0387
print("| rule | recall | FT | J | E[mAP loss]/frame (pi=0.5) |")
def risk(pred):
    miss = 1 - pred[pos].mean()
    ft = pred[neg].mean()
    return miss, ft, 0.5 * (miss * CM + ft * CF)
for nm, pred in (("dark50>0.80 (current)", old),
                 ("dark16>0.615 (J*)", D["dark16"] > 0.615),
                 ("dark16>0.62 (adopted)", new)):
    miss, ft, r = risk(pred)
    print(f"| {nm} | {1-miss:.3f} | {ft:.3f} | {1-miss-ft:.3f} | {r:.5f} |")
# Bayes-optimal threshold sweep for dark16 and dark50
for nm in ("dark16", "dark50"):
    s = D[nm]
    ts = np.unique(np.round(s, 3))
    best = min(((risk(s > t)[2], t) for t in ts))
    miss, ft, r = risk(s > best[1])
    print(f"| {nm} Bayes-opt t={best[1]:.3f} | {1-miss:.3f} | {ft:.3f} | "
          f"{1-miss-ft:.3f} | {r:.5f} |")

# risk reduction summary
_, _, r_old = risk(old)
_, _, r_new = risk(new)
print(f"\n  risk reduction dark50@0.80 -> dark16@0.62: {r_old:.5f} -> {r_new:.5f} "
      f"({100*(r_old-r_new)/r_old:.1f}% lower expected mAP loss)")

# ----------------------------------- 5. decompose ver2-doc vs full-set gap --
print("\n## 5. decomposition: documented ver2 J=0.79 -> dark16 J=0.849")
r0, f0 = 0.900, 0.110  # documented ver2 subset numbers
print(f"  (a) documented ver2 (subset n=150~200, golden Y<50): J={r0-f0:.3f}")
gr = (D['y50_ratio'] > 0.80)
miss, ft, _ = risk(gr)
print(f"  (b) same rule, full 1150 frames (golden Y<50): J={1-miss-ft:.3f}")
miss, ft, _ = risk(old)
print(f"  (c) HW-equivalent dark50>0.80, full set: J={1-miss-ft:.3f}")
s = D['dark50']
ts = np.unique(np.round(s, 3))
bj = max(((( (s>t)[pos].mean() - (s>t)[neg].mean()), t) for t in ts))
print(f"  (d) dark50, ratio re-tuned (t={bj[1]:.3f}): J={bj[0]:.3f}")
miss, ft, _ = risk(new)
print(f"  (e) dark16>0.62 (statistic + ratio): J={1-miss-ft:.3f}")
