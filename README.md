# Zeej Blog

Zeej Blog 是一个邀请制个人站，包含碎碎念、项目展示、成员资料、聊天申请、私聊、通知、站务后台和站内机器人。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Axios
- 后端：FastAPI、SQLAlchemy、Pydantic、JWT
- 数据库：本地默认 SQLite；可通过 `DATABASE_URL` 切换其他 SQLAlchemy 数据库

## 本地启动

需要 Node.js、npm 和 Python 3.12（或兼容版本）。

```powershell
npm install
Copy-Item .env.example .env

Set-Location backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，至少设置：

- `SECRET_KEY`：不少于 16 位的随机字符串
- `ADMIN_EMAIL`：站长邮箱
- `ADMIN_PASSWORD`：首次建库使用，至少 8 位并同时包含字母和数字

分别启动后端和前端：

```powershell
# 终端 1
Set-Location backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# 终端 2（项目根目录）
npm run dev -- --port 5180 --strictPort
```

访问 `http://localhost:5180/`；API 文档位于 `http://127.0.0.1:8001/api/docs`。

也可在 Windows 中运行 `start.bat`。它依赖已经创建好的 `backend/.venv` 和两份 `.env` 文件。

## 验证

```powershell
npm run build
Set-Location backend
.\.venv\Scripts\python -m pytest -q
```

测试会强制使用临时 SQLite 数据库，不会读取或修改 `backend/blog.db`。

## 数据与迁移

后端启动时会自动调用 `app.migrate.migrate_schema()`。当前迁移属于轻量 SQL 迁移，不带版本号；启动包含真实数据的环境前必须先备份数据库。

```powershell
New-Item -ItemType Directory -Force backend\backups
Copy-Item backend\blog.db ("backend\backups\blog-{0}.db" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
```

备份文件、`.env`、数据库和上传内容均不得提交 Git。

## 配置与交接

- 前端配置模板：[`.env.example`](.env.example)
- 后端配置模板：[`backend/.env.example`](backend/.env.example)
- 接管、验证和发布检查：[`docs/TAKEOVER.md`](docs/TAKEOVER.md)

任何真实密码、SMTP 授权码、API Key、服务器登录信息都只能保存在受控密钥系统或本机 `.env` 中，不能写入 README、聊天记录或提交历史。
