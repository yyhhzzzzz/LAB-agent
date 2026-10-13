# Findings

- `Equipment` 已有 `equipment_code`、`name`、类别、型号、厂商、序列号、位置、状态和描述字段，编码唯一。
- `WorkOrder` 已有设备、请求人、标题、描述、优先级、状态、解决方案和时间字段；初始状态可使用模型默认值 `submitted`。
- 文档上传接口已存在，但当前允许不填设备编码，且只返回上传结果；本功能应要求教师/管理员按设备上传并保存 `uploaded_by_id`。
- `get_current_user` 和 `require_roles` 已存在，可直接复用，不重复实现认证逻辑。
- 前端当前路由只有登录和 Assistant Dashboard；可新增管理页并按当前用户角色显示入口。
- 项目不使用 migrations；数据库初始化使用 `Base.metadata.create_all()`，本次不改变模型结构。
- 工作目录不包含 `.git`，当前无法使用 `git diff/status` 检查变更；后续通过文件清单、类型检查和测试核对。
- 管理端维修工单按结构化表单创建，不含附件上传；若“上传”特指上传文件，需要扩展数据模型建立工单附件关系。
- 已实现 `/api/v1/equipments` 与 `/api/v1/work-orders` 列表/创建 API；设备文档继续走 `/api/v1/documents` 并由管理页强制选择设备。
