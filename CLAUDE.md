# HDU Contest Crawler

## 项目背景

从 HDU OJ 的私有比赛（需购买账号）爬取题面，保存为 Markdown 文件，供本地阅读或进一步处理。

## 文件结构

```
crawler/
├── fetch.py          # 主脚本
├── pyproject.toml    # uv 项目配置
├── uv.lock
├── credentials.txt   # 账号密码（gitignored，自动生成）
├── output/           # 输出目录（gitignored）
│   └── {cid}/
│       ├── 1001.md
│       └── ...
└── CLAUDE.md
```

## 运行方式

```
uv run python fetch.py
```

交互流程：
1. 输入 contest ID（默认 1198）
2. 脚本自动登录
3. 输入要抓取的题目编号（空格分隔），直接回车抓取全部
4. 输出到 `output/{cid}/{pid}.md`

## 登录机制

- 每个 contest 的登录是独立的，token 是 per-contest 的 JWT
- 登录端点：`POST https://acm.hdu.edu.cn/contest/login?cid={cid}`
- 表单字段：`username`, `password`
- 账号密码保存在 `credentials.txt`（格式 `username:password`），首次运行时提示输入
- 登录失败时自动删除 `credentials.txt`，下次重新提示

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
