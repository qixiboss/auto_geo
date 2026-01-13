# AutoGeo 智能多平台文章发布助手

> 老王备注：一个用 Electron + Vue3 + FastAPI + Playwright 搞的桌面应用，自动发布文章到多个平台！

## 功能特性

- ✅ **多平台支持**：知乎、百家号、搜狐、头条号
- ✅ **账号管理**：安全的 Cookie 存储和授权
- ✅ **文章编辑**：富文本编辑器，支持图片上传
- ✅ **批量发布**：一键发布到多个平台
- ✅ **发布进度**：实时查看发布状态
- ✅ **桌面应用**：Electron 跨平台客户端

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 后端 | FastAPI + SQLAlchemy + Playwright |
| 桌面 | Electron |
| 数据库 | SQLite |

## 快速开始

### 环境要求

- **Node.js**: 18+ 
- **Python**: 3.10+
- **操作系统**: Windows / macOS / Linux

### 1. 克隆项目

```bash
git clone https://github.com/aAAaqwq/auto_geo.git
cd auto_geo
```

### 2. 启动后端

```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 启动后端服务
python main.py
```

后端服务运行在 `http://127.0.0.1:8001`

### 3. 启动前端

```bash
# 新开一个终端，进入前端目录
cd fronted

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端会自动打开 Electron 桌面窗口。

## 目录结构

```
auto_geo/
├── backend/              # 后端服务 (FastAPI)
│   ├── api/              # API 路由
│   ├── database/         # 数据库
│   ├── services/         # 业务服务
│   ├── main.py           # 入口文件
│   └── requirements.txt  # Python 依赖
│
├── fronted/              # 前端应用 (Electron + Vue3)
│   ├── electron/         # Electron 主进程
│   ├── src/              # Vue 源码
│   ├── package.json      # Node 依赖
│   └── vite.config.ts    # Vite 配置
│
├── docs/                 # 项目文档
│   ├── overview/         # 项目总览
│   ├── architecture/     # 架构设计
│   └── features/         # 功能说明
│
└── README.md             # 本文件
```

## 常用命令

### 后端

```bash
cd backend
python main.py           # 启动服务
```

### 前端

```bash
cd fronted
npm run dev              # 启动开发服务器
npm run build            # 构建生产版本
npm run type-check       # TypeScript 类型检查
```

## API 文档

后端启动后访问：`http://127.0.0.1:8001/docs`

## 开发说明

### 端口配置

| 服务 | 地址 |
|------|------|
| 前端开发服务器 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8001 |
| WebSocket | ws://127.0.0.1:8001/ws |

### 数据存储

- **数据库**: `backend/database/auto_geo.db`
- **Cookies**: `.cookies/` 目录
- **日志**: `logs/` 目录

## 常见问题

### Q: 前端启动后提示无法连接后端？

A: 需要先启动后端服务。开两个终端，分别运行：
- 终端1: `cd backend && python main.py`
- 终端2: `cd fronted && npm run dev`

### Q: Playwright 浏览器安装失败？

A: 使用国内镜像：
```bash
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
playwright install chromium
```

### Q: 编译 TypeScript 时报错？

A: 先运行 `npm run build:electron` 编译 Electron 主进程代码。

## 许可证

MIT License

---

**维护者**: 老王
**更新日期**: 2025-01-13
