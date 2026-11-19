# -*- coding: utf-8 -*-
"""Quản lý quan sát — giống bản gốc (skao_trt/apps/obs_manager.py),
thêm đường `last_...` để phân tích sau mỗi lần đo."""
from typing import Callable, Optional

import numpy as np
from numpy.typing import NDArray
from numpy import ptp

from ..gain_search import find_optimal_gain
from ..record_data import record_power_spectrum
from ..sdr_wrapper import MockRtlSdr

try:
    from rtlsdr import RtlSdr  # type: ignore
except Exception:
    RtlSdr = None  # chưa cài pyrtlsdr


class _MissingSdr:
    """Thay thế khi KHÔNG có RTL-SDR thật và KHÔNG --mock: khởi tạo sẽ ném đúng
    lỗi như app gốc ("Could not open SDR (device index = 0)"), tuyệt đối không
    lặng lẽ chạy giả lập."""

    def __init__(self):
        raise OSError('Could not open SDR (device index = 0) — '
                      'không tìm thấy thiết bị RTL-SDR hoặc thiếu thư viện pyrtlsdr. '
                      'Cắm USB SDR + cài driver (Zadig), hoặc bật nút MOCK trên thanh công cụ để thử.')


class ObsManager:
    """Quản lý việc ghi, lưu và vẽ dữ liệu. Không xử lý ngoại lệ
    (để caller xử lý) — như bản gốc."""

    def __init__(self, mock_device: bool = False, n_integrations: int = 25):
        self.mock_requested = mock_device
        if mock_device:
            self.sdr_class = MockRtlSdr
        elif RtlSdr is not None:
            self.sdr_class = RtlSdr          # thiết bị thật (lỗi mở thiết bị sẽ nêu rõ)
        else:
            self.sdr_class = _MissingSdr     # báo lỗi như app gốc, KHÔNG giả lập
        self.using_mock = self.sdr_class is MockRtlSdr
        self.mock_reason = "yêu cầu --mock" if mock_device else ""
        self.gain: Optional[float] = None
        self.baseline_power_spectrum: Optional[NDArray] = None
        self.last_freq: Optional[NDArray] = None
        self.last_power: Optional[NDArray] = None
        self.on_progress: Optional[Callable] = None
        self.n_integrations = int(n_integrations)   # số lượt tích lũy mỗi lần đo
        self.gain_curve = []                        # (gain, sigma) từ gain search
        self.last_sigma = 0.0                       # sigma lớn nhất lần đo gần nhất
        self.sat_limit = 0.35                       # ngưỡng bão hoà ADC

    def set_mock(self, enabled: bool):
        """Bật/tắt thiết bị giả lập bằng nút toggle trên thanh công cụ.
        Đổi thiết bị = vô hiệu hoá hiệu chuẩn cũ → phải Chuẩn bị lại."""
        if enabled:
            self.sdr_class = MockRtlSdr
            self.mock_reason = "bật bằng nút MOCK trên thanh công cụ"
        else:
            self.sdr_class = RtlSdr if RtlSdr is not None else _MissingSdr
            self.mock_reason = ""
        self.using_mock = self.sdr_class is MockRtlSdr
        self.mock_requested = enabled
        self.gain = None                       # reset hiệu chuẩn
        self.baseline_power_spectrum = None

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
