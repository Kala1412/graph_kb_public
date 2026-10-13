# 医疗知识库前端

医疗知识库与智能问答项目的 Web 界面，使用 Vue 3、Vite、Element Plus 和 Pinia。包含知识库管理、流式问答、图谱浏览、个人档案、讨论区以及管理员页面。

项目背景、后端配置与整体运行方式见 [项目说明](../README.md)，开发约定见 [AGENTS.md](../AGENTS.md)。

## 本地开发

使用 Node.js 20.19+ 或 22.12+，并先启动后端及存储服务。API 配置位于 `src/api/index.js`。

```sh
npm install
npm run dev
```

## 构建与检查

```sh
npm run build
npm run preview
```

`npm run lint` 会执行 Oxlint 和 ESLint 自动修复；`npm run format` 使用 Prettier 重写源码格式。运行前确认工作区中的修改范围。

## 目录

- `src/api/`：接口封装、Token 刷新和 SSE 解析。
- `src/router/`：路由与权限守卫。
- `src/stores/`：会话及本地状态。
- `src/views/`：用户页面，`admin/` 下为管理页面。
- `src/components/`：图谱画布、文件状态等共享组件。
