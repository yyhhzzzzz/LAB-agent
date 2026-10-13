# Task Plan: Work-order-first Assistant with Conversation Memory

## Goal

Extend the existing LangGraph chat Assistant so it checks completed repair work orders first, reads applicable documents only when no resolved work-order history exists, and persists/reuses conversation history across requests.

## Phases

1. Inspect and reuse current `WorkOrder`, `Conversation`, and `ConversationMessage` models — complete.
2. Add SQL-backed LangGraph tools and deterministic work-order-first graph routing, including relevance assessment and cited work-order evidence — complete.
3. Add authenticated, persisted chat sessions and bounded memory loading with fixed equipment scope — complete.
4. Connect Vue session continuation and restored transcript, including equipment restoration — complete.
5. Add meaningful graph/API tests and update setup/API/model configuration documentation — complete.
6. Run backend tests, frontend build, stale-reference scan, and update this plan — complete.

## Decisions

- Reuse existing `work_orders` table/model; it already contains equipment, problem description, status, and repair resolution. Startup `create_all` creates it for new databases.
- Treat completed work orders with non-empty `resolution` as candidates; have the model assess relevance to the current issue. If no relevant record exists for the selected equipment, read SQL documents.
- Reuse existing conversation tables. Sessions are owned by the authenticated user and continued through opaque random UUIDs.
- Preserve equipment scope per message and load only the matching scope into prompt memory.
- Use the current OpenAI-compatible provider settings (`OPENAI_API_KEY`, `OPENAI_API_BASE`, `CHAT_MODEL_NAME`).

## Errors Encountered

| Error | Resolution |
|---|---|
| Workspace has no Git metadata | Validation will use tests/build and direct file inspection; no commit can be created here. |
| Session summary described guest-owned sessions, while implementation uses existing authentication | Correct the plan and service documentation to match authenticated user ownership. |

## Status

Complete. Backend tests pass (16), frontend type-check/build pass, and the repository scan reports no legacy search-stack references. Workspace has no Git metadata, so no commit was created.
