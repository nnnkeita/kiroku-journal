# -*- coding: utf-8 -*-
import sys
import os
import subprocess

# === Git自動同期（本番環境のみ） ===
PROJECT_ROOT = '/home/nnnkeita/kiroku-journal'
if os.path.exists(PROJECT_ROOT + '/.git'):
    if not os.environ.get('WSGI_GIT_SYNCED'):
        try:
            result = subprocess.run(
                ['git', '-C', PROJECT_ROOT, 'pull', 'origin', 'main'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"[WSGI] ✅ Git pull success", file=sys.stderr, flush=True)
            else:
                print(f"[WSGI] ⚠️ Git pull: {result.stderr[:200]}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[WSGI] ⚠️ Git sync error: {str(e)[:100]}", file=sys.stderr, flush=True)
        os.environ['WSGI_GIT_SYNCED'] = '1'

# PythonAnywhereの問題を回避：sys.pathをリセット
import builtins
_original_import = builtins.__import__

# venvから標準ライブラリを使う
venv_lib = '/home/nnnkeita/.virtualenvs/kiroku-journal/lib/python3.11'
sys.path = [venv_lib + '/site-packages', '/usr/lib/python3.11', '/usr/local/lib/python3.11']

os.chdir(PROJECT_ROOT)

# Flask アプリを読み込む
from dotenv import load_dotenv
load_dotenv('/home/nnnkeita/kiroku-journal/config/.env')

from app.flask_app import app
with app.app_context():
    from app.database import init_db
    init_db()

application = app

