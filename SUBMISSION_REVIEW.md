# Kiểm tra trước khi nộp

Ngày: 09/10/2026, Asia/Saigon. Phạm vi: code, 15 artifact đã sinh và repo public hiện có. Đây là bản ghi kiểm tra, không phải xác nhận điểm số.

## Kiểm tra tự động

- self_check.py: 5/5 topic OK, git/secrets OK, READY to submit.
- unittest: 27/27 test đạt.
- pip check: No broken requirements found.
- Mọi meta: >=3 task calls, 4 source families; n_sources và source_families khớp sources.json.
- Cấu trúc báo cáo: TL;DR, Background, 5–6 themes, Trends and open problems, References.
- Mọi citation có source, mọi source được trích dẫn, đúng một reference line/source và URL khớp.
- Mọi source family được đối chiếu với quy tắc ID/URL trong code; không đổi nhãn chỉ từ tên miền.
- File cho sẵn model.py/sandbox.py/self_check.py/finalize_citations.py không đổi so với HEAD của đề (so sánh bỏ khác biệt CRLF/LF).
- Scan file chuẩn bị nộp và 5 commit lịch sử trước commit bài: không match mẫu khóa của self_check; .env/.venv bị ignore. Pattern scan có giới hạn.
- GitHub API xác nhận origin public, default branch main. Trạng thái commit/push cuối được xác nhận sau khi đóng gói.

## Đối chiếu 25 nguồn mẫu

Chọn 5 nguồn/báo cáo: ưu tiên nguồn cũ nhất có ngày, nguồn mới nhất có ngày, HF daily, HF search, web; bổ sung nếu lựa chọn trùng. Tất cả 25 URL lấy được nội dung qua web_fetch. Đọc abstract hoặc văn bản lấy được; đọc thêm PDF chính chủ cho chi tiết PPO, InstructGPT, Toolformer và FVD không có đầy đủ trong abstract.

Bảng chỉ xác nhận **mệnh đề liên quan đến nguồn cụ thể** bên dưới. Một câu tổng hợp trích dẫn nhiều nguồn cần kết hợp các nguồn đó; bảng không xác nhận mọi phần của cả câu hay mọi claim trong survey. Không kiểm chứng đầy đủ kết quả thực nghiệm bằng việc chạy lại mô hình nghiên cứu. Riêng mẫu VBench xác nhận cấu trúc 16 chiều và human annotations, không đo lại mức tương quan.

| Báo cáo | Citation | Nguồn | Mệnh đề đã đối chiếu |
|---|---:|---|---|
| efficient | [18] | [DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter ](https://huggingface.co/papers/1910.01108) | DistilBERT dùng distillation để giảm kích thước và giữ phần lớn khả năng hiểu ngôn ngữ. |
| efficient | [3] | [Tailoring the Quantization Space for 1-Bit KV Cache Compression ](https://arxiv.org/abs/2610.03027) | TaSQ nhắm vào suy giảm chất lượng của KV-cache vector quantization ở chế độ 1-bit. |
| efficient | [20] | [The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits ](https://huggingface.co/papers/2402.17764) | BitNet b1.58 dùng trọng số ternary và báo cáo parity theo model size/training tokens. |
| efficient | [11] | [A Survey of Small Language Models ](https://huggingface.co/papers/2410.20011) | Survey SLM bao quát kiến trúc, huấn luyện và compression cho tài nguyên hạn chế. |
| efficient | [7] | [vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention ](https://blog.vllm.ai/2023/06/20/vllm.html) | Blog vLLM báo cáo fragmentation, tối đa 24x so với HF và 3.5x so với TGI trong benchmark riêng. |
| llm | [1] | [MRKL Systems: A modular, neuro-symbolic architecture that combines large language models, external knowledge sources and discrete reasoning ](https://arxiv.org/abs/2205.00445) | MRKL kết hợp model ngôn ngữ với các module kiến thức và suy luận rời rạc. |
| llm | [16] | [Learn2Play Bench: How Well Do LLM Agents Learn from Experience in Unfamiliar Environments? ](https://huggingface.co/papers/2610.08215) | Learn2Play đánh giá retention và ảnh hưởng của harness khi giữ nguyên backbone. |
| llm | [8] | [MCPToolBench++: A Large Scale AI Agent Model Context Protocol MCP Tool Use Benchmark ](https://huggingface.co/papers/2508.07575) | MCPToolBench++ thu thập hơn 4k server và hơn 40 category theo mô tả tác giả. |
| llm | [3] | [ReAct: Synergizing Reasoning and Acting in Language Models ](https://arxiv.org/abs/2210.03629) | ReAct đan xen reasoning và action để thu thập thông tin từ môi trường. |
| llm | [2] | [Toolformer: Language Models Can Teach Themselves to Use Tools ](https://arxiv.org/abs/2302.04761) | Toolformer sinh, thực thi và lọc API call theo cải thiện dự đoán token; đã đọc thêm PDF mục 2. |
| reinforcement | [1] | [Proximal Policy Optimization Algorithms ](https://arxiv.org/abs/1707.06347) | PPO dùng clipped surrogate và nhiều epoch minibatch; đã đối chiếu PDF mục 3/5. |
| reinforcement | [11] | [Learning to Steer, Steering to See: Unveiling the Geometry of RLVR in Large Language Models via Trainable Vectors ](https://huggingface.co/papers/2609.34344) | Nghiên cứu RLVR dùng vector steering và mô tả effective manifold dung lượng thấp. |
| reinforcement | [6] | [Reward Under Attack: Analyzing the Robustness and Hackability of Process Reward Models ](https://huggingface.co/papers/2603.06621) | PRM hacking study báo cáo reward >0.9, accuracy <4% và stylistic shortcuts 43%. |
| reinforcement | [2] | [Training language models to follow instructions with human feedback (InstructGPT) ](https://arxiv.org/abs/2203.02155) | InstructGPT dùng SFT, reward model, PPO và per-token KL penalty; PDF mục 3.5 xác nhận penalty. |
| reinforcement | [3] | [Direct Preference Optimization: Your Language Model is Secretly a Reward Model ](https://arxiv.org/abs/2305.18290) | DPO giải bài toán preference bằng classification loss, không cần sampling trong fine-tuning. |
| video | [24] | [Towards Accurate Generative Models of Video: A New Metric & Challenges ](https://arxiv.org/abs/1812.01717) | FVD dùng I3D/Kinetics, xét temporal coherence và human study; đã đọc thêm PDF mục 1/2. |
| video | [19] | [Real-Time Joint Audio-Video Generation by Parallel Adapter Composition ](https://arxiv.org/abs/2610.10343) | Parallel adapter composition hỗ trợ joint audio-video streaming và few-step generation. |
| video | [10] | [Semantic Generative Tuning for Unified Multimodal Models ](https://huggingface.co/papers/2605.18714) | SGT dùng segmentation proxy để nối understanding và visual generation. |
| video | [13] | [VBench: Comprehensive Benchmark Suite for Video Generative Models ](https://huggingface.co/papers/2311.17982) | VBench có 16 chiều đánh giá và human preference annotations; mẫu xác nhận mệnh đề về cấu trúc benchmark. |
| video | [1] | [Video generation models as world simulators ](https://openai.com/index/video-generation-models-as-world-simulators/) | Bài Sora mô tả transformer trên spacetime patches của video/image latent codes. |
| world | [1] | [World Models ](https://arxiv.org/abs/1803.10122) | World Models học biểu diễn và policy trong môi trường tưởng tượng rồi transfer ra môi trường thật. |
| world | [30] | [Multi-Agent Egocentric World Model with Fine-Grained Embodied Interaction ](https://huggingface.co/papers/2610.12299) | ME-World tạo ego streams đồng bộ cho nhiều agent với tương tác fine-grained. |
| world | [29] | [SPW-Nav: A Streaming Panoramic World Model for Language-Guided Navigation ](https://huggingface.co/papers/2610.08941) | SPW-Nav báo cáo streaming một phút video 2K 360° và điều khiển bằng chỉ dẫn ngôn ngữ. |
| world | [10] | [MoWM: Mixture-of-World-Models for Embodied Planning via Latent-to-Pixel Feature Modulation ](https://huggingface.co/papers/2509.21797) | MoWM kết hợp latent/pixel representation và báo cáo task success trên CALVIN. |
| world | [2] | [Learning Latent Dynamics for Planning from Pixels ](https://arxiv.org/abs/1811.04551) | PlaNet học latent dynamics và lựa chọn hành động bằng online planning. |

## Tính toàn vẹn artifact

SUBMISSION_MANIFEST.json ghi SHA-256 và số byte của đủ 15 file. Kiểm tra cuối phải khớp manifest. Không sửa nội dung survey/sources trong quá trình chuẩn bị nộp. .gitattributes giữ nguyên line endings của artifact trong git.

## Phần chấm thủ công còn lại

Giảng viên dùng validator riêng và có thể chọn citation khác, chạy lại một topic hoặc đánh giá độ sâu của tổng hợp. Đạt self-check và kiểm mẫu không đồng nghĩa chắc chắn đạt 100 điểm. Rubric không yêu cầu reflection riêng; LAB_REPORT.md có reflection kỹ thuật bổ sung dựa trên kết quả thực tế.
