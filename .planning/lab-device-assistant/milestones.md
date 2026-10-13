# Implementation Milestones

Priorities use `P0` for graduation-critical work, `P1` for useful enhancements, and `P2` for optional extensions.

## M0: Lock Scope and Runtime Contract (P0)

Deliverables:

- Confirm Vue 3 as the final frontend; the former React prototype is removed and will not be extended.
- Add typed assistant event names and run status values.
- Define tool input/output schemas and mutation confirmation rule.
- Document the relational database and original-file storage boundary.

Acceptance:

- A single document describes the run lifecycle, tool lifecycle and terminal states.
- Backend tests can construct an Assistant run with fake repositories and fake tools.

## M1: Relational Document Ingestion (P0)

Deliverables:

- Persist uploaded files and document metadata.
- Add `document_chunks` and processing status fields.
- Make PDF/Markdown parsing preserve page and chapter metadata.
- Store document chunks and citation metadata in the relational database.
- Read document context directly from database records in the Assistant.

Acceptance:

- Uploading the sample manual creates one document row and its chunk rows.
- Assistant answers cite the expected document, chapter, and page when available.
- Uploading the same checksum is idempotent and does not duplicate document chunks.

## M2: Persistent Conversation Memory (P0)

Deliverables:

- Add conversations and conversation messages.
- Load recent messages and optional summary before each Assistant run.
- Persist user, assistant and tool-result messages.
- Add context budget and conversation isolation by user.

Acceptance:

- A follow-up question resolves “这个设备/刚才的故障” using prior context.
- Restarting FastAPI does not erase the conversation.
- A different conversation cannot read the first conversation's messages.

## M3: Tool Registry and Real Tool Execution (P0)

Deliverables:

- Define a registry of typed tools with descriptions, schemas and handlers.
- Implement `get_equipment` and `get_maintenance_history` against repositories/services; load manual contents from SQL as part of the Assistant context.
- Implement `create_work_order` with a confirmation boundary and real database write.
- Add precondition, timeout, error normalization and audit persistence.

Acceptance:

- An Assistant run shows tool start/end events and a persisted invocation row.
- A rejected or malformed tool call becomes a structured error result.
- Mutation tools execute only after an explicit confirmation path.

## M4: Assistant Loop and Observability (P0)

Deliverables:

- Refactor the LangGraph workflow into bounded classify/load-context/decide/act/observe/answer stages.
- Add a maximum step count and request timeout.
- Add `assistant_run` and `assistant_event` records.
- Expose JSON and SSE output; preserve final JSON response for tests.
- Add verification that checks loaded document evidence, citation shape and safety rules.

Acceptance:

- A run can execute a read tool, inspect its result and produce a final answer.
- Tool failure is visible in the event stream and persisted with terminal status.
- No run can loop beyond the configured step limit.

## M5: Vue Application (P0)

Deliverables:

- Create the Vue 3 + Vite + TypeScript + Pinia + Vue Router application.
- Implement login/session state, dashboard, equipment list/detail, document upload, chat, evidence panel and work orders.
- Connect chat to SSE and confirmation endpoint.
- Display document citations and tool lifecycle status.

Acceptance:

- A user can select equipment, ask a question, see evidence, confirm a work order and reload the conversation.
- Loading, empty, error and disconnected states are visible and recoverable.

## M6: Evaluation and Thesis Evidence (P0)

Deliverables:

- Replace fixed evaluation numbers with executable evaluators.
- Build a versioned dataset of representative equipment questions and expected citations/actions.
- Evaluate answer grounding, source accuracy, memory/tool/verification ablations, latency and tool-success measurements.
- Export JSON/CSV and charts used in the thesis.

Acceptance:

- A clean environment can run one documented command to reproduce evaluation results.
- Each reported metric links to a dataset, configuration and run output.

## M7: Deployment and Presentation (P1)

Deliverables:

- Docker Compose for PostgreSQL, backend and Vue frontend.
- Seed data and one-command document initialization.
- API, architecture, database and demo documentation.
- Known limitations and future-work section.

Acceptance:

- The complete demo can be started from a fresh checkout with documented environment variables.
- The demo script covers manual query, diagnosis, memory follow-up and confirmed work order creation.

## Optional Extensions (P2)

- Long-term semantic memory for prior cases.
- Maintenance scheduling tool.
- Background ingestion queue with Redis.
- More advanced reranking or OCR for scanned manuals.
- Multi-agent collaboration only after the single-Assistant metrics are stable.

## Assistant Roadmap Mapping (2026-10-11)

当前实现按 `assistant_roadmap.md` 的 A0-A6 执行，和上面的基础设施里程碑对应如下：

| Assistant slice | 依赖 | 可交付结果 |
|-------------|------|------------|
| A0 契约和第一条链路 | 关系库文档读取 | `POST /api/v1/assistant/chat`、证据约束回答、引用校验、步骤轨迹 |
| A1 LLM 受控回答 | A0 | 可切换的 provider、结构化回答、无依据拒答、降级 |
| A2 会话记忆 | A0，A1 可选 | 会话/消息/运行持久化、重启恢复、隔离 |
| A3 只读工具 | A0/A2 | 工具注册表、设备和维修历史查询、有限决策循环 |
| A4 修改工具 | A3 + 数据库 | 确认式工单草案、幂等写入、审计 |
| A5 事件和前端 | A0-A4 | JSON + SSE、Assistant 步骤和工具状态、Vue 闭环 |
| A6 评测 | A0-A5 的可测试接口 | 回答、记忆、工具、安全和延迟指标 |

毕业答辩的最小可用路径是 A0-A4；A5-A6 必须至少提供最小闭环和可复现实验。多 Assistant、长期语义记忆、复杂调度和插件系统都放在 P2。
