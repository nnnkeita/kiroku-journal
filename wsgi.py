# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import json
import shutil
from datetime import datetime

# === Git自動同期 + キャッシュクリア（毎回実行） ===
PROJECT_ROOT = '/home/nnnkeita/kiroku-journal'
SYNC_STATUS_FILE = os.path.join(PROJECT_ROOT, '.wsgi_sync_status')
LAST_SYNC_FILE = os.path.join(PROJECT_ROOT, '.wsgi_last_sync_hash')

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

def get_current_git_hash():
    """現在のGitハッシュを取得"""
    try:
        result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

def get_last_sync_hash():
    """前回の同期時点のGitハッシュを取得"""
    try:
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, 'r') as f:
                return f.read().strip()
    except:
        pass
    return None

def save_sync_hash(git_hash):
    """同期完了時のGitハッシュを保存"""
    try:
        with open(LAST_SYNC_FILE, 'w') as f:
            f.write(git_hash)
    except:
        pass

def clear_python_cache():
    """Pythonのバイトコンパイル済みファイルをクリア"""
    try:
        # app フォルダ配下の __pycache__ をクリア
        for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, 'app')):
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                print(f"[WSGI] 🗑 Removing cache: {cache_path}", file=sys.stderr, flush=True)
                shutil.rmtree(cache_path, ignore_errors=True)
    except Exception as e:
        print(f"[WSGI] ⚠️ Cache clear error: {e}", file=sys.stderr, flush=True)

def perform_git_sync():
    """Git同期を実行"""
    try:
        print("[WSGI] 📥 Fetching latest code from GitHub...", file=sys.stderr, flush=True)
        
        # git fetch を実行してリモートの最新情報を取得
        fetch_result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'fetch', 'origin'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )
        
        if fetch_result.returncode != 0:
            print(f"[WSGI] ⚠️ Git fetch failed: {fetch_result.stderr[:100]}", file=sys.stderr, flush=True)
        
        # git reset --hard origin/main を実行（ローカル変更を無視して最新に）
        reset_result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'reset', '--hard', 'origin/main'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )
        
        output = reset_result.stdout + reset_result.stderr
        
        if reset_result.returncode == 0:
            msg = f"✅ Git sync success: Updated to latest main branch"
            print(msg, file=sys.stderr, flush=True)
            # キャッシュクリア
            clear_python_cache()
            log_sync_status('success', output[:200])
            return True
        else:
            msg = f"⚠️ Git reset failed (code {reset_result.returncode}): {output[:150]}"
            print(msg, file=sys.stderr, flush=True)
            log_sync_status('failed', output[:200])
            return False
            
    except subprocess.TimeoutExpired:
        msg = "[WSGI] ⚠️ Git sync timeout"
        print(msg, file=sys.stderr, flush=True)
        log_sync_status('timeout', 'Git sync timed out')
        return False
        
    except Exception as e:
        msg = f"[WSGI] ⚠️ Git sync error: {str(e)[:100]}"
        print(msg, file=sys.stderr, flush=True)
        log_sync_status('error', str(e)[:200])
        return False

# Reload時にgit syncを実行（毎回チェック）
if os.path.exists(PROJECT_ROOT + '/.git'):
    print("[WSGI] 🔄 Starting git sync check...", file=sys.stderr, flush=True)
    current_hash = get_current_git_hash()
    last_hash = get_last_sync_hash()
    
    # Reloadされた場合は強制的に同期
    print(f"[WSGI] Current: {current_hash[:8] if current_hash else 'unknown'}, Last: {last_hash[:8] if last_hash else 'none'}", file=sys.stderr, flush=True)
    
    if perform_git_sync():
        if current_hash:
            save_sync_hash(current_hash)
        print("[WSGI] ✅ Git sync completed", file=sys.stderr, flush=True)
    else:
        print("[WSGI] ⚠️ Git sync skipped or failed", file=sys.stderr, flush=True)
else:
    print("[WSGI] ℹ️ Not a git repository, skipping sync", file=sys.stderr, flush=True)

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


