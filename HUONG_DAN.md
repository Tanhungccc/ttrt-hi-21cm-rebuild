# HƯỚNG DẪN DỤNG APP — SKAO-TRT bản hiệu chỉnh
## Đi qua từng nút bấm, theo thứ tự một buổi quan sát

Giao diện từ trên xuống: **hàng ô nhập (toạ độ + nút phụ)** → logo → **đồ thị phổ**
→ **3 nút chính [Chuẩn bị] [Quan sát] [Thoát]** → thanh trạng thái.

---

## A. Các ô nhập & nút phụ (hàng trên cùng)

### 1. Ô `l (độ)` — kinh tuyến thiên hà
Nhập hướng trỏ theo tọa độ thiên hà. Gợi ý: `30` (nhìn vào tâm Ngân Hà),
`90`, `135`, `180` (anticenter). Khi nạp file FITS, ô này **tự điền** từ header.

### 2. Ô `b (độ)` — vĩ tuyến thiên hà
Độ cao so với mặt phẳng Ngân Hà. Để `0` là quan sát trong mặt phẳng TH.

### 3. Ô `lat` / 4. Ô `lon` — vị trí nơi quan sát
Vĩ/kinh độ của kính. **Nếu mang kính đi nơi khác: phải đúng vị trí mới**
(mặc định 10.76 / 106.66 = TP.HCM). Dùng cho hiệu chỉnh LSR.

### 5. Tick `Áp dụng hiệu chỉnh LSR`
**Nên luôn bật.** Bật = trục vận tốc được cộng hiệu chỉnh LSR (±50 km/s) để
so sánh được với dữ liệu thiên văn quốc tế. Tắt chỉ khi muốn xem "vận tốc thô".

### 6. Nút `Tự động tìm vị trí (IP)`
**Bấm khi đem kính tới chỗ mới.** App tự dò lat/lon qua mạng (ipinfo.io) và điền
vào ô lat/lon. Kiểm tra lại nếu sai; mất mạng thì nhập tay.

### 7. Nút `Drift (Mặt Trời)`
**Drift scan Mặt Trời** — dùng khi CHƯA có LNA: anten đứng yên hướng lên trời,
app đo lặp ~2 phút rồi vẽ **công suất theo thời gian**; đỉnh đi qua = Mặt Trời
băng qua beam (nhờ Trái Đất tự quay). Lưu CSV vào `observations/`.
Lưu ý: tín hiệu Mặt Trời là liên tục → xem RAW/đồ thị drift, không phải view đã khử nền.

### 8. Nút `Tải dữ liệu (FITS/CSV)`
**Bấm khi muốn phân tích file có sẵn thay vì đo trực tiếp** (ví dụ file trong
`sample_data/salsa/`). Chọn file `.fits` (kính SALSA) hoặc `.csv` (app đã lưu).
App tự đọc (l,b), vị trí + thời điểm quan sát từ file, hiệu chỉnh theo **nơi
sinh ra phép đo** (không theo nơi bạn đang ngồi) và cảnh báo nếu lệch vị trí.

---

## B. 3 nút chính (dưới đồ thị) — thứ tự một buổi đo

### 8. Nút `Chuẩn bị` — bấm ĐẦU TIÊN mỗi buổi
Trước khi bấm: **gắn điện trở 50 Ω (terminator)** vào đầu vào RF.
App sẽ:
1. Dò gain tối ưu cho SDR (thanh trạng thái hiện "Đang thử gain ...")
2. Ghi phổ nền (điện trở tải) để làm mốc hiệu chuẩn (~30 giây)
Khi xong, đồ thị hiện: *"Chuẩn bị hoàn tất — Gain tối ưu = ..."*.
→ **Tháo terminator, gắn anten vào.**

### 9. Nút `Quan sát` — bấm mỗi lần đo (bao nhiêu lần tùy ý)
Sau khi đã bấm Chuẩn bị và điền l, b:
1. Thu phổ ~30 giây (thanh trạng thái: "Đang quan sát ...")
2. Hiện **đồ thị phổ**: trục dưới = tần số, **trục trên = v_LSR**, tam giác hồng = đỉnh tìm được
3. In ra **bảng phân tích** (terminal + file): mỗi đỉnh →
   `lại gần / trôi xa / khí cục bộ` → R, khoảng cách, nhánh tay xoắn
   → dòng cuối luôn là **"Vị trí của chúng ta"**
4. Tự lưu vào thư mục `observations/`: `.csv` (số liệu), `.png` (đồ thị),
   `_analysis.txt` (bảng phân tích) — kèm vị trí + thời điểm quan sát
Muốn đo hướng khác: **đổi l, b rồi bấm Quan sát lại** (không cần Chuẩn bị lại).

### 10. Nút `Thoát` — đóng app khi xong.

---

## C. Thanh công cụ đồ thị (nằm ngay trên đồ thị)
Từ trái sang: **Home** (về mặc định) · **Back/Forward** (lùi/tiến vùng zoom) ·
**Pan** (kéo) · **Zoom** (kéo ô để zoom) · **Save** (lưu ảnh PNG thủ công).

**Nút `MOCK (giả lập)` ở ĐẦU BÊN PHẢI của thanh này** — bật/tắt thiết bị giả lập:
* **Bật** (ô có màu hồng): app chạy với thiết bị GIẢ — mọi màn hình/tiêu đề/đều
  ghi `[MOCK]`/`[GIẢ LẬP MOCK]`; dùng để tập nút, demo, không cần phần cứng.
* **Tắt** (mặc định): thiết bị THẬT — không cắm SDR thì báo lỗi
  `Could not open SDR (device index = 0)` y như app gốc.
* **Đổi trạng thái → phải bấm `Chuẩn bị` lại** (hiệu chuẩn cũ bị vô hiệu hoá).

## D. Thanh trạng thái (dưới cùng)
Hiện bước app đang làm / kết quả vừa xong / lỗi (nếu có). Khi thấy chữ lạ → đọc ở đây trước.

---

## E. Chạy từ dòng lệnh (tuỳ chọn)
```bash
python tabletop_app.py --language Vietnamese        # giao diện tiếng Việt
python tabletop_app.py --mock --demo                # thử KHÔNG cần phần cứng (phổ giả lập)
python tabletop_app.py --data <file.fits|csv>       # mở app + tự nạp file
python tabletop_app.py --selftest                   # kiểm tra nhanh, không mở cửa sổ
```
Thứ tự khuyến nghị cho buổi đầu: `--mock --demo` (quen nút) → `--data sample_data/...`
(quen phân tích) → chạy thật với RTL-SDR (Chuẩn bị → Quan sát).

## F. Xử lý nhanh khi gặp sự cố
| Hiện tượng | Xử lý |
|---|---|
| Chuẩn bị báo `Could not open SDR (device index = 0)` và Device Manager hiện **`Bulk-In, Interface`** lỗi | **Thiếu driver WinUSB**: mở `zadig-2.9.exe` trong thư mục app → Options ▸ List All Devices → chọn `Bulk-In, Interface 0` (USB ID 0BDA:2838) → chọn **WinUSB** → Install Driver → cắm lại USB |
| Bấm Quan sát báo "Vui lòng chạy bước Chuẩn bị trước!" | Bấm **Chuẩn bị** trước |
| Tiêu đề/màn hình có chữ **[MOCK]** / **[GIẢ LẬP MOCK]** | Đang bật chế độ giả lập (nút `MOCK` trên thanh công cụ hoặc `--mock`) — số liệu là GIẢ LẬP, không phải đo thật |
| Chuẩn bị báo lỗi `Could not open SDR (device index = 0)` (như app gốc) | Chưa cắm USB SDR / thiếu thư viện `pyrtlsdr` / thiếu driver (Zadig) → cắm thiết bị, hoặc **bật nút `MOCK`** trên thanh công cụ để thử |
| Chuẩn bị "hoàn tất" nhưng phổ Quan sát méo, kỳ lạ | Có thể đã chạy Chuẩn bị khi **chưa gắn terminator** → nền sai → bấm Chuẩn bị lại với terminator đã gắn |
| Báo "Không đủ công suất RF" | Kiểm tra terminator/anten/LNA, cáp |
| Ảnh hưởng của vị trí: cảnh báo "KHÁC vị trí hiện tại" | Bình thường khi nạp dữ liệu nơi khác — app đã tự chỉnh đúng nơi sinh ra phép đo |
| Muốn hiệu chỉnh theo vị trí mới | Bấm **Tự động tìm vị trí (IP)** hoặc nhập tay lat/lon |
