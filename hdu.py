"""
hdu-tool — interactive REPL for HDU contest problems
Usage: uv run python hdu.py [--target-dir PATH]
"""
import argparse
import re
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

_STYLE = Style.from_dict({
    'completion-menu.completion':         'bg:default fg:default',
    'completion-menu.completion.current': 'bg:default fg:default bold',
    'completion-menu':                    'bg:default fg:default',
})

# ANSI colors
_G = '\033[32m'   # green
_R = '\033[31m'   # red
_Y = '\033[33m'   # yellow
_C = '\033[36m'   # cyan
_RST = '\033[0m'

def _color_verdict(v: str) -> str:
    if v == 'Accepted':                return f'{_G}{v}{_RST}'
    if v in ('Wrong Answer', 'Runtime Error', 'Time Limit Exceeded',
             'Memory Limit Exceeded', 'Output Limit Exceeded'):
        return f'{_R}{v}{_RST}'
    if v == 'Compilation Error':       return f'{_Y}{v}{_RST}'
    if v in ('Judging', 'Pending', 'Compiling', 'Running', 'Queuing'):
        return f'{_C}{v}{_RST}'
    return v

import requests

import fetch as _fetch
import submit as _submit

DELAY = 0.4

HELP_TEXT = """\
Commands:
  use <cid>        — switch contest and login
  fetch [pid ...]  — fetch problems (all if no pids given)
  submit <pid>     — submit {pid}.cpp with live updating output
  submit <pid> -c  — submit with clean output (no live updates)
  status [n]       — show last n submissions (default 10)
  help             — show this message
  exit / quit      — exit"""


class State:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.cid: int | None = None
        self.session: requests.Session | None = None
        self.pids: list[str] = []

    @property
    def prompt(self) -> str:
        cid_str = str(self.cid) if self.cid else ''
        return f'hdu [{cid_str}]> '

    def require_contest(self):
        if self.cid is None or self.session is None:
            print("No contest selected. Run: use <cid>")
            return False
        return True


# ── Command handlers ──────────────────────────────────────────────────────────

def cmd_use(state: State, args: list[str]):
    if not args:
        print("Usage: use <cid>")
        return
    try:
        cid = int(args[0])
    except ValueError:
        print("cid must be an integer.")
        return

    print(f"Logging in to contest {cid}...", end=' ', flush=True)
    try:
        session = _fetch.login(cid)
    except _fetch.AuthError as e:
        print(f"\n{e}")
        return

    print("ok")
    print(f"Fetching problem list...", end=' ', flush=True)
    try:
        pids = _fetch.get_problem_ids(session, cid)
    except _fetch.AuthError as e:
        print(f"\n{e}")
        return

    state.cid = cid
    state.session = session
    state.pids = pids

    if pids:
        print(f"Contest {cid}: {len(pids)} problems ({pids[0]}–{pids[-1]})")
    else:
        print(f"Contest {cid}: no problems found (check access permissions)")


def cmd_fetch(state: State, args: list[str]):
    if not state.require_contest():
        return

    if args:
        selected = args
        unknown = [p for p in selected if p not in state.pids]
        if unknown:
            print(f"Unknown pids: {' '.join(unknown)}")
            return
    else:
        selected = state.pids

    results = []
    for pid in selected:
        print(f"Fetching {pid}...", end=' ', flush=True)
        try:
            title, info, sections = _fetch.fetch_problem(state.session, state.cid, pid)
            prob_dir = _fetch.save_problem_dir(state.target_dir, state.cid, pid, title, info, sections)
            results.append((pid, title, info, sections))
            print(f"done  →  {prob_dir}")
        except _fetch.AuthError:
            print("auth failure")
            return
        except requests.RequestException as e:
            print(f"network error: {e}")
        except Exception as e:
            print(f"error: {e}")
        time.sleep(DELAY)

    if results:
        md_path = _fetch.save_all_problems_md(state.target_dir, state.cid, results)
        print(f"problems.md  →  {md_path}")


def cmd_submit(state: State, args: list[str]):
    if not state.require_contest():
        return
    if not args:
        print("Usage: submit <pid> [-c]")
        return

    pid = args[0]
    clean = '-c' in args
    if '-c' in args:
        args.remove('-c')

    # Resolve .cpp file: canonical location first, then cwd fallback
    canonical = state.target_dir / str(state.cid) / pid / f'{pid}.cpp'
    if canonical.exists():
        cpp_file = canonical
    else:
        cwd_cpps = list(Path.cwd().glob('*.cpp'))
        if len(cwd_cpps) == 1:
            cpp_file = cwd_cpps[0]
        elif len(cwd_cpps) > 1:
            print("Multiple .cpp files in cwd:")
            for i, f in enumerate(cwd_cpps):
                print(f"  {i+1}. {f.name}")
            choice = input("Pick number: ").strip()
            try:
                cpp_file = cwd_cpps[int(choice) - 1]
            except (ValueError, IndexError):
                print("Invalid choice.")
                return
        else:
            print(f"No .cpp file found at {canonical} or in cwd.")
            return

    code = cpp_file.read_text(encoding='utf-8')
    print(f"Submitting {cpp_file.name} for pid {pid}...", end=' ', flush=True)

    try:
        run_id = _submit.submit(state.session, state.cid, pid, code)
    except Exception as e:
        print(f"submit error: {e}")
        return

    print(f"run_id={run_id}, waiting for verdict...", end=' ', flush=True)

    if not clean:
        BLOCK_LINES = 6
        UP = f'\033[{BLOCK_LINES}A'
        EL = '\033[K'
        def print_block(row: dict):
            print(f"  Run ID  : {row['run_id']}{EL}")
            print(f"  Problem : {row['pid']}{EL}")
            print(f"  Time    : {row['time']}{EL}")
            print(f"  Memory  : {row['memory']}{EL}")
            print(f"  Language: {row['language']}{EL}")
            print(f"  Verdict : {_color_verdict(row['verdict'])}{EL}", flush=True)

        row = None
        first = True
        for row in _submit.poll_verdict(state.session, state.cid, run_id):
            if not first:
                print(UP, end='')
            else:
                print()
                first = False
            print_block(row)
        final_row = row
    else:
        # In clean mode, we consume the generator but do not print anything until it finishes
        final_row = None
        for row in _submit.poll_verdict(state.session, state.cid, run_id):
            final_row = row
        print(f"done\n")
        if final_row:
            print(f"  Run ID  : {final_row['run_id']}")
            print(f"  Problem : {final_row['pid']}")
            print(f"  Time    : {final_row['time']}")
            print(f"  Memory  : {final_row['memory']}")
            print(f"  Language: {final_row['language']}")
            print(f"  Verdict : {_color_verdict(final_row['verdict'])}")

    if not final_row:
        print("Error: Could not retrieve verdict.")
        return

    if final_row['verdict'] == 'Compilation Error':
        print()
        log = _submit.get_ce_log(state.session, state.cid, run_id)
        print(log)


def cmd_status(state: State, args: list[str]):
    if not state.require_contest():
        return
    n = 10
    if args:
        try:
            n = int(args[0])
        except ValueError:
            print("Usage: status [n]")
            return

    rows = _submit.get_status(state.session, state.cid, n=n)
    if not rows:
        print("No submissions found.")
        return

    header = f"{'Run ID':<10} {'Time':<20} {'PID':<8} {'Exec':<10} {'Mem':<10} {'Lang':<8} Verdict"
    print(header)
    print('-' * len(header))
    for r in rows:
        print(f"{r['run_id']:<10} {r['time_str']:<20} {r['pid']:<8} {r['time']:<10} {r['memory']:<10} {r['language']:<8} {_color_verdict(r['verdict'])}")


# ── REPL ──────────────────────────────────────────────────────────────────────

COMMANDS = {
    'use':    cmd_use,
    'fetch':  cmd_fetch,
    'submit': cmd_submit,
    'status': cmd_status,
}


class _HduCompleter(Completer):
    def __init__(self, state: 'State'):
        self.state = state

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        tokens = text.split()
        word = document.get_word_before_cursor(pattern=re.compile(r'[^\s]+'))

        if not tokens or (len(tokens) == 1 and not text.endswith(' ')):
            # completing command name
            for cmd in list(COMMANDS) + ['help', 'exit', 'quit']:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
        elif tokens[0] in ('submit', 'fetch') and self.state.pids:
            # completing pid
            already = set(tokens[1:]) if text.endswith(' ') else set(tokens[1:-1])
            for pid in self.state.pids:
                if pid.startswith(word) and pid not in already:
                    yield Completion(pid, start_position=-len(word))


def repl(state: State):
    session: PromptSession = PromptSession(
        history=InMemoryHistory(),
        completer=_HduCompleter(state),
        complete_while_typing=False,
        style=_STYLE,
    )
    print("hdu-tool  (type 'help' for commands)")
    while True:
        try:
            line = session.prompt(state.prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ('exit', 'quit'):
            break
        elif cmd == 'help':
            print(HELP_TEXT)
        elif cmd in COMMANDS:
            try:
                COMMANDS[cmd](state, args)
            except Exception as e:
                print(f"Error: {e}")
        else:
            print(f"Unknown command: {cmd!r}. Type 'help' for commands.")


def main():
    parser = argparse.ArgumentParser(description='HDU Contest Tool')
    parser.add_argument('--target-dir', type=Path, default=None,
                        help='Root directory for problem output (default: parent of script dir)')
    args = parser.parse_args()

    if args.target_dir is not None:
        target_dir = args.target_dir.resolve()
    else:
        target_dir = (Path(__file__).parent / '..').resolve()

    repl(State(target_dir))


if __name__ == '__main__':
    main()
