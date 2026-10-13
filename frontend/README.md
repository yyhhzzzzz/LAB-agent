# Laboratory Equipment Assistant — Frontend

Vue 3 + Vite + TypeScript 的实验室设备问答工作台。

## 启动

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## 当前范围

- **一个 View**:`AssistantView` —— 会话导航 / Assistant 问答流 / 设备选择
- **设计系统**:`styles/tokens.css` + `styles/base.css`
- **后端连接**:开发服务器将 `/api` 代理到 `http://127.0.0.1:8000`

## 数据来源

问答界面调用 `POST /api/v1/assistant/chat`，由 LangGraph Assistant 直接读取关系型数据库中的手册正文并生成回答。

## 目录

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── index.html
├── env.d.ts
└── src/
    ├── main.ts
    ├── App.vue
    ├── styles/
    │   ├── tokens.css             # 设计 token(色板/字体/间距/圆角/动效)
    │   └── base.css               # reset + 排版基础
    └── views/
        └── AssistantView.vue      # Assistant 问答工作台
```

## 设计语言

- **暖米白**:`--c-bg-0: #FAFAF7` 起,4 档灰阶
- **主色**:teal `--c-accent: #0F766E`(克制使用)
- **字体**:Inter(sans) + JetBrains Mono(代码/编号/页码)
- **节奏**:4px 网格、subtle borders、表态通过色阶而非阴影
