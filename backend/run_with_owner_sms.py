"""Supervise the existing web command and owner SMS worker in one paid instance.
Usage: python run_with_owner_sms.py -- <your existing web start command>
Apply migrations before using this launcher. Do not use with shell '&' commands.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    command = sys.argv[1:]
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        print('Usage: python run_with_owner_sms.py -- <existing web start command>', file=sys.stderr)
        return 2
    os.chdir(Path(__file__).resolve().parent)
    stopping = False
    children = []

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    exit_code = 0
    try:
        children.append(subprocess.Popen(command, start_new_session=True))
        children.append(subprocess.Popen([sys.executable, '-u', 'manage.py', 'process_owner_sms', '--loop'], start_new_session=True))
        while not stopping:
            if any(child.poll() is not None for child in children):
                # A dead worker must not leave a healthy-looking web service indefinitely.
                print('A StockFlow process exited; stopping both for service restart.', file=sys.stderr)
                exit_code = 1
                break
            time.sleep(1)
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == 'posix':
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.terminate()
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(child.pid, signal.SIGKILL)
                else:
                    child.kill()
                child.wait()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
