# HDU Contest Tool

## 项目背景

从 HDU OJ 的私有比赛（需购买账号）爬取题面、自动建立题目目录结构，并支持代码提交与判题结果轮询。

## 文件结构

```
hdu-tool/
├── hdu.py            # 交互式 REPL 入口（推荐）
├── fetch.py          # 题面爬取（可独立运行）
├── submit.py         # 代码提交（可独立运行）
├── pyproject.toml    # uv 项目配置
├── uv.lock
├── credentials.txt   # 账号密码（gitignored，自动生成）
└── CLAUDE.md
```

输出目录（在 hdu-tool 的上一级，即 `contest/`）：

```
contest/
└── {cid}/
    ├── problems.md       # 所有题面合并
    └── {pid}/
        ├── problem.md
        ├── {pid}.cpp     # 从 ~/.skeleton.cpp 复制
        ├── input.txt     # 第一个样例输入
        ├── output.txt    # 第一个样例输出
        ├── {pid}_input0.txt
        └── {pid}_output0.txt
```

## 运行方式

### 推荐：交互式 REPL

```
uv run python hdu.py [--target-dir PATH]
```

命令：`use <cid>`、`fetch [pid ...]`、`submit <pid>`、`status [n]`、`help`、`exit`

支持上下方向键历史、Tab 补全命令名和题号。

### 独立运行

```bash
uv run python fetch.py <cid> [pid ...] [--target-dir PATH]
uv run python submit.py <cid> <pid> <file> [--language N]
```

## 登录机制

- 每个 contest 的登录是独立的，token 是 per-contest 的 JWT
- 登录端点：`POST https://acm.hdu.edu.cn/contest/login?cid={cid}`
- 表单字段：`username`, `password`
- 账号密码保存在 `credentials.txt`（格式 `username:password`），首次运行时提示输入
- 登录失败时自动删除 `credentials.txt`，下次重新提示

## 提交机制

- 提交端点：`POST https://acm.hdu.edu.cn/contest/submit?cid={cid}&pid={pid}`
- 表单字段：`language`（0=G++，5=Java）、`code`（源码文本）
- 无 CSRF token
- 提交后轮询 `/contest/status?cid={cid}`，取第一行匹配 run_id 的 verdict
- CE 详情：`GET /contest/compilation-error-log?cid={cid}&rid={run_id}`，解析 `div.compilation-error-log`

## 题面结构（HTML → Markdown）

- 题目列表页：`/contest/problems?cid={cid}`，解析 `pid=` 链接
- 单题页：`/contest/problem?cid={cid}&pid={pid}`
- 题面内容在 `div.problem-detail-block` 里，OJ 本身已用 Markdown 存储（含 `$...$` 公式），直接提取文本即可，无需转换
- 样例输入输出在 `div.problem-detail-value.code-block`，用 ` ``` ` 包裹

## 关键决策记录

- 最初用 cookie 方案，后来发现每个 contest 的 cookie 独立，改为账号密码自动登录更合适
- 不用 Selenium，HDU 题面是服务端渲染，`requests` + `bs4` 足够
- 请求间隔 `DELAY = 0.4s`，避免被封
- `is_auth_failure()` 检测响应 URL 含 `login` 或响应体含 `name="password"` 来判断鉴权失败
- 输出目录用 pid 作为文件夹名（如 `1001/`），不转换为字母（A/B/C），适应 HDU 的绝对编号习惯
- `readline.set_completer_delims(' \t')` 确保 Tab 补全时 pid 不被 `-` 等字符截断
