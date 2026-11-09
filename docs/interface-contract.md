# SPE-CC-00A — Interface Contract DEV1 ↔ DEV2 ↔ DEV3

**Bản rà soát 09/11/2026 — dựa trên bản Phase 1 đã nộp.**

> **Nguồn bắt buộc:** `Spe-Ass-Spec-SPE-CC-00A.pdf` (Phase 1, trang nội dung 1–3).  
> **Nguồn quy ước code:** thiết kế DES1 chi tiết và trao đổi DEV1–DEV2–DEV3.  
> Phân biệt rõ **[P1] có trong PDF**, **[AGREED] nhóm/DEV đã thống nhất**, **[TODO] cần triển khai/kiểm tra**, **[OPEN] chưa chốt**. Các quy ước kỹ thuật không phải là yêu cầu nguyên văn của PDF.

## 1. Giao tiếp giữa ba DEV — đọc phần này trước

| Người | Trách nhiệm | Tình trạng |
|---|---|---|
| **DEV1** (Core) | `EventQueue`, `SpeSequentialDispatcher`, đồng hồ thời gian mô phỏng và `events_processed`; tiếp tục coroutine/timeout/cancellation/error handling | Core đồng bộ có test; phần bất đồng bộ chưa hoàn tất |
| **DEV2** (Model) | Viết sáu mô hình hàng đợi, mạng A → B; xử lý arrival/service/rejection, quản lý request và state | Chưa có trong ZIP kiểm tra |
| **DEV3** (Metrics/Experiment) | Nhận mốc thời gian, bộ đếm, trạng thái; tính metrics và chạy thí nghiệm | Chưa có trong ZIP kiểm tra |

**[AGREED]** DEV2 dùng `BkSysLogicalProcess` (LP đồng bộ) và `SpeSequentialDispatcher` của DEV1 để chạy mô hình DES. **Điều này không tự động hoàn thành yêu cầu bất đồng bộ của đề**: PDF Phase 1 còn mô tả non-blocking, notification, timeout, cancellation và communication failure. DEV1 cần kiểm thử và nhóm cần thể hiện phần này trong sản phẩm tích hợp (**[TODO]**).

## 2. Event và payload

**[P1]** Dispatcher lấy event có thời gian sớm nhất; thời gian mô phỏng không được đi lùi. Mỗi event dùng lớp `Event` của `bkitevsim`:

| Trường | Ý nghĩa |
|---|---|
| `timestamp` | Thời điểm theo **thời gian mô phỏng** |
| `sender_id`, `receiver_id` | ID của LP gửi và nhận |
| `event_type` | Loại sự kiện |
| `payload` | Dữ liệu gắn với sự kiện; DEV2/DEV3 sử dụng |

**[AGREED — DES1, không quy định tên trong PDF]** Ba chuỗi sự kiện:

1. `SERVICE_COMPLETE` (ưu tiên 0)
2. `TRANSFER_ARRIVAL` (ưu tiên 1)
3. `EXTERNAL_ARRIVAL` (ưu tiên 2)

Sắp thứ tự theo `timestamp` → ưu tiên loại event → thứ tự thêm vào nếu cùng thời gian và loại. Các event type khác hiện nhận ưu tiên mặc định (3); **không tự xem quy tắc timeout mới là đã chốt**.

**[AGREED — DEV2 đề xuất, PDF không ấn định schema]** Các trường payload dùng chung khi phù hợp:

| Trường | Ý nghĩa |
|---|---|
| `request_id` | ID request (giữ nguyên khi chuyển A → B) |
| `station_id` | Trạm hiện tại |
| `arrival_time` | Thời điểm đến; mạng hai trạm cần phân biệt đến hệ thống và đến từng trạm |
| `service_time` | **Thời lượng** phục vụ, không phải thời điểm bắt đầu |
| `server_id` | Server được phân công, có thể chưa tồn tại lúc arrival |

**Không bắt buộc cả năm trường ở mọi event.** DEV1 định tuyến bằng metadata của `Event`, không tính metrics từ payload. `service_start_time` và `completion_time` cần được ghi nhận tại request/state/collector để DEV3 tính các chỉ số, nhưng không bắt buộc nằm trong mọi payload.

## 3. Dữ liệu DEV3 cần để tính metrics — theo PDF Phase 1, trang nội dung 2

| Chỉ số [P1] | Dữ liệu cần có |
|---|---|
| Waiting time `Wq` | arrival → service start của **request đã hoàn thành** |
| Response time `R` | arrival → departure của **request đã hoàn thành** |
| Throughput `X = C / T` | số hoàn thành `C`, thời gian quan sát `T` |
| Average queue length `Lq` | tích phân `Q(t)` trên toàn bộ `[0, T]` |
| Utilization `U` | tích phân số server bận `B(t)` trên `[0, T]`, chia `cT` |
| Rejection probability `D / A` | số bị từ chối và tổng số đến |
| Unfinished at stop | số request còn trong hệ thống tại `T` |

**Ngoại lệ [P1]:** M/M/∞ không có utilization với số server cố định; request được chấp nhận trong M/M/∞ và M/M/n/n không phải chờ; với mạng A → B phải tính response/wait toàn mạng và queue/utilization **riêng từng trạm**, count hoàn thành tại đầu ra B.

**[OPEN]** Cơ chế DEV2 gửi record/counters/snapshot cho DEV3 (callback, collector hay state access), ai đọc/ghi JSON và schema chính thức vẫn chưa được xác nhận. **Không coi các trường đó là API đã triển khai.**

## 4. Cách dùng Core đồng bộ hiện có

```python
from bkitevsim.core import Simulation, SimulationOptions
from spe_core.dispatcher import SpeSequentialDispatcher

# QueueLP do DEV2 cung cấp, kế thừa BkSysLogicalProcess.
sim = Simulation(
    options=SimulationOptions(end_time=1000.0),
    models={"queue": QueueLP},
)
sim.create_lp(lp_id=0, model_name="queue")

# Gán dispatcher DEV1 trước sim.run().
sim.dispatcher = SpeSequentialDispatcher(end_time=sim.options.end_time)
stats = sim.run()

processed_events = stats["events_processed"]
last_event_time = sim.dispatcher.current_time
observation_end = sim.options.end_time
```

`events_processed` đếm **event được xử lý**, không phải request hoàn thành. `last_event_time` **không nhất thiết bằng** `observation_end`: DEV3 dùng `T = 1000` cho mẫu số và tích phân đến hết cửa sổ quan sát. Core **chưa tự đọc config JSON hoặc xuất kết quả JSON**.

Chi tiết từng bước xem `how-to-use-dev1-core.md`.

## 5. Quy định thí nghiệm PHẢI theo PDF đã nộp [P1, trang nội dung 1–3]

- Mô hình: M/M/1, M/M/1/K, M/M/∞, M/M/n/n, M/M/c, M/M/c/K và mạng **Source → A → B → Exit** (A, B đều M/M/1).
- Interarrival và service độc lập, phân phối exponential; **FCFS**.
- Với hệ hữu hạn, **K = tổng request trong hệ thống (đang chờ + đang phục vụ)**; M/M/n/n dùng K = n và **không có chỗ chờ**.
- `λ = 0.3, 0.6, 0.9`; `μ = 1.0` cho **mỗi server** (cả mỗi trạm A/B); `c/n = 1, 2`; `K = 2, 5` khi mô hình áp dụng.
- Mỗi trường hợp chạy **5 lần**, mỗi lần **T = 1000**; hệ thống bắt đầu **rỗng**, đo **từ t = 0**, **không warm-up**.
- Năm random seeds phải **khác nhau giữa các lần chạy** và **dùng lại cùng danh sách** giữa các cấu hình so sánh. **[OPEN]** PDF không ấn định 5 số seed cụ thể.
- Waiting/response chỉ tính trên **request được chấp nhận và hoàn thành trong cửa sổ quan sát**; thống kê thêm request đang dở tại thời điểm dừng. **Không tự cho request chạy tiếp sau T để tính hai chỉ số này.**

## 6. Trạng thái thực tế và điều kiện bàn giao

**Đã kiểm tra trên `SPE(1).zip`:** `EventQueue`, `SpeSequentialDispatcher`, `SpeCoEventLoop` bản đầu; chạy `py -m unittest discover -s tests -p "test_spe_*.py" -v` được **8 PASS**. Chưa có model M/M thực tế, collector, tích hợp JSON và các test đầy đủ cho lỗi coroutine/timeout/cancellation.

**Có thể bàn giao cho DEV2 ngay:** Core **đồng bộ** làm nền triển khai. **Chưa thể xác nhận toàn bộ Phase 1 đã được hiện thực hóa hoặc hệ thống sẵn sàng nộp Phase 2.** Khi tích hợp cần kiểm tra thêm: mô hình FCFS/K, collector `Q(t)`/`B(t)` đến T, routing A → B, báo lỗi receiver không tồn tại, và luồng bất đồng bộ thực sự.
