# Laboratory Equipment Assistant (实验室设备助手)

基于 LangGraph + FastAPI + SQLAlchemy + Vue 的实验室设备问答与辅助诊断平台。

## 核心功能

- **维修工单优先**：设备助手先读取所选设备已完成且有维修结论的工单；找到记录后据此生成解决方案。
- **文档兜底**：没有可用维修记录时，设备助手读取关系数据库中该设备适用的手册和 SOP 正文，并附带章节、页码等来源信息。
- **会话记忆**：登录用户的对话写入数据库，可通过会话 ID 继续提问并恢复历史消息。
- **文档导入**：教师和管理员可上传 PDF、Markdown 和 TXT 文件，系统提取正文并保存来源信息。

---

## 🏗️ 目录结构概览

```text
lab-device-assistant/
├── backend/          # FastAPI 后端服务、LangGraph Assistant
├── frontend/         # Vue 3 + Vite + TypeScript 前端操作台
├── data/             # 手册、SOPs、设备元数据、评测集
├── scripts/          # 数据导入与评测运行脚本
├── evaluation/       # 评测基线与消融实验
└── docs/             # 架构设计、数据字典与 API 文档
```

---

## 🚀 快速启动

### 启动 API 并提问（Conda `agent` 环境）

先安装后端依赖：

```bash
conda activate agent
cd backend
python -m pip install -e ".[dev]"
```

关系型业务数据默认使用项目根目录下的 `data/lab_device_assistant.sqlite3`。FastAPI 启动时会按 SQLAlchemy 模型创建尚不存在的表；需要使用 PostgreSQL 时，在 `.env` 中设置 `DATABASE_URL=postgresql+asyncpg://...`。数据库表和端点设计见 [`docs/database.md`](docs/database.md)。

在项目根目录的 `.env` 配置聊天模型接口：

```dotenv
OPENAI_API_KEY=你的模型服务密钥
OPENAI_API_BASE=https://api.openai.com/v1
CHAT_MODEL_NAME=gpt-4o-mini
```

`OPENAI_API_BASE` 用于 OpenAI 兼容服务，也可以留空使用默认地址；`CHAT_MODEL_NAME` 应填写该服务支持的模型名。请勿将密钥提交到版本控制。另建议为登录令牌配置固定的随机 `SECRET_KEY`，避免服务重启后令牌失效。

首次启动时，数据库会补充三个初始账号：`stu`（学生）、`tec`（教师）和 `admin`（管理员），初始密码均为 `12345678`。已有同名账号会保留现有密码和角色。初始密码只用于开发和演示；部署到共享或生产环境前请更换密码，并为 `SECRET_KEY` 配置随机密钥。

新开一个终端并启动 API：

```bash
conda activate agent
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

登录接口为 `POST /api/v1/auth/login`，成功后返回 Bearer token。设备助手对话需要登录，学生、教师和管理员均可使用；文档上传需要教师或管理员权限。文档上传接口为 `POST /api/v1/documents`，支持 PDF、Markdown 和 TXT。后端提取正文和章节/页码后保存到关系型数据库；设备助手按工单优先、文档兜底的顺序读取当前设备的维修资料。默认单文件上限为 25 MiB，可通过 `DOCUMENT_UPLOAD_MAX_BYTES` 调整；设备助手单次读取的文本上限由 `DOCUMENT_CONTEXT_MAX_CHARS` 控制。

先登录教师账号获取 token：

```bash
ACCESS_TOKEN=$(curl -sS http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"tec","password":"12345678"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

上传文档示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F 'equipment_code=TDL5A' \
  -F 'file=@data/TDL5A_centrifuge.md'
```

向设备助手提问：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/assistant/chat \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"query":"离心机运行中出现异常振动时应如何检查？","equipment_id":"TDL5A"}'
```

响应包含 `conversation_id`、`answer`、`status` 和来源列表。后续请求可传入该 `conversation_id` 延续会话；`GET /api/v1/assistant/conversations` 返回当前用户自己的历史会话摘要，助手页面右侧可以切换会话；`GET /api/v1/assistant/conversations/{conversation_id}` 恢复指定会话的历史消息和设备范围。设备筛选会保留通用文档；如果范围内文档超过上下文上限，API 会返回 HTTP 413，提示缩小设备范围后重试。

运行后端测试：

```bash
cd backend
python -m pytest -q
```

