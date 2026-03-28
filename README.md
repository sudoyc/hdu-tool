# HDU Contest Crawler

Fetches problems from an HDU OJ contest and saves them as Markdown files.

## Setup

```
uv sync
```

## Usage

```
uv run python fetch.py
```

On first run, you'll be prompted for your HDU contest username and password. These are saved to `credentials.txt` (gitignored) and reused automatically on subsequent runs.

You'll then be prompted for the contest ID and which problems to fetch. Press Enter at the problem selection prompt to fetch all problems.

## Output

Problems are saved to `output/{cid}/{pid}.md`.
