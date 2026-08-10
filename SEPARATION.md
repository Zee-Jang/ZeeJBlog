# Zeej 目录分离说明

原 monorepo `Cursor/Todolist/` 已拆成两个独立项目：

| 新路径 | 说明 |
|--------|------|
| `d:\sdd\Cursor\blog` | Zeej 个人站（原 `Todolist/blog`） |
| `d:\sdd\Cursor\zeej-todolist` | 岸上 Todo（原 `Todolist/todolist`） |

> Windows 下文件夹名不区分大小写，`Todolist` 与 `todolist` 冲突，故 Todo 项目暂用名 **`zeej-todolist`**。关闭 Cursor 并删掉旧目录后，可自行改名为 `todolist`。

## 请你本地做的收尾

1. 在 Cursor 中 **关闭** 当前 `Todolist` 工作区  
2. **打开** `d:\sdd\Cursor\blog` 作为新工作区  
3. 确认两边都正常后，删除旧目录里的重复副本：
   - `d:\sdd\Cursor\Todolist\blog`
   - `d:\sdd\Cursor\Todolist\todolist`
4. 若 `Todolist` 只剩空壳 / `.claude`，可整夹删除或改名归档  
5. 新目录未复制 `node_modules` / `.venv`，需重新安装：

```bat
cd /d d:\sdd\Cursor\blog
npm install
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd /d d:\sdd\Cursor\zeej-todolist\frontend
npm install
cd ..\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

线上服务器 `/opt/todolist` 不受本次本机目录调整影响。
