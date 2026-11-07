"""Convenience runner: starts two independent Flask node processes.

Usage from project root: python -m scripts.run_both
Stop with Ctrl+C. Separate browser windows: :5001 and :5002.
"""
import subprocess
import sys
import time


def main():
    processes = []
    try:
        for module in ('scripts.run_cesena', 'scripts.run_forli'):
            processes.append(subprocess.Popen([sys.executable, '-m', module]))
        print('Cesena: http://127.0.0.1:5001 | Forli: http://127.0.0.1:5002', flush=True)
        print('Press Ctrl+C to stop both servers.', flush=True)
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError('A node exited unexpectedly. Inspect the error output above.')
            time.sleep(0.4)
    except KeyboardInterrupt:
        print('\nStopping both nodes...', flush=True)
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == '__main__':
    main()
