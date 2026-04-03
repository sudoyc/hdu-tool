# hdu-tool

HDU OJ 私有比赛题面爬取 + 提交工具。

## 依赖

```
uv sync   # 安装 requests, beautifulsoup4, lxml, prompt_toolkit
```

首次运行时会提示输入账号密码，保存到 `credentials.txt`（已 gitignore）。

可选：在 `~/.skeleton.cpp` 放默认代码模板，fetch 时会自动复制到每题目录。

---

## 推荐用法：交互式 REPL

```
uv run python hdu.py [--target-dir PATH]
```

`--target-dir` 默认是脚本上一级目录（即 `contest/`）。

```
hdu []> use 1212          # 登录并切换比赛
hdu [1212]> fetch         # 抓取全部题目
hdu [1212]> fetch 1001    # 只抓 1001
hdu [1212]> submit 1001   # 提交，显示实时判题动画
hdu [1212]> submit 1001 -c# 提交，开启 clean 模式（无动画，阻塞直到最终结果）
hdu [1212]> status        # 查看最近 10 条提交记录
hdu [1212]> status 20     # 查看最近 20 条
hdu [1212]> exit
```

支持上下方向键浏览历史，Tab 补全命令名和题号（基于 `prompt_toolkit`，zsh/bash 均可用）。

---

## 单独使用 fetch.py

```
uv run python fetch.py <cid> [pid ...] [--target-dir PATH]
```

```bash
# 抓取比赛 1212 的全部题目，输出到 ../1212/
uv run python fetch.py 1212

# 只抓 1001 和 1002
uv run python fetch.py 1212 1001 1002

# 指定输出目录
uv run python fetch.py 1212 --target-dir ~/contest
```

每题输出到 `{target-dir}/{cid}/{pid}/`，包含：

重复 fetch 时，`problem.md`、`{pid}_input0.txt`、`{pid}_output0.txt` 会覆盖更新；`input.txt`、`output.txt`、`{pid}.cpp` 仅首次创建，不会覆盖你的修改。

```
1212/
  problems.md          ← 所有题面合并
  1001/
    problem.md
    1001.cpp           ← 从 ~/.skeleton.cpp 复制
    input.txt          ← 第一个样例输入
    output.txt         ← 第一个样例输出
    1001_input0.txt    ← 同 input.txt（编辑器插件格式）
    1001_output0.txt   ← 同 output.txt
```

---

## 单独使用 submit.py

```
uv run python submit.py <cid> <pid> <file> [--language N] [-c/--clean]
```

```bash
# 提交 1001.cpp，显示判题动画
uv run python submit.py 1212 1001 1001.cpp

# 指定语言（0=G++，5=Java，默认 0）
uv run python submit.py 1212 1001 Solution.java --language 5
```

提交后实时刷新判题状态（Time / Memory / Verdict 原地更新），直到得到最终结果。Verdict 带颜色显示。如果是 CE，自动打印编译错误详情。

---

## 文件结构

```
hdu-tool/
  hdu.py          ← 交互式 REPL 入口
  fetch.py        ← 题面爬取（可独立运行）
  submit.py       ← 代码提交（可独立运行）
  credentials.txt ← 账号密码（自动生成，gitignored）
  pyproject.toml
```
