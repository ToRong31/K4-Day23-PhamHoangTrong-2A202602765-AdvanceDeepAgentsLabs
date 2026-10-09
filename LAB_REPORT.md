# Báo cáo tổng kết thực hành Deep Research Agent

**Sinh viên:** Phạm Hoàng Trọng — 2A202602765.
**Ngày kiểm tra:** 09/10/2026 (Asia/Saigon).
**Bài:** thực hành cá nhân Advanced Deep Agents; yêu cầu theo [RUBRIC.md](RUBRIC.md).

## 1. Mục tiêu và phạm vi

Triển khai một chương trình Python nhận chủ đề, tự lập kế hoạch, giao các câu hỏi nghiên cứu cho subagent, tìm tài liệu qua nhiều nguồn, rồi viết survey tiếng Anh có trích dẫn kiểm tra được. Bài sử dụng LLM có sẵn hỗ trợ tool calling, không huấn luyện model mới. Phần nộp gồm mã nguồn và năm bộ báo cáo trong `reports/`.

Báo cáo tổng kết này ghi nhận cách triển khai và kết quả từ artifact thực tế. Đây là tài liệu bổ sung; rubric không yêu cầu reflection riêng. Nội dung survey và sources nộp không được sửa tay trong quá trình kiểm tra cuối.

## 2. Thiết kế và công nghệ

Luồng chính: `research.py` đọc chủ đề → `make_model()` tạo LLM → `open_sandbox()` mở backend → upload validator/finalizer → lead lập kế hoạch bằng `write_todos` → giao `task` cho researcher → đọc ghi chú → tổng hợp sources và thân báo cáo → finalizer/normalizer/validator → kiểm tra mẫu → download ba artifact.

| Thành phần | Cài đặt và chức năng |
|---|---|
| Deep Agents 0.7.21 | Agent có công cụ file, task cho subagent và execute khi backend là sandbox |
| LangChain / LangGraph | Tool schema, middleware và graph điều phối; Deep Agents dùng framework này bên dưới |
| LLM | `deepseek/deepseek-flash` trong metadata; kết nối qua model.py và cấu hình riêng ở .env |
| HTTPX 0.28.1 | HTTPS gọi arXiv, HF và Exa MCP trên host |
| arXiv | Atom XML, chuẩn hóa id và URL, newest-first, throttle có lock |
| Hugging Face | Daily Papers và topic search, JSON compact, summary ngắn |
| Exa MCP | HTTP POST JSON-RPC, giải mã JSON/SSE, phát hiện throttling dù HTTP 200 |
| Daytona / Docker | Backend hỗ trợ lưu file, upload/download, execute; Docker là phương án thay thế |
| Python standard library | Regex, JSON, thống kê, hash, staging file và validator chạy trong sandbox |
| unittest + mock | 27 regression test offline, không tiêu token LLM |

Các tệp triển khai: `tools.py`, `agents.py`, `research.py`, `check_citations.py`. `model.py`, `sandbox.py`, `self_check.py`, `finalize_citations.py` giữ nguyên bản đã commit trong bộ đề.

### 2.1 Phân vai và hợp đồng dữ liệu

Lead chia ít nhất ba câu hỏi độc lập, prompt yêu cầu phát nhiều task trong cùng lượt để hỗ trợ song song. Researcher chỉ nhận thông điệp giao việc, vì vậy lead phải gửi đủ chủ đề, câu hỏi, họ nguồn, đường dẫn ghi chú riêng và định dạng. Researcher ghi nguồn, URL, ngày, bằng chứng và giới hạn. Citation-checker dùng web_fetch để đánh giá claim bằng SUPPORTED/PARTIAL/UNSUPPORTED/UNVERIFIABLE.

Mỗi source có n, id, url, title, date, source. Nhãn source phản ánh công cụ phát hiện nguồn: arxiv/hf-daily/hf-search/web. Tài liệu arXiv tìm qua web có thể mang nhãn web. Không suy ra công cụ phát hiện chỉ từ tên miền.

### 2.2 Retry và an toàn

RetryableError phân biệt lỗi tạm thời với lỗi lập trình/HTTP không nên thử lại. with_retry dùng Retry-After hoặc backoff lũy thừa có jitter, chặn bởi cap, không ngủ sau lần cuối. Lock bảo đảm các lời gọi arXiv từ nhiều researcher cách nhau ít nhất ba giây. Mỗi tool trả chuỗi dữ liệu, NO RESULTS hoặc ERROR; khóa trong lỗi được che trước khi đưa cho agent.

Khóa và công cụ mạng ở host. Sandbox chỉ nhận script, ghi chú và báo cáo. Prompt coi nội dung nguồn là dữ liệu không đáng tin, không làm theo chỉ dẫn trong trang web và không thêm số liệu từ trí nhớ. open_sandbox dọn tài nguyên khi kết thúc hoặc lỗi.

### 2.3 Kiểm tra đầu ra

Finalizer sinh References, gộp URL trùng, loại nguồn không trích dẫn và đánh số theo thứ tự xuất hiện. Validator kiểm tra source rỗng, số/URL trùng, trích dẫn thiếu nguồn, nguồn không được dùng, dòng References thiếu/trùng và URL không khớp. Validator bỏ qua code/link Markdown và hiểu citation nhóm/range.

Sau lỗi ID–URL của Hugging Face trong một lượt chạy, đã bổ sung chuẩn hóa tương đương (version suffix, id là URL, trailing slash) và kiểm tra identity ngay trong sandbox bằng `--normalize`. Nếu id thật sự là bài khác hoặc URL sai family thì từ chối, không tự đoán nguồn. References được sinh lại trước khi validator in OK; bytes tải về được lưu nguyên vẹn.

Chương trình chính chạy validator trong sandbox và kiểm tra lại đầu ra, source families và task count. Artifact được staging rồi thay file; lỗi ghi có rollback. Cơ chế này không phải giao dịch nguyên tử nếu tiến trình bị kill giữa nhiều lần thay file.

### 2.4 Giới hạn thực thi

Lead: 150 model calls, 300 tool calls, tối đa 12 task calls. Researcher: 40/60. Checker: 15/20. Lead graph có recursion_limit=1000. Các giới hạn này không phải hard cap về token, tiền hay wall-clock. Metadata đếm task của lead, gồm cả checker, không phải số researcher độc lập.

## 3. Kết quả năm chủ đề

| Chủ đề / artifact | Nguồn | Task calls | Themes | Phút | Phạm vi ngày nguồn có ngày |
|---|---:|---:|---:|---:|---|
| [survey about efficient inference and small language models](reports/survey-about-efficient-inference-and-small-language-models.md) | 25 | 8 | 5 | 14.0 | 2019-10-02 → 2026-10-02 |
| [survey about LLM agents and tool use](reports/survey-about-llm-agents-and-tool-use.md) | 21 | 6 | 5 | 8.0 | 2022-05-01 → 2026-10-07 |
| [survey about reinforcement learning for LLM reasoning](reports/survey-about-reinforcement-learning-for-llm-reasoning.md) | 26 | 7 | 6 | 30.8 | 2017-07-20 → 2026-09-28 |
| [survey about video and multimodal generation](reports/survey-about-video-and-multimodal-generation.md) | 25 | 7 | 6 | 56.9 | 2019-03-27 → 2026-10-07 |
| [survey about world model](reports/survey-about-world-model.md) | 44 | 12 | 5 | 16.3 | 2018-05-09 → 2026-10-08 |

Mỗi báo cáo có đủ bốn họ nguồn, TL;DR, Background, 3–6 themes, Trends and open problems và References. Các nguồn có ngày trong mỗi báo cáo bao gồm tài liệu nền tảng và tài liệu trong hai năm gần nhất. Ngày trong sources là metadata của nguồn, không chứng minh ngày truy xuất hay ngày xuất bản chính xác của mọi phiên bản.

Tổng: **141 mục nguồn** theo từng báo cáo; chưa deduplicate giữa các chủ đề. Tổng elapsed của năm lượt thành công: **7559.5 giây (126.0 phút)**, không tính những lượt thất bại hoặc thử tool riêng. Token lead: **7,181,105 input / 161,328 output**. Token subagent không nằm trong thống kê này; giá tiền còn phụ thuộc provider, cache và mức phí, nên không quy đổi thành tổng chi phí tiền.

Các survey so sánh nhiều hướng tiếp cận trong cùng theme. Ví dụ world models so sánh latent dynamics, video generation, feature-space models và evaluation; RL reasoning phân biệt optimizer, reward, data và infrastructure; agents phân biệt harness, training, benchmark và safety; video phân biệt backbone, multimodal interface, control, efficiency và metrics; efficient inference so sánh quantization, serving, small-model training và deployment.

## 4. Kiểm chứng và đối chiếu rubric

| Hạng mục | Bằng chứng hiện có | Giới hạn kết luận |
|---|---|---|
| Tools/retry (20 điểm) | Tool triển khai đủ; regression test transient error, backoff, throttle, SSE, redaction | API thật có thể thay đổi hoặc bị throttling khi giảng viên chạy lại |
| Agent/subagent (20 điểm) | Mọi meta có >=3 task và 4 nhãn; prompt lập kế hoạch, đủ ngữ cảnh, kiểm tra notes; middleware có giới hạn | Metadata task count không chứng minh lịch chạy song song; cần trace nếu muốn kiểm lịch thực thi |
| Sandbox (10 điểm) | Code upload và execute validator, file trong sandbox, download sau OK, cleanup trong with | Metadata không lưu đầy đủ trace sandbox; bằng chứng là code và các artifact |
| Citations (15 điểm) | Cả năm validator OK; 25 URL mẫu truy xuất được và đối chiếu mệnh đề liên quan | Không chứng minh mọi claim; giảng viên còn kiểm tra mẫu và dùng validator riêng |
| Chất lượng survey (25 điểm) | Đúng headings, 5–6 themes, tổng hợp so sánh, nguồn cũ/mới, mục vấn đề mở | Không tự gán điểm; độ chính xác và chiều sâu còn do giảng viên đánh giá |
| Repo (10 điểm) | README có setup/run/output; dependency check đạt; file cho sẵn giữ nguyên; secret-pattern scan không có match | Pattern scan không chứng minh tuyệt đối rằng không có bí mật thuộc định dạng khác |

Đã chạy `self_check.py`: cả 5 chủ đề và git/secrets đều OK, thông báo READY to submit. `unittest` có 27 test đạt; `pip check` báo không có dependency hỏng. Kiểm tra lịch sử local trước commit bài nộp có 5 commit, không phát hiện .env được track hoặc mẫu khóa của self_check. Repo origin đã được xác nhận public qua metadata GitHub ngày 09/10/2026.

Chi tiết nguồn mẫu: [SUBMISSION_REVIEW.md](SUBMISSION_REVIEW.md). Hash artifact: [SUBMISSION_MANIFEST.json](SUBMISSION_MANIFEST.json).

## 5. Reflection kỹ thuật — phần bổ sung

**Prompt rõ vẫn cần mã kiểm tra.** Lỗi HF cho thấy validator trích dẫn đạt chưa đủ: References có thể khớp URL nhưng metadata id lại lệch. Chuyển kiểm tra identity vào sandbox giúp agent thấy lỗi ngay; chỉ chuẩn hóa khi hai giá trị tương đương giúp tránh che giấu việc gán nhầm bài.

**LLM nên làm tổng hợp; quy tắc cấu trúc nên do Python thực hiện.** Việc đánh số nguồn và sinh References bằng finalizer giảm lỗi định dạng. Citation-checker phục vụ lớp ngữ nghĩa vì regex không biết claim có được nguồn hỗ trợ hay không. Việc kiểm tra mẫu vẫn cần giới hạn kết luận.

**Chi phí thực tế phải đọc từ nhiều tín hiệu.** Năm lượt thành công mất từ khoảng 8 đến 57 phút. Token của lead còn chưa gồm subagent, và số lượt gọi bị chặn không đồng nghĩa token ít. Ghi chú gọn, hạn chế kiểm chứng lặp và một bộ đếm token dùng chung là những cải tiến hợp lý cho phiên bản sau.

**Song song đòi hỏi tài nguyên dùng chung được kiểm soát.** Nhiều researcher cần file notes riêng; arXiv cần lock và throttle chung. Chia nhiệm vụ giúp phân tán tìm kiếm nhưng lead vẫn phải kiểm kết quả và provenance, tránh coi mọi subagent response là đúng.

**Đầu ra có thể kiểm tra lại quan trọng hơn một lần chạy thành công.** Ba artifact tách nội dung, provenance và execution metadata. Hash bảo vệ việc đối chiếu bản nộp, còn self_check tạo một bước kiểm tra lặp lại được trước khi nộp. Không sửa tay survey để giữ đúng yêu cầu đề.

## 6. Cách tái tạo và đọc bài nộp

Xem [README.md](README.md) để cài requirements, cấu hình riêng trong .env, chạy từng topic hoặc cả năm. Đọc báo cáo trực tiếp không cần API key. Kiểm tra offline:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe self_check.py
```

Phần nộp là public repo có mã nguồn và 15 artifact. Reflection ở đây là bổ sung, không thay thế năm survey và không được coi là yêu cầu bắt buộc của rubric.
