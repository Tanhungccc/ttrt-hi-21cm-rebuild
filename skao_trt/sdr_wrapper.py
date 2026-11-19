# -*- coding: utf-8 -*-
"""Lớp bọc thiết bị SDR — giống bản gốc (skao_trt/sdr_wrapper.py).

Gồm: parse_gain, MockRtlSdr (thiết bị giả lập cho máy không có RTL-SDR),
SdrDevice = Union[MockRtlSdr, RtlSdr]. Import rtlsdr lười (lazy) để máy
không cài pyrtlsdr vẫn chạy được ở chế độ mock.
"""
from typing import Final, Union

import numpy as np
from numpy.typing import NDArray

Gain = float


def parse_gain(gain: str) -> float:
    """Ép chuỗi gain thành float (ngưỡng an toàn của gain đã kiểm tra ở ngoài)."""
    try:
        return float(gain)
    except (TypeError, ValueError):
        raise TypeError(f"Gain không hợp lệ: {gain!r}")


class MockRtlSdr:
    """RTL-SDR giả lập: trả nhiễu Gaussian, gain cho phép theo bảng RTL-SDR thật."""

    MAX_READ_SAMPLES: Final[int] = 2 ** 21
    GAINS: Final[list] = [
        0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6,
        19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2,
        38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6,
    ]

    def __init__(self):
        self.sample_rate = 2.4e6
        self.center_freq = 1420.40575177e6
        self._gain: Gain = 0.0

    def close(self):
        pass

    def read_samples(self, num_samples: int) -> NDArray[np.complex128]:
        if num_samples > self.MAX_READ_SAMPLES:
            raise ValueError(f"Chỉ đọc tối đa {self.MAX_READ_SAMPLES} mẫu/lần")
        # Biên độ ADC tăng theo gain (dB) — đủ để gain search hoạt động như thật
        amp = min(0.02 * 10 ** (self._gain / 20.0), 0.9)
        noise = np.random.normal(0.0, amp / np.sqrt(2), num_samples)
        return (noise + 1j * np.random.normal(0.0, amp / np.sqrt(2), num_samples)).astype(np.complex128)

    @property
    def gain(self) -> Gain:
        return self._gain

    @gain.setter
    def gain(self, value: Gain):
        self._gain = float(value)

    @property
    def get_gain(self) -> Gain:
        return self._gain

    @property
    def valid_gains_db(self) -> list:
        return self.GAINS


def _make_rtlsdr_class():
    """Import RtlSdr thật nếu máy có pyrtlsdr; không thì chỉ dùng MockRtlSdr."""
    try:
        from rtlsdr import RtlSdr  # type: ignore
        return RtlSdr
    except Exception:
        return None


RtlSdr = _make_rtlsdr_class()
SdrDevice = Union[MockRtlSdr, "RtlSdr"]
