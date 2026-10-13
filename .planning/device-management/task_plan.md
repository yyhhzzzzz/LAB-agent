# Task Plan: Teacher/Admin Equipment Workflow

## Goal

为教师和管理员端增加设备创建、设备关联文档上传、维修工单创建功能，复用现有 SQLAlchemy 表、认证和文档解析流程，不引入 migrations、Qdrant 或 BM25。

## Phases

- [x] 盘点现有模型、认证、文档上传和前端路由
- [x] 实现设备与维修工单 API，并补充角色、输入校验和错误处理
- [x] 复用现有文档上传接口，使管理页上传时必须关联设备
- [x] 增加教师/管理员工作台，接入设备、文档和工单表单
- [x] 增加后端 API 测试，运行后端/前端验证

## Decisions

- 复用 `equipments`、`documents`、`document_chunks`、`work_orders` 表；不新增数据库表或迁移。
- 设备创建和文档上传仅允许 `teacher`、`admin`。
- 维修工单创建仅允许教师、管理员，`requester_id` 从当前 token 获取，避免客户端伪造。
- “上传维修工单”按提交结构化维修工单表单实现；现有 `WorkOrder` 没有附件字段，本次不新增文件附件模型。
- 工单初始状态为 `submitted`；状态流转和分配不纳入本次切片。
- 文档上传继续使用现有 Markdown/TXT/PDF 解析和去重逻辑，必须提供设备编码。

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| 系统 `python3` 缺少 FastAPI/pytest | 首次尝试运行后端测试 | 改用项目环境 `/opt/miniconda3/envs/assistant/bin/python`，18 项测试通过 |

## Status

Complete.
