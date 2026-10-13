# Progress Log

## Current checkpoint: 2026-10-12

### Architecture and implementation status

- The active stack is FastAPI, Vue, SQLAlchemy, and LangGraph.
- Document upload saves the original file locally and stores parsed text, document metadata, chapter/page information, and source paths in SQL.
- LangGraph loads document contents from SQL for the selected equipment, generates an answer, and returns source metadata with the response.
- SQLAlchemy creates missing tables at startup; the project does not use a migration system.
- The assistant chat contract is `POST /api/v1/assistant/chat` with `query` and optional `equipment_id`; the response contains `answer`, `status`, and `sources`.
- The root and frontend READMEs and database design note describe this flow.

### Database foundation verification

- Document uploads persist `documents` and `document_chunks`, link a supplied equipment code when a matching equipment exists, and record processing state.
- Backend verification on 2026-10-12: 10 tests passed; `python -m compileall -q app tests` passed.

### Remaining Assistant work

- Complete the LangGraph answer flow with the configured model provider, evidence-grounded prompts, and source validation.
- Add persistent conversation memory and context limits.
- Add equipment and maintenance-history tools, then confirmation-gated work-order actions.
- Complete the Vue conversation flow and answer/source evaluation.

## PDF semantic conversion research

- `pypdf` extracts text by page but cannot reliably preserve scanned content, tables, columns, visual reading order, or diagram meaning.
- For readable manuals, the proposed optional preprocessing provider converts PDF content into a structured Markdown document while preserving page references. The original PDF remains available for audit.
- The conversion must preserve factual details, label uncertainty, avoid inventing procedures or parameters, and validate non-empty bounded output.
- The provider adapter needs configured credentials, request limits/timeouts, redacted logs, and deterministic mock tests. A live provider call is separate from normal local tests.
- Image-aware conversion should return Markdown plus an asset manifest containing source page, asset identifier, type, caption, extracted labels/values, and grounded description. Original images may be stored locally and referenced from the Markdown.
- Long manuals may require page-batched conversion and a merge/validation step to avoid output truncation while preserving section and page boundaries.

## PDF provider prototype verification

- A local mock HTTP test verified Base64 PDF input, Markdown extraction, output persistence, and that API credentials are not printed.
- The script uses the configured provider endpoint and model variables; TLS verification remains enabled and can use the configured CA bundle or `certifi`.
- No live provider request was made during the local prototype verification.

## Planning references

- `task_plan.md`: active phases and outstanding work.
- `architecture.md`: current SQL document-context and LangGraph boundaries.
- `assistant_roadmap.md`: A0-A6 delivery order and acceptance criteria.
- `milestones.md`: project deliverables and acceptance criteria.
