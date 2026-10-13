# Progress

## 2026-10-12

- 已读取并应用 `planning-with-files` skill。
- 已完成现有设备、文档、工单模型和前端结构盘点。
- 已创建本功能的持久化任务计划、发现记录和进度文件。
- 确认设备/工单表已存在；认证角色依赖、文档上传解析流程可以复用。
- 工作目录无 `.git` 元数据，使用文件检查和测试验证改动。
- 工单权限修正为教师/管理员；按结构化维修工单表单创建，暂不添加附件字段。
- 已新增 `backend/app/api/equipment.py`，注册设备和工单列表/创建接口。
- 已新增 `backend/tests/test_equipment_api.py`，覆盖角色权限、设备创建/重复值、工单创建、设备不存在和输入校验。
- 新增 `frontend/src/api/equipment.ts`，统一封装设备、工单和设备文档上传请求。
- 新增 `frontend/src/views/EquipmentManagementView.vue`，提供设备创建、关联文档上传、维修工单提交及列表展示。
- 新增 `/management`（兼容别名 `/equipment-management`）教师/管理员路由，Dashboard 对对应角色显示入口，学生被路由守卫拦截。
- 修正前端文件选择器扩展名，只暴露后端实际支持的 `.pdf`、`.md`、`.txt`。
- 使用 `/opt/miniconda3/envs/assistant/bin/python -m pytest -q` 验证：18 passed in 4.39s。
- 使用 `python3 -m compileall -q app tests` 验证后端编译通过；前端 `npm run type-check` 和 `npm run build` 均通过。
- 重启后台服务并通过浏览器实测登录后访问 `http://127.0.0.1:5173/management`，页面和新 API 正常加载。
- 按需求从管理页移除“设备类型/类别”字段，并保留数据库中的旧 nullable 列以兼容已有数据。
