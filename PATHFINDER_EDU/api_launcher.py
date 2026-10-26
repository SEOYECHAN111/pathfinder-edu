# -*- coding: utf-8 -*-
"""Compatibility launcher. Keys are configured in the administrator portal.

No terminal prompt and no secrets are printed or embedded in the script.
Environment variables may still be set by advanced users.
"""
import subprocess
import socket
import os
import sys
from pathlib import Path


def main():
    site = Path(__file__).resolve().parent
    port = int(os.environ.get('PF_PORT','8765'))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check:
        check.settimeout(0.7)
        try:
            check.connect(('127.0.0.1',port))
        except OSError:
            pass
        else:
            print(f'ERROR: 127.0.0.1:{port} is already in use.')
            print('An older PATHFINDER server may still be running. Close its black terminal window and launch this version again.')
            print('If needed, run: set PF_PORT=8879, and then launch this batch file in the same CMD window.')
            return 2
    print('PATHFINDER EDU: http://127.0.0.1:8765/')
    print('ADMIN > API 키·사용량 관리: Secret Key 등록, 사용량 Tracking, 연결 테스트')
    print('Windows: saved keys are encrypted with current-user DPAPI.')
    return subprocess.call([sys.executable, str(site / 'server.py')], cwd=str(site))

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
