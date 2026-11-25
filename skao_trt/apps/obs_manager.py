# -*- coding: utf-8 -*-
"""Quản lý quan sát — giống bản gốc (skao_trt/apps/obs_manager.py),
thêm đường `last_...` để phân tích sau mỗi lần đo."""
from typing import Callable, Optional

import numpy as np
from numpy.typing import NDArray
from numpy import ptp

from ..gain_search import find_optimal_gain
from ..hardware import probe_sdr
from ..record_data import record_power_spectrum
from ..sdr_wrapper import MockRtlSdr

try:
    from rtlsdr import RtlSdr  # type: ignore
except Exception:
    RtlSdr = None  # chưa cài pyrtlsdr

VALID_SOURCE_MODES = ("auto", "mock", "real")


class _MissingSdr:
    """Thay thế khi KHÔNG có RTL-SDR thật và không fallback mock: khởi tạo sẽ ném đúng
    lỗi như app gốc ("Could not open SDR (device index = 0)")."""

    def __init__(self):
        raise OSError('Could not open SDR (device index = 0) — '
                      'không tìm thấy thiết bị RTL-SDR hoặc thiếu thư viện pyrtlsdr. '
                      'Cắm USB SDR + cài driver (Zadig), hoặc dùng chế độ Tự động/MOCK.')


class ObsManager:
    """Quản lý việc ghi, lưu và vẽ dữ liệu; hỗ trợ 3 chế độ nguồn: auto / mock / real."""

    def __init__(self, mock_device: bool = False, n_integrations: int = 25,
                 source_mode: Optional[str] = None):
        if source_mode is None:
            source_mode = "mock" if mock_device else "auto"
        if source_mode not in VALID_SOURCE_MODES:
            raise ValueError(f"source_mode không hợp lệ: {source_mode!r}")
        self.gain: Optional[float] = None
        self.baseline_power_spectrum: Optional[NDArray] = None
        self.last_freq: Optional[NDArray] = None
        self.last_power: Optional[NDArray] = None
        self.on_progress: Optional[Callable] = None
        self.n_integrations = int(n_integrations)   # số lượt tích lũy mỗi lần đo
        self.gain_curve = []                        # (gain, sigma) từ gain search
        self.last_sigma = 0.0                       # sigma lớn nhất lần đo gần nhất
        self.sat_limit = 0.35                       # ngưỡng bão hoà ADC
        self.last_probe: dict = {}
        self.set_source_mode(source_mode)

    def probe_hardware(self) -> dict:
        """Dò SDR đang cắm thật và cập nhật `last_probe`."""
        self.last_probe = probe_sdr()
        return self.last_probe

    def _has_usable_rtlsdr(self, probe: dict) -> bool:
        return bool(probe.get("found") and probe.get("kind") == "rtlsdr" and RtlSdr is not None)

    def set_source_mode(self, mode: str, *, allow_fallback: bool = False):
        """Đặt chế độ nguồn ('auto' | 'mock' | 'real'). Đổi nguồn = reset hiệu chuẩn."""
        if mode not in VALID_SOURCE_MODES:
            raise ValueError(f"source_mode không hợp lệ: {mode!r}")
        self.source_mode = mode
        if mode == "mock":
            self.sdr_class = MockRtlSdr
            self.mock_reason = "chọn chế độ MOCK"
        elif mode == "real":
            probe = self.probe_hardware()
            self.sdr_class = RtlSdr if self._has_usable_rtlsdr(probe) else _MissingSdr
            self.mock_reason = ""
        else:  # auto
            probe = self.probe_hardware()
            if self._has_usable_rtlsdr(probe):
                self.sdr_class = RtlSdr
                self.mock_reason = ""
            elif allow_fallback:
                self.sdr_class = MockRtlSdr
                self.mock_reason = f"tự động fallback ({probe.get('error') or 'không thấy SDR'})"
            else:
                self.sdr_class = _MissingSdr
                self.mock_reason = ""
        self.using_mock = self.sdr_class is MockRtlSdr
        self.mock_requested = (mode == "mock")
        self.gain = None
        self.baseline_power_spectrum = None

    def activate_fallback_mock(self, reason: str = "tự động fallback (không thấy SDR)"):
        """Chuyển sang MockRtlSdr khi chế độ 'auto' không thấy SDR."""
        self.sdr_class = MockRtlSdr
        self.using_mock = True
        self.mock_requested = False
        self.mock_reason = reason
        self.gain = None
        self.baseline_power_spectrum = None

    def set_mock(self, enabled: bool):
        """Bật/tắt thiết bị giả lập bằng nút toggle trên thanh công cụ.
        Đổi thiết bị = vô hiệu hoá hiệu chuẩn cũ → phải Chuẩn bị lại."""
        if enabled:
            self.set_source_mode("mock")
            self.mock_reason = "bật bằng nút MOCK trên thanh công cụ"
        else:
            self.set_source_mode("auto")

    @property
    def ready_to_record(self) -> bool:
        return self.gain is not None

    @property
    def ready_to_observe(self) -> bool:
        return self.baseline_power_spectrum is not None

    def find_optimal_gain(self, sample_rate: float, center_freq: float):
        self.gain, self.gain_curve = find_optimal_gain(
            self.sdr_class, sample_rate, center_freq, on_progress=self.on_progress)

    def auto_reduce_gain(self) -> float | None:
        """TỰ FALL BACK khi bão hoà ADC (Mặt Trời/RFI mạnh qua chảo + LNA):
        hạ gain một nấc trong bảng gain; trả về gain mới (None nếu đã tận cùng)."""
        from ..sdr_wrapper import MockRtlSdr
        table = [float(g) for g in MockRtlSdr.GAINS]   # bảng R828D chuẩn
        lower = [g for g in table if g < (self.gain if self.gain is not None else 0)]
        if not lower:
            return None
        self.gain = lower[-1]
        return self.gain

    def record_baseline_power_spectrum(self, sample_rate: float, center_freq: float):
        assert self.ready_to_record
        _, self.baseline_power_spectrum, self.last_sigma = record_power_spectrum(
            self.sdr_class, self.gain, sample_rate, center_freq,
            n_integrations=self.n_integrations, on_progress=self.on_progress)

    def record_normalised_sky_power_spectrum(self, sample_rate: float,
                                             center_freq: float,
                                             n_integrations: int | None = None) -> tuple[NDArray, NDArray]:
        assert self.ready_to_observe
        freq, sky, self.last_sigma = record_power_spectrum(
            self.sdr_class, self.gain, sample_rate, center_freq,
            n_integrations=(self.n_integrations if n_integrations is None
                            else int(n_integrations)),
            on_progress=self.on_progress)
        # Chuẩn hóa: tỉ lệ sky/baseline quy về thang ~300 (nhiệt độ load),
        # như cách bản gốc/dẫn xuất chuẩn hóa (sky/bl*300).
        norm = sky / self.baseline_power_spectrum * 300.0
        self.last_freq, self.last_power = freq, norm
        return freq, norm
