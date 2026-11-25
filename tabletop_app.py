# -*- coding: utf-8 -*-
"""SKAO Table-top Radio Telescope — bản TÁI DỰNG CÓ HIỆU CHỈNH.

Giống bản gốc (bằng chứng: REA inspect-python-pyc trên SKAO-TRT-0.1.0,
xem REBUILD_STRUCTURE.json): LogoBar / InteractiveFigure / ButtonsBar /
StatusBar / TabletopApp (prepare, observe, exit, run) / parse_args / main.

PHẦN HIỆU CHỈNH (sửa sai số + bổ sung phân tích):
1. Hiệu chỉnh LSR cho trục vận tốc (bản gốc vẽ Frequency, chưa trừ chuyển
   động Trái Đất + Mặt Trời → lệch tới ±50 km/s).
2. Nhập hướng trỏ (l, b) + vị trí quan sát; gắn nhãn mọi kết quả theo (l,b).
3. Sau mỗi lần đo: tìm đỉnh phổ → phân loại shift (lại gần / trôi xa / cục bộ)
   → R, khoảng cách, nhánh tay xoắn → tóm tắt "vị trí của chúng ta".
4. --demo: phổ giả lập theo (l,b); --selftest: chạy trọn pipeline không cần GUI.

Chạy:  python tabletop_app.py [--language Vietnamese] [--mock] [--demo]
       python tabletop_app.py --selftest
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import tkinter as tk
import tkinter.font
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from skao_trt import analysis, data_io, hardware
from skao_trt.apps.languages import SUPPORTED_LANGUAGES
from skao_trt.apps.obs_manager import ObsManager
from skao_trt.constants import HI_FREQ_MHZ, SKAO_BLUE, SKAO_MAGENTA
from skao_trt.plotting import plot_power_spectrum_on_axes

SAMPLE_RATE = 2.4e6
CENTER_FREQ = HI_FREQ_MHZ * 1e6

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def make_config(width: int) -> dict:
    return {
        "window.width": width,
        "window.fontsize": 11,
        "figure.aspect_ratio": 0.55,
        "figure.dpi": 100,
        "figure.text.fontsize": 10,
        "figure.axislabels.fontsize": 10,
        "figure.ticklabels.fontsize": 8,
        "figure.title.fontsize": 12,
    }


def get_logo_path():
    return os.path.join(ASSET_DIR, "skao_logo_bar.jpg")


def get_default_font_family() -> str:
    return tkinter.font.nametofont("TkCaptionFont").actual("family")


class LogoBar:
    """Logo SKAO ở đầu cửa sổ — như bản gốc."""

    def __init__(self, parent: tk.Widget, imgpath: str, width: int, font):
        from PIL import Image, ImageTk
        img = Image.open(imgpath)
        h = round(img.height * width / img.width)
        img = img.resize((width, h))
        self.image = ImageTk.PhotoImage(img)
        self.label = tk.Label(parent, image=self.image, bg="white")
        self.label.pack(side=tk.TOP, fill=tk.X)

    def dispose(self):
        self.label.pack_forget()


class InteractiveFigure:
    """Khung matplotlib nhúng — như bản gốc, thêm tham số peaks/title."""

    def __init__(self, parent: tk.Widget, config: dict, title: str, font):
        self.config = config
        self.frame = tk.Frame(parent)
        w = config["window.width"]
        aspect = config["figure.aspect_ratio"]
        self.fig = Figure(figsize=(w / config["figure.dpi"], w * aspect / config["figure.dpi"]),
                          dpi=config["figure.dpi"])
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.10, right=0.95, bottom=0.12, top=0.86)
        self.canvas = FigureCanvasTkAgg(self.fig, self.frame)
        self.clear_axes()
        self.navbar = NavigationToolbar2Tk(self.canvas, self.frame)
        self.dispose()  # đóng gói layout như bản gốc (pack khi hiển thị)

    def clear_axes(self):
        self.ax.clear()
        self.ax.axis("off")
        self.canvas.draw()

    def display_text(self, lines: list, title: str | None = None):
        self.clear_axes()
        cfg = self.config
        y = 0.85 if title else 0.5
        if title:
            self.ax.text(0.02, y, title, fontweight="bold",
                         fontsize=cfg["figure.text.fontsize"] + 2,
                         color=SKAO_MAGENTA, transform=self.ax.transAxes)
            y -= 0.12
        for line in lines:
            self.ax.text(0.02, y, line, fontsize=cfg["figure.text.fontsize"],
                         color=SKAO_BLUE, transform=self.ax.transAxes)
            y -= 0.09
        self.canvas.draw()

    def dispose(self):
        self.frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.navbar.pack(side=tk.BOTTOM, fill=tk.X)

    def plot_power_spectrum(self, freq, pwr, peaks=None, title: str = "",
                            x_unit: str = "freq", show_extras: bool = False,
                            lsr_corr: float = 0.0):
        self.clear_axes()
        self.ax.axis("on")
        plot_power_spectrum_on_axes(self.ax, freq, pwr, peaks=peaks, x_unit=x_unit,
                                    show_extras=show_extras, lsr_corr=lsr_corr)
        fs = self.config["figure.axislabels.fontsize"]
        self.ax.set_title(title, fontsize=self.config["figure.title.fontsize"],
                          fontweight="bold", color=SKAO_BLUE)
        self.ax.tick_params(axis="both", labelsize=self.config["figure.ticklabels.fontsize"])
        self.canvas.draw()


class ButtonsBar:
    def __init__(self, parent: tk.Widget, button_definitions, font):
        self.frame = tk.Frame(parent)
        self.buttons = []
        for i, (text, command) in enumerate(button_definitions):
            self._create_button(text, command, font, i)

    def _create_button(self, text: str, command, font, column: int):
        b = tk.Button(self.frame, text=text, command=command, font=font)
        self.buttons.append(b)
        self.frame.grid_columnconfigure(column, weight=1)
        b.grid(row=0, column=column, sticky="ew")

    def dispose(self):
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)


class StatusBar:
    def __init__(self, parent: tk.Widget, status: str, font):
        self.label = tk.Label(parent, text=status, font=font, relief=tk.SUNKEN, anchor=tk.W)
        self.label.pack(side=tk.BOTTOM, fill=tk.X)

    def dispose(self):
        self.label.pack_forget()

    def update_status(self, status: str):
        self.label.config(text=status)


class TabletopApp:
    """Ứng dụng chính — luồng Prepare/Observe/Exit như bản gốc,
    thêm ô nhập hướng trỏ và bảng phân tích sau mỗi phép đo."""

    def __init__(self, width: int = 1024, mock: bool = False, demo: bool = False,
                 language: str = "English", n_integrations: int = 25,
                 source_mode: str | None = None):
        self.lang = SUPPORTED_LANGUAGES[language]
        self.demo = demo
        self.root = tk.Tk()
        self.root.title(self.lang.APP_TITLE)
        self.config = make_config(width)
        self.font = (get_default_font_family(), self.config["window.fontsize"])

        # --- ô nhập hướng trỏ (phần hiệu chỉnh) ---
        self._create_pointing_row()

        self.logo_bar = LogoBar(self.root, get_logo_path(), self.config["window.width"], self.font)
        self.interactive_figure = InteractiveFigure(
            self.root, self.config, self.lang.FIGURE_TITLE, self.font)
        self.buttons_bar = ButtonsBar(self.root, [
            (self.lang.PREPARE, self.prepare),
            (self.lang.OBSERVE, self.observe),
            (self.lang.LBL_CLEAR, self.clear_view),
            (self.lang.EXIT, self.exit),
        ], self.font)
        self.buttons_bar.dispose()  # bản gốc: dispose() = finalize/pack layout
        self.status_bar = StatusBar(self.root, self.lang.READY, self.font)
        self.obs_manager = ObsManager(mock_device=mock, n_integrations=n_integrations,
                                      source_mode=source_mode)
        self.obs_manager.on_progress = None
        self.is_mock = self.obs_manager.using_mock
        self._create_mock_toggle()
        self.refresh_hw_status()
        self._update_title()
        if self.is_mock:
            self.update_status(f"⚠ {self.lang.WARN_MOCK_TITLE} — {self.obs_manager.mock_reason}")
        self._display_welcome_text()

    def _create_pointing_row(self):
        """2 hàng gọn để KHÔNG đè chữ: hàng 1 = toạ độ mục tiêu + hiệu chuẩn,
        hàng 2 = Az/El từ mount + các nút chức năng."""
        L = self.lang
        row1 = tk.Frame(self.root, bg="white")
        row1.pack(side=tk.TOP, fill=tk.X)
        row2 = tk.Frame(self.root, bg="white")
        row2.pack(side=tk.TOP, fill=tk.X)
        self.l_var = tk.StringVar(value="30.0")
        self.b_var = tk.StringVar(value="0.0")
        self.lat_var = tk.StringVar(value="10.76")
        self.lon_var = tk.StringVar(value="106.66")
        self.lsr_var = tk.BooleanVar(value=True)
        self.az_var = tk.StringVar(value="")
        self.el_var = tk.StringVar(value="")
        for label, var, w in ((L.LBL_L, self.l_var, 6), (L.LBL_B, self.b_var, 6),
                              (L.LBL_LAT, self.lat_var, 7), (L.LBL_LON, self.lon_var, 7)):
            tk.Label(row1, text=label, bg="white", font=self.font).pack(side=tk.LEFT, padx=(10, 2))
            tk.Entry(row1, textvariable=var, width=w, font=self.font).pack(side=tk.LEFT)
        tk.Checkbutton(row1, text=L.LBL_LSR, variable=self.lsr_var,
                       bg="white", font=self.font).pack(side=tk.LEFT, padx=10)
        # Az/El từ encoder của mount → tự đổi sang (l,b)
        tk.Label(row2, text="Az", bg="white", font=self.font).pack(side=tk.LEFT, padx=(10, 2))
        tk.Entry(row2, textvariable=self.az_var, width=5, font=self.font).pack(side=tk.LEFT)
        tk.Label(row2, text="El", bg="white", font=self.font).pack(side=tk.LEFT, padx=(4, 2))
        tk.Entry(row2, textvariable=self.el_var, width=5, font=self.font).pack(side=tk.LEFT)
        tk.Button(row2, text="Az/El → (l,b)", command=self.azel_to_lb,
                  font=self.font).pack(side=tk.LEFT, padx=4)
        tk.Button(row2, text=L.LBL_SUN, command=self.pointing_help,
                  font=self.font).pack(side=tk.LEFT, padx=4)
        tk.Button(row2, text=L.LBL_AUTODETECT, command=self.detect_location,
                  font=self.font).pack(side=tk.LEFT, padx=4)
        tk.Button(row2, text=L.LBL_DRIFT, command=self.drift_scan,
                  font=self.font).pack(side=tk.LEFT, padx=4)
        tk.Button(row2, text=L.LBL_LOAD, command=self.load_data,
                  font=self.font).pack(side=tk.LEFT, padx=4)
        tk.Button(row2, text=L.LBL_HW_CHECK, command=self.show_hardware_status,
                  font=self.font).pack(side=tk.LEFT, padx=4)

    def _create_mock_toggle(self):
        """Nút toggle trên thanh công cụ đồ thị: Nguồn (Auto/Mock/Real) + MOCK + RAW."""
        L = self.lang
        self._src_labels = {
            "auto": L.LBL_SRC_AUTO,
            "mock": L.LBL_SRC_MOCK,
            "real": L.LBL_SRC_REAL,
        }
        self.source_var = tk.StringVar(value=self._src_labels[self.obs_manager.source_mode])
        self.source_combo = ttk.Combobox(
            self.interactive_figure.navbar, textvariable=self.source_var,
            values=list(self._src_labels.values()), state="readonly", width=10,
            font=self.font)
        self.source_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_source_changed())
        self.source_combo.pack(side=tk.RIGHT, padx=4)

        self.hw_label = tk.Label(
            self.interactive_figure.navbar, text="", bg="white", font=self.font)
        self.hw_label.pack(side=tk.RIGHT, padx=6)

        self.mock_var = tk.BooleanVar(value=self.is_mock)
        self.mock_toggle = tk.Checkbutton(
            self.interactive_figure.navbar, text=self.lang.LBL_MOCK_TOGGLE,
            variable=self.mock_var, command=self.toggle_mock,
            font=self.font, fg=SKAO_MAGENTA, selectcolor="#ffd6e7",
            activebackground="white", bg="white")
        self.mock_toggle.pack(side=tk.RIGHT, padx=8)
        self.raw_var = tk.BooleanVar(value=False)
        self.raw_toggle = tk.Checkbutton(
            self.interactive_figure.navbar, text=self.lang.LBL_EXTRAS,
            variable=self.raw_var, command=self.toggle_view,
            font=self.font, fg=SKAO_BLUE, selectcolor="#d6e0ff",
            activebackground="white", bg="white")
        self.raw_toggle.pack(side=tk.RIGHT, padx=8)
        self._last_plot = None

    def _source_key(self) -> str:
        txt = self.source_var.get()
        for k, v in self._src_labels.items():
            if v == txt:
                return k
        return "auto"

    def refresh_hw_status(self) -> dict:
        """Dò SDR và cập nhật nhãn trạng thái (🟢 thật / 🟡 mô phỏng / 🔴 thiếu)."""
        probe = self.obs_manager.probe_hardware()
        mode = self.obs_manager.source_mode
        if self.obs_manager.using_mock:
            text, col = "🟡 MOCK", "#b36b00"
        elif self.obs_manager._has_usable_rtlsdr(probe):
            tun = f" ({probe['tuner']})" if probe.get("tuner") else ""
            text, col = f"🟢 {probe['name']}{tun}", "#1a7f37"
        elif mode == "real":
            text, col = "🔴 Không có SDR", "#c62828"
        else:
            text, col = "🟡 Tự động → fallback MOCK", "#b36b00"
        self.hw_label.configure(text=text, fg=col)
        return probe

    def show_hardware_status(self):
        """Hiển thị kết quả dò SDR, chuỗi thu dự phòng (detect_chain) và hồ sơ POAM."""
        probe = self.refresh_hw_status()
        chain = hardware.detect_chain(goal="hi", probe=probe)
        lines = [
            f"SDR probe: {hardware.probe_summary()}",
            f"Chế độ nguồn: {self.obs_manager.source_mode}",
            "",
            *chain.summary().splitlines(),
            "",
            *hardware.poam_profile_summary().splitlines(),
        ]
        self._show(lines, title=self.lang.LBL_HW_CHECK)

    def on_source_changed(self):
        mode = self._source_key()
        self.obs_manager.set_source_mode(mode)
        self.is_mock = self.obs_manager.using_mock
        self.mock_var.set(self.is_mock)
        self.refresh_hw_status()
        self._update_title()
        self.update_status(f"Nguồn dữ liệu: {self._src_labels[mode]} — bấm Chuẩn bị")

    def toggle_view(self):
        """RAW (chưa xử lý) ON = phổ thô như app gốc; OFF (mặc định) = view
        khoa học: tích hợp + khử nền + Gaussian smooth + v_LSR + dò đỉnh."""
        if self._last_plot is not None:
            self._draw_plot()
        else:
            self.update_status("Tuỳ chọn xem sẽ áp dụng ở lần Quan sát/Tải dữ liệu tới")

    def toggle_mock(self):
        """Bật/tắt thiết bị giả lập — đổi thiết bị thì vô hiệu hoá hiệu chuẩn cũ."""
        want = self.mock_var.get()
        if want == self.is_mock:
            return
        self.obs_manager.set_mock(want)
        self.is_mock = self.obs_manager.using_mock
        self.source_var.set(self._src_labels[self.obs_manager.source_mode])
        self.refresh_hw_status()
        self._update_title()
        if self.is_mock:
            self.update_status(f"⚠ ĐÃ BẬT {self.lang.WARN_MOCK_TITLE} — phải bấm Chuẩn bị lại")
            self._show([self.lang.WARN_MOCK_L1,
                        "Bấm Chuẩn bị để chạy với thiết bị GIẢ LẬP."],
                       title=self.lang.WARN_MOCK_TITLE)
        else:
            self.update_status("Chế độ Tự động — ưu tiên SDR thật, bấm Chuẩn bị lại")
            self._show(["Chế độ Tự động: ưu tiên RTL-SDR thật; nếu không thấy sẽ hỏi fallback MOCK.",
                        "Muốn bắt buộc SDR thật (báo lỗi nếu thiếu), chọn 'SDR thật'."],
                       title=self.lang.READY)

    def _update_title(self):
        base = self.lang.APP_TITLE
        if self.is_mock:
            base += f"  [{self.lang.WARN_MOCK_TITLE}]"
        self.root.title(base)

    def _show(self, lines, title=""):
        """Mọi màn hình chữ — nếu đang GIẢ LẬP thì luôn dán nhãn MOCK."""
        if self.is_mock:
            lines = [f"⚠ {self.lang.WARN_MOCK_TITLE} — {self.lang.WARN_MOCK_L1}"] + list(lines)
            title = (title + "  [MOCK]") if title else self.lang.WARN_MOCK_TITLE
        self.interactive_figure.display_text(lines, title=title)

    def _display_welcome_text(self):
        L = self.lang
        lines = [L.WELCOME_L1, L.WELCOME_L2, L.WELCOME_L3]
        self._show(lines, title=L.WELCOME_TITLE)

    def update_status(self, status: str):
        if self.is_mock and "GIẢ LẬP" not in status:
            status += " [GIẢ LẬP MOCK]"
        self.status_bar.update_status(status)
        self.root.update_idletasks()

    def display_error(self, e: Exception):
        L = self.lang
        self._show([L.ERROR_L1, f"Error: {e}"], title=L.ERROR_TITLE)
        print(traceback.format_exc())
        self.update_status(f"Error: {e}")

    # ------------------------------------------------------------- chuẩn bị
    def prepare(self):
        L = self.lang
        try:
            probe = self.refresh_hw_status()
            if self.obs_manager.source_mode == "auto" and not self.obs_manager.using_mock:
                if not self.obs_manager._has_usable_rtlsdr(probe):
                    ok = messagebox.askokcancel(
                        "Không thấy RTL-SDR — chạy MÔ PHỎNG (fallback)?",
                        "\n".join([
                            f"Không tìm thấy RTL-SDR ({probe.get('error') or 'không rõ lý do'}).",
                            "",
                            "OK = Tự động chuyển sang MÔ PHỎNG (MOCK) để thử quy trình",
                            "Cancel = Dừng lại để cắm thiết bị / cài driver Zadig",
                        ]))
                    if not ok:
                        self.update_status("Đã huỷ Chuẩn bị — chưa có RTL-SDR")
                        return
                    self.obs_manager.activate_fallback_mock(
                        f"tự động fallback ({probe.get('error') or 'không thấy SDR'})")
                    self.is_mock = True
                    self.mock_var.set(True)
                    self.refresh_hw_status()
                    self._update_title()

            self.update_status(L.PREP_START_STATUS)
            self._show([L.PREP_STEP1_L1, L.PREP_STEP1_L2], title=L.PREP_STEP1_TITLE)

            def on_gain(gain):
                self.update_status(f"{L.PREP_GAIN_STATUS} {gain}")
                self.root.update_idletasks()

            from skao_trt.gain_search import find_optimal_gain
            gain, curve = find_optimal_gain(
                self.obs_manager.sdr_class, SAMPLE_RATE, CENTER_FREQ,
                on_progress=on_gain)
            self.obs_manager.gain = gain
            self.obs_manager.gain_curve = curve

            self._show([L.PREP_STEP2_L1], title=L.PREP_STEP2_TITLE)
            self.update_status(L.PREP_BASELINE_STATUS)
            self.obs_manager.record_baseline_power_spectrum(SAMPLE_RATE, CENTER_FREQ)
            self.update_status(L.PREP_DONE_STATUS)
            diag = (analysis.chain_report(gain_curve=self.obs_manager.gain_curve)
                    + [""] + hardware.detect_chain(goal="hi", probe=probe).summary().splitlines())
            self._show(
                [L.PREP_COMPLETE_L1.format(gain=self.obs_manager.gain),
                 L.PREP_COMPLETE_L2, L.PREP_COMPLETE_L3, L.PREP_COMPLETE_L4,
                 L.PREP_COMPLETE_L5] + diag,
                title=L.PREP_COMPLETE_TITLE)
            for d in diag:
                print(d)
        except Exception as e:
            msg = str(e)
            if "Could not open SDR" not in msg:
                msg += (" — gợi ý: kiểm tra đã cắm RTL-SDR? Đã cài driver (Zadig)? "
                        "Muốn thử không phần cứng thì bật nút MOCK trên thanh công cụ")
            self.display_error(Exception(msg))

    # ------------------------------------------------------------- quan sát
    def observe(self):
        L = self.lang
        try:
            if not self.obs_manager.ready_to_observe:
                self.update_status(L.OBS_NOT_READY_STATUS)
                return
            l = float(self.l_var.get())
            b = float(self.b_var.get())
            self._show([L.OBS_L1, L.OBS_L2], title=L.OBSERVE_TITLE)
            self.update_status(L.OBS_START_STATUS)

            freq, pwr = self.obs_manager.record_normalised_sky_power_spectrum(
                SAMPLE_RATE, CENTER_FREQ)
            # TỰ FALL BACK khi bão hoà ADC (vd. chảo + LNA đang trỏ Mặt Trời)
            extra = []
            if self.obs_manager.last_sigma > self.obs_manager.sat_limit:
                newg = self.obs_manager.auto_reduce_gain()
                if newg is not None:
                    extra.append(f"⚠ ADC bão hoà (tín hiệu rất mạnh) — đã TỰ HẠ gain → {newg} và đo lại.")
                    freq, pwr = self.obs_manager.record_normalised_sky_power_spectrum(
                        SAMPLE_RATE, CENTER_FREQ)
            if self.is_mock:
                # giả lập thì phổ cũng phải giả lập CÓ CẤU TRÚC HI theo (l,b) —
                # nhiễu trơn không có ý nghĩa để tập phân tích
                pwr = analysis.demo_spectrum(l, b, freq)

            self.update_status(L.OBS_PLOT_STATUS)
            v_radio = analysis.freq_to_vradio(freq)
            corr = self._get_corr(l, b)
            v_lsr = v_radio + (corr or 0.0)
            report = self._analyse_and_plot(l, b, v_lsr, pwr, plot_x=freq,
                                            x_unit="freq", corr=corr,
                                            extra_lines=extra
                                            + analysis.chain_report(
                                                y_factor=float(np.mean(pwr)) / 300.0,
                                                sky_pwr=pwr))
            self.update_status(L.OBS_DONE_STATUS)
        except Exception as e:
            self.display_error(e)

    def detect_location(self):
        """Tự tìm vị trí hiện tại qua IP (ipinfo.io) — cùng dịch vụ với GUI
        HI_starplot. Phục vụ 'tự động hiệu chỉnh theo vị trí thực' khi di chuyển
        kính tới nơi khác; nhập tay vẫn được ưu tiên nếu tự phát hiện sai."""
        try:
            import urllib.request, json
            with urllib.request.urlopen("https://ipinfo.io/json", timeout=5) as u:
                loc = json.loads(u.read().decode())["loc"]   # "lat,lon"
            lat, lon = loc.split(",")
            self.lat_var.set(f"{float(lat):.2f}")
            self.lon_var.set(f"{float(lon):.2f}")
            self.update_status(f"Vị trí tự phát hiện: lat={lat}, lon={lon} — kiểm tra lại nếu sai!")
        except Exception as e:
            self.update_status(f"Không tự phát hiện được vị trí ({e}) — nhập tay")

    def azel_to_lb(self):
        """ĐỔI Az/El (đọc từ encoder của mount POAM) → (l,b) thiên hà,
        tự động theo thời điểm hiện tại. Cập nhật luôn ô l, b."""
        try:
            az = float(self.az_var.get())
            el = float(self.el_var.get())
        except ValueError:
            self.update_status("Nhập số vào ô Az và El trước khi đổi!")
            return
        try:
            from astropy.coordinates import SkyCoord, EarthLocation, AltAz
            from astropy.time import Time
            import astropy.units as u
            t = Time.now()
            loc = EarthLocation(lat=float(self.lat_var.get()) * u.deg,
                                lon=float(self.lon_var.get()) * u.deg)
            c = SkyCoord(az=az * u.deg, alt=el * u.deg, frame="altaz",
                         obstime=t, location=loc)
            g = c.transform_to("galactic")
            self.l_var.set(f"{g.l.deg:.1f}")
            self.b_var.set(f"{g.b.deg:.1f}")
            self.update_status(f"Az/El ({az}°,{el}°) → (l,b) = "
                               f"({g.l.deg:.1f}°, {g.b.deg:.1f}°)")
        except Exception as e:
            self.display_error(e)

    def pointing_help(self):
        """Trợ lý trỏ: mục tiêu (l,b) và Mặt Trời đang ở Alt/Az nào NGAY BÂY GIỜ,
        giờ qua trung tuyến — để trỏ tay hoặc nhập vào mount POAM.
        PHẦN TỰ ĐỘNG: app tự tính toạ độ, LSR, thời điểm. PHẦN CHƯA tự động:
        động cơ trỏ (nằm trong controller POAM) — bạn nhập Alt/Az vào đó."""
        try:
            from astropy.coordinates import SkyCoord, EarthLocation, AltAz, get_sun
            from astropy.time import Time
            import astropy.units as u
            t = Time.now()
            loc = EarthLocation(lat=float(self.lat_var.get()) * u.deg,
                                lon=float(self.lon_var.get()) * u.deg)
            l, b = float(self.l_var.get()), float(self.b_var.get())
            tgt = SkyCoord(l=l * u.deg, b=b * u.deg, frame="galactic")
            aa = tgt.transform_to(AltAz(obstime=t, location=loc))
            ts = Time([t.to_datetime() + datetime.timedelta(minutes=10 * k)
                       for k in range(145)])
            aas = tgt.transform_to(AltAz(obstime=ts, location=loc))
            k = int(aas.alt.deg.argmax())
            sun = get_sun(t).transform_to(AltAz(obstime=t, location=loc))
            lines = [
                f"MỤC TIÊU (l,b)=({l:.1f}°,{b:.1f}°):  Alt = {aa.alt.deg:.1f}°,  "
                f"Az = {aa.az.deg:.1f}°  (ngay bây giờ)",
                f"   → qua trung tuyến lúc {ts[k].iso[11:16]} UTC, Alt cực đại {aas.alt.deg[k]:.1f}°",
                f"MẶT TRỜI:  Alt = {sun.alt.deg:.1f}°,  Az = {sun.az.deg:.1f}°",
                "Tự động: app tính toạ độ (l,b), hiệu chỉnh LSR, thời điểm.",
                "Trỏ cơ cấu: nhập Alt/Az ở trên vào mount POAM (hoặc trỏ tay theo)."]
            if aa.alt.deg < 0:
                lines.append("⚠ Mục tiêu ĐANG DƯỚI CHÂN TRỜI — chờ tới giờ qua trung tuyến.")
            if sun.alt.deg < 0:
                lines.append("ℹ Mặt Trời đang dưới chân trời.")
            self._show(lines, title=self.lang.LBL_SUN)
            self.update_status(f"Mục tiêu: Alt={aa.alt.deg:.1f}°, Az={aa.az.deg:.1f}° | "
                               f"MT: Alt={sun.alt.deg:.1f}°, Az={sun.az.deg:.1f}°")
        except Exception as e:
            self.display_error(e)

    def drift_scan(self, n_steps: int = 40, step_integrations: int = 3):
        """Drift scan Mặt Trời: anten ĐỨNG YÊN, đo lặp ~2 phút, vẽ công suất
        theo thời gian — đỉnh đi qua = Mặt Trời băng qua beam (xoay Trái Đất).
        Dùng cho tình huống KHÔNG có LNA (tín hiệu Mặt Trời đủ mạnh)."""
        L = self.lang
        try:
            if not self.obs_manager.ready_to_observe:
                self.update_status(L.OBS_NOT_READY_STATUS)
                return
            self._show(["Drift scan: đo lặp, anten đứng yên hướng lên trời.",
                        f"{n_steps} điểm × {step_integrations} tích lũy (~2 phút)..."],
                       title="Sun drift scan")
            times, powers = [], []
            t0 = datetime.datetime.now()
            for k in range(n_steps):
                freq, pwr = self.obs_manager.record_normalised_sky_power_spectrum(
                    SAMPLE_RATE, CENTER_FREQ, n_integrations=step_integrations)
                # TỰ FALL BACK: bão hoà ADC (MT qua beam / RFI mạnh) → hạ gain, đo lại
                if self.obs_manager.last_sigma > self.obs_manager.sat_limit:
                    newg = self.obs_manager.auto_reduce_gain()
                    if newg is not None:
                        self.update_status(f"⚠ Bão hoà ADC — tự hạ gain → {newg}, đo lại điểm {k + 1}")
                        freq, pwr = self.obs_manager.record_normalised_sky_power_spectrum(
                            SAMPLE_RATE, CENTER_FREQ, n_integrations=step_integrations)
                if self.is_mock:
                    # giả lập đường đi của Mặt Trời qua beam (đỉnh Gaussian theo giờ)
                    tt = (k + 0.5) / n_steps
                    pwr = pwr + 60 * np.exp(-0.5 * ((tt - 0.5) / 0.12) ** 2)
                times.append((datetime.datetime.now() - t0).total_seconds())
                powers.append(float(np.mean(pwr)))
                self.update_status(f"Drift scan: {k + 1}/{n_steps}")
                self.root.update_idletasks()

            fig_if = self.interactive_figure
            fig_if.clear_axes()
            fig_if.ax.axis("on")
            fig_if.ax.plot(times, powers, color=SKAO_BLUE)
            fig_if.ax.set_xlabel("Thời gian [s]")
            fig_if.ax.set_ylabel("Công suất TB dải [a.u.]")
            title = "Sun drift scan — công suất theo thời gian"
            if self.is_mock:
                title += "  [MOCK]"
            fig_if.ax.set_title(title, fontsize=fig_if.config["figure.title.fontsize"],
                                fontweight="bold", color=SKAO_BLUE)
            fig_if.ax.grid()
            fig_if.canvas.draw()
            self._last_plot = None

            outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "observations")
            os.makedirs(outdir, exist_ok=True)
            now = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            np.savetxt(os.path.join(outdir, f"TTRT_{now}_driftscan.csv"),
                       np.vstack([times, powers]).T, delimiter=",",
                       header="time_s,power_bandavg", comments="# ")
            self.update_status(f"Drift scan hoàn tất — lưu observations/TTRT_{now}_driftscan.csv")
        except Exception as e:
            self.display_error(e)

    def load_data(self, path: str | None = None):
        """Nạp phổ HI từ file (FITS SALSA / CSV) và phân tích như một lần đo."""
        L = self.lang
        try:
            if path is None:
                from tkinter import filedialog
                path = filedialog.askopenfilename(
                    title=L.LBL_LOAD,
                    filetypes=[("HI spectrum", "*.fits *.fit *.fts *.csv *.txt"),
                               ("All files", "*.*")])
                if not path:
                    return
            spec = data_io.load_spectrum(path)
            l = spec.l if spec.l is not None else float(self.l_var.get())
            b = spec.b if spec.b is not None else float(self.b_var.get())
            self.l_var.set(f"{l:.1f}")
            self.b_var.set(f"{b:.1f}")

            # --- hiệu chỉnh theo VỊ TRÍ + THỜI ĐIỂM QUAN SÁT của phép đo ---
            ui_lat, ui_lon = float(self.lat_var.get()), float(self.lon_var.get())
            site_lat = spec.lat if spec.lat is not None else ui_lat
            site_lon = spec.lon if spec.lon is not None else ui_lon
            notes = []
            if spec.lat is not None and (abs(spec.lat - ui_lat) > 0.5 or
                                         abs((spec.lon or ui_lon) - ui_lon) > 0.5):
                notes.append(f"⚠ Dữ liệu quan sát tại {spec.site_name or '(không rõ tên)'} "
                             f"(lat={spec.lat:.2f}, lon={spec.lon:.2f}) KHÁC vị trí hiện tại "
                             f"(lat={ui_lat:.2f}, lon={ui_lon:.2f}) → hiệu chỉnh theo "
                             f"VỊ TRÍ QUAN SÁT, không theo nơi phân tích.")
            if spec.lsr_applied:
                corr = 0.0   # file đã hiệu chỉnh LSR sẵn → KHÔNG cộng thêm
            else:
                if spec.lat is None:
                    notes.append("⚠ File không có vị trí quan sát — tạm giả sử vị trí "
                                 "trong ô nhập (kiểm tra lại!).")
                corr = self._get_corr(l, b, obstime=spec.obstime,
                                      lat=site_lat, lon=site_lon)
                if corr is None:
                    corr = 0.0
                    notes.append("⚠ Không tính được LSR (thiếu astropy).")
            v_lsr = spec.v_lsr + (corr or 0.0)
            x_unit = "freq" if spec.freq_mhz is not None else "vel"
            plot_x = spec.freq_mhz if spec.freq_mhz is not None else v_lsr
            # offset v_LSR <-> trục tần số THẬT của file (vd. FITS: −VELO-LSR)
            if spec.freq_mhz is not None:
                map_corr = float(np.mean(spec.v_lsr -
                                         analysis.freq_to_vradio(spec.freq_mhz)))
            else:
                map_corr = 0.0

            self.update_status(L.OBS_PLOT_STATUS)
            report = self._analyse_and_plot(l, b, v_lsr, spec.intensity,
                                            plot_x=plot_x, x_unit=x_unit,
                                            corr=corr, source=spec.source,
                                            map_corr=map_corr)
            report.insert(1, f"Hiệu chỉnh theo vị trí quan sát: lat={site_lat:.2f}, "
                             f"lon={site_lon:.2f}"
                             + (f", t={spec.obstime}" if spec.obstime else ""))
            for j, note in enumerate(notes, 2):
                report.insert(j, note)
            for line in notes:
                print(line)
            self.update_status(L.OBS_DONE_STATUS)
        except Exception as e:
            self.display_error(e)

    def _get_corr(self, l, b, obstime=None, lat=None, lon=None):
        """LSR theo VỊ TRÍ/THỜI ĐIỂM của phép đo (mặc định: ô nhập + hiện tại)."""
        if not self.lsr_var.get():
            return None
        return analysis.lsr_correction(
            l, b, obstime=obstime,
            lat_deg=float(self.lat_var.get()) if lat is None else lat,
            lon_deg=float(self.lon_var.get()) if lon is None else lon)

    def _analyse_and_plot(self, l, b, v_lsr, intensity, plot_x, x_unit="freq",
                          corr=0.0, source: str = "", map_corr=None,
                          extra_lines=None):
        """Pipeline: tích hợp (sẵn) → khử nền → Gaussian smooth → v_LSR →
        dò đỉnh → phân tích shift/pointing/vị trí chúng ta → vẽ.

        map_corr: offset v_LSR ↔ trục tần số (mặc định = corr) — truyền đúng
        để marker & trục phụ khớp đỉnh.
        """
        if map_corr is None:
            map_corr = corr
        processed, detr, base = analysis.process_spectrum(v_lsr, intensity)
        peaks = analysis.find_peaks(v_lsr, processed)
        result = analysis.analyse_observation(l, b, peaks, corr_lsr=corr)
        report = analysis.format_analysis(result)
        if self.is_mock:
            report.insert(0, "⚠ GIẢ LẬP MOCK — số liệu KHÔNG phải đo thật!")
        if source:
            report.insert(0, f"Dữ liệu đầu vào: {source}")
        if extra_lines:
            report.extend(extra_lines)
        for line in report:
            print(line)

        peak_marks = [{"v_lsr": p.v_lsr, "amplitude": p.amplitude} for p in peaks]
        title = self.lang.FIGURE_TITLE
        if self.is_mock:
            title += "  [MOCK]"
        self._last_plot = dict(
            v_lsr=v_lsr, raw=intensity, processed=processed,
            freq=plot_x if x_unit == "freq" else None,
            peaks=peak_marks, map_corr=map_corr, title=title)
        self._draw_plot()
        self._save_results(l, b, v_lsr, intensity, processed, report,
                           site_lat=float(self.lat_var.get()),
                           site_lon=float(self.lon_var.get()),
                           obstime=datetime.datetime.now(datetime.timezone.utc)
                                     .strftime("%Y-%m-%dT%H:%M:%SZ"))
        return report

    def _draw_plot(self):
        """Vẽ theo tuỳ chọn xem: mặc định = khoa học đã xử lý; RAW = thô."""
        from skao_trt.plotting import plot_processed_on_axes, plot_power_spectrum_on_axes
        d = self._last_plot
        if d is None:
            return
        fig_if = self.interactive_figure
        fig_if.clear_axes()
        fig_if.ax.axis("on")
        title = d["title"]
        if self.raw_var.get():
            title += "  — RAW"
            if d["freq"] is not None:
                plot_power_spectrum_on_axes(fig_if.ax, d["freq"], d["raw"],
                                            x_unit="freq", lsr_corr=d["map_corr"])
            else:
                plot_power_spectrum_on_axes(fig_if.ax, d["v_lsr"], d["raw"],
                                            x_unit="vel", lsr_corr=d["map_corr"])
        else:
            title += "  — đã xử lý"
            plot_processed_on_axes(fig_if.ax, d["v_lsr"], d["processed"],
                                   peaks=d["peaks"], lsr_corr=d["map_corr"])
        fig_if.ax.set_title(title, fontsize=fig_if.config["figure.title.fontsize"],
                            fontweight="bold", color=SKAO_BLUE)
        fig_if.ax.tick_params(axis="both",
                              labelsize=fig_if.config["figure.ticklabels.fontsize"])
        fig_if.canvas.draw()

    def clear_view(self):
        """Nút Clear (như app gốc): xoá đồ thị về màn hình trống."""
        self.interactive_figure.clear_axes()
        self._last_plot = None
        self.update_status(self.lang.READY)

    def _save_results(self, l, b, v_lsr, intensity, processed, report,
                      site_lat=None, site_lon=None, obstime=None):
        now = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        base = f"TTRT_{now}_l{int(l)}_b{int(b)}"
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "observations")
        os.makedirs(outdir, exist_ok=True)
        hdr = ["v_LSR_kms,intensity_raw,intensity_processed",
               f"site_lat={site_lat}", f"site_lon={site_lon}",
               f"obstime={obstime}", f"l={l}", f"b={b}"]
        np.savetxt(os.path.join(outdir, base + ".csv"),
                   np.vstack([v_lsr, intensity, processed]).T, delimiter=",",
                   header="\n".join(hdr), comments="# ")
        with open(os.path.join(outdir, base + "_analysis.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        self.interactive_figure.fig.savefig(os.path.join(outdir, base + ".png"))

    def exit(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ------------------------------------------------------------------ CLI
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--mock", action="store_true", help="dùng MockRtlSdr (không cần RTL-SDR)")
    p.add_argument("--real", action="store_true", help="bắt buộc RTL-SDR thật (không fallback mock)")
    p.add_argument("--demo", action="store_true", help="phổ giả lập theo (l,b)")
    p.add_argument("--selftest", action="store_true", help="chạy pipeline không cần GUI")
    p.add_argument("--data", type=str, default=None,
                   help="nạp phổ HI từ file (FITS SALSA / CSV) khi khởi động")
    p.add_argument("--nint", type=int, default=25,
                   help="số lượt tích lũy mỗi lần đo (mặc định 25 ≈ 9 giây; "
                        "tăng khi thiếu LNA, vd. 300 ≈ 2 phút)")
    p.add_argument("--language", type=str, default="English",
                   choices=list(SUPPORTED_LANGUAGES.keys()))
    args, _ = p.parse_known_args()
    if args.demo and not args.mock:
        args.mock = True   # --demo là dữ liệu giả lập → luôn đi kèm mock (có nhãn MOCK)
    return args


def selftest():
    """Chạy trọn pipeline (mock + demo) không mở GUI — dùng để kiểm thử."""
    from skao_trt.apps.languages import validate_languages
    validate_languages()
    print("=== SELFTEST: mock prepare + demo observe (l=30, b=0) ===")
    mgr = ObsManager(mock_device=True)
    from skao_trt.gain_search import find_optimal_gain
    mgr.gain, mgr.gain_curve = find_optimal_gain(mgr.sdr_class, SAMPLE_RATE, CENTER_FREQ)
    mgr.record_baseline_power_spectrum(SAMPLE_RATE, CENTER_FREQ)
    freq, pwr = mgr.record_normalised_sky_power_spectrum(SAMPLE_RATE, CENTER_FREQ)
    pwr = analysis.demo_spectrum(30.0, 0.0, freq)

    corr = analysis.lsr_correction(30.0, 0.0)
    v_lsr = analysis.freq_to_vradio(freq) + (corr or 0.0)
    processed, detr, base = analysis.process_spectrum(v_lsr, pwr)
    peaks = analysis.find_peaks(v_lsr, processed)
    result = analysis.analyse_observation(30.0, 0.0, peaks, corr_lsr=corr)
    for line in analysis.format_analysis(result):
        print(line)
    assert peaks, "selftest: không tìm thấy đỉnh phổ giả lập"
    assert corr is not None, "selftest: thiếu astropy → không hiệu chỉnh LSR"

    # --- kiểm tra marker cắm ĐÚNG đỉnh trên view khoa học (trục v_LSR) ---
    from matplotlib.figure import Figure
    from skao_trt.plotting import plot_processed_on_axes
    fig = Figure()
    ax = fig.add_subplot(111)
    marks = [{"v_lsr": p.v_lsr, "amplitude": p.amplitude} for p in peaks]
    plot_processed_on_axes(ax, v_lsr, processed, peaks=marks, lsr_corr=corr)
    mx = [float(t) for ln in ax.lines if ln.get_marker() == "v" for t in ln.get_xdata()]
    assert len(mx) == len(peaks), "selftest: số marker ≠ số đỉnh"
    dv_chan = abs(float(v_lsr[1] - v_lsr[0]))
    for p in peaks:
        off = min(abs(m - p.v_lsr) for m in mx) / dv_chan
        assert off <= 0.5, f"selftest: marker lệch {off:.2f} kênh tại v={p.v_lsr}"
    print("Marker alignment: OK (≤0.5 kênh)")
    # --- kiểm tra dò phần cứng & fallback chuỗi thu ---
    probe = hardware.probe_sdr()
    assert "found" in probe, "selftest: probe_sdr thiếu khoá 'found'"
    ch = hardware.detect_chain(goal="hi", probe=probe)
    assert 60 < ch.t_sys_k < 250, f"selftest: T_sys 1420 MHz bất thường: {ch.t_sys_k}"
    ch_fb = hardware.detect_chain(have={"lna": "rtl_internal"}, probe=probe)
    assert ch_fb.t_sys_k > 800 and "lna" in ch_fb.fallbacks, "selftest: fallback LNA nội sai"
    assert "POAM RTP-3.7" in hardware.poam_profile_summary(), "selftest: thiếu hồ sơ POAM"
    mgr_auto = ObsManager(source_mode="auto")
    if not mgr_auto.using_mock and not mgr_auto._has_usable_rtlsdr(mgr_auto.last_probe):
        mgr_auto.activate_fallback_mock("selftest")
        assert mgr_auto.using_mock, "selftest: auto fallback không kích hoạt MockRtlSdr"
    print("Hardware probe & fallback: OK")
    print("=== SELFTEST OK ===")


def main():
    args = parse_args()
    if args.selftest:
        selftest()
        return
    src_mode = "mock" if args.mock else ("real" if args.real else "auto")
    app = TabletopApp(width=args.width, mock=args.mock, demo=args.demo,
                      language=args.language, n_integrations=args.nint,
                      source_mode=src_mode)
    if args.data:
        app.root.after(200, lambda: app.load_data(args.data))
    app.run()


if __name__ == "__main__":
    main()
