# -*- coding: utf-8 -*-
"""Ngôn ngữ giao diện — bản tái dựng từ skao_trt/apps/languages.py gốc.

Bản gốc có 10 ngôn ngữ (StrEnum, mỗi ngôn ngữ ~36 hằng chuỗi). Bản tái dựng
giữ nguyên cấu trúc đó với English (chuỗi gốc đã khôi phục từ bytecode) và
Vietnamese (bổ sung cho nhóm bạn); thêm nhãn cho phần hiệu chỉnh (pointing,
phân tích). Muốn thêm ngôn ngữ: tạo class mới giống English.
"""
from enum import StrEnum


class English(StrEnum):
    NAME = "English"
    # trạng thái & nút
    STATUS = "Status"
    READY = "Ready"
    PREPARE = "Prepare"
    OBSERVE = "Observe"
    EXIT = "Exit"
    # chào mừng
    APP_TITLE = "SKAO Table-top Radio Telescope (TRT) App — corrected rebuild"
    WELCOME_TITLE = "Short instruction manual:"
    WELCOME_L1 = "1. Prepare (calibrates the RF device against the load)"
    WELCOME_L2 = "2. Observe as many times as you want"
    WELCOME_L3 = "3. Each observation is analysed: shift case, pointing, your position"
    FIGURE_TITLE = "Hydrogen Line (HI) signal of the Milky Way"
    # chuẩn bị
    PREP_START_STATUS = "Preparing ..."
    PREP_STEP1_TITLE = "This step calibrates your RF device"
    PREP_STEP1_L1 = "Searching for optimal gain ..."
    PREP_STEP1_L2 = "IMPORTANT: connect the 50 Ohm terminator (RF load) first!"
    PREP_GAIN_STATUS = "Trying gain"
    PREP_STEP2_TITLE = "Recording baseline power spectrum ..."
    PREP_STEP2_L1 = "Do not disconnect the RF load during this step ..."
    PREP_BASELINE_STATUS = "Recording baseline power spectrum ..."
    PREP_DONE_STATUS = "Preparation complete!"
    PREP_COMPLETE_TITLE = "Preparation complete"
    PREP_COMPLETE_L1 = "Optimum Gain = {gain}"
    PREP_COMPLETE_L2 = "You can observe the Milky Way!"
    PREP_COMPLETE_L3 = " - Remove RF termination"
    PREP_COMPLETE_L4 = " - Connect your antenna to the receiver"
    PREP_COMPLETE_L5 = " - Set pointing (l, b) and press Observe"
    # quan sát
    OBS_NOT_READY_STATUS = "Please run the preparation step first!"
    OBSERVE_TITLE = "Sky observation in progress"
    OBS_L1 = "This should take about 30 seconds ..."
    OBS_L2 = "An interactive graph will appear at the end!"
    OBS_START_STATUS = "Observing ..."
    OBS_PLOT_STATUS = "Plotting ..."
    OBS_DONE_STATUS = "Observation finished!"
    # lỗi
    ERROR_TITLE = "Something went wrong"
    ERROR_L1 = "Check status bar and terminal for more information."
    # nhãn hiệu chỉnh (mới)
    LBL_L = "l (deg)"
    LBL_B = "b (deg)"
    LBL_LAT = "Lat"
    LBL_LON = "Lon"
    LBL_LSR = "Apply LSR correction"
    LBL_LOAD = "Load data (FITS/CSV)"
    LBL_AUTODETECT = "Auto-detect site (IP)"
    LBL_MOCK_TOGGLE = "MOCK"
    LBL_EXTRAS = "RAW (chưa xử lý)"
    LBL_DRIFT = "Drift (Mặt Trời)"
    LBL_SUN = "Trỏ (Alt/Az)"
    LBL_CLEAR = "Xóa"
    WARN_MOCK_TITLE = "SIMULATION MODE (MOCK)"
    WARN_MOCK_L1 = "No real measurement is being made — the spectra are SIMULATED."
    LBL_ANALYSIS = "Analysis (shift case / pointing / our position)"


class Vietnamese(StrEnum):
    NAME = "Vietnamese"
    STATUS = "Trạng thái"
    READY = "Sẵn sàng"
    PREPARE = "Chuẩn bị"
    OBSERVE = "Quan sát"
    EXIT = "Thoát"
    APP_TITLE = "Kính vô tuyến Bàn (TRT) của SKAO — bản tái dựng có hiệu chỉnh"
    WELCOME_TITLE = "Hướng dẫn nhanh:"
    WELCOME_L1 = "1. Bấm Chuẩn bị (hiệu chuẩn thiết bị RF với điện trở tải)"
    WELCOME_L2 = "2. Bấm Quan sát bao nhiêu lần tùy ý"
    WELCOME_L3 = "3. Mỗi lần đo được phân tích: hướng dịch chuyển, hướng trỏ, vị trí của chúng ta"
    FIGURE_TITLE = "Tín hiệu vạch HI của Ngân Hà"
    PREP_START_STATUS = "Đang chuẩn bị ..."
    PREP_STEP1_TITLE = "Bước này hiệu chuẩn thiết bị RF của bạn"
    PREP_STEP1_L1 = "Đang tìm gain tối ưu ..."
    PREP_STEP1_L2 = "QUAN TRỌNG: hãy gắn điện trở 50 Ω (terminator) vào đầu vào RF trước!"
    PREP_GAIN_STATUS = "Đang thử gain"
    PREP_STEP2_TITLE = "Đang ghi phổ nền ..."
    PREP_STEP2_L1 = "Không ngắt điện trở RF trong bước này ..."
    PREP_BASELINE_STATUS = "Đang ghi phổ nền ..."
    PREP_DONE_STATUS = "Chuẩn bị hoàn tất!"
    PREP_COMPLETE_TITLE = "Chuẩn bị hoàn tất"
    PREP_COMPLETE_L1 = "Gain tối ưu = {gain}"
    PREP_COMPLETE_L2 = "Bạn đã có thể quan sát Ngân Hà!"
    PREP_COMPLETE_L3 = " - Tháo điện trở RF"
    PREP_COMPLETE_L4 = " - Nối anten vào đầu thu"
    PREP_COMPLETE_L5 = " - Nhập hướng trỏ (l, b) rồi bấm Quan sát"
    OBS_NOT_READY_STATUS = "Vui lòng chạy bước Chuẩn bị trước!"
    OBSERVE_TITLE = "Đang quan sát bầu trời"
    OBS_L1 = "Bước này mất khoảng 30 giây ..."
    OBS_L2 = "Đồ thị tương tác sẽ hiện ra khi xong!"
    OBS_START_STATUS = "Đang quan sát ..."
    OBS_PLOT_STATUS = "Đang vẽ ..."
    OBS_DONE_STATUS = "Quan sát hoàn tất!"
    ERROR_TITLE = "Đã xảy ra lỗi"
    ERROR_L1 = "Xem thanh trạng thái và terminal để biết thêm chi tiết."
    LBL_L = "l (độ)"
    LBL_B = "b (độ)"
    LBL_LAT = "Vĩ độ"
    LBL_LON = "Kinh độ"
    LBL_LSR = "Áp dụng hiệu chỉnh LSR"
    LBL_LOAD = "Tải dữ liệu (FITS/CSV)"
    LBL_AUTODETECT = "Tự động tìm vị trí (IP)"
    LBL_MOCK_TOGGLE = "MOCK (giả lập)"
    LBL_EXTRAS = "RAW (unprocessed)"
    LBL_DRIFT = "Drift scan (Sun)"
    LBL_SUN = "Pointing (Alt/Az)"
    LBL_CLEAR = "Clear"
    WARN_MOCK_TITLE = "CHẾ ĐỘ GIẢ LẬP (MOCK)"
    WARN_MOCK_L1 = "KHÔNG có phép đo thật nào diễn ra — phổ hiển thị là GIẢ LẬP."
    LBL_ANALYSIS = "Phân tích (shift / hướng trỏ / vị trí chúng ta)"


SUPPORTED_LANGUAGES = {lang.NAME: lang for lang in (English, Vietnamese)}


def validate_languages() -> None:
    """Đảm bảo mọi ngôn ngữ có đủ hằng như English (tham chiếu)."""
    ref = set(English.__members__)
    for name, lang in SUPPORTED_LANGUAGES.items():
        missing = ref - set(lang.__members__)
        if missing:
            raise AssertionError(f"Ngôn ngữ {name} thiếu hằng: {sorted(missing)}")
