"""
HDU Contest Submit submodule — imported by hdu.py
"""
import time
import requests
from bs4 import BeautifulSoup

PENDING = {'', 'Judging', 'Pending', 'Compiling', 'Running', 'Queuing'}


def submit(session: requests.Session, cid: int, pid: str, code: str, language: int = 0) -> int:
    """Submit code and return the run_id."""
    # 1. Get the current max run_id before submitting
    pre_rows = get_status(session, cid, n=1)
    pre_max_id = int(pre_rows[0]['run_id']) if pre_rows else 0

    # 2. Submit the code
    url = f'https://acm.hdu.edu.cn/contest/submit?cid={cid}&pid={pid}'
    # allow_redirects=False lets us check if it successfully returns a 302
    resp = session.post(url, data={'language': str(language), 'code': code},
                        timeout=15, allow_redirects=False)

    if resp.status_code != 302:
        # If it didn't redirect to status, submission failed (e.g. rate limit, too short, unauth)
        soup = BeautifulSoup(resp.text, 'lxml')
        error_div = soup.find('div', class_='submit-error')
        err_msg = error_div.get_text(strip=True) if error_div else "Unknown submission error"
        raise RuntimeError(f"Submission failed (HTTP {resp.status_code}): {err_msg}")

    # 3. Fetch status and verify we got a NEW run_id
    # Sometimes it takes a fraction of a second for the DB to update
    for _ in range(5):
        rows = get_status(session, cid, n=3)
        for row in rows:
            if int(row['run_id']) > pre_max_id:
                return int(row['run_id'])
        time.sleep(0.5)

    raise RuntimeError("Submission seemed to succeed but new run_id did not appear in status list.")


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
                 timeout: float = 30.0):
    """Yield status rows until verdict is final (or timeout)."""
    rid = str(run_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = get_status(session, cid, n=20)
        for row in rows:
            if row['run_id'] == rid:
                yield row
                if row['verdict'] not in PENDING:
                    return
                break
        time.sleep(0.2)
    yield {'run_id': rid, 'verdict': 'Timeout', 'time': '-', 'memory': '-', 'language': '-', 'pid': '-', 'time_str': '-'}


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

    _G = '\033[32m'; _R = '\033[31m'; _Y = '\033[33m'; _RST = '\033[0m'
    def _cv(v):
        if v == 'Accepted': return f'{_G}{v}{_RST}'
        if v == 'Compilation Error': return f'{_Y}{v}{_RST}'
        return f'{_R}{v}{_RST}'

    parser = argparse.ArgumentParser(description='Submit a solution to an HDU contest problem')
    parser.add_argument('cid', type=int, help='Contest ID')
    parser.add_argument('pid', help='Problem ID (e.g. 1001)')
    parser.add_argument('file', help='Path to .cpp file')
    parser.add_argument('--language', type=int, default=0,
                        help='Language code: 0=G++ (default), 5=Java')
    parser.add_argument('-c', '--clean', action='store_true',
                        help='Clean mode: wait for final verdict without live updates')
    args = parser.parse_args()

    code = open(args.file, encoding='utf-8').read()

    try:
        session = login(args.cid)
    except AuthError as e:
        print(e); sys.exit(1)

    print(f"Submitting {args.file} for pid {args.pid}...", end=' ', flush=True)
    run_id = submit(session, args.cid, args.pid, code, args.language)
    print(f"run_id={run_id}, waiting for verdict...", end=' ', flush=True)

    if not args.clean:
        UP = '\033[6A'
        EL = '\033[K'
        row = None
        first = True
        for row in poll_verdict(session, args.cid, run_id):
            if not first:
                print(UP, end='')
            else:
                print()
                first = False
            print(f"  Run ID  : {row['run_id']}{EL}")
            print(f"  Problem : {row['pid']}{EL}")
            print(f"  Time    : {row['time']}{EL}")
            print(f"  Memory  : {row['memory']}{EL}")
            print(f"  Language: {row['language']}{EL}")
            print(f"  Verdict : {_cv(row['verdict'])}{EL}", flush=True)
        final_row = row
    else:
        final_row = None
        for row in poll_verdict(session, args.cid, run_id):
            final_row = row

        if not final_row:
            print("\nError: Could not retrieve verdict.")
            sys.exit(1)

        print(f"done\n")
        print(f"  Run ID  : {final_row['run_id']}")
        print(f"  Problem : {final_row['pid']}")
        print(f"  Time    : {final_row['time']}")
        print(f"  Memory  : {final_row['memory']}")
        print(f"  Language: {final_row['language']}")
        print(f"  Verdict : {_cv(final_row['verdict'])}")

    if final_row and final_row['verdict'] == 'Compilation Error':
        print()
        print(get_ce_log(session, args.cid, run_id))
