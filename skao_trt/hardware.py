# -*- coding: utf-8 -*-
"""Mô hình phần cứng + tự dò SDR + tự fallback cho chuỗi thu HI 21 cm (RTP-3.7).

Đồng bộ cơ chế với `pulsar observation/code/psr_hw.py`:
1. `probe_sdr()` — dò SDR đang cắm thật (RTL-SDR / SoapySDR / PlutoSDR) không ném lỗi.
2. `PARTS` & `detect_chain()` — chọn chuỗi LNA / BPF / SDR / Clock theo thứ tự ưu tiên,
   tự fallback khi thiếu linh kiện và tính T_sys, SEFD, biên độ ADC + cảnh báo.
3. `poam_profile_summary()` — tóm tắt hồ sơ thiết bị thực tế tại trạm POAM RTP-3.7.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

K_B = 1.380649e-23
JY = 1e-26
T_CMB = 2.725
T_SKY_1420 = 3.0
T_GROUND = 25.0


PARTS: dict[str, dict] = {
    # ---- LNA / front-end ----
    "sawbird_hi": dict(
        kind="lna", name="Nooelec SAWbird+HI (LNA+SAW)",
        nf_db=0.6, gain_db=30.0, lo_mhz=1380, hi_mhz=1460,
        ip3_dbm=-10, bias=True,
        note="SAW 1420 MHz, tối ưu cho HI 21 cm",
    ),
    "spf5189z": dict(
        kind="lna", name="SPF5189Z (LNA rời)",
        nf_db=0.6, gain_db=20.0, lo_mhz=50, hi_mhz=2000,
        ip3_dbm=-5, bias=True,
        note="LNA băng rộng; cần thêm lọc khi RFI mạnh",
    ),
    "zkl33uln": dict(
        kind="lna", name="Mini-Circuits ZKL-33ULN-S+",
        nf_db=1.5, gain_db=18.0, lo_mhz=30, hi_mhz=1000,
        ip3_dbm=0, bias=True,
        note="Dải tới 1000 MHz — ngoài băng 1420 MHz",
    ),
    "rtl_internal": dict(
        kind="lna", name="LNA nội RTL-SDR (dự phòng cuối)",
        nf_db=8.0, gain_db=44.0, lo_mhz=24, hi_mhz=1766,
        ip3_dbm=-15, bias=False,
        note="NF ~8 dB → T_rec ~1500 K: CHỈ dùng khi thiếu/hỏng LNA ngoài",
    ),

    # ---- Bộ lọc ----
    "saw_1420": dict(
        kind="bpf", name="SAW 1420 MHz (tích hợp SAWbird)",
        nf_db=0.5, lo_mhz=1400, hi_mhz=1440,
        note="Chặn RFI ngoài băng ~25 MHz — phù hợp cho HI 21 cm",
    ),
    "bpf_1300_1500": dict(
        kind="bpf", name="BPF 1300-1500 MHz",
        nf_db=1.5, lo_mhz=1300, hi_mhz=1500,
        note="Bộ lọc L-band dự phòng",
    ),

    # ---- SDR ----
    "rtlsdr_v5": dict(
        kind="sdr", name="RTL-SDR v5 (TCXO ±0.5 ppm)",
        bw_mhz=2.4, max_rate_msps=3.2, bits=8, reliable_rate=2.4,
        ppm=0.5, gain_db=0.0,
        note="Đủ cho vạch HI 21 cm (±250 km/s)",
    ),
    "soapy": dict(
        kind="sdr", name="SoapySDR (chung)",
        bw_mhz=10.0, max_rate_msps=10.0, bits=12, reliable_rate=8.0,
        ppm=0.5, gain_db=0.0,
        note="Backend SoapySDR (chưa nối trực tiếp luồng IQ trong SKAO-TRT)",
    ),
    "pluto": dict(
        kind="sdr", name="ADALM-Pluto (libiio)",
        bw_mhz=20.0, max_rate_msps=20.0, bits=12, reliable_rate=16.0,
        ppm=0.5, gain_db=0.0,
        note="Backend PlutoSDR (chưa nối trực tiếp luồng IQ trong SKAO-TRT)",
    ),

    # ---- Thiết bị thực tế POAM RTP-3.7 tại trạm ----
    "poam_receiver": dict(
        kind="receiver",
        name="POAM Radio Telescope Receiver (100 MHz–6 GHz, USB3 + LAN)",
        lo_mhz=100.0, hi_mhz=6000.0, bw_mhz=50.0,
        max_rate_msps=15.0, reliable_rate=10.0, bits=16, nchan_rx=8,
        gain_min_db=0.0, gain_max_db=70.0,
        iq_stream=False,
        lband_feed_confirmed=False,
        exports=("line.csv", "continuum.txt", "scan.txt"),
        note="Xuất phổ qua RTCS; CHƯA có API luồng IQ trực tiếp cho app ngoài.",
    ),
    "poam_ncu": dict(
        kind="calibrator",
        name="POAM Noise Calibrator Unit (NCU)",
        ip="192.168.1.100", eca_m2=6.40, enr_db=30.0,
        sequence_s=dict(noise=20, load=20, sun=240, cycle=280),
        note="Hiệu chuẩn qua tab RTCS Calibrator; chưa đo xác minh thực địa.",
    ),
    "poam_acu": dict(
        kind="acu",
        name="POAM Antenna Control Unit V1.5c03 (AZ/EL/POL, Modbus TCP)",
        ip="192.168.1.10", port=502,
        travel_deg=dict(az=(0.0, 360.0), el=(0.0, 90.0)),
        limits="công tắc hành trình cứng; hiện báo EL DOWN LIMIT ở ~29–30°",
        park_el_deg=85.0,
        gps_lock=False,
        note="PC/RTCS giữ UTC+7; không tự xoá EL DOWN LIMIT khi chưa kiểm tra cơ khí.",
    ),

    # ---- Phụ trợ ----
    "bias_tee": dict(kind="aux", name="Bias-tee 5V"),
    "gpsdo": dict(kind="aux", name="GPSDO 10 MHz", ppm=0.0001),
}


@dataclass
class ChainResult:
    band_mhz: float
    parts: dict
    fallbacks: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    t_rec_k: float = 0.0
    t_sys_k: float = 0.0
    gain_db: float = 0.0
    sefd_jy: float = 0.0
    bw_mhz: float = 0.0
    adc_headroom_db: float = 0.0
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"=== CHUỖI THU @ {self.band_mhz:.0f} MHz ==="]
        for pos, pid in self.parts.items():
            tag = " (DỰ PHÒNG)" if pos in self.fallbacks else ""
            name = PARTS.get(pid, {}).get("name", pid)
            lines.append(f"  {pos:8} -> {name}{tag}")
        if self.missing:
            lines.append(f"  THIẾU: {', '.join(self.missing)} (dùng cấu hình dự phòng)")
        lines.append(
            f"  T_rec = {self.t_rec_k:.0f} K | T_sys = {self.t_sys_k:.0f} K | "
            f"SEFD = {self.sefd_jy/1e3:.1f} kJy | gain = {self.gain_db:.0f} dB"
        )
        for w in self.warnings:
            lines.append(f"  ⚠ {w}")
        return "\n".join(lines)


def t_rec_from_nf(nf_db: float) -> float:
    """Nhiệt độ ồn tương đương (K) từ NF (dB), T0 = 290 K."""
    return 290.0 * (10 ** (nf_db / 10.0) - 1.0)


def probe_sdr() -> dict:
    """Dò SDR đang cắm thật (không bao giờ ném exception)."""
    info = dict(
        found=False, kind=None, part_id=None, name=None,
        tuner=None, serial=None, n_devices=0, error=None,
    )
    try:
        from rtlsdr import RtlSdr  # type: ignore
    except Exception as e:
        info["error"] = f"chưa cài pyrtlsdr ({type(e).__name__})"
    else:
        try:
            n = int(RtlSdr.get_device_count())
        except Exception:
            n = 0
        info["n_devices"] = n
        if n > 0:
            try:
                dev = RtlSdr(0)
                try:
                    info["tuner"] = str(dev.get_tuner_type())
                except Exception:
                    pass
                try:
                    info["serial"] = str(dev.get_serial_number())
                except Exception:
                    pass
                dev.close()
                info.update(found=True, kind="rtlsdr", part_id="rtlsdr_v5",
                            name="RTL-SDR", error=None)
                return info
            except Exception as e:
                info["error"] = f"mở RTL-SDR lỗi: {type(e).__name__}: {e}"
        else:
            info["error"] = "không thấy thiết bị RTL-SDR nào trên USB"

    for mod, part, name in (("SoapySDR", "soapy", "SoapySDR"),
                            ("iio", "pluto", "PlutoSDR (libiio)")):
        try:
            __import__(mod)
        except Exception:
            continue
        info.update(found=True, kind=mod.lower(), part_id=part, name=name, error=None)
        return info
    return info


def probe_summary() -> str:
    """Câu mô tả ngắn gọn trạng thái SDR để hiện trên GUI."""
    p = probe_sdr()
    if p["found"]:
        tun = f" ({p['tuner']})" if p.get("tuner") else ""
        return f"Đã kết nối: {p['name']}{tun}"
    return f"Không tìm thấy SDR — {p.get('error') or 'không rõ lý do'}"


def detect_chain(have: dict | None = None, goal: str = "hi",
                 probe: dict | None = None) -> ChainResult:
    """Xây chuỗi thu tốt nhất ở 1420 MHz và tự fallback khi thiếu linh kiện."""
    have = dict(have or {})
    probe = probe if probe is not None else probe_sdr()
    band_mhz = 1420.0
    fb, miss = [], []
    parts: dict[str, str] = {}

    # ---- SDR
    sdr_id = have.get("sdr")
    if not sdr_id:
        if probe.get("found") and probe.get("part_id") in PARTS:
            sdr_id = probe["part_id"]
        else:
            sdr_id = "rtlsdr_v5"
            fb.append("sdr")
            miss.append("sdr(thiết bị)")
    parts["sdr"] = sdr_id
    sdr = PARTS[sdr_id]

    # ---- LNA
    lna_order = ["sawbird_hi", "spf5189z", "rtl_internal"]
    want_lna = have.get("lna")
    if want_lna in PARTS:
        parts["lna"] = want_lna
        if want_lna != lna_order[0]:
            fb.append("lna")
    else:
        parts["lna"] = lna_order[0]
        fb.append("lna")
    if parts["lna"] == "rtl_internal":
        miss.append("lna_ngoài")
    lna = PARTS[parts["lna"]]

    # ---- BPF
    bpf_order = ["saw_1420", "bpf_1300_1500"] if goal == "hi" else ["bpf_1300_1500", "saw_1420"]
    want_bpf = have.get("bpf")
    parts["bpf"] = want_bpf if want_bpf in PARTS else bpf_order[0]
    if parts["bpf"] != bpf_order[0]:
        fb.append("bpf")
    bpf = PARTS[parts["bpf"]]

    # ---- Phụ trợ
    parts["bias"] = "bias_tee"
    if "gpsdo" in (have.get("aux") or []):
        parts["clock"] = "gpsdo"
    else:
        parts["clock"] = f"tcxo_{sdr_id}"
        fb.append("clock")

    t_rec = t_rec_from_nf(lna["nf_db"])
    t_sys = T_CMB + T_SKY_1420 + T_GROUND + t_rec + t_rec_from_nf(bpf.get("nf_db", 0.0)) * 0.3
    gain_db = lna["gain_db"] + sdr.get("gain_db", 0.0)
    bw = min(sdr["bw_mhz"], bpf["hi_mhz"] - bpf["lo_mhz"])
    if parts["bpf"] == "saw_1420":
        bw = min(bw, 25.0)

    noise_floor_dbm = -174 + 10 * math.log10(bw * 1e6) + lna["nf_db"] + T_GROUND / 290 * 10
    headroom = -10.0 - (noise_floor_dbm + gain_db)

    warns = []
    if lna["lo_mhz"] > band_mhz or lna["hi_mhz"] < band_mhz:
        warns.append(f"LNA {lna['name']} không phủ {band_mhz:.0f} MHz")
    if headroom < 6:
        warns.append(f"Biên ADC chỉ còn {headroom:.0f} dB — dễ bão hoà, cần hạ gain")
    if t_sys > 500:
        warns.append(f"T_sys = {t_sys:.0f} K RẤT CAO (dùng LNA nội/thiếu LNA ngoài) — nên tích lũy dài (--nint lớn)")
    if sdr_id in ("soapy", "pluto"):
        warns.append(f"Phát hiện {sdr['name']} nhưng SKAO-TRT hiện thu trực tiếp qua pyrtlsdr hoặc fallback Mock")

    aeff = 0.55 * math.pi * 3.7**2 / 4
    sefd = 2 * K_B * t_sys / aeff / JY

    return ChainResult(
        band_mhz=band_mhz, parts=parts, fallbacks=sorted(set(fb)), missing=miss,
        t_rec_k=t_rec, t_sys_k=t_sys, gain_db=gain_db, sefd_jy=sefd,
        bw_mhz=bw, adc_headroom_db=headroom, warnings=warns,
    )


def poam_profile_summary() -> str:
    """Tóm tắt hồ sơ thiết bị thực tế POAM RTP-3.7 tại trạm."""
    rx, acu, ncu = PARTS["poam_receiver"], PARTS["poam_acu"], PARTS["poam_ncu"]
    feed = ("C-band box tại tiêu điểm; L-band feed chưa xác nhận lắp"
            if not rx.get("lband_feed_confirmed") else "L-band feed đã xác nhận")
    return "\n".join([
        "=== HỒ SƠ THIẾT BỊ POAM RTP-3.7 ===",
        f"Receiver: {rx['lo_mhz']:.0f}–{rx['hi_mhz']:.0f} MHz | BW {rx['bw_mhz']:.0f} MHz | "
        f"IQ stream API: {'CÓ' if rx['iq_stream'] else 'CHƯA CÓ (RTCS xuất line/continuum/scan)'}",
        f"Feed: {feed}.",
        f"ACU: Modbus {acu['ip']}:{acu['port']} | EL DOWN LIMIT ≈29–30° | PARK EL={acu['park_el_deg']:.0f}° | GPS OFF",
        f"NCU: {ncu['ip']} | chu trình Noise/Load/Sun = 20/20/240 s",
    ])
