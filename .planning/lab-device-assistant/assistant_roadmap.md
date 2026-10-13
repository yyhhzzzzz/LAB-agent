# Laboratory Equipment Assistant 路线规划

## 1. 当前基线

当前文档处理和问答链路以关系型数据库为唯一正文来源：

```text
Markdown/PDF/TXT 上传
  -> 解析、切块
  -> documents / document_chunks
  -> Assistant 按设备读取数据库正文
  -> 回答附文档、章节和页码来源
```

当前系统仍缺少以下设备 Assistant 能力：

- LLM 生成回答和无依据拒答策略
- 会话记忆和上下文注入
- 设备、维修记录等受控工具
- 工具调用确认、审计和失败恢复
- Assistant 运行步骤、状态和事件
- 面向 Assistant 的端到端评测

LangGraph 是 Assistant 的工作流运行时。文档正文及章节、页码、来源路径存放在关系型数据库中，Assistant 按设备范围读取完整文档内容并据此生成回答。

## 2. 目标形态

目标是一个面向实验室设备管理的单 Assistant：用户选择设备并描述问题，LangGraph 读取设备上下文和关系库中的手册/SOP 正文，必要时调用只读工具，给出带章节来源的建议；涉及数据变更时先请求确认，再执行工单或状态更新。

第一版必须满足以下边界：

1. 一个 Assistant、一个有界运行循环、一个实验室设备管理领域。
2. 每次运行有最大步骤数、超时和明确的终态。
3. 回答事实必须来自已加载的数据库文档或工具结果；没有证据时明确说明资料不足。
4. 查询类工具先于修改类工具；修改类工具必须经过显式确认。
5. Assistant 核心与 Vue 解耦，先提供 JSON API，再增加 SSE 事件流。
6. API key 只存在后端配置，不能进入前端、日志或引用内容。

## 3. 分阶段交付

### A0：Assistant 契约和第一条垂直链路（当前优先级 P0）

目的：把数据库文档读取和回答能力包装成稳定的 Assistant 边界，并可用 fake model 测试。

后端工作：

- 新增 `POST /api/v1/assistant/chat`。
- 请求包含 `query` 和可选 `equipment_id`。
- 响应包含 `answer`、`status` 和 `sources`。
- 从关系库读取与所选设备相关的完整文档正文，保留全局文档和来源元数据。
- 把文档读取和回答生成记录成结构化步骤，例如 `documents.loaded`、`answer.completed`。
- 在返回前校验引用必须来自已加载的文档来源；没有证据时返回无依据提示。

验收：

- 有文档依据的问题返回至少一个章节引用，引用可追溯到 `document_id/chunk_id/source_path`。
- 不匹配问题返回 `no_answer`，不拼接模型或模板中的虚构步骤。
- 设备范围、全局 SOP、空文档和数据库读取异常都有 API 测试。
- Vue 只调用 Assistant Chat API，不再直接拼装“资料读取完成”文本。

### A1：LLM 受控回答（P0）

目的：让 Assistant 根据 LangGraph 加载的数据库文档上下文生成自然语言答案，同时保留证据边界。

后端工作：

- 定义 `LLMProvider` 接口：`complete(messages, timeout) -> ProviderResult`。
- 先实现一个 OpenAI-compatible provider，模型、地址、超时和密钥全部由环境变量配置；使用 fake provider 测试，不要求本地测试调用外部服务。
- 固定提示词结构：设备上下文、用户问题、编号证据、回答规则、引用格式。
- 要求模型只引用给定证据，不知道时输出无依据标记，不允许编造参数、报警处理或安全步骤。
- 对模型返回做 JSON/schema 解析、超时、有限重试和敏感信息脱敏；解析失败时返回受控失败状态。
- 引用校验器检查回答中的引用编号、引用章节和证据 ID 是否一致。

验收：

- 使用 fake provider 可以稳定测试生成、拒答、超时和格式错误。
- 真实 provider 关闭时仍可使用 fake provider 验证本地工作流。
- 任何 `llm` 模式回答都包含至少一条有效引用，除非明确为 `no_answer`。

### A2：持久化会话记忆（P0）

目的：支持“刚才那个故障”“这个设备”等追问，并可在重启后恢复。

后端工作：

- 用 SQLAlchemy 定义 `conversations`、`conversation_messages` 和 `assistant_runs`；本地开发使用 SQLite 文件，部署时切换 PostgreSQL。
- 每次运行先持久化用户消息，再加载最近 8-12 条消息和设备上下文；完成后持久化 Assistant 回复、引用和运行状态。
- 设定字符/token 预算；超出预算时截断旧消息，不能删除审计记录。
- 按 `conversation_id` 和用户权限隔离历史，禁止通过请求参数读取其他会话。

验收：

- 第二轮问题能够解析上一轮选定的设备和故障语境。
- 重启后端后会话仍可读取。
- 两个会话相互不可见，非法会话 ID 返回受控错误。

### A3：只读工具注册和有限决策循环（P0）

目的：让 Assistant 在读取文档上下文的基础上选择受控工具。

工具契约：

```text
name
description
input_schema
output_schema
execute(context, args, timeout)
precondition(context, args)
```

首批只读工具：

1. 手册/SOP 内容由文档上下文节点直接从 SQL 加载，并保留对应来源。
2. `get_equipment`：读取设备基本信息、型号和当前状态。
3. `get_maintenance_history`：读取维修记录摘要。

运行循环：

```text
classify -> load SQL document context/tool -> observe -> answer -> verify
```

每次最多 3 个工具步骤；工具参数必须经过 schema 校验；错误转为结构化工具结果并终止或回退，不允许无限重试。

验收：

- 测试可注入 fake tool，验证 Assistant 选择、参数校验、成功和失败路径。
- 前端能显示工具开始、完成和错误状态。
- 工具返回结果进入回答上下文，并保留调用参数摘要和耗时。

### A4：修改类工具和确认边界（P0）

目的：形成设备维修流程，但把数据修改控制在明确的用户确认动作之后。

首个修改工具：`create_work_order`。Assistant 只能提出工单草案，响应中携带 `confirmation_token` 和结构化字段；用户确认后调用独立确认接口执行写入。

安全规则：

- 未确认的请求不得写入数据库。
- 工单字段使用 Pydantic schema 校验，设备必须存在。
- 每次调用记录 `tool_invocation`，包含状态、错误、开始/结束时间和脱敏参数。
- 重复确认使用幂等键，不能创建重复工单。

验收：

- 未确认、过期 token、非法参数和重复请求都有测试。
- 成功写入后返回工单 ID，并在会话中显示结果。
- 工具失败不会伪装成成功，也不会丢失运行审计记录。

### A5：事件流和 Vue 工作台（P0）

先保留 JSON API 作为测试和降级路径，再增加：

- `POST /api/v1/assistant/chat/stream`：SSE 输出步骤、文档来源、工具状态和最终回答。
- Vue API client 统一封装 chat、stream、conversation 和 confirm。
- 当前页面展示回答模式、Assistant 步骤、引用、原文预览、加载、断线、无答案和错误状态。
- 会话 ID、设备 ID 和最后一次引用在刷新后恢复。

验收：

- 用户可以完成“选择设备 → 提问 → 查看引用 → 生成工单草案 → 确认工单”的演示路径。
- 断线后能重试，错误信息不暴露 API key 或内部堆栈。

### A6：评测与毕业设计证据（P0）

数据集按能力拆分：

- 可回答问题：预期的数据库文档章节/页码来源。
- 不可回答题：预期无答案。
- 多轮记忆题：需要上一轮设备或故障上下文。
- 工具题：预期工具、参数和结果。
- 安全题：必须拒绝越权或未确认的写操作。

指标：

- 文档依据：来源完整率、来源章节准确率、无依据回答率。
- 回答：引用有效率、事实一致性、拒答准确率。
- Assistant：工具选择准确率、工具成功率、确认拦截率、平均延迟、失败恢复率。
- 记忆：跨轮解析准确率、重启恢复率、会话隔离通过率。

对照组：固定提示词回答、数据库文档上下文回答、Assistant + 工具；每次记录数据集版本和配置。

## 4. 建议目录和接口边界

第一轮代码实现优先新增/扩展以下模块：

```text
backend/app/assistant/
  contracts.py       # 请求、响应、引用、步骤、运行状态
  runner.py          # 有界 Assistant 编排
  provider.py        # LLMProvider 和 fake/provider adapter
  verifier.py        # 引用、回答和安全规则校验
  tools/             # 工具 schema、注册表和处理器
backend/app/api/assistant.py
backend/app/modules/conversation_service.py
backend/app/modules/assistant_run_service.py
frontend/src/api/assistant.ts
```

复用 `DocumentIngestionService`、`DocumentRecordService` 和关系库 repository；LangGraph、Vue 和评测脚本不得引入独立的文档副本。

## 5. 实施顺序和停止条件

推荐每个阶段都形成一个可运行切片：

1. A0 完成前不接真实 LLM。
2. A1 的 fake provider、引用校验和降级路径通过测试后，再配置真实模型。
3. A2 的会话隔离通过测试后，再把历史注入提示词。
4. A3 只读工具稳定后，才设计 A4 的写操作。
5. A4 的确认和幂等测试通过后，再接 SSE 和完整演示。
6. A6 的基线指标稳定后，才考虑 reranker、多 Assistant 或长期语义记忆。

如果任一阶段无法在本地 Conda 环境独立测试，就先补 fake adapter 或内存 repository，不以 Docker、外部模型或远程数据库作为唯一前置条件。

## 6. 主要风险和处理

| 风险 | 处理 |
|------|------|
| 模型编造设备参数 | 证据编号、引用校验、无证据拒答、人工评测集 |
| 外部模型不可用或费用失控 | provider 配置、超时、有限重试和 fake provider；失败时返回受控状态 |
| Assistant 无限循环 | 最大步骤数、全局超时、终止状态和事件记录 |
| 工具误写数据 | 只读工具先行、确认 token、权限/schema/幂等校验 |
| 会话越权 | 服务端按用户和会话过滤，不能信任前端 equipment/conversation 参数 |
| 文档总量增长导致 Assistant 上下文过大 | 通过设备范围、文档数上限和上下文预算控制；超限时明确报错并提示缩小设备/文档范围 |
| 计划过大导致无法答辩 | 以 A0-A4 为毕业核心，A5/A6 完成最小闭环，其他能力列为扩展 |

## 7. Assistant MVP 完成定义

当以下路径在本地环境可复现时，Assistant MVP 完成：

```text
上传设备手册
  -> 选择设备并提问
  -> LangGraph 从 SQL 加载手册正文并返回有来源的回答
  -> 追问使用同一会话上下文
  -> Assistant 调用至少一个只读工具
  -> 需要写入时生成工单草案并等待确认
  -> 确认后写入并展示工单 ID
  -> 评测脚本输出回答来源、记忆和工具指标
```

外部 Qwen PDF Markdown 转换属于文档预处理能力，放在 Assistant MVP 之前作为独立 provider 切片；它不能替代 Assistant 的运行时、记忆和工具闭环。
