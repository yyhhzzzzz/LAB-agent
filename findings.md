# Findings

- `backend/app/db/models.py` already defines `WorkOrder`/`work_orders` with equipment, title, description, priority/status, resolution, and completion time. A new maintenance-history table is unnecessary.
- `backend/app/db/models.py` also defines `Conversation` and `ConversationMessage`; the app has a login API and the Assistant API binds conversations to the authenticated user.
- `create_all` creates missing tables but does not migrate existing schemas; avoid adding columns to existing tables for this slice.
- Current `POST /api/v1/assistant/chat` has no session ID and the graph only reads documents. The Vue app currently does not persist a conversation identifier.
- The configured model factory uses LangChain `ChatOpenAI`; set `OPENAI_API_KEY`, optional `OPENAI_API_BASE` for compatible endpoints, and `CHAT_MODEL_NAME`.
- The frontend stores the opaque conversation ID in `sessionStorage`. The history endpoint currently returns the conversation's equipment UUID, while the UI selector uses equipment codes; restoring the selector needs an equipment code/selector in the API response.
- `AssistantConversationService` currently has an outdated guest-owner docstring even though ownership is enforced by `get_current_user`.
- The root README still contains legacy-search terminology in sentences describing the new behavior. Describe direct SQL document reading positively and remove old architecture comparisons.
- Equipment input may be either equipment code or equipment UUID; work-order queries must resolve both.

## Implementation notes

- Work-order tool should return a bounded list of completed records with a non-empty resolution, scoped to one equipment.
- The graph must invoke work-order tool first; only the empty-history branch invokes the document tool. Tool results feed a grounded answer and typed citations.
- Persist latest conversation turns in existing SQL message records; load recent messages under a character budget and the same equipment scope.
- Keep restored equipment selection aligned with the first saved message's equipment selector; avoid adding a schema column because the selector is already stored in message metadata.

## Validation

- Backend test suite: 16 passed using `conda run -n agent python -m pytest -q`.
- Frontend type-check and production build: passed using `npm run build`.
- Full repository text scan for removed retrieval-stack terms: no matches after README and database docs were updated.
- System Python does not have `pytest`; the configured `agent` Conda environment does and was used for the successful run.
- Follow-up review found that the work-order source IDs were not included in the final answer evidence, API callers could change equipment scope while continuing a conversation, and any completed record blocked document fallback. The implementation now asks the LLM to judge work-order relevance, passes valid `Wn` labels to solution generation, returns HTTP 409 for cross-scope conversation reuse, and has regression coverage for these paths.
