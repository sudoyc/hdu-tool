# HDU Contest Crawler

Fetches problems from an HDU OJ contest and saves them as Markdown files.

## Setup

```
uv sync
```

## Cookie setup (recommended)

1. Log in to https://acm.hdu.edu.cn in your browser.
2. Export cookies in Netscape format using a browser extension (e.g. "Get cookies.txt LOCALLY").
3. Save the file as `cookie.txt` in this directory (next to `fetch.py`).

If your cookie expires, re-export and replace `cookie.txt`. Alternatively, the script can log in interactively with username/password (note: team accounts typically require cookie export).

## Usage

```
uv run python fetch.py
```

You'll be prompted for the contest ID and which problems to fetch. Press Enter at the problem selection prompt to fetch all problems.

## Output

Problems are saved to `output/{cid}/{pid}.md`.
