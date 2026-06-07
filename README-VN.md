# Nexus-KB

Nexus-KB là kiến trúc tham chiếu mã nguồn mở cho Enterprise RAG và Knowledge Graph Engine, kết hợp MCP connector, workflow AI có kiểm soát và vector search có tính sẵn sàng cao.

Kho mã hiện ở giai đoạn tài liệu kiến trúc và nền tảng. Thành phần có thể chạy ngay là demo cụm Qdrant nhiều node trong thư mục `qdrant-multi-node-cluster/`.

## Mục tiêu

- Chuẩn hóa kiến trúc ingest tài liệu, semantic search, trích xuất thực thể, Knowledge Graph, audit và human review.
- Định nghĩa rõ quy tắc cho AI coding agent để hạn chế sinh code lệch kiến trúc hoặc thiếu kiểm thử.
- Cung cấp demo Qdrant HA để kiểm thử hành vi vector database trong môi trường local.
- Giữ tiêu chuẩn open-source: tài liệu rõ, không commit secret/runtime data, có hướng dẫn đóng góp và báo cáo bảo mật.

## Tài liệu chính

- [README.md](README.md): tổng quan chính của dự án.
- [docs/action.md](docs/action.md): chiến lược, roadmap và kế hoạch thực hiện Nexus-KB.
- [docs/architecture.md](docs/architecture.md): kiến trúc nguồn chuẩn.
- [AGENTS.md](AGENTS.md): quy tắc vận hành cho AI agent và contributor.
- [CONTRIBUTING.md](CONTRIBUTING.md): hướng dẫn đóng góp.
- [SECURITY.md](SECURITY.md): chính sách báo cáo lỗ hổng.
- [qdrant-multi-node-cluster/README.md](qdrant-multi-node-cluster/README.md): hướng dẫn chạy demo Qdrant.

## Nguyên tắc repository

- Không commit secret, token, log, session, dữ liệu khách hàng, raw document, model weight hoặc snapshot database.
- Dùng `.gitkeep` để giữ các thư mục placeholder cần tồn tại nhưng chưa có source code.
- Mọi thay đổi kiến trúc nên cập nhật `docs/architecture.md` trước, sau đó mới cập nhật README hoặc rule liên quan.
