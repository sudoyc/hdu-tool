"""
HDU Contest Problem Crawler — submodule
Imported by hdu.py; not meant to be run directly.
"""
import getpass
import shutil
import requests
from bs4 import BeautifulSoup
from pathlib import Path

CREDS_FILE = Path(__file__).parent / 'credentials.txt'
SKELETON = Path.home() / '.skeleton.cpp'
DELAY = 0.4

SAMPLE_IN  = {'sample input', '样例输入', '输入样例'}
SAMPLE_OUT = {'sample output', '样例输出', '输出样例'}


class AuthError(Exception):
    pass


# ── Auth helpers ──────────────────────────────────────────────────────────────

def is_auth_failure(resp) -> bool:
    if 'login' in resp.url:
        return True
    if 'name="password"' in resp.text and '<form' in resp.text:
        return True
    return False


def load_credentials() -> tuple[str, str]:
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
    username, password = load_credentials()
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'

    url = f'https://acm.hdu.edu.cn/contest/login?cid={cid}'
    resp = session.post(url, data={'username': username, 'password': password}, timeout=15)

    if is_auth_failure(resp):
        CREDS_FILE.unlink(missing_ok=True)
        raise AuthError("Login failed. Credentials removed — please check your username/password.")

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
        raise ValueError("No valid problems selected.")
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


# ── Sample extraction ─────────────────────────────────────────────────────────

def extract_samples(sections: list) -> tuple[str, str]:
    def strip_fences(s: str) -> str:
        lines = s.splitlines()
        if lines and lines[0].strip().startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        return '\n'.join(lines)

    first_in = first_out = ''
    for label, content in sections:
        key = label.strip().lower()
        if not first_in and key in SAMPLE_IN:
            first_in = strip_fences(content)
        if not first_out and key in SAMPLE_OUT:
            first_out = strip_fences(content)
    return first_in, first_out


# ── Saving ────────────────────────────────────────────────────────────────────

def save_problem_dir(target_dir: Path, cid: int, pid: str,
                     title: str, info: dict, sections: list) -> Path:
    prob_dir = target_dir / str(cid) / pid
    prob_dir.mkdir(parents=True, exist_ok=True)

    (prob_dir / 'problem.md').write_text(
        to_markdown(pid, title, info, sections), encoding='utf-8')

    cpp_dest = prob_dir / f'{pid}.cpp'
    if SKELETON.exists():
        shutil.copy2(SKELETON, cpp_dest)
    else:
        cpp_dest.write_text('', encoding='utf-8')

    first_in, first_out = extract_samples(sections)
    (prob_dir / 'input.txt').write_text(first_in, encoding='utf-8')
    (prob_dir / 'output.txt').write_text(first_out, encoding='utf-8')
    (prob_dir / f'{pid}_input0.txt').write_text(first_in, encoding='utf-8')
    (prob_dir / f'{pid}_output0.txt').write_text(first_out, encoding='utf-8')

    return prob_dir


def save_all_problems_md(target_dir: Path, cid: int,
                         results: list[tuple[str, str, dict, list]]):
    parts = [to_markdown(pid, title, info, sections)
             for pid, title, info, sections in results]
    out = (target_dir / str(cid) / 'problems.md')
    out.write_text('\n\n---\n\n'.join(parts), encoding='utf-8')
    return out


# ── Standalone CLI ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse, sys, time

    parser = argparse.ArgumentParser(description='Fetch HDU contest problems')
    parser.add_argument('cid', type=int, help='Contest ID')
    parser.add_argument('pids', nargs='*', help='Problem IDs (default: all)')
    parser.add_argument('--target-dir', type=Path, default=None,
                        help='Output root (default: parent of this script)')
    args = parser.parse_args()

    target_dir = args.target_dir.resolve() if args.target_dir else (Path(__file__).parent / '..').resolve()

    try:
        session = login(args.cid)
    except AuthError as e:
        print(e); sys.exit(1)

    try:
        all_pids = get_problem_ids(session, args.cid)
    except AuthError as e:
        print(e); sys.exit(1)

    selected = args.pids if args.pids else all_pids
    unknown = [p for p in selected if p not in all_pids]
    if unknown:
        print(f"Unknown pids: {' '.join(unknown)}"); sys.exit(1)

    results = []
    for pid in selected:
        print(f"Fetching {pid}...", end=' ', flush=True)
        try:
            title, info, sections = fetch_problem(session, args.cid, pid)
            prob_dir = save_problem_dir(target_dir, args.cid, pid, title, info, sections)
            results.append((pid, title, info, sections))
            print(f"done  →  {prob_dir}")
        except AuthError as e:
            print(f"auth failure: {e}"); sys.exit(1)
        except Exception as e:
            print(f"error: {e}")
        time.sleep(DELAY)

    if results:
        print(f"problems.md  →  {save_all_problems_md(target_dir, args.cid, results)}")
