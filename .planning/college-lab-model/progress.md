# Progress

## 2026-10-13

- 已读取当前模型、设备/文档/工单 API、初始化和前端结构。
- 已确认最小领域关系：学院 -> 实验室 -> 设备；教师管理本学院多个实验室；学生按学院获得实验室使用范围。
- 已创建本功能持久化计划并完成业务代码实现。
- 已新增 `College`、`Laboratory` ORM 模型，并将用户、设备分别关联学院和实验室；实验室编号在学院内唯一。
- 已新增学院/实验室创建与查询、管理员绑定用户学院、教师/学生列表、教师/管理员添加学生 API。
- 设备创建与查询按实验室管理范围授权，设备接口返回实验室信息；设备模型移除冗余位置字段。
- 学生可在本学院设备范围内提交维修工单，教师/管理员按管理范围查看并通过状态接口审核、分配和完成工单。
- 默认 `stu`/`tec` 用户保持未绑定学院，由管理员通过学院绑定接口配置；未使用 migrations。
- 已新增学院/实验室/组织权限、同学院编号唯一、学生提交及工单审核测试。
- 按用户确认的空库策略，启动初始化仅执行 `create_all()` 和默认账号 seed，不包含迁移或旧表兼容逻辑；默认 `stu`、`tec` 保持未绑定学院，由管理员在界面绑定。
- 已移除 `Equipment.location` ORM 字段和设备 API 字段；新建设备必须关联实验室，旧的 assistant/document 测试 fixture 可继续创建未关联的 ORM 设备。
- `cd backend && /opt/miniconda3/envs/assistant/bin/python -m pytest -q`：20 passed。
- `cd backend && /opt/miniconda3/envs/assistant/bin/python -m compileall -q app tests`：通过。
- 前端已扩展学院、实验室、教师学院绑定和学生账号管理表单，设备创建要求选择实验室。
- 前端管理页已按角色显示学院实验室范围，学生可以查看可用设备并提交维修申请，教师/管理员可审核工单状态。
- 新增 `src/api/organization.ts` 及工单状态更新 API 封装；`npm run type-check` 与 `npm run build` 已通过。
- Dashboard 的设备选择改为读取当前用户可见设备，避免使用硬编码设备列表；设备表单已移除旧位置字段并改为实验室选择。
- 管理员可以将既有教师和学生账号绑定到学院；这支持初始化的 `tec`、`stu` 账号加入学院关系。
- Assistant 聊天入口复用设备范围校验，已阻止通过手写设备编号绕过学院/实验室访问权限。
- 管理端新增管理员专用教师账号表单，要求绑定已有学院；创建后立即更新教师列表并选作实验室管理教师。
- 新增 `POST /api/v1/users/teachers`，复用学院用户创建、密码哈希、邮箱/用户名唯一性校验；学生和教师调用均返回 403。
- 验证：后端 `pytest -q` 23 passed，`compileall` 通过；前端 `npm run type-check` 和 `npm run build` 通过。
- 用户提出将工单管理从设备管理中独立；已确认现有 API 支持三种角色按权限访问，将保留学生提交/查看本人进度，并为教师/管理员提供管理侧栏入口和处理操作。
- 新增 `WorkOrderManagementView.vue` 和 `/management/work-orders` 路由；教师/管理员侧栏新增“工单管理”，学生可直接进入同页提交报修并查看本人进度。
- 设备管理页移除工单加载、提交、列表和审核逻辑；首页工单入口统一跳转独立工单页。
- 验证：前端 `npm run type-check`、`npm run build` 通过；`npm run lint` 因项目未安装 `eslint` 命令无法执行；后端现有测试保持 23 passed。
- 用户要求在对话页面右侧展示当前用户的所有历史对话；现有表和历史恢复接口可复用，正新增按用户过滤的列表 API 和右侧切换面板。
- 新增 `GET /api/v1/assistant/conversations`，按当前用户过滤、按更新时间倒序返回会话摘要；设备助手右侧新增对话记录面板，支持刷新、切换和恢复历史消息。
- 验证：后端 `pytest -q` 24 passed，`compileall` 通过；前端 `npm run type-check` 和 `npm run build` 通过。
- 完成对话列表浏览器验证：桌面右侧面板可见，窄屏面板移至聊天输入区下方；学生账号无历史数据时显示空状态提示。未发送 AI 请求、未写入测试对话。
- 最终验证：后端 `python -m pytest -q` 24 passed，`python -m compileall -q app tests` 通过；前端 `npm run type-check` 和 `npm run build` 通过。
