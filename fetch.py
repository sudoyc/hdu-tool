"""
HDU Contest Problem Crawler
Usage: uv run python fetch.py
"""
import getpass
import sys
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

CREDS_FILE = Path(__file__).parent / 'credentials.txt'
OUT_BASE = Path(__file__).parent / 'output'
DELAY = 0.4


class AuthError(Exception):
    pass


# ── Auth helpers ──────────────────────────────────────────────────────────────

def is_auth_failure(resp) -> bool:
    if 'login' in resp.url:
        return True
    # contest login page contains a password field
    if 'name="password"' in resp.text and '<form' in resp.text:
        return True
    return False


def load_credentials() -> tuple[str, str]:
    """Load saved credentials, or prompt and save them."""
    if CREDS_FILE.exists():
        try:
            text = CREDS_FILE.read_text().strip()
            username, password = text.split(':', 1)
            return username, password
        except Exception:
            print("credentials.txt is malformed, please re-enter.")

    print("Enter your HDU contest credentials (saved to credentials.txt for future use).")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    CREDS_FILE.write_text(f"{username}:{password}")
    return username, password


def login(cid: int) -> requests.Session:
    """Log in to the contest and return an authenticated session."""
    username, password = load_credentials()
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'

    url = f'https://acm.hdu.edu.cn/contest/login?cid={cid}'
    resp = session.post(url, data={'username': username, 'password': password}, timeout=15)

    if is_auth_failure(resp):
        # Credentials may be wrong — delete saved file so user is re-prompted next time
        CREDS_FILE.unlink(missing_ok=True)
        print("Login failed. Credentials removed — please check your username/password.")
        sys.exit(1)

    return session


# ── Prompts ───────────────────────────────────────────────────────────────────

def prompt_cid() -> int:
    while True:
        raw = input("Contest ID [1198]: ").strip()
        if not raw:
            return 1198
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer.")


def prompt_pid_selection(pids: list[str]) -> list[str]:
    raw = input("Which problems? (space-separated IDs, or Enter for all): ").strip()
    if not raw:
        return pids
    selected = raw.split()
    invalid = [p for p in selected if p not in pids]
    if invalid:
        print(f"Warning: {invalid} not in problem list, skipping.")
    valid = [p for p in selected if p in pids]
    if not valid:
        print("No valid problems selected.")
        sys.exit(1)
    return valid


# ── Fetching ──────────────────────────────────────────────────────────────────

def get_problem_ids(session: requests.Session, cid: int) -> list[str]:
    url = f'https://acm.hdu.edu.cn/contest/problems?cid={cid}'
    resp = session.get(url, timeout=15)
    resp.encoding = 'utf-8'
    if is_auth_failure(resp):
        raise AuthError("Not authenticated.")
    soup = BeautifulSoup(resp.text, 'lxml')
    pids = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'contest/problem?' in href and 'pid=' in href:
            pid = href.split('pid=')[-1].split('&')[0]
            if pid not in pids:
                pids.append(pid)
    return pids


def fetch_problem(session: requests.Session, cid: int, pid: str):
    url = f'https://acm.hdu.edu.cn/contest/problem?cid={cid}&pid={pid}'
    resp = session.get(url, timeout=15)
    resp.encoding = 'utf-8'
    if is_auth_failure(resp):
        raise AuthError("Session expired mid-fetch.")
    soup = BeautifulSoup(resp.text, 'lxml')

    title = ''
    sidebar = soup.find('div', class_='problem-sidebar')
    if sidebar:
        h = sidebar.find(['h1', 'h2', 'h3'])
        if h:
            title = h.get_text(strip=True)
    if not title:
        title = soup.title.string if soup.title else f'Problem {pid}'

    info = {}
    for pair in soup.find_all('div', class_='info-pair'):
        label_el = pair.find('div', class_='info-label')
        value_el = pair.find('div', class_='info-value')
        if label_el and value_el:
            info[label_el.get_text(strip=True)] = value_el.get_text(strip=True)

    sections = []
    for block in soup.find_all('div', class_='problem-detail-block'):
        label_el = block.find('div', class_='problem-detail-label')
        value_el = block.find('div', class_='problem-detail-value')
        if not label_el or not value_el:
            continue
        label = label_el.get_text(strip=True)
        if 'code-block' in value_el.get('class', []):
            content = f'```\n{value_el.get_text()}\n```'
        else:
            content = value_el.get_text('\n', strip=False).strip()
        sections.append((label, content))

    return title, info, sections


def to_markdown(pid: str, title: str, info: dict, sections: list) -> str:
    lines = [f'# {pid} {title}', '']
    if info:
        for k, v in info.items():
            lines.append(f'- **{k}**: {v}')
        lines.append('')
    for label, content in sections:
        lines += [f'## {label}', '', content, '']
    return '\n'.join(lines)


def save_problem(cid: int, pid: str, md: str) -> Path:
    out_dir = OUT_BASE / str(cid)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{pid}.md'
    path.write_text(md, encoding='utf-8')
    return path


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("HDU Contest Problem Crawler")
    print("----------------------------")

    cid = prompt_cid()
    session = login(cid)

    print(f"\nFetching problem list for contest {cid}...")
    try:
        pids = get_problem_ids(session, cid)
    except AuthError as e:
        print(f"Auth error: {e}")
        sys.exit(1)

    if not pids:
        print("No problems found. Check the contest ID or your access permissions.")
        sys.exit(1)

    print(f"Found {len(pids)} problems: {' '.join(pids)}\n")
    selected = prompt_pid_selection(pids)

    for pid in selected:
        print(f"Fetching {pid}...", end=' ', flush=True)
        try:
            title, info, sections = fetch_problem(session, cid, pid)
            md = to_markdown(pid, title, info, sections)
            path = save_problem(cid, pid, md)
            print(f"done  →  {path.relative_to(Path(__file__).parent)}")
        except AuthError:
            print("auth failure — stopping.")
            sys.exit(1)
        except requests.RequestException as e:
            print(f"network error: {e}")
        except Exception as e:
            print(f"error: {e}")
        time.sleep(DELAY)

    print("\nAll done.")


if __name__ == '__main__':
    main()
