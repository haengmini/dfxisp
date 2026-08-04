#!/usr/bin/env python3
"""checker_adaptive_tau.py -- sensor-metadata-adaptive dark threshold tau(s,g)
for the scene checker (strengthening-strategy item #1).

Campaign : checker-sota #1 (2026-07-10), branch exp/principled-checker-rm-2026-07-05.
Track    : checker-strengthening-2026-07-10.md item #1 step 1 ("tau(s,g) parametric
           model + tools/checker_adaptive_tau.py prototype -- EXIF -> tau. AODRaw
           NOT required, start now: derivation + scaffold"). This is the
           DERIVATION + SCAFFOLD only; the real-data stratified validation
           (fixed-tau vs adaptive-tau recall/FT per ISO stratum on LOD/AODRaw)
           is PENDING a downloaded dataset + GPU mAP.

Problem it solves (see results/checker-principles-2026-07-05.md, Principle 3).
  The deployed checker (src/dfxisp_accel.cpp:145 checker_select_mode) counts
  pixels below a FIXED `dark_pixel_threshold` (an AXI-lite runtime register,
  line 403) and routes to LOW_LIGHT when that ratio exceeds DARK_RATIO_PCT.
  That constant was calibrated on synthetic pseudo-RAW; on a real sensor whose
  exposure (s), analog gain (g), and black level (BLC) vary frame-to-frame the
  absolute threshold's meaning collapses. Principle 3 says the threshold must
  sit at the READ-NOISE FLOOR, which is itself gain-dependent.

Model (from checker-strengthening-2026-07-10.md #1, "설계"):
      tau(g) = BLC(g) + k * sigma_read_DN(g)
      sigma_read_DN(g) = sigma_read_e * g / K
  with g = analog gain (linear, e.g. ISO/ISO_base), K = conversion gain (e-/DN),
  sigma_read_e = read noise in electrons (EMVA 1288 dark-frame series), and k a
  Rose-criterion-style detectability factor (start k=5, sweepable).

  Exposure normalization: the LOW_LIGHT decision must live on a SCENE-REFERRED
  light axis so that the same scene shot at different (s*g) yields the SAME
  decision. Above-black signal scales linearly with the exposure product
  r = (s*g)/(s0*g0); so we either scale the signal threshold by r
  (exposure_scaled_tau) or, equivalently, normalize the measured frame back to
  the reference axis (normalize_to_reference) -- an integer subtract+shift in HW.

Sensor characterization (sigma_read_e, K) is an EMVA 1288 flat-field + dark-frame
procedure done ONCE on real hardware. Until a board exists this scaffold takes
them as documented-default parameters (SensorParams), and reads per-frame
ISO/ExposureTime/FNumber best-effort from EXIF (exiftool, graceful null
fallback -- mirrors tools/aodraw_adapter.py:extract_exif).

Usage:
  python3 tools/checker_adaptive_tau.py --selftest          # no dataset needed
  python3 tools/checker_adaptive_tau.py --tau --iso 6400 \\
      --exposure 0.033 --black 800 --white 16380            # one-off tau print
      # 800/16380 = measured SonyNOD (Sony RX100 VII) black/white level,
      # see tools/build_sonynod_dataset.py:11. Override --black/--white for
      # any other sensor (AODRaw etc. -- read per-file via rawpy instead).

KNOWN OPEN ISSUE (found in the SonyNOD real-data validation,
results/checker-adaptive-tau-realdata-2026-07-13.md Sec.3-4): the register
this module produces (tau_for_frame()["register"]) correctly moves with ISO
-- lower ISO gives a lower register per the sigma_read_DN(g) model -- but
analyze_adaptive_tau_sonynod.py compares the resulting dark-ratio against
the FIXED C1 cutoff (dark_ratio > 0.62) borrowed from the non-adaptive
checker. That mismatch (adaptive register, non-adaptive judgement cutoff)
cost recall on all 4 ISO<=1600 frames in the SonyNOD test split. Not a bug
in this module's tau math; it means a deployment of Path A must either
re-derive the judgement cutoff alongside tau(s,g), or compare
tau_for_frame()["register"] directly against an absolute DN threshold
instead of going through a fixed dark-ratio percentage. Unresolved --
next real-data run (AODRaw/PASCALRAW, once downloaded) should test a
cutoff that scales with the adaptive register before trusting low-ISO
recall numbers.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# =====================================================================  model  ==


@dataclass(frozen=True)
class SensorParams:
    """One-time sensor characterization + reference capture setting.

    DEFAULTS ARE PLACEHOLDERS for a generic Sony-class CMOS (LOD/AODRaw are Sony
    .ARW). Replace with EMVA 1288 measurements once a board exists:
      * sigma_read_e : read noise (electrons), from a dark-frame series at each
                       gain (EMVA 1288 s.7); the value here is the base-gain
                       read noise, scaled to gain g inside sigma_read_dn().
      * K            : conversion gain (e-/DN) at base gain, from the
                       photon-transfer curve (EMVA 1288 s.6).
      * iso_base     : ISO at which analog gain g == 1.0.
    Reference (s0,g0) anchors the scene-referred axis; a natural choice is the
    dataset's median (ISO, ExposureTime), set per-campaign.
    """

    sigma_read_e: float = 3.0      # e- RMS read noise at base gain (placeholder)
    K: float = 0.25               # e-/DN conversion gain at base gain (placeholder)
    iso_base: float = 100.0       # ISO giving analog gain 1.0
    iso0: float = 800.0           # reference ISO  -> g0
    exposure0_s: float = 1.0 / 60  # reference exposure time (s) -> s0


def gain_from_iso(iso: float, iso_base: float = 100.0) -> float:
    """Linear analog gain g from ISO. g = ISO / ISO_base (g=1 at base ISO)."""
    return float(iso) / float(iso_base)


def sigma_read_dn(gain: float, sigma_read_e: float, K: float) -> float:
    """Read-noise standard deviation projected into the RAW DN domain at analog
    gain g:  sigma_read_DN(g) = sigma_read_e * g / K   (strategy #1 equation).
    Higher analog gain amplifies the electron-domain read noise into more DN."""
    return sigma_read_e * float(gain) / float(K)


def tau_from_sensor(black_level: float, gain: float, sigma_read_e: float,
                    K: float, k: float = 5.0) -> float:
    """Adaptive dark threshold in the native RAW DN domain (same units as
    rawpy black_level_per_channel / white_level):

        tau(g) = BLC(g) + k * sigma_read_DN(g)

    A pixel below tau has not risen k noise-sigmas above the black floor, i.e.
    it is statistically indistinguishable from "no light" (Rose criterion, k~5).
    This is the EXPOSURE-AGNOSTIC noise floor; combine with exposure_scaled_tau
    / normalize_to_reference for the scene-referred decision. k is sweepable."""
    return float(black_level) + float(k) * sigma_read_dn(gain, sigma_read_e, K)


# ----------------------------------------------------------- exposure axis --
def relative_exposure(s: float, g: float, s0: float, g0: float) -> float:
    """Relative exposure product r = (s*g)/(s0*g0). Above-black scene signal
    scales linearly with r, so r is the factor that maps a measured light axis
    to/from the reference (s0,g0) axis."""
    return (float(s) * float(g)) / (float(s0) * float(g0))


def exposure_scaled_tau(tau_signal: float, black_level: float, r: float) -> float:
    """Scene-referred threshold form. Given a reference above-black signal
    threshold `tau_signal` (e.g. k*sigma_read_DN at the reference gain) and the
    relative exposure r, the operating threshold on the MEASURED frame is:

        tau_meas = BLC + r * tau_signal

    Then `x < tau_meas`  <=>  `(x-BLC)/r < tau_signal`, so the classified-dark
    set is invariant to a pure (s*g) rescale of the same scene (see selftest b)."""
    return float(black_level) + float(r) * float(tau_signal)


def normalize_to_reference(x: float, black_level: float, r: float) -> float:
    """Histogram-shift form (equivalent to exposure_scaled_tau, HW-friendly).
    Maps a MEASURED value back onto the reference light axis:

        x_ref = BLC + (x - BLC) / r

    then compare against a FIXED reference tau. In HW, if r is a power of two
    this is an integer subtract + right/left shift on the histogram bins -- no
    multiply, matching the 1-pass integer streaming contract."""
    return float(black_level) + (float(x) - float(black_level)) / float(r)


# ------------------------------------------------------- register mapping --
def to_register_domain(tau_dn: float, black_level: float, white_level: float,
                       shift8: bool = True) -> int:
    """Map a native-RAW-DN tau to the value the driver writes into the AXI-lite
    `dark_pixel_threshold` register. The checker consumes the "shift8" pseudo-RAW
    scale used by the dataset adapters (aodraw_adapter.to_shift8_bin):
        lin = (dn - black)/(white - black);  u8 = round(lin*255);  reg = u8<<8.
    Returns a uint16-range int (clamped to [0, 65535])."""
    denom = max(float(white_level) - float(black_level), 1.0)
    lin = (float(tau_dn) - float(black_level)) / denom
    lin = min(max(lin, 0.0), 1.0)
    u8 = int(round(lin * 255.0))
    reg = (u8 << 8) if shift8 else u8
    return max(0, min(reg, 0xFFFF))


def tau_for_frame(exif: dict, black_level: float, white_level: float,
                  sp: SensorParams, k: float = 5.0) -> dict:
    """Assemble a per-frame adaptive threshold from an EXIF dict (ISO,
    exposure_s) + per-file black/white (rawpy) + sensor params. Returns both the
    native-DN tau and the register-domain value, plus the relative exposure r.
    Missing ISO/exposure fall back to the reference setting (r=1, g=g_ref)."""
    iso = exif.get("iso") or sp.iso0
    s = exif.get("exposure_s") or sp.exposure0_s
    g = gain_from_iso(iso, sp.iso_base)
    g0 = gain_from_iso(sp.iso0, sp.iso_base)
    r = relative_exposure(s, g, sp.exposure0_s, g0)
    # Noise floor at THIS gain (absolute), then push the scene-referred signal
    # threshold (defined at the reference gain) onto the measured axis via r,
    # and take the stricter (higher) of the two: a pixel must clear BOTH the
    # read-noise floor and the exposure-normalized scene threshold.
    tau_floor = tau_from_sensor(black_level, g, sp.sigma_read_e, sp.K, k)
    tau_sig_ref = k * sigma_read_dn(g0, sp.sigma_read_e, sp.K)
    tau_scene = exposure_scaled_tau(tau_sig_ref, black_level, r)
    tau_dn = max(tau_floor, tau_scene)
    return {
        "iso": iso, "exposure_s": s, "gain": g, "r": r,
        "tau_dn": tau_dn,
        "register": to_register_domain(tau_dn, black_level, white_level),
    }


# ======================================================================  EXIF  ==
def extract_exif(path: Path, exiftool: str | None = None) -> dict:
    """Best-effort ISO / ExposureTime / FNumber for tau(exposure,gain). Tries
    exiftool (-j -n) if given/available; else records nulls. rawpy does NOT
    expose these, so this stays a separate, optional pass. Mirrors
    tools/aodraw_adapter.py:extract_exif -- MUST NOT crash if exiftool absent."""
    out = {"iso": None, "exposure_s": None, "f_number": None}
    tool = exiftool or "exiftool"
    try:
        r = subprocess.run([tool, "-j", "-n", "-ISO", "-ExposureTime",
                            "-FNumber", str(path)], capture_output=True,
                           text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)[0]
            out["iso"] = d.get("ISO")
            out["exposure_s"] = d.get("ExposureTime")
            out["f_number"] = d.get("FNumber")
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError,
            IndexError):
        pass
    return out


# ---------------------------------------------------------------- LOD hook --
# HOOK (once LOD/AODRaw is adapted via tools/aodraw_adapter.py):
#   for row in frames_meta.csv:  e={"iso":row.iso,"exposure_s":row.exposure_s}
#   reg = tau_for_frame(e, row.black_level, row.white_level, SP)["register"]
#   -> write reg into checker `dark_pixel_threshold` (Path A) before rendering
#      that frame, then run checker_stat_sweep.py / eval_map_newrm.py per stratum.


# ==================================================================  selftest  ==
def _dark_count(hist_vals, tau: float) -> int:
    """# pixels strictly below tau (the checker's dark-pixel count kernel)."""
    return int(sum(1 for v in hist_vals if v < tau))


def _selftest() -> int:
    """Exercise every pure-logic path with synthetic sensor metadata. No dataset
    and no exiftool required. Asserts + prints PASS/FAIL per check."""
    ok = True
    sp = SensorParams()

    # (a) tau increases monotonically with analog gain (read-noise floor rises).
    black = 800.0   # measured SonyNOD (RX100 VII) black level, build_sonynod_dataset.py:11
    gains = [1.0, 2.0, 4.0, 8.0, 16.0]
    taus = [tau_from_sensor(black, g, sp.sigma_read_e, sp.K, k=5.0) for g in gains]
    mono = all(t2 > t1 for t1, t2 in zip(taus, taus[1:]))
    assert mono, f"tau not monotone in gain: {taus}"
    assert all(t > black for t in taus), f"tau must exceed BLC: {taus}"
    print(f"[{'ok' if mono else 'FAIL'}] tau monotone in gain: "
          f"g={gains} -> tau={[round(t, 2) for t in taus]}")
    ok = ok and mono

    # (b) exposure normalization: a pure (s*g) rescale of a fixed synthetic scene
    #     must leave the dark-pixel COUNT invariant. Build reference above-black
    #     signals, measure at reference, then at 4x brighter exposure product.
    scene_signal = [0.0, 2.0, 5.0, 8.0, 20.0, 50.0, 120.0, 300.0]  # above-black
    ref_meas = [black + d for d in scene_signal]
    tau_sig = 5.0 * sigma_read_dn(1.0, sp.sigma_read_e, sp.K)   # ref signal thresh
    tau_ref = exposure_scaled_tau(tau_sig, black, r=1.0)
    n_ref = _dark_count(ref_meas, tau_ref)
    r = 4.0                                                      # 4x (s*g)
    scaled_meas = [black + r * d for d in scene_signal]
    # form 1: scale tau by r
    tau_scaled = exposure_scaled_tau(tau_sig, black, r=r)
    n_scaled = _dark_count(scaled_meas, tau_scaled)
    # form 2 (HW): normalize the measured frame back, compare vs the fixed tau_ref
    norm_meas = [normalize_to_reference(x, black, r) for x in scaled_meas]
    n_norm = _dark_count(norm_meas, tau_ref)
    inv = (n_ref == n_scaled == n_norm)
    assert inv, f"exposure-normalized dark count not invariant: {n_ref},{n_scaled},{n_norm}"
    # and confirm a NAIVE fixed threshold would have broken (sanity of the test).
    n_naive = _dark_count(scaled_meas, tau_ref)
    print(f"[{'ok' if inv else 'FAIL'}] exposure-normalized dark count invariant "
          f"under 4x (s*g): ref={n_ref} scaled_tau={n_scaled} hist_norm={n_norm} "
          f"(naive-fixed would give {n_naive})")
    ok = ok and inv

    # (c) k sweep behaves sensibly: tau strictly increases with k, and at k=0
    #     tau collapses to BLC (pure floor).
    ks = [0.0, 3.0, 5.0, 7.0]
    tk = [tau_from_sensor(black, 4.0, sp.sigma_read_e, sp.K, k=kk) for kk in ks]
    kmono = all(b > a for a, b in zip(tk, tk[1:]))
    kzero = abs(tk[0] - black) < 1e-9
    assert kmono and kzero, f"k sweep bad: {tk}"
    print(f"[{'ok' if kmono and kzero else 'FAIL'}] k sweep: k={ks} -> "
          f"tau={[round(t, 2) for t in tk]} (k=0 -> BLC)")
    ok = ok and kmono and kzero

    # (d) EXIF reader returns nulls gracefully when the tool is missing.
    e = extract_exif(Path("/nonexistent.ARW"), exiftool="definitely-not-a-tool")
    grace = e == {"iso": None, "exposure_s": None, "f_number": None}
    assert grace, f"EXIF fallback not graceful: {e}"
    print(f"[{'ok' if grace else 'FAIL'}] extract_exif graceful null fallback (no tool)")
    ok = ok and grace

    # (e) end-to-end tau_for_frame with a synthetic EXIF dict + register mapping.
    frame = tau_for_frame({"iso": 6400, "exposure_s": 1 / 30}, black_level=800,
                          white_level=16380, sp=sp, k=5.0)
    reg_ok = (0 <= frame["register"] <= 0xFFFF) and (frame["tau_dn"] > 800)
    assert reg_ok, f"tau_for_frame bad: {frame}"
    print(f"[{'ok' if reg_ok else 'FAIL'}] tau_for_frame ISO6400: "
          f"tau_dn={frame['tau_dn']:.2f} r={frame['r']:.3f} "
          f"register(shift8)={frame['register']}")
    ok = ok and reg_ok

    print("\nselftest: ALL PASS" if ok else "\nselftest: FAIL")
    return 0 if ok else 1


# ======================================================================  main  ==
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="run pure-logic self-tests (no dataset/exiftool needed)")
    ap.add_argument("--tau", action="store_true",
                    help="print tau for a single (iso,exposure,black,white)")
    ap.add_argument("--iso", type=float, default=None)
    ap.add_argument("--exposure", type=float, default=None, help="seconds")
    ap.add_argument("--black", type=float, default=800.0,
                    help="black level; default = measured SonyNOD (RX100 VII) value")
    ap.add_argument("--white", type=float, default=16380.0,
                    help="white level; default = measured SonyNOD (RX100 VII) value")
    ap.add_argument("--k", type=float, default=5.0)
    ap.add_argument("--raw", type=Path, default=None,
                    help="RAW file to read EXIF from (best-effort)")
    ap.add_argument("--exiftool", default=None, help="path to exiftool binary")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if args.tau:
        sp = SensorParams()
        exif = {"iso": args.iso, "exposure_s": args.exposure, "f_number": None}
        if args.raw is not None:
            exif = extract_exif(args.raw, args.exiftool)
        frame = tau_for_frame(exif, args.black, args.white, sp, k=args.k)
        print(json.dumps(frame, indent=2))
        return 0

    ap.error("use --selftest or --tau (with --iso/--exposure or --raw)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
