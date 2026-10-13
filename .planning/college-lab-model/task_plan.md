# Task Plan: College and Laboratory Relationships

## Goal

为学院、实验室、教师、学生和设备建立最小关系模型：实验室属于学院并由本学院一名教师管理，设备直接属于一个实验室；学生按所属学院使用本学院全部实验室，学生维修申请复用现有工单状态流转。

## Phases

- [x] 确认关系、权限和最小字段设计
- [x] 扩展 SQLAlchemy 模型和初始化策略
- [x] 增加学院/实验室/学生管理 API 与权限校验
- [x] 增加管理员创建教师账号功能
- [x] 调整设备、文档、工单接口和学生可见范围
- [x] 更新教师/管理员/学生端页面
- [x] 增加测试并运行后端/前端验证
- [x] 将工单提交、查看和处理从设备管理页拆分为独立工单页
- [x] 在设备助手右侧展示当前用户所有持久化对话，并支持切换恢复

## Decisions

- `colleges` 只保存 `id`、`name`。
- `laboratories` 只保存 `id`、`laboratory_number`、`college_id`、`manager_teacher_id`；在同一学院内实验室编号唯一。
- 教师和学生都必须属于一个学院；管理员可以不属于学院。
- 每个实验室只能由一名本学院教师管理，一个教师可以管理多个本学院实验室。
- 每台设备必须直接关联一个实验室；不再用 `Equipment.location` 作为实验室关系。
- 学生可使用所属学院全部实验室；学生与实验室不建立额外多对多表。
- 学生提交维修工单后状态为 `submitted`，教师或管理员审核并流转为 `approved`、`rejected` 或后续处理状态。
- 管理员创建学院和实验室；教师、管理员可以添加学生，教师只能添加本学院学生，管理员可添加任意学院学生。
- 项目不使用 migrations；本地旧 SQLite 数据没有需要保留的内容，重建数据库时直接删除数据库文件，由 `create_all()` 创建最新结构。

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| None yet | - | - |

## Status

Completed.
