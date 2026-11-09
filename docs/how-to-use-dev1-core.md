# DEV1 Core — Hướng dẫn DEV2/DEV3 (bản đối chiếu Phase 1)

**Phạm vi:** hướng dẫn bắt đầu dùng Core **đồng bộ**. Ví dụ dưới đây **không phải** mô hình M/M/1 hoàn chỉnh, không tạo dữ liệu metrics cuối cùng.

## 1. Chuẩn bị thư mục

```text
D:\SPE\
├── bkitevsim\        # framework giảng viên cung cấp; có trên máy mỗi người
├── spe_core\         # code DEV1
├── docs\             # hai tài liệu Markdown
└── tests\            # test DEV1
```

`bkitevsim/` bị `.gitignore` bỏ qua. Sau khi clone GitHub, mỗi người phải tự đặt thư viện giảng viên cung cấp đúng vị trí; đừng mặc định thư viện tự xuất hiện.

## 2. Kiểm thử Core hiện tại

Mở PowerShell tại `D:\SPE`:

```powershell
py -m unittest discover -s tests -p "test_spe_*.py" -v
```

Kết quả trên ZIP được kiểm tra: `Ran 8 tests ... OK`. Test `tests/test_event_queue.py` **cố ý tái hiện lỗi LadderQueue gốc** và không thuộc tập 8 test trên.

## 3. Ví dụ LP đồng bộ tối thiểu

Tạo file `try_dev1_core.py` ở **thư mục gốc** của repo và dán:

```python
from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_process import BkSysLogicalProcess
from spe_core.dispatcher import SpeSequentialDispatcher

class ExampleStation(BkSysLogicalProcess):
    def initialize(self):
        self.send_event(Event(
            timestamp=1.0,
            sender_id=self.lp_id,
            receiver_id=self.lp_id,
            event_type="EXTERNAL_ARRIVAL",
            payload={"request_id": 1, "station_id": self.lp_id, "arrival_time": 1.0},
        ))

    def handle_event(self, event):
        if event.event_type == "EXTERNAL_ARRIVAL":
            self.send_event(Event(
                timestamp=2.0,
                sender_id=self.lp_id,
                receiver_id=self.lp_id,
                event_type="SERVICE_COMPLETE",
                payload={"request_id": 1, "station_id": self.lp_id, "server_id": 0},
            ))
        elif event.event_type == "SERVICE_COMPLETE":
            print("Request", event.payload["request_id"],
                  "completed at", event.timestamp)

sim = Simulation(
    options=SimulationOptions(end_time=1000.0),
    models={"example": ExampleStation},
)
sim.create_lp(lp_id=0, model_name="example")

# Quan trọng: Simulation không tự chọn SpeSequentialDispatcher.
sim.dispatcher = SpeSequentialDispatcher(end_time=sim.options.end_time)
stats = sim.run()

print("events_processed =", stats["events_processed"])
print("last_event_time =", sim.dispatcher.current_time)
print("observation_end =", sim.options.end_time)
```

Chạy:

```powershell
py try_dev1_core.py
```

Kết quả chính (có thể kèm dòng logging):

```text
Request 1 completed at 2.0
events_processed = 2
last_event_time = 2.0
observation_end = 1000.0
```

**Phân biệt:** 2 event được xử lý **không có nghĩa** đã xong 2 request. `last_event_time = 2` **không thay thế** mốc đo metrics `T = 1000`.

## 4. Khi DEV2 viết mô hình thực tế

1. Tạo LP kế thừa `BkSysLogicalProcess`, cài `initialize()` và `handle_event()`.
2. Theo PDF Phase 1: FCFS, exponential arrival/service, K bao gồm chờ + phục vụ, mô hình không có chỗ chờ phải reject đúng quy tắc.
3. Sử dụng ba event type đã thống nhất theo DES1: `SERVICE_COMPLETE`, `TRANSFER_ARRIVAL`, `EXTERNAL_ARRIVAL`.
4. Duy trì cùng `request_id` khi chuyển từ A sang B. Phân biệt arrival ở hệ thống và arrival ở từng station để tính response toàn mạng.
5. Cung cấp timestamp, counters và trạng thái thay đổi của trạm cho DEV3 theo **cơ chế collector sẽ thống nhất khi tích hợp**. Chưa có API mặc định cho collector trong Core DEV1.

## 5. Khi DEV3 tích hợp

- Lấy `stats["events_processed"]` từ core cho **số event được xử lý**.
- Lấy `sim.options.end_time` cho **T = 1000**; không lấy `sim.dispatcher.current_time` làm mẫu số nếu event cuối sớm hơn T.
- Lấy request records, số arrival/rejection/completion và trạng thái chờ/bận từ DEV2 để tính metrics theo Phase 1.
- Tính trung bình queue length và utilization bằng tích phân trạng thái đến T; ghi cả số request còn trong hệ thống tại T.
- JSON đầu vào/đầu ra và địa điểm lưu kết quả **chưa có schema/owner chính thức**, cần ghi lại khi ba DEV ghép code.

## 6. Trạng thái chưa hoàn thiện

Core đồng bộ **đủ để DEV2 bắt đầu**, nhưng **chưa phải nghiệm thu toàn hệ thống**. `SpeCoEventLoop` hiện mới có test sắp sự kiện, wait theo simulation time và message cơ bản. Phần non-blocking/notification, timeout, cancellation, task failure/communication failure theo PDF Phase 1 cần kiểm thử và tích hợp tiếp ở DV-03/DV-04.

Không merge branch DEV1 vào `main` như thể toàn bộ ứng dụng đã hoàn chỉnh trước khi có kiểm thử với DEV2/DEV3.
