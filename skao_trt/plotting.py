# -*- coding: utf-8 -*-
"""Vẽ phổ công suất — giống bản gốc (skao_trt/plotting.py), thêm trục v_LSR
và đánh dấu đỉnh phổ (bổ sung của bản hiệu chỉnh).

Bản gốc: plot_power_spectrum(freq, pwr) và plot_power_spectrum_on_axes(ax, ...)
với đường đứt SKAO_MAGENTA tại HI_FREQ_MHZ, nhãn trục Frequency [MHz] /
Intensity [a.u.].
"""
import numpy as np
from numpy.typing import NDArray

from .constants import C_KMS, HI_FREQ_MHZ, SKAO_BLUE, SKAO_MAGENTA


def _v_lsr_of(freq_mhz):
    return C_KMS * (HI_FREQ_MHZ - np.asarray(freq_mhz)) / HI_FREQ_MHZ


def plot_processed_on_axes(ax, v_lsr: NDArray, processed: NDArray, peaks=None,
                           lsr_corr: float = 0.0):
    """VIEW KHOA HỌC (mặc định): phổ đã tích hợp + khử nền + Gaussian smooth,
    trục X = v_LSR (trục phụ = tần số), vạch nghỉ tại v=0, dò đỉnh có marker."""
    v = np.asarray(v_lsr)
    y = np.asarray(processed, dtype=float)
    span = float(np.ptp(y)) or 1.0
    yn = (y - float(np.min(y))) / span
    ax.plot(v, yn, color=SKAO_BLUE)
    ax.vlines(0, 0, 1, color=SKAO_MAGENTA, linestyles="dashed")   # v_LSR = 0
    ax.set_xlabel("v_LSR [km/s]")
    ax.set_ylabel("Intensity [a.u.]")
    ax.set_xlim(min(v), max(v))
    ax.set_ylim(0, 1.08)   # chừa rìa trên cho nhãn marker
    ax.grid()
    f_of_v = lambda vv: HI_FREQ_MHZ * (1 - (vv - lsr_corr) / C_KMS)
    ax2 = ax.secondary_xaxis("top", functions=(
        f_of_v, lambda f: C_KMS * (HI_FREQ_MHZ - f) / HI_FREQ_MHZ + lsr_corr))
    ax2.set_xlabel("Frequency [MHz]")

    if peaks:
        for p in peaks:
            y_at = (p["amplitude"] - float(np.min(y))) / span
            ax.plot([p["v_lsr"]], [min(y_at, 1.0)], "v", color=SKAO_MAGENTA)
            ax.annotate(f"{p['v_lsr']:+.0f}", (p["v_lsr"], min(y_at, 1.0)),
                        textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8, color=SKAO_MAGENTA)


def plot_power_spectrum(freq: NDArray, pwr: NDArray, peaks=None, x_unit: str = "freq",
                        show_extras: bool = False, lsr_corr: float = 0.0):
    """Giống bản gốc: trả về matplotlib Figure của phổ công suất."""
    import matplotlib.pyplot as plt
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plot_power_spectrum_on_axes(ax, freq, pwr, peaks=peaks, x_unit=x_unit,
                                show_extras=show_extras, lsr_corr=lsr_corr)
    return fig


def plot_power_spectrum_on_axes(ax, x: NDArray, pwr: NDArray, peaks=None,
                                x_unit: str = "freq", show_extras: bool = False,
                                lsr_corr: float = 0.0):
    """Vẻ theo ĐÚNG phong cách app gốc: phổ SKAO_BLUE, đường đứt SKAO_MAGENTA
    tại vạch HI, lưới, trục Y chuẩn hoá 0–1, nhãn gốc.

    show_extras=True (tuỳ chọn, nút toggle trên thanh công cụ) mới thêm
    trục phụ v_LSR và đánh dấu đỉnh.

    lsr_corr (km/s): hiệu chỉnh LSR ĐÃ áp dụng cho phổ này — BẮT BUỘC truyền
    đúng để đổi qua lại v_LSR ↔ tần số khớp nhau:  v_LSR = c(f0−f)/f0 + lsr_corr.
    Sai lệch lsr_corr = mũi tên & trục phụ trượt khỏi đỉnh đúng bằng corr.
    """
    x = np.asarray(x)
    pwr = np.asarray(pwr, dtype=float)
    span = float(np.ptp(pwr)) or 1.0
    y = (pwr - float(np.min(pwr))) / span          # chuẩn hoá 0–1 như app gốc
    ax.plot(x, y, color=SKAO_BLUE)

    # đổi v_LSR <-> tần số PHẢI đi qua cùng một quy ước với lúc tính trục vận tốc
    f_of_v = lambda vv: HI_FREQ_MHZ * (1 - (vv - lsr_corr) / C_KMS)
    v_of_f = lambda f: C_KMS * (HI_FREQ_MHZ - f) / HI_FREQ_MHZ + lsr_corr

    if x_unit == "freq":
        ax.vlines(HI_FREQ_MHZ, 0, 1, color=SKAO_MAGENTA, linestyles="dashed")
        ax.set_xlabel("Frequency [MHz]")
    else:
        ax.vlines(0, 0, 1, color=SKAO_MAGENTA, linestyles="dashed")  # v_LSR = 0 = nghỉ
        ax.set_xlabel("v_LSR [km/s]")
    ax.set_ylabel("Intensity [a.u.]")
    ax.set_xlim(min(x), max(x))
    ax.set_ylim(0, 1)
    ax.grid()

    if show_extras:
        ax2 = ax.secondary_xaxis("top", functions=(
            v_of_f if x_unit == "freq" else f_of_v,
            f_of_v if x_unit == "freq" else v_of_f))
        ax2.set_xlabel("v_LSR [km/s]" if x_unit == "freq" else "Frequency [MHz]")
        if peaks:
            for p in peaks:
                v = p["v_lsr"]
                x_at = f_of_v(v) if x_unit == "freq" else v
                y_at = (p["amplitude"] - float(np.min(pwr))) / span
                ax.plot([x_at], [min(y_at, 1.0)], "v", color=SKAO_MAGENTA)
                ax.annotate(f"{v:+.0f}", (x_at, min(y_at, 1.0)),
                            textcoords="offset points", xytext=(0, 8),
                            ha="center", fontsize=8, color=SKAO_MAGENTA)
