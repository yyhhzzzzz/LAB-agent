# Laboratory Equipment Assistant Architecture Plan

## 1. Target and Scope

目标是一个面向实验室设备的单 Assistant 设备平台：用户选择设备并描述故障，LangGraph 从关系型数据库读取设备、维修记录和手册/SOP 正文，调用受控工具完成查询或创建工单，返回带来源的诊断建议，并保存会话和执行轨迹。

毕业设计 MVP 只覆盖一个 Assistant、一个实验室领域、有限步工具循环和有限数量工具。系统重点是可解释的数据库上下文读取、可追踪的工具调用和可复现的评测，不追求通用自主 Assistant。

## 2. Technology Boundary

### Final Stack

- Backend: FastAPI, Pydantic, SQLAlchemy async, LangGraph, PostgreSQL.
- Document access: parsed document contents and source locations are stored in the relational database. LangGraph reads the full applicable document contents from those records directly.
- File storage: local `data/documents` for the thesis demo; an S3-compatible store can replace it later.
- Frontend: Vue 3, Vite, TypeScript, Pinia, Vue Router. The former React demo was removed; Vue will be created in milestone M5.
- Runtime events: Server-Sent Events (SSE) for chat progress, with a normal JSON endpoint retained for simple requests/tests.
- Optional: Redis only for background ingestion jobs or rate limiting; it is not part of the MVP data source.

### What Is Borrowed from `pi`

| Pi idea | Equipment Assistant adaptation |
|---------|--------------------|
| Explicit AssistantContext/transcript | Typed `AssistantState` with recent messages, equipment context, database document contents and tool events |
| Tool schema and execute contract | Pydantic input/output schemas, authorization, timeout, error result and audit record |
| Turn-based Assistant Loop | LangGraph nodes grouped as classify, load context, decide, act, observe, answer |
| `beforeToolCall`/`afterToolCall` | Precondition/permission checks and post-execution audit/event recording |
| Lifecycle events | SSE events for node start/end, document loading, tool start/end and final response |
| `prepareRequest`/context transform | Load recent memory, summary and selected equipment facts before each model request |
| Append-oriented session persistence | `conversation_messages` and `assistant_runs/events` tables; full branch replay is out of scope |

### Explicitly Out of Scope

- Pi's plugin marketplace and general-purpose coding tools.
- Multi-agent delegation and autonomous subagent trees.
- Conversation branches, distributed durable scheduler and cross-provider model catalog.
- Unbounded self-directed loops. Every run has a step limit, timeout and terminal state.

## 3. Backend Modules

```text
backend/app/
  api/                 # HTTP/SSE endpoints and request auth
  assistant/
    graph.py           # LangGraph topology
    state.py           # Typed run state
    runtime.py         # run id, limits, event sink, cancellation
    tools/              # tool specs + handlers
    events.py           # event types and serialization
  modules/
    conversation_service.py
    document_service.py
    equipment_service.py
    work_order_service.py
    assistant_run_service.py
  knowledge/
    ingestion.py       # parse, clean, chunk, metadata
  db/
    models.py
    repositories.py
```

The assistant graph should depend on service/tool interfaces rather than hardcoded data. Tests can inject an in-memory repository; production uses SQLAlchemy repositories.

## 4. Data Model

### Relational Tables

Existing tables remain the business source of truth: `users`, `equipments`, `documents`, `work_orders`, `maintenance_plans`.

Add:

```text
document_chunks
- id, document_id
- chunk_index, content, chapter
- page_start, page_end, source_path, checksum, created_at

conversations
- id, user_id, equipment_id, title, summary
- created_at, updated_at, status

conversation_messages
- id, conversation_id, role, content, metadata_json, created_at

assistant_runs
- id, conversation_id, user_query, status, intent
- started_at, completed_at, error_message

assistant_events
- id, run_id, sequence, event_type, node_name
- payload_json, started_at, completed_at

tool_invocations
- id, run_id, tool_name, arguments_json
- result_json, status, error_message, started_at, completed_at
```

## 5. Document Ingestion Flow

```text
UploadFile
  → save original file and checksum
  → create documents row
  → parse PDF/Markdown/TXT with page/section metadata
  → split into bounded text chunks with page/section metadata
  → insert document_chunks
  → mark document processing status ready
```

Ingestion must be idempotent: uploading the same file for the same equipment returns the existing document without duplicating chunks. Parsing or database failures must return a clear error and leave no partial database transaction.

## 6. Assistant Run Flow

```text
request accepted
  → create assistant_run and persist user message
  → load recent messages + summary + equipment snapshot
  → classify intent
  → read applicable manual/SOP contents and source metadata from SQL
  → diagnose or answer from evidence
  → decide whether an action is needed
  → request tool call or ask for confirmation
  → validate and execute tool
  → append tool result and observe
  → re-plan or produce final answer
  → verify citation/safety rules
  → persist assistant message, events and terminal run status
```

For the MVP, tools that mutate data require explicit confirmation from the user or a dedicated API action. A diagnosis response may recommend a work order without creating it; a confirmed action calls `create_work_order` and shows the returned id.

### Tool Contract

Every tool should expose:

```text
name, description
input_schema, output_schema
execute(context, args, signal)
precondition(context, args)
audit_metadata
```

Initial tools:

1. `get_equipment`
2. `get_maintenance_history`
3. Load manual/SOP document contents from SQL within the selected equipment scope.
4. `create_work_order` (mutation, confirmation required)
5. `update_equipment_status` (mutation, engineer/admin role required)

`schedule_maintenance` is a second milestone tool, not a prerequisite for the first end-to-end demo.

## 7. Memory Design

- Short-term memory: last 8–12 conversation messages loaded from PostgreSQL.
- Compressed memory: conversation summary updated after a configurable threshold.
- Domain memory: equipment and work-order records are queried through tools, not copied permanently into prompts.
- Optional long-term facts: explicit user preferences or equipment aliases with source and confidence; defer case-memory expansion until the core evaluation is stable.

Use a token/character budget before each LLM request. Old messages are summarized or dropped from the prompt while remaining persisted for audit.

## 8. Vue Frontend Modules

```text
src/
  api/              # axios client + SSE client
  stores/           # auth, equipment, conversation, assistant run
  router/
  views/
    Dashboard.vue
    Equipment.vue
    Documents.vue
    Chat.vue
    WorkOrders.vue
    Maintenance.vue
  components/
    ChatTimeline.vue
    AssistantEventTimeline.vue
    EvidencePanel.vue
    ToolConfirmation.vue
    DocumentUploader.vue
```

The Chat view displays assistant text, cited chunks, event/tool status and confirmation controls. It must preserve `conversation_id` and `equipment_id` across messages and recover the latest conversation after a page reload.

## 9. API Surface

```text
POST /api/v1/auth/login
GET  /api/v1/equipment
GET  /api/v1/equipment/{id}
POST /api/v1/documents              # multipart file + optional equipment_code
GET  /api/v1/documents
POST /api/v1/conversations
GET  /api/v1/conversations/{id}/messages
POST /api/v1/chat                 # JSON response for tests
POST /api/v1/assistant/chat/stream           # SSE assistant events
POST /api/v1/assistant-runs/{id}/confirm
GET  /api/v1/work-orders
POST /api/v1/work-orders
GET  /api/v1/evaluation/runs/{id}
```

### Assistant chat API

Vue 和评测通过 Assistant Chat API 提交问题。LangGraph 直接加载 SQL 中的文档正文和来源信息，再生成回答：

```text
POST /api/v1/assistant/chat
{
  "query": "转子如何维护？",
  "equipment_id": "TDL5A"
}

{
  "query": "转子如何维护？",
  "status": "completed | no_documents",
  "answer": "...",
  "sources": [{"id": "S1", "document_id": "...", "filename": "...", "source_path": "...", "chapter": "...", "page_start": 1, "page_end": 2, "excerpt": "..."}]
}
```

If the applicable document contents exceed the configured context limit, the endpoint returns HTTP 413 before invoking the model.

`status` 标识完成、无依据回答或失败。引用来源必须来自本次已加载的数据库文档；写操作单独走确认接口，不能让 `assistant/chat` 直接改变设备或工单数据。

## 10. Acceptance Criteria

The graduation MVP is complete when:

- A PDF manual can be uploaded, stored as SQL document contents, loaded by equipment scope, and cited with correct chapter/page metadata.
- A second message in the same conversation can use the first message's context after a process restart.
- The Assistant invokes at least one read-only tool and one confirmed mutation tool, with persisted invocation records.
- The UI receives visible lifecycle events and renders evidence and tool outcomes.
- Baseline and ablation experiments run from committed datasets and produce reproducible metrics.
- A failed tool or LLM request produces a terminal error event and leaves an auditable run record.
