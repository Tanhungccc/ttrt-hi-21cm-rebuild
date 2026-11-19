# -*- coding: utf-8 -*-
"""Nạp phổ HI từ file — PHẦN MỚI trong bản hiệu chỉnh.

Hỗ trợ:
1. FITS của kính SALSA (Onsala): trục tần số WCS, BUNIT='K', toạ độ GLON/GLAT
   trong header, hiệu chỉnh LSR lưu ở VELO-LSR → v_LSR = v_radio − VELO-LSR
   (dấu đã kiểm định thống kê trên 75 phổ mặt phẳng TH: đỉnh khí cục bộ hội tụ
   về v≈0 với 81% trong ±15 km/s — quy ước '+' chỉ đạt 27%).
2. CSV của app này lưu ra: freq_MHz, v_LSR_kms, intensity.
3. CSV/text xuất từ SALSA: `frequency_hz,amplitude,vlsr_mps` + `# Target: l, b`.
4. CSV 2 cột (v_kms, intensity) hoặc (freq_MHz, intensity) — tự nhận biết.

Mọi phổ trả về trục v_LSR; cờ `lsr_applied` cho biết đã hiệu chỉnh LSR chưa
(để app không cộng thêm lần nữa — tránh lỗi double-correction).
"""
from dataclasses import dataclass

import numpy as np

from .constants import C_KMS, HI_FREQ_MHZ

RESTFREQ_HZ = 1420405751.77


@dataclass
class LoadedSpectrum:
    v_lsr: np.ndarray          # km/s
    intensity: np.ndarray      # K hoặc a.u.
    freq_mhz: np.ndarray | None = None
    l: float | None = None
    b: float | None = None
    unit: str = "a.u."
    lsr_applied: bool = True
    source: str = ""
    # provenance: vị trí + thời điểm QUAN SÁT (để hiệu chỉnh theo nơi sinh ra
    # phép đo, không theo nơi ngồi phân tích)
    lat: float | None = None
    lon: float | None = None
    obstime: str | None = None   # ISO UTC
    site_name: str = ""


# đài quan sát đã biết → toạ độ (khi header không có LAT/LON)
KNOWN_SITES = {
    "SALSA": (57.40, 12.23, "Onsala, Sweden"),
    "ONSALA": (57.40, 12.23, "Onsala, Sweden"),
}


def _freq_to_vradio(freq_mhz):
    return C_KMS * (HI_FREQ_MHZ - np.asarray(freq_mhz)) / HI_FREQ_MHZ


def load_fits(path: str) -> LoadedSpectrum:
    from astropy.io import fits
    h = fits.getheader(path)
    d = fits.getdata(path).astype(float).ravel()
    n = len(d)
    i = np.arange(1, n + 1)
    if "CRVAL1" in h:
        freq_hz = h["CRVAL1"] + (i - h.get("CRPIX1", 1)) * h["CDELT1"]
    else:
        raise ValueError("FITS không có trục tần số (CRVAL1)")
    freq_mhz = freq_hz / 1e6
    v_radio = C_KMS * (HI_FREQ_MHZ - freq_mhz) / HI_FREQ_MHZ

    # --- provenance: vị trí + thời điểm quan sát ---
    obstime = h.get("DATE-OBS") or h.get("DATE") or None
    lat = h.get("OBSGEO-B", h.get("LATITUDE", h.get("SITELAT", None)))
    lon = h.get("OBSGEO-L", h.get("LONGITUDE", h.get("SITELON", None)))
    site_name = str(h.get("TELESCOP", "")).strip() or str(h.get("ORIGIN", "")).strip()
    if lat is None:
        for key, (klat, klon, kname) in KNOWN_SITES.items():
            if key in site_name.upper() or key in path.upper():
                lat, lon, site_name = klat, klon, kname
                break

    if "VELO-LSR" in h:
        vlsr_corr = float(h["VELO-LSR"])
        return LoadedSpectrum(
            v_lsr=v_radio - vlsr_corr, intensity=d, freq_mhz=freq_mhz,
            l=float(h["CRVAL2"]) if "CRVAL2" in h else None,
            b=float(h["CRVAL3"]) if "CRVAL3" in h else None,
            unit=str(h.get("BUNIT", "a.u.")).strip(), lsr_applied=True,
            source=f"{path} (FITS, VELO-LSR={vlsr_corr:+.2f} km/s tại {site_name or 'không rõ'})",
            lat=lat, lon=lon, obstime=obstime, site_name=site_name)
    # không có VELO-LSR → để app tự hiệu chỉnh theo vị trí/thời điểm quan sát
    return LoadedSpectrum(
        v_lsr=v_radio, intensity=d, freq_mhz=freq_mhz,
        l=float(h["CRVAL2"]) if "CRVAL2" in h else None,
        b=float(h["CRVAL3"]) if "CRVAL3" in h else None,
        unit=str(h.get("BUNIT", "a.u.")).strip(), lsr_applied=False,
        source=f"{path} (FITS, chưa LSR — cần hiệu chỉnh theo vị trí quan sát)",
        lat=lat, lon=lon, obstime=obstime, site_name=site_name)


def load_csv(path: str) -> LoadedSpectrum:
    l = b = None
    lat = lon = obstime = None
    site_name = ""
    v_col = f_col = y_col = None
    header_cols = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    data_start = 0
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            low = body.lower()
            # provenance dạng "key = value" (app này tự ghi khi lưu)
            if "=" in body and ":" not in body.split("=", 1)[0]:
                key, val = [t.strip() for t in body.split("=", 1)]
                kl = key.lower()
                try:
                    if kl == "site_lat":
                        lat = float(val)
                    elif kl == "site_lon":
                        lon = float(val)
                    elif kl == "obstime":
                        obstime = val
                    elif kl in ("site", "site_name", "observatory"):
                        site_name = val
                    elif kl == "l":
                        l = float(val)
                    elif kl == "b":
                        b = float(val)
                except ValueError:
                    pass
            # metadata kiểu SALSA: "# Target: 90.0000, 0.0000 deg"
            elif "target" in low and "," in body:
                try:
                    nums = body.split(":", 1)[1].replace("deg", "").split(",")
                    l, b = float(nums[0]), float(nums[1])
                except Exception:
                    pass
            continue
        parts = [p.strip() for p in s.replace(";", ",").split(",")]
        try:
            [float(p) for p in parts if p]
            data_start = idx
            break
        except ValueError:
            header_cols = [p.lower() for p in parts]
            data_start = idx + 1
    arr = np.genfromtxt(lines[data_start:], delimiter=",", comments="#")
    if arr.ndim != 2:
        arr = np.genfromtxt(lines[data_start:], comments="#")

    if header_cols:
        def find(*keys):
            for k in keys:
                for j, c in enumerate(header_cols):
                    if k in c.replace(" ", ""):
                        return j
            return None
        f_col = find("freq")
        v_col = find("v_lsr", "vlsr", "velocity", "_v_", "km")
        y_col = find("intensity", "amplitude", "amp", "power", "t_a", "temp")
        if y_col is None:
            y_col = arr.shape[1] - 1
    else:
        # không header: 2 cột → tự đoán (freq ~1400-1440 | v ~ -600..600)
        if arr.shape[1] >= 2:
            col0 = arr[:, 0]
            if 1300 < np.nanmedian(col0) < 1500:
                f_col, y_col = 0, 1
            else:
                v_col, y_col = 0, 1

    y = arr[:, y_col]
    if f_col is not None:
        freq_mhz = arr[:, f_col]
        if np.nanmedian(freq_mhz) > 1e6:      # Hz → MHz
            freq_mhz = freq_mhz / 1e6
        v = _freq_to_vradio(freq_mhz)         # chưa LSR (cộng thêm ở app)
        lsr_applied = False
    else:
        v = arr[:, v_col]
        if np.nanmax(np.abs(v)) > 1000:       # m/s → km/s (SALSA export)
            v = v / 1000.0
        freq_mhz = None
        lsr_applied = True
    return LoadedSpectrum(v_lsr=v, intensity=y, freq_mhz=freq_mhz, l=l, b=b,
                          unit="a.u.", lsr_applied=lsr_applied, source=path,
                          lat=lat, lon=lon, obstime=obstime, site_name=site_name)


def load_spectrum(path: str) -> LoadedSpectrum:
    low = path.lower()
    if low.endswith((".fits", ".fit", ".fts")):
        return load_fits(path)
    return load_csv(path)
