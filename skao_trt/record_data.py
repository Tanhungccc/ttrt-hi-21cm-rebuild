# -*- coding: utf-8 -*-
"""Thu phổ công suất — giống bản gốc (skao_trt/record_data.py).

Chuẩn hóa kênh bằng FFT rồi gộp (reshape + sum) thành 256 kênh thô, tích lũy
n_integrations lượt. Trục tần số dùng np.fft.fftfreq như bản gốc.
"""
import numpy as np
from numpy.typing import NDArray

from .sdr_wrapper import SdrDevice

N_CHANNELS = 256
N_INTEGRATIONS = 25
SAMPLES_PER_READ = 2 ** 21


def record_power_spectrum(sdr_class, gain: float, sample_rate: float,
                          center_freq: float,
                          n_integrations: int = N_INTEGRATIONS,
                          n_channels: int = N_CHANNELS,
                          samples_per_read: int = SAMPLES_PER_READ,
                          on_progress=None) -> tuple[NDArray, NDArray]:
    """Trả về (freq_MHz, power, max_sigma) của phổ trung bình nhiều lượt tích lũy.
    max_sigma = biên độ sigma lớn nhất qua các lượt — dùng phát hiện bão hoà ADC."""
    sdr: SdrDevice = sdr_class()
    try:
        sdr.sample_rate = sample_rate
        sdr.center_freq = center_freq
        sdr.gain = gain

        pws = np.zeros(n_channels)
        max_sigma = 0.0
        for i in range(n_integrations):
            if on_progress is not None:
                on_progress(i + 1, n_integrations)
            print(f"Recording... {i + 1}/{n_integrations}")
            data = sdr.read_samples(samples_per_read)
            max_sigma = max(max_sigma,
                            float(np.std(data.real)), float(np.std(data.imag)))
            n = len(data)
            spec = np.fft.fftshift(np.fft.fft(data))
            pwr = np.abs(spec / n * 2) ** 2
            pws += pwr.reshape(n_channels, n // n_channels).sum(axis=1)

        freqs = np.fft.fftshift(np.fft.fftfreq(samples_per_read, d=1.0 / sample_rate))
        # tâm mỗi kênh thô (n_channels kênh đều nhau qua dải thu)
        edges = np.linspace(freqs[0], freqs[-1], n_channels + 1)
        freq_mhz = (edges[:-1] + edges[1:]) / 2 / 1e6 + center_freq / 1e6
        return freq_mhz, pws / n_integrations, max_sigma
    except Exception:
        raise
    finally:
        try:
            sdr.close()
        except Exception:
            pass
