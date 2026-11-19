# SKAO-TRT — bản tái dựng có hiệu chỉnh

Tái dựng ứng dụng **SKAO Table-top Radio Telescope (v0.1.0)** từ bằng chứng
nghịch đảo (REA), giữ nguyên cấu trúc và luồng hoạt động của bản gốc, đồng thời
**hiệu chỉnh sai số** và bổ sung phân tích khoa học cho kính POAM RTP-3.7.

## Cơ sở bằng chứng (REA)

| Bằng chứng | Kết quả |
|---|---|
| `rea inspect-artifact` trên bộ cài | PE + Inno Setup, payload Python 3.11/PyInstaller |
| `rea inspect-artifact` trên app exe | CArchive: 709 node (696 module PYZ + 15 thành viên) |
| `rea inspect-python-pyc` trên 9 `.pyc` | Cây code object + tên file nguồn gốc — xem `REBUILD_STRUCTURE.json` |

Từ đó khôi phục được: cấu trúc module (`skao_trt/{constants,plotting,gain_search,
record_data,sdr_wrapper}.py`, `skao_trt/apps/{languages,obs_manager,tabletop_app}.py`),
tên class/method, chuỗi UI, thuật toán (gain search bằng std tín hiệu, chuẩn hóa
`sky/baseline*300`, gộp FFT 256 kênh × 25 lượt tích lũy, MockRtlSdr).
**Lưu ý trung thực:** một vài chi tiết nội bộ là suy luận từ hành vi (ngưỡng RF
trong gain search, hằng số chuẩn hóa) — được ghi chú trong code.

## Giống bản gốc

* Luồng **Prepare / Observe / Exit**, thanh trạng thái, hộp thoại chào mừng.
* Dò gain tối ưu → ghi phổ nền (terminator/load) → quan sát chuẩn hóa.
* Vẽ phổ công suất với đường đứt tại 1420.405752 MHz (SKAO_BLUE / SKAO_MAGENTA).
* `MockRtlSdr` chạy không cần phần cứng; đa ngôn ngữ (StrEnum).

## Hiệu chỉnh (sửa sai số + bổ sung)

1. **Hiệu chỉnh LSR** cho trục vận tốc (bản gốc chỉ vẽ tần số, chưa trừ chuyển
   động Trái Đất + chuyển động riêng Mặt Trời — lệch tới ±50 km/s).
2. **Nhập hướng trỏ (l, b)** + vĩ/kinh độ nơi quan sát; **tự động hiệu chỉnh theo
   vị trí thực**: nút "Tự động tìm vị trí (IP)" (ipinfo.io) khi di chuyển kính tới
   nơi khác; khi nạp file, app đọc vị trí + thời điểm quan sát từ provenance
   (header FITS / comment CSV) và **hiệu chỉnh theo nơi SINH RA phép đo**, cảnh báo
   nếu khác vị trí hiện tại; khi lưu luôn ghi kèm site_lat/site_lon/obstime để
   nạp lại không bao giờ lệch.
3. **Phân tích sau mỗi phép đo** ("từng trường hợp shift"): tìm đỉnh phổ →
   phân loại *lại gần / trôi xa / khí cục bộ* → R, khoảng cách gần–xa, nhánh
   tay xoắn → tóm tắt **vị trí của chúng ta trên Milky Way**.
4. Lưu tự động: CSV (freq, v_LSR, intensity) + PNG + `*_analysis.txt`.
5. `--demo` (phổ giả lập theo (l,b)) và `--selftest` (chạy pipeline không GUI).

## Cách chạy

```bash
pip install -r requirements.txt              # cài ĐẦY ĐỦ thư viện + driver lib cho SDR
python tabletop_app.py --selftest            # kiểm thử không cần phần cứng
python tabletop_app.py --mock --demo --language Vietnamese
python tabletop_app.py --data ../../sample_data/salsa/Observe-1/spectrum_11115.fits
python tabletop_app.py                       # với RTL-SDR thật (đã cài driver — xem HUONG_DAN mục F)
```

Kết quả quan sát được ghi vào thư mục `observations/`.

## Dữ liệu mẫu để test (không cần phần cứng)

`sample_data/salsa/` — **579 phổ HI 21cm thật** từ kính SALSA 2.3 m (Onsala,
Zenodo 1182827), 191 hướng l = 6–225°, kèm `Analysis-*/OUT.txt` (kết quả fit
Gaussian của tác giả) để đối chiếu. Nút **"Tải dữ liệu (FITS/CSV)"** trên app
hoặc cờ `--data` tự đọc toạ độ (l,b) và hiệu chỉnh LSR từ header FITS
(`v_LSR = v_radio − VELO-LSR`, dấu đã kiểm định thống kê).

Các lỗi đã gỡ khi test với dữ liệu thật:

1. **Dấu hiệu chỉnh LSR của FITS SALSA** (sai cả quỹ đạo phân tích) — sửa theo
   kiểm định thống kê 75 phổ mặt phẳng (khí cục bộ hội tụ v≈0 với 81%).
2. **Hình học khoảng cách chỉ đúng cho b=0** — sửa công thức cho b ≠ 0
   (R_min, nghiệm gần/xa đầy đủ cos b).
3. **Ngưỡng baseline bị dải phát xạ rộng thổi phồng** — ước lượng từ biên phổ.
4. **Đỉnh ảo trên sườn nhiễu** — lọc prominence; và lưu ý: phân rã thành phần
   blend là xấp xỉ (bản gốc SALSA fit Gaussian với seed nhập tay).

## Ánh xạ module với bản gốc

| Bản gốc (bằng chứng REA) | Bản tái dựng | Ghi chú |
|---|---|---|
| `skao_trt/constants.py` | `skao_trt/constants.py` | + R0, Θ0, c |
| `skao_trt/plotting.py` | `skao_trt/plotting.py` | + trục v_LSR, marker đỉnh |
| `skao_trt/gain_search.py` | `skao_trt/gain_search.py` | + callback tiến trình |
| `skao_trt/record_data.py` | `skao_trt/record_data.py` | như bản gốc |
| `skao_trt/sdr_wrapper.py` | `skao_trt/sdr_wrapper.py` | như bản gốc |
| — | `skao_trt/data_io.py` | **MỚI**: nạp FITS/CSV + provenance vị trí/thời điểm |
| `skao_trt/apps/obs_manager.py` | `skao_trt/apps/obs_manager.py` | + last_freq/last_power |
| `skao_trt/apps/languages.py` | `skao_trt/apps/languages.py` | EN (gốc) + VI (mới) |
| `skao_trt/apps/tabletop_app.py` | `tabletop_app.py` | + pointing, LSR, phân tích |
| — | `skao_trt/analysis.py` | **MỚI**: LSR + động học Ngân Hà |
