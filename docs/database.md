# Database design

The three application surfaces share one account table. `users.role` distinguishes `student`, `teacher`, and `admin`. Assistant conversation endpoints require an active account; document upload is limited to teachers and administrators, with ownership recorded in `documents.uploaded_by_id`.

The relational database is the source of truth for accounts, equipment, work orders, maintenance plans, document metadata and contents, conversations, and assistant activity. LangGraph reads applicable repair records from `work_orders` first. When there are no completed records with a resolution for the selected equipment, it reads the applicable manual and SOP contents from `documents` and `document_chunks` to prepare an answer.

```mermaid
erDiagram
  COLLEGES ||--o{ USERS : contains
  COLLEGES ||--o{ LABORATORIES : contains
  USERS ||--o{ LABORATORIES : manages
  LABORATORIES ||--o{ EQUIPMENTS : contains
  USERS ||--o{ WORK_ORDERS : requests
  USERS o|--o{ WORK_ORDERS : assigned_to
  EQUIPMENTS ||--o{ WORK_ORDERS : concerns
  EQUIPMENTS ||--o{ MAINTENANCE_PLANS : schedules
  USERS ||--o{ MAINTENANCE_PLANS : creates
  EQUIPMENTS o|--o{ DOCUMENTS : documents
  USERS o|--o{ DOCUMENTS : owns
  DOCUMENTS ||--o{ DOCUMENT_CHUNKS : contains
  USERS ||--o{ CONVERSATIONS : owns
  EQUIPMENTS o|--o{ CONVERSATIONS : context
  CONVERSATIONS ||--o{ CONVERSATION_MESSAGES : contains
  CONVERSATIONS ||--o{ ASSISTANT_RUNS : runs
  USERS ||--o{ ASSISTANT_RUNS : starts
  ASSISTANT_RUNS ||--o{ ASSISTANT_EVENTS : emits
  ASSISTANT_RUNS ||--o{ ASSISTANT_TOOL_INVOCATIONS : records
```

## Local setup

Install backend dependencies with `python -m pip install -e ".[dev]"`. By default, the app uses `data/lab_device_assistant.sqlite3`. Set `DATABASE_URL` to override it. SQLite paths are resolved from the project root; PostgreSQL URLs use the async driver, for example:

```text
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/lab_device_assistant
```

When FastAPI starts, SQLAlchemy creates the current tables with `Base.metadata.create_all()`. This project does not use migrations. The local SQLite database can be deleted when the schema changes; startup then creates a fresh database and seeds the development accounts.

After table creation, startup adds missing `stu`, `tec`, and `admin` accounts with the corresponding roles. Each receives the development password `12345678`, stored only as a salted PBKDF2 hash. Existing accounts with those usernames are left untouched.

## Table responsibilities

- `colleges`:学院目录。教师和学生通过 `users.college_id` 归属学院。
- `laboratories`:实验室号码、所属学院和负责教师；`(college_id, laboratory_number)` 唯一。
- `users`: one identity per account, password hash only, the three application roles, and optional college membership for initial unassigned development accounts.
- `equipments`: shared equipment catalog and lifecycle status. Each API-created equipment points directly to one laboratory through `laboratory_id`.
- `work_orders`, `maintenance_plans`: repair and maintenance records. Assistant repair-history lookup reads completed work orders with a non-empty `resolution`, scoped to equipment.
- `documents`, `document_chunks`: source metadata, processing state, document text, and citation locations including chapter and page.
- `conversations`, `conversation_messages`: user-owned chat history.
- `assistant_runs`, `assistant_events`, `assistant_tool_invocations`: bounded Assistant execution and tool audit records.

Administrators can create a teacher account with `POST /api/v1/users/teachers`. The request requires `username`, `password` (8-128 characters), `display_name`, and an existing `college_id`; `email` is optional. Usernames and supplied email addresses must be unique. New passwords are hashed before storage, and only administrators can call this endpoint.

Documents can be added through authenticated `POST /api/v1/documents` using multipart fields `file` and optional `equipment_code` and `title`. Only teacher and administrator accounts can upload; a teacher can upload only for equipment in laboratories they manage. The original file is stored under `data/uploads` by default; set `DOCUMENT_STORAGE_PATH` to change it. Extracted content and citation metadata are stored in the relational database for direct Assistant reading.

Passwords must be hashed before persistence. Do not store plaintext credentials or place credentials in source control. Account authorization, ownership checks, and work-order transition rules must be enforced by services/API handlers.

The Assistant exposes `GET /api/v1/assistant/conversations` for the authenticated user's conversation summaries, ordered by recent activity. `GET /api/v1/assistant/conversations/{conversation_id}` returns the selected conversation messages; both endpoints enforce user ownership.
