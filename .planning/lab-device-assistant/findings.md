# Findings & Decisions

## Requirements and current architecture

- The project is a graduation MVP for laboratory equipment management, manual-based diagnosis, work orders, and maintenance plans.
- The active stack is FastAPI, Vue, SQLAlchemy, and LangGraph.
- Uploaded source files remain in `data/documents` by default. Parsed document contents and their chapter, page, equipment, and source-path metadata live in SQL tables `documents` and `document_chunks`.
- LangGraph loads the full applicable document contents from SQL for the selected equipment, along with their source metadata. The graph reasons over that content and produces an answer with traceable sources.
- The relational database is the sole source of document text. There is no second document corpus to synchronize.
- The shared account model uses `student`, `teacher`, and `admin` roles. Authorization belongs in services/API handlers; the role value alone does not grant access.
- SQLAlchemy creates missing tables at application startup. No migration system is used.
- The chat API is `POST /api/v1/assistant/chat`; requests use `query` and optional `equipment_id`, and responses include `answer`, `status`, and `sources`.

## LangGraph and runtime design

- Keep one bounded Assistant with explicit state, a configured model provider, and auditable execution steps.
- Useful graph stages include intent classification, equipment/history loading, SQL document loading, diagnosis, answer generation, and source/safety validation.
- Every factual claim about a manual must be supported by the document contents loaded for that run. Preserve document ID, filename, chapter, page range, and source path with each source.
- If the loaded documents do not support an answer, state that the available material is insufficient rather than inventing a procedure or parameter.
- Tool contracts should define typed inputs/outputs, authorization and preconditions, bounded execution, normalized errors, and audit records.
- Mutating operations such as work-order creation require a separate explicit confirmation path and idempotency protection.
- Load recent conversation context within a token/character budget; keep the full message history in SQL for audit and recovery.
- The Vue application calls the Assistant API and renders its answer, sources, execution events, and confirmation state.

## Reusable ideas from `pi`

- Keep the runtime separate from the UI and expose structured lifecycle events.
- Represent the active transcript, equipment facts, loaded document contents, tools, and run events in explicit typed state.
- Define tools as contracts with schemas and structured results rather than untyped function names.
- Load persisted context before each model request and apply a bounded prompt budget.
- Append conversation messages and execution events to SQL for recovery and audit.
- Defer plugin marketplaces, conversation branches, durable schedulers, and general-purpose autonomous assistant features.

## PDF-to-Markdown preprocessing research

- `pypdf` extracts text page by page but cannot reliably interpret scanned pages, tables, columns, reading order, or the meaning of diagrams.
- For readable manuals, a multimodal language model can restructure PDF content into canonical Markdown before the normal SQL document-ingestion flow. The original PDF remains the audit source.
- The conversion prompt must preserve facts, tables, steps, warnings, and page markers; unknown visual details must remain explicitly uncertain, with no invented procedures or values.
- Keep the provider behind an adapter that accepts file bytes and returns bounded Markdown plus page and asset metadata. Enforce request size/time limits, redact credentials from logs, and test with a deterministic fake provider.
- Long documents may need page-batched conversion and a merge/validation pass. Reject truncated, empty, or malformed output before storing the converted text.
- Image-aware conversion should return an asset manifest with page, asset ID, image type, caption, extracted labels/values, and a grounded description. Important original images can be stored locally and linked from Markdown.
- Provider-specific file upload states, limits, and request shapes must be validated with a small non-sensitive fixture before implementation is committed.

## Technical decisions

| Decision | Rationale |
|----------|-----------|
| Use one bounded LangGraph Assistant | Provides observable reasoning and tool flow within the graduation-project scope |
| Keep document text and source metadata in SQL | Provides one authoritative, transactional source for both business records and Assistant context |
| Load full applicable document contents from SQL | Matches the required direct-read workflow and keeps the graph grounded in source material |
| Store original files locally for the MVP | Keeps source artifacts available for audit without adding an external storage dependency |
| Use Vue 3 as the final frontend | Keeps the product aligned with the selected application stack |
| Persist messages, runs, events, and tool invocations | Supports recovery, source traceability, and repeatable evaluation |
| Require explicit confirmation for write actions | Prevents an answer-generation request from silently mutating equipment or work-order data |

## Verification notes

- Backend checks on 2026-10-12: 10 tests passed; `python -m compileall -q app tests` passed.
- Local PDF conversion prototype checks use a mock HTTP service and do not send a real PDF or credential to an external provider.
- A live model/provider request is not part of the normal test suite.

## References

- Reference runtime: https://github.com/earendil-works/pi
- Database schema: `docs/database.md`
- Document parser and SQL ingestion: `backend/app/modules/document_ingestion.py`
- SQL document models: `backend/app/db/models.py`
