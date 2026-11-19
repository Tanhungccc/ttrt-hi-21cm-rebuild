# -*- coding: utf-8 -*-
"""Dò gain tối ưu — giống bản gốc (skao_trt/gain_search.py).

Nguyên tắc bản gốc (từ bytecode): duyệt `valid_gains_db`, mỗi gain đọc một
lượt mẫu, tính std của phần thực/ảo; gain đủ công suất RF (std vượt ngưỡng)
được chọn; không có → NotEnoughRFPower. Ngưỡng 0.05 ADC-σ là giá trị tái dựng
(suy luận từ hành vi, không có trong bằng chứng).
"""
import numpy as np

from .sdr_wrapper import Gain, SdrDevice


class NotEnoughRFPower(Exception):
    """RF không đủ mạnh để chọn gain nào."""


def _gain_table_db(sdr) -> list:
    """Bảng gain (dB) cho cả Mock lẫn RtlSdr thật.
    pyrtlsdr.get_gains() trả về gain ở đơn vị 1/10 dB → đổi về dB."""
    gains = getattr(sdr, "valid_gains_db", None)
    if gains is not None:
        return [float(g) for g in gains]
    return [float(g) / 10.0 for g in sdr.get_gains()]


def _read_gain(sdr) -> float:
    """Đọc gain hiện tại cho cả Mock (property) lẫn RtlSdr thật (method)."""
    g = sdr.get_gain
    return float(g() if callable(g) else g)


def find_optimal_gain(sdr_class, sample_rate: float, center_freq: float,
                      on_progress=None, rf_threshold: float = 0.004,
                      sat_limit: float = 0.35) -> Gain:
    """Chọn gain CAO NHẤT trước khi ADC bão hoà — quy tắc đúng cho thu radio
    (bản gốc kiểm tra bão hoà bằng histogram). Với tín hiệu yếu (anten telescop,
    mức ADC ~0.01) vẫn chọn được gain; không dùng ngưỡng 'đủ mạnh' tuyệt đối.
    """
    sdr: SdrDevice = sdr_class()
    try:
        sdr.sample_rate = sample_rate
        sdr.center_freq = center_freq
        chosen = None
        curve = []
        for gain in _gain_table_db(sdr):
            if on_progress is not None:
                on_progress(gain)
            sdr.gain = gain
            data = sdr.read_samples(2 ** 16)
            sigma = max(float(np.std(data.real)), float(np.std(data.imag)))
            curve.append((float(gain), sigma))
            print(f"Trying gain {gain}  (sigma={sigma:.4f})")
            if sigma > sat_limit:
                break                    # bắt đầu bão hoà → dừng, giữ gain trước
            if sigma >= rf_threshold:
                chosen = float(gain)     # hợp lệ → tiếp tục tìm gain cao hơn
        if chosen is None:
            raise NotEnoughRFPower(
                "Không tìm thấy gain nào dùng được — kiểm tra anten/LNA/cáp.")
        print(f"Optimum Gain = {chosen}")
        return chosen, curve
    finally:
        sdr.close()
