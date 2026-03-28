"""
HDU Contest Submit submodule — imported by hdu.py
"""
import time
import requests
from bs4 import BeautifulSoup

PENDING = {'', 'Judging', 'Pending', 'Compiling', 'Running', 'Queuing'}


def submit(session: requests.Session, cid: int, pid: str, code: str, language: int = 0) -> int:
    """Submit code and return the run_id."""
    url = f'https://acm.hdu.edu.cn/contest/submit?cid={cid}&pid={pid}'
    session.post(url, data={'language': str(language), 'code': code}, timeout=15)

    # The newest submission is always the first row
    rows = get_status(session, cid, n=1)
    if not rows:
        raise RuntimeError("Could not retrieve run_id after submission.")
    return int(rows[0]['run_id'])


def get_status(session: requests.Session, cid: int, n: int = 10) -> list[dict]:
    """Return the last n submission rows as dicts."""
    url = f'https://acm.hdu.edu.cn/contest/status?cid={cid}'
    resp = session.get(url, timeout=15)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table')
    if not table:
        return []
    rows = table.find_all('tr')[1:]  # skip header
    result = []
    for row in rows[:n]:
        cells = [td.get_text(strip=True) for td in row.find_all('td')]
        if len(cells) >= 7:
            result.append({
                'run_id':   cells[0],
                'time_str': cells[1],
                'pid':      cells[2],
                'time':     cells[3],
                'memory':   cells[4],
                'language': cells[5],
                'verdict':  cells[6],
            })
    return result


def poll_verdict(session: requests.Session, cid: int, run_id: int,
                 timeout: float = 30.0) -> dict:
    """Poll until verdict is final. Returns the full row dict."""
    rid = str(run_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = get_status(session, cid, n=20)
        for row in rows:
            if row['run_id'] == rid and row['verdict'] not in PENDING:
                return row
        time.sleep(0.5)
    return {'run_id': rid, 'verdict': 'Timeout', 'time': '-', 'memory': '-', 'language': '-', 'pid': '-', 'time_str': '-'}


def get_ce_log(session: requests.Session, cid: int, run_id: int) -> str:
    """Fetch compilation error log text."""
    url = f'https://acm.hdu.edu.cn/contest/compilation-error-log?cid={cid}&rid={run_id}'
    resp = session.get(url, timeout=15)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'lxml')
    el = soup.find('div', class_='compilation-error-log')
    return el.get_text() if el else '(no CE log available)'


# ── Standalone CLI ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse, sys
    from fetch import login, AuthError

    parser = argparse.ArgumentParser(description='Submit a solution to an HDU contest problem')
    parser.add_argument('cid', type=int, help='Contest ID')
    parser.add_argument('pid', help='Problem ID (e.g. 1001)')
    parser.add_argument('file', help='Path to .cpp file')
    parser.add_argument('--language', type=int, default=0,
                        help='Language code: 0=G++ (default), 5=Java')
    args = parser.parse_args()

    code = open(args.file, encoding='utf-8').read()

    try:
        session = login(args.cid)
    except AuthError as e:
        print(e); sys.exit(1)

    print(f"Submitting {args.file} for pid {args.pid}...", end=' ', flush=True)
    run_id = submit(session, args.cid, args.pid, code, args.language)
    print(f"run_id={run_id}, waiting for verdict...", end=' ', flush=True)

    row = poll_verdict(session, args.cid, run_id)
    print()
    print(f"  Run ID  : {row['run_id']}")
    print(f"  Problem : {row['pid']}")
    print(f"  Time    : {row['time']}")
    print(f"  Memory  : {row['memory']}")
    print(f"  Language: {row['language']}")
    print(f"  Verdict : {row['verdict']}")

    if row['verdict'] == 'Compilation Error':
        print()
        print(get_ce_log(session, args.cid, run_id))
