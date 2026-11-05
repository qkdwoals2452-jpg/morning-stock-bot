"""Bounded polling session; GitHub schedule is recovery, not the poll clock."""
import argparse
import os
import time
import requests
import subprocess
from breaking_news import run


def deployment_changed():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        return False
    try:
        local = subprocess.check_output(['git', 'rev-parse', 'HEAD'], timeout=10).decode().strip()
        remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'],
                                         stderr=subprocess.DEVNULL, timeout=10).decode().split()
        return bool(remote and remote[0] != local)
    except (OSError, subprocess.SubprocessError):
        print('BREAKING VERSION CHECK UNAVAILABLE', flush=True)
        return False


def poll(cycles, interval=300, scan=run, clock=time.monotonic, sleep=time.sleep,
         should_handoff=lambda: False):
    if not 1 <= cycles <= 66 or interval < 300:
        raise ValueError('1..66 cycles; interval must be at least 300 seconds')
    completed = errors = 0
    for index in range(cycles):
        started = clock()
        scan_ok = False
        try:
            scan()
            completed += 1
            scan_ok = True
        except Exception as exc:
            # API errors can contain credentials; log only the exception type.
            errors += 1
            print('BREAKING POLL ERROR:', index + 1, type(exc).__name__, flush=True)
        print('BREAKING POLL:', index + 1, 'completed:', completed, 'errors:', errors, flush=True)
        if scan_ok and should_handoff():
            print('BREAKING SAFE HANDOFF: completed checkpoint before deployment change', flush=True)
            break
        if index + 1 < cycles:
            sleep(max(0, interval - (clock() - started)))
    if not completed:
        raise RuntimeError('모든 감시 조회 실패')


def handoff():
    token = os.environ['GH_TOKEN']
    repo = os.environ['GITHUB_REPOSITORY']
    # No self-dispatch from local machines or untrusted branches.
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise RuntimeError('main 운영 실행에서만 감시 인계 가능')
    try:
        response = requests.post(
            f'https://api.github.com/repos/{repo}/actions/workflows/breaking-news.yml/dispatches',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'},
            json={'ref': 'main'}, timeout=20)
        if response.status_code != 204:
            raise RuntimeError('감시 인계 요청 거부')
    except Exception:
        raise RuntimeError('다음 감시 실행 인계 실패; 예약 복구 또는 수동 실행 필요') from None
    print('BREAKING HANDOFF ACCEPTED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycles', type=int, default=66)
    parser.add_argument('--handoff-only', action='store_true')
    args = parser.parse_args()
    if args.handoff_only:
        handoff()
    else:
        poll(args.cycles, should_handoff=deployment_changed)
