# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import json
from datetime import datetime

# === Git自動同期（本番環境のみ） ===
PROJECT_ROOT = '/home/nnnkeita/kiroku-journal'
SYNC_STATUS_FILE = os.path.join(PROJECT_ROOT, '.wsgi_sync_status')

def log_sync_status(status, message):
    """同期状態をファイルに記録"""
    try:
        with open(SYNC_STATUS_FILE, 'w') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'status': status,
                'message': message
            }))
    except:
        pass

def perform_git_sync():
    """Git同期を実行"""
    try:
        # git pullを実行
        result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'pull', 'origin', 'main'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT
        )
        
        output = result.stdout + result.stderr
        
        if result.returncode == 0:
            msg = f"✅ Git pull success: {output[:100]}"
            print(msg, file=sys.stderr, flush=True)
            log_sync_status('success', output[:200])
            return True
        else:
            msg = f"⚠️ Git pull failed (code {result.returncode}): {output[:150]}"
            print(msg, file=sys.stderr, flush=True)
            log_sync_status('failed', output[:200])
            return False
            
    except subprocess.TimeoutExpired:
        msg = "[WSGI] ⚠️ Git pull timeout"
        print(msg, file=sys.stderr, flush=True)
        log_sync_status('timeout', 'Git pull timed out')
        return False
        
    except Exception as e:
        msg = f"[WSGI] ⚠️ Git sync error: {str(e)[:100]}"
        print(msg, file=sys.stderr, flush=True)
        log_sync_status('error', str(e)[:200])
        return False

# 初回起動時のみgit pullを実行
if not os.environ.get('WSGI_GIT_SYNCED') and os.path.exists(PROJECT_ROOT + '/.git'):
    print("[WSGI] Starting git sync...", file=sys.stderr, flush=True)
    perform_git_sync()
    os.environ['WSGI_GIT_SYNCED'] = '1'

# ============================================================

# PythonAnywhereの問題を回避：sys.pathをリセット
import builtins
_original_import = builtins.__import__

# venvから標準ライブラリを使う
venv_lib = '/home/nnnkeita/.virtualenvs/kiroku-journal/lib/python3.11'
if os.path.exists(venv_lib):
    sys.path = [venv_lib + '/site-packages', '/usr/lib/python3.11', '/usr/local/lib/python3.11']

os.chdir(PROJECT_ROOT)

# Flask アプリを読み込む
try:
    from dotenv import load_dotenv
    load_dotenv(f'{PROJECT_ROOT}/config/.env')

    from app.flask_app import app
    with app.app_context():
        from app.database import init_db
        init_db()

    application = app
    print("[WSGI] ✅ Application loaded successfully", file=sys.stderr, flush=True)
    
except Exception as e:
    print(f"[WSGI] ❌ Application load error: {e}", file=sys.stderr, flush=True)
    raise


