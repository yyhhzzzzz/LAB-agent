# Findings

- 当前模型只有 `User.department` 自由文本，没有学院或实验室模型。
- `Equipment` 当前有自由文本 `location`，设备、文档、工单和会话均以设备为中心关联；新增 `laboratory_id` 后可由设备间接得到实验室和学院。
- `WorkOrder` 已有 `submitted`、`approved`、`rejected`、`in_progress` 等状态，可复用学生报修审核流，不需新建申请表。
- 数据库初始化使用 `Base.metadata.create_all()`，不会为已有 SQLite 表自动增加字段；本项目明确不使用 migrations，需要设计启动兼容方案。
- 现有设备接口只允许教师/管理员，学生工单创建也尚未开放；本次需要按学院范围调整查询和创建权限。
- 实验室管理教师必须是教师角色且与实验室同学院，这类跨表角色/学院约束主要由服务层校验。
