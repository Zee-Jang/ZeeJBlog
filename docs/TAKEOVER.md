# 项目接管手册

## 当前边界

- 主项目：Zeej Blog（本仓库）
- Todo 项目已经拆分，不属于本仓库的运行时依赖
- 前端默认端口：`5180`
- 后端默认端口：`8001`
- 后端健康检查：`GET /api/health`
- 本地数据库默认位置：`backend/blog.db`
- 上传目录：`backend/uploads/`

接管基线来自 `codex/takeover-baseline` 分支。接管前遗留的未提交成果已原样保存在提交 `3166908`，没有推送远程。

## 启动副作用

导入 `app.main` 会创建上传目录；FastAPI 启动阶段还会：

1. 调用 `migrate_schema()` 创建表并补充字段；
2. 创建或校正站长账户；
3. 创建机器人账户、默认项目、默认内容和站点设置。

因此，排查生产数据库时不能直接用开发配置启动。先确认 `DATABASE_URL` 指向，再备份数据库。

## 配置分级

必须配置：

- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_EMAIL`
- 首次初始化所需的 `ADMIN_PASSWORD`

按功能选配：

- SMTP：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`
- DeepSeek：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`
- 远程项目导入：`GITHUB_TOKEN`、`GITEE_TOKEN`
- 旧聊天表重建：`DROP_LEGACY_CHAT_TABLES=true`。检测到旧版 `visitor_id` 结构时启动会直接报错；只有备份数据库后显式开启，才会重建聊天表（清空聊天记录）

生产环境必须保持：

- `MAIL_DEV_MODE=false`
- `SEED_DEFAULT_INVITE=false`
- `CORS_ORIGINS` 只包含实际站点域名

## 发布前检查

1. 工作区无意外改动：`git status --short`
2. 前端构建通过：`npm run build`
3. 后端测试通过：在 `backend` 中运行 `python -m pytest -q`
4. 生产数据库和上传目录已有独立备份
5. 用脱敏后的配置检查 SMTP、机器人和远程仓库功能
6. 部署后检查 `/api/health`、登录、帖子列表、聊天和管理后台
7. 确认浏览器控制台与服务日志没有新错误

仓库内的 `.github/workflows/verify.yml` 会在 GitHub 的 push 和 pull request 上执行同样的前端构建与后端测试。

## 当前技术债

- 自定义迁移没有版本表、升级记录和回滚能力，后续应迁移到 Alembic。
- 自动化测试刚建立基线，聊天撤回/引用、用户删除/恢复等状态流转仍需覆盖。
- 部署主机、反向代理和进程管理方式尚无可信文档。
- 前端认证令牌存储在 `localStorage`；必须持续控制 XSS 风险，后续可评估 httpOnly Cookie。
- 历史会话中出现过敏感字段或命令片段，应按敏感资料管理，并轮换可能暴露过的凭据。

## 禁止事项

- 不把 `.env`、数据库、用户上传文件或服务器私钥提交到 Git。
- 不在未备份数据库时运行新的迁移。
- 不把历史对话中描述的“已部署”视作线上验证结果。
- 不在一个巨大提交中混合数据库、后端接口和前端交互修复。
