# Findings

- 用户确认新产品名为“实验室设备助手”，并要求代码、API 和数据库命名一并替换。
- 当前助手 API 使用 `/api/v1/assistant`，前后端多处直接引用；OpenAPI 中不再注册旧 `/api/v1/agent`。
- 当前数据库默认文件为 `data/lab_device_assistant.sqlite3`，原文件完整保存在 `data/archive/database-before-assistant-rename.sqlite3`。
- 只读检查表行数：`users` 5、`colleges` 2、`laboratories` 1、`equipments` 1、`documents` 1、`document_chunks` 17、`conversations` 3、`conversation_messages` 12、`work_orders` 2；保养计划与 AI 执行跟踪表当前为空。
- 新库验证保留 5 个用户、2 个学院、1 个实验室、1 台设备、1 份文档、17 个文档块、3 个对话、12 条消息和 2 张维修工单。空的 `agent_runs`、`agent_events`、`tool_invocations` 追踪表已在新副本中移除，应用启动创建 `assistant_runs`、`assistant_events` 和 `assistant_tool_invocations`。
- `maintenance` 对设备状态表示“维修中”，`maintenance_plans` 表示保养计划，二者是实际维修/保养业务含义；产品品牌可替换，但须保留清晰领域语义。
