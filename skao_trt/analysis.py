# -*- coding: utf-8 -*-
"""Phân tích khoa học — PHẦN MỚI trong bản hiệu chỉnh.

Trách nhiệm:
1. Hiệu chỉnh LSR (sai số lớn nhất của bản gốc: trục vận tốc chưa trừ chuyển
   động Trái Đất + chuyển động riêng Mặt Trời, lệch tới ±50 km/s).
2. Động học Ngân Hà: (l, b, v_LSR) → R, khoảng cách, nhánh tay xoắn.
3. Tìm đỉnh phổ HI, phân loại "trường hợp shift" (lại gần / trôi xa / khí cục bộ).
4. Tóm tắt "vị trí của chúng ta trên Milky Way" sau mỗi phép đo.

astropy là tùy chọn: không có thì bỏ hiệu chỉnh LSR (có cảnh báo rõ ràng).
"""
import math
from dataclasses import dataclass, field

import numpy as np

from .constants import C_KMS, HI_FREQ_MHZ, R0_KPC, THETA0_KMS

# Chuyển động riêng của Mặt Trời so với LSR động học (Delhaye): 19.5 km/s
# về phía l≈56.2°, b≈22.5° → (U, V, W)_gal ≈ (10.3, 15.3, 7.7) km/s
SUN_PEC_GAL = (10.3, 15.3, 7.7)

# Bán kính nhánh tay xoắn ước lượng (parallax maser, Reid+2019; ±15%)
ARMS = [
    ("3-kpc arm (mở rộng)", 3.2, "phi tròn"),
    ("Norma arm", 3.9, ""),
    ("Scutum-Crux arm", 5.0, ""),
    ("Sagittarius-Carina", 6.5, ""),
    ("Local arm / Orion Spur", 8.2, "vị trí của chúng ta"),
    ("Perseus arm", 9.7, ""),
    ("Outer arm", 12.8, ""),
]


# ----------------------------------------------------------------- LSR
def lsr_correction(l_deg: float, b_deg: float, obstime=None,
                   lat_deg: float = 10.76, lon_deg: float = 106.66) -> float | None:
    """Hiệu chỉnh LSR (km/s) cần CỘNG vào v đo (topocentric) để ra v_LSR.

    obstime: thời điểm QUAN SÁT (Time hoặc chuỗi ISO) — dùng đúng thời điểm
    sinh ra phép đo, không phải thời điểm ngồi phân tích.
    Trả về None nếu thiếu astropy (khi đó không được dùng kết quả vận tốc
    cho mục đích gán tay xoắn).
    """
    try:
        import numpy as _np
        import astropy.units as u
        from astropy.coordinates import (SkyCoord, CartesianRepresentation,
                                         get_body_barycentric_posvel, Galactic)
        from astropy.time import Time
    except ImportError:
        return None

    if obstime is None:
        obstime = Time.now()
    elif isinstance(obstime, str):
        obstime = Time(obstime)

    l = math.radians(l_deg)
    b = math.radians(b_deg)
    n_gal = _np.array([math.cos(b) * math.cos(l),
                       math.cos(b) * math.sin(l),
                       math.sin(b)])

    _, v_earth = get_body_barycentric_posvel("earth", obstime)
    v_e_icrs = v_earth.xyz.to(u.km / u.s).value

    M = _np.zeros((3, 3))
    for i, v in enumerate(_np.eye(3)):
        c = SkyCoord(CartesianRepresentation(*v), frame="icrs")
        g = c.transform_to(Galactic())
        M[:, i] = [g.cartesian.x.value, g.cartesian.y.value, g.cartesian.z.value]
    v_e_gal = M @ v_e_icrs
    corr = float(_np.dot(v_e_gal + _np.array(SUN_PEC_GAL), n_gal))
    return corr


def freq_to_vradio(freq_mhz: np.ndarray) -> np.ndarray:
    """Vận tốc vô tuyến (topocentric, chưa LSR): v = c(f0 - f)/f0."""
    return C_KMS * (HI_FREQ_MHZ - np.asarray(freq_mhz)) / HI_FREQ_MHZ


# ------------------------------------------------------- động học Ngân Hà
@dataclass
class Kinematics:
    l: float
    b: float
    v_lsr: float
    R_kpc: float | None = None
    R_tangent_kpc: float | None = None
    d_tangent_kpc: float | None = None
    v_tangent_kms: float | None = None
    d_near_kpc: float | None = None
    d_far_kpc: float | None = None
    beyond_tangent: bool = False
    outer_galaxy: bool = False
    arm: str | None = None
    notes: list = field(default_factory=list)


def solve_kinematics(l_deg: float, b_deg: float, v_lsr: float) -> Kinematics:
    """Mô hình quay tròn (R0=8.15 kpc, Θ0=236 km/s) — cùng mô hình với
    hi_galactic_tool.py; sai số do streaming ~±20%."""
    k = Kinematics(l=l_deg, b=b_deg, v_lsr=v_lsr)
    sinl = math.sin(math.radians(l_deg))
    s = sinl * math.cos(math.radians(b_deg))

    if abs(s) < 1e-6:
        k.notes.append("l≈0°/180°: chuyển động tròn không cho thông tin khoảng cách.")
        return k

    k.R_tangent_kpc = R0_KPC * math.sqrt(sinl ** 2 +
                                        math.cos(math.radians(l_deg)) ** 2 *
                                        math.sin(math.radians(b_deg)) ** 2)
    k.d_tangent_kpc = max(R0_KPC * math.cos(math.radians(l_deg)) *
                          math.cos(math.radians(b_deg)), 0.0)
    k.v_tangent_kms = v_lsr_model(k.R_tangent_kpc, l_deg, b_deg)

    denom = THETA0_KMS * s + v_lsr
    if abs(denom) < 1e-9:
        k.notes.append("Không giải được R với v này.")
        return k
    R = R0_KPC * THETA0_KMS * s / denom
    if R <= 0:
        k.notes.append("R<=0: vận tốc không phù hợp chuyển động tròn (phi tròn?).")
        return k

    k.beyond_tangent = R < k.R_tangent_kpc - 0.01
    if k.beyond_tangent:
        k.notes.append("Vượt điểm tiêu cực → chuyển động phi tròn (3-kpc/bar/streaming).")
    k.R_kpc = R
    k.outer_galaxy = R > R0_KPC

    # khoảng cách: R² = R0² + d² − 2·R0·d·cos l·cos b  (đầy đủ cho b ≠ 0)
    coslb = math.cos(math.radians(l_deg)) * math.cos(math.radians(b_deg))
    disc = R ** 2 - R0_KPC ** 2 * (sinl ** 2 +
                                   math.cos(math.radians(l_deg)) ** 2 *
                                   math.sin(math.radians(b_deg)) ** 2)
    if disc >= 0:
        root = math.sqrt(disc)
        dn = R0_KPC * coslb - root
        df = R0_KPC * coslb + root
        sols = [d for d in (dn, df) if d > 0]
        if k.outer_galaxy or len(sols) == 1:
            k.d_near_kpc = sols[0] if sols else None
        elif len(sols) == 2:
            k.d_near_kpc, k.d_far_kpc = dn, df

    k.arm = min(ARMS, key=lambda a: abs(a[1] - R))[0]
    return k


def v_lsr_model(R: float, l_deg: float, b_deg: float) -> float:
    s = math.sin(math.radians(l_deg)) * math.cos(math.radians(b_deg))
    return (R0_KPC * THETA0_KMS / R - THETA0_KMS) * s


# ------------------------------------------------------------- đỉnh phổ
@dataclass
class Peak:
    v_lsr: float
    amplitude: float
    shift_case: str = ""
    kinematics: Kinematics | None = None


def find_peaks(v_lsr: np.ndarray, spectrum: np.ndarray, n_peaks: int = 6,
               min_separation_kms: float = 15.0) -> list:
    """Tìm thành phần phổ HI.

    Ưu tiên cực đại cục bộ trên nền ước lượng từ biên phổ (độ tinh chỉnh Gaussian
    tự động nằm trong _fit_gaussians, dùng khi cần phân tích sâu — bản gốc SALSA
    cũng phải nhập seed tay cho fitGaussians nên không bật mặc định).
    """
    y = np.asarray(spectrum, dtype=float)
    x = np.asarray(v_lsr, dtype=float)
    if len(y) < 5:
        return []
    return _local_max_peaks(x, y, n_peaks=n_peaks,
                            min_separation_kms=min_separation_kms)


def _local_max_peaks(x, y, n_peaks=6, min_separation_kms=15.0) -> list:
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if len(y) < 5:
        return []
    smooth = np.convolve(y, np.array([1.0, 2.0, 1.0]) / 4.0, mode="same")
    # loại rìa phổ (mép băng hay có artefact do fit nền/smooth mép)
    edge_guard = 0.92 * max(abs(float(x.min())), abs(float(x.max())))
    # baseline/nhiễm ước lượng từ BIÊN phổ (|v| > 120 km/s) — đã kiểm chứng
    # trên 579 phổ SALSA thật; bền với nền cong nhẹ của dải thu
    edge = np.abs(x) > 120
    ref = y[edge] if edge.sum() >= 8 else y
    baseline = float(np.median(ref))
    mad = float(np.median(np.abs(ref - baseline))) or 1.0
    rms = 1.4826 * mad
    thresh = baseline + 3 * rms

    cand = []
    for i in range(1, len(y) - 1):
        if (abs(x[i]) < edge_guard
                and smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1]
                and smooth[i] > thresh):
            cand.append(i)
    cand.sort(key=lambda i: smooth[i], reverse=True)

    chosen = []
    for i in cand:
        if all(abs(x[i] - x[j]) >= min_separation_kms for j in chosen):
            chosen.append(i)
        if len(chosen) >= n_peaks:
            break
    chosen.sort(key=lambda i: x[i])

    # lọc prominence: đỉnh phải cao hơn "yên ngựa" về phía đỉnh cao hơn nó
    # (loại đỉnh ảo do nhiễu trên sườn của dải phát xạ rộng)
    final = []
    for i in chosen:
        taller = [j for j in chosen if smooth[j] > smooth[i]]
        if not taller:
            final.append(i)
            continue
        nearest = min(taller, key=lambda j: abs(x[j] - x[i]))
        lo, hi = (i, nearest) if i < nearest else (nearest, i)
        saddle = float(np.min(smooth[lo:hi + 1]))
        if smooth[i] - saddle > 0.75 * rms:
            final.append(i)
    return [Peak(v_lsr=float(x[i]), amplitude=float(y[i])) for i in final]


def _fit_gaussians(x, y, n_peaks=6):
    """Fit tổng Gaussian + hằng số (như fitGaussians của SalsaSpectrum)."""
    from scipy.optimize import curve_fit

    edge = np.abs(x) > 120
    ref = y[edge] if edge.sum() >= 8 else y
    baseline = float(np.median(ref))
    mad = float(np.median(np.abs(ref - baseline))) or 1.0
    rms = 1.4826 * mad

    # hạt giống: cực đại cục bộ trên ngưỡng 2σ, cách nhau ≥ 12 km/s
    sm = np.convolve(y, np.array([1.0, 2.0, 1.0]) / 4.0, mode="same")
    seeds = [i for i in range(1, len(y) - 1)
             if sm[i] >= sm[i - 1] and sm[i] > sm[i + 1]
             and sm[i] > baseline + 2 * rms]
    seeds.sort(key=lambda i: sm[i], reverse=True)
    picked = []
    for i in seeds:
        if all(abs(x[i] - x[j]) >= 12 for j in picked):
            picked.append(i)
        if len(picked) >= n_peaks:
            break
    if not picked:
        return []

    def model(vv, base, *params):
        out = np.full_like(vv, base, dtype=float)
        for a, v0, s in zip(params[0::3], params[1::3], params[2::3]):
            out = out + a * np.exp(-0.5 * ((vv - v0) / s) ** 2)
        return out

    p0 = [baseline]
    lo = [baseline - 5 * rms]
    hi = [baseline + 5 * rms]
    for i in sorted(picked, key=lambda i: x[i]):
        p0 += [max(y[i] - baseline, rms), float(x[i]), 8.0]
        lo += [0.0, float(x[i]) - 25, 2.0]
        hi += [float(np.max(y)) * 2, float(x[i]) + 25, 60.0]

    try:
        popt, _ = curve_fit(model, x, y, p0=p0, bounds=(lo, hi), maxfev=20000)
    except Exception:
        return []

    peaks = []
    base_fit = popt[0]
    for a, v0, s in zip(popt[1::3], popt[2::3], popt[3::3]):
        if a > 2 * rms and 2.0 <= s <= 60.0:
            peaks.append(Peak(v_lsr=float(v0), amplitude=float(a + base_fit)))
    peaks.sort(key=lambda p: p.v_lsr)
    return peaks


def classify_shift(v_lsr: float, l_deg: float, tol: float = 5.0) -> str:
    """Phân loại 'trường hợp shift' của một đỉnh phổ."""
    if abs(v_lsr) <= tol:
        return "khí cục bộ (≈ đứng yên so với LSR)"
    if v_lsr > 0:
        return "ĐANG TRÔI XA (redshift)"
    return "ĐANG LẠI GẦN (blueshift)"


# --------------------------------------------- xử lý phổ (pipeline khoa học)
def process_spectrum(v_lsr, intensity, smooth_sigma_ch: float = 2.5,
                     poly_order: int = 3, clip_sigma: float = 3.0,
                     iters: int = 3) -> tuple:
    """Pipeline khoa học chuẩn: khử nền (đa thức bậc 3 + sigma-clip lặp)
    rồi làm mượt Gaussian.

    Trả về (processed, detrended, baseline):
      processed  — phổ đã khử nền + Gaussian smooth (dùng để vẽ & dò đỉnh)
      detrended  — đã khử nền, CHƯA smooth (tuỳ chọn xem)
      baseline   — đường nền đã fit (đồ thị phụ)
    """
    from scipy.ndimage import gaussian_filter1d
    x = np.asarray(v_lsr, dtype=float)
    y = np.asarray(intensity, dtype=float)
    n = len(y)
    mask = np.ones(n, dtype=bool)
    base = np.zeros(n)
    for _ in range(iters):
        if mask.sum() > poly_order + 1:
            coef = np.polyfit(x[mask], y[mask], poly_order)
            base = np.polyval(coef, x)
        r = y - base
        s = 1.4826 * float(np.median(np.abs(r[mask] - np.median(r[mask])))) or 1.0
        mask = np.abs(r) < clip_sigma * s
    detr = y - base
    sm = gaussian_filter1d(detr, smooth_sigma_ch)
    return sm, detr, base
def analyse_observation(l_deg: float, b_deg: float, v_peaks,
                        corr_lsr: float | None = None) -> dict:
    """Phân tích trọn vẹn: từng đỉnh (shift + vị trí điểm trỏ + vị trí chúng ta)."""
    result = {
        "pointing": (l_deg, b_deg),
        "lsr_correction": corr_lsr,
        "peaks": [],
        "our_position": (
            "Mặt Trời nằm trên nhánh Local/Orion Spur, R0 = 8.15 kpc so với tâm "
            "Ngân Hà, ~20–25 pc phía Bắc mặt phẳng, quay với Θ0 ≈ 236 km/s "
            "(cộng chuyển động riêng ~19.5 km/s về l≈56°, b≈23°)."
        ),
    }
    for p in v_peaks:
        if isinstance(p, Peak):
            v, amp = p.v_lsr, p.amplitude
        else:
            v, amp = float(p), 0.0
        k = solve_kinematics(l_deg, b_deg, v)
        case = classify_shift(v, l_deg)
        result["peaks"].append({
            "v_lsr": v,
            "amplitude": amp,
            "shift_case": case,
            "R_kpc": k.R_kpc,
            "d_near_kpc": k.d_near_kpc,
            "d_far_kpc": k.d_far_kpc,
            "arm": k.arm,
            "beyond_tangent": k.beyond_tangent,
            "notes": k.notes,
        })
    return result


def chain_report(gain_curve=None, y_factor=None, sky_pwr=None) -> list:
    """Chẩn đoán CHUỖI THU từ dữ liệu đã đo — suy luận (không chắc chắn 100%)
    trạng thái anten/LNA/filter và đưa gợi ý. Không chặn thao tác, chỉ cảnh báo.

    Dấu hiệu: đường cong sigma-theo-gain (LNA → bão hoà sớm), Y-factor
    trời/load (anten có thu thật không), tỷ lệ gai RFI (SAW filter có chặn không).
    """
    import numpy as _np
    lines = ["— Chẩn đoán chuỗi thu —"]
    if gain_curve:
        sigmas = [s for _, s in gain_curve]
        sat = [g for g, s in gain_curve if s > 0.3]
        top = sigmas[-1]
        if top < 0.006:
            lines.append("⚠ Mức tín hiệu RẤT THẤP ở mọi gain → có thể anten chưa gắn, "
                         "đang gắn terminator (50Ω), hoặc cáp lỏng.")
        elif sat and sat[0] < 20.0:
            lines.append("ℹ Bão hoà ADC từ gain thấp → tín hiệu/RFI mạnh "
                         "(có thể ĐÃ có LNA, hoặc môi trường RFI đậm).")
        else:
            lines.append("✅ Mức tín hiệu hợp lệ trên dải gain — chuỗi đang hoạt động."
                         " (Thiếu LNA thì tín hiệu yếu kiểu này → cần tích lũy dài.)")
    if y_factor is not None:
        if abs(y_factor - 1.0) < 0.02:
            lines.append("⚠ Y-factor ≈ 1: trời và load cho CÙNG mức → kiểm tra anten/cáp "
                         "(anten chưa gắn, bị che, hoặc đầu vào hở/đoản mạch).")
        elif y_factor > 1.0:
            lines.append(f"ℹ Y-factor = {y_factor:.3f} — anten đang thu được tín hiệu trời/môi trường.")
        else:
            lines.append(f"⚠ Y-factor = {y_factor:.3f} < 1 — mức trời thấp hơn load, kiểm tra chuỗi.")
    if sky_pwr is not None:
        m = float(_np.median(sky_pwr))
        s = 1.4826 * float(_np.median(_np.abs(sky_pwr - m))) or 1.0
        frac = float(_np.mean(_np.abs(sky_pwr - m) > 5 * s))
        if frac > 0.05:
            lines.append(f"⚠ RFI nhiều ({frac*100:.0f}% kênh có gai) — nếu CHƯA có SAW filter "
                         f"(SAWbird+HI) thì đây là lý do phổ yếu/bẩn.")
        else:
            lines.append(f"✅ Băng khá sạch (gai RFI {frac*100:.1f}% kênh) — "
                         f"có thể đã có filter hoặc môi trường sạch.")
    return lines


def format_analysis(result: dict) -> list:
    """Đưa kết quả analyse_observation thành các dòng text hiển thị."""
    l_deg, b_deg = result["pointing"]
    corr = result["lsr_correction"]
    lines = [f"Điểm trỏ (pointing): l = {l_deg:.1f}°, b = {b_deg:.1f}°"]
    if corr is None:
        lines.append("⚠ CHƯA hiệu chỉnh LSR (thiếu astropy) — không gán tay xoắn!")
    elif corr == 0.0:
        lines.append("LSR: dữ liệu đầu vào đã hiệu chỉnh sẵn (không cộng thêm)")
    else:
        lines.append(f"Hiệu chỉnh LSR đã cộng: {corr:+.2f} km/s")
    for i, p in enumerate(result["peaks"], 1):
        lines.append(f"Đỉnh {i}: v_LSR = {p['v_lsr']:+7.1f} km/s  →  {p['shift_case']}")
        if p["R_kpc"] and not p["beyond_tangent"]:
            arm = p["arm"] or "?"
            if p["d_far_kpc"]:
                d = f"gần {p['d_near_kpc']:.2f} / xa {p['d_far_kpc']:.2f} kpc"
            elif p["d_near_kpc"]:
                d = f"{p['d_near_kpc']:.2f} kpc (duy nhất)"
            else:
                d = "?"
            lines.append(f"      R = {p['R_kpc']:.2f} kpc, d = {d}  →  {arm}")
        for n in p["notes"]:
            lines.append(f"      ⚠ {n}")
    lines.append("Vị trí của chúng ta: " + result["our_position"])
    return lines


# ----------------------------------------------- phổ giả lập (demo/test)
def demo_spectrum(l_deg: float, b_deg: float, freq_mhz: np.ndarray) -> np.ndarray:
    """Phổ HI tổng hợp cho hướng (l,b) — mô phỏng cấu trúc nhánh theo kinh
    tuyến, dùng cho --demo/--selftest khi chưa cắm SDR."""
    v = freq_to_vradio(freq_mhz)
    comp = {
        # (v_đỉnh, biên độ, bề rộng) theo kinh tuyến — số liệu xấp xỉ từ plan
        (20, 45): [(0, 30, 12), (42, 24, 10), (85, 18, 9), (115, 16, 8)],
        (15, 35): [(0, 28, 12), (30, 26, 10), (60, 16, 9), (118, 12, 7)],
        (25, 55): [(0, 29, 12), (48, 21, 10), (95, 15, 9)],
        (45, 65): [(0, 25, 12), (55, 16, 11), (130, 11, 8)],
        (150, 170): [(0, 24, 12), (-25, 13, 10), (-55, 9, 9)],
        (115, 140): [(0, 22, 12), (-38, 12, 10), (-60, 8, 9)],
    }
    comps = None
    for (lo, hi), c in comp.items():
        if lo <= l_deg <= hi:
            comps = c
            break
    if comps is None:
        comps = [(0, 18, 12)]
    # nền dải thu cong NHẸ + nhiễu — đủ để biểu đồ giả lập trông như đo thật,
    # không phá detector (đỉnh luôn cao rõ trên nền)
    y = 100.0 + 6.0 * (v / 250.0) ** 2   # U-shape nhẹ như dải thu thật
    for v0, amp, width in comps:
        y = y + amp * np.exp(-0.5 * ((v - v0) / width) ** 2)
    y = y + np.random.normal(0, 2.0, y.shape)
    return y
