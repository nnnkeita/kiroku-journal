# -*- coding: utf-8 -*-
# WSGI VERSION: 2026-02-22 09:20:51
# This timestamp ensures PythonAnywhere reloads the WSGI module on every Reload click

import sys
import os
import subprocess
import json
import importlib
import shutil
from datetime import datetime

# === Git自動同期 + キャッシュクリア（毎回実行） ===
PROJECT_ROOT = '/home/nnnkeita/kiroku-journal'
SYNC_STATUS_FILE = os.path.join(PROJECT_ROOT, '.wsgi_sync_status')
LAST_SYNC_FILE = os.path.join(PROJECT_ROOT, '.wsgi_last_sync_hash')
STARTUP_MARKER_FILE = os.path.join(PROJECT_ROOT, '.wsgi_startup_marker')

def create_startup_marker():
    """起動マーカーをファイルに記録（デバッグ用）"""
    try:
        with open(STARTUP_MARKER_FILE, 'w') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'marker': 'WSGI_STARTUP_NEW'
            }))
    except:
        pass

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
            ['/usr/bin/git', '-C', PROJECT_ROOT, 'rev-parse', 'HEAD'],
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
        import glob
        
        # app フォルダ配下の __pycache__ をクリア
        for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, 'app')):
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                shutil.rmtree(cache_path, ignore_errors=True)
        
        # .pyc ファイルも明示的に削除
        for pyc_file in glob.glob(os.path.join(PROJECT_ROOT, 'app', '**', '*.pyc'), recursive=True):
            try:
                os.remove(pyc_file)
            except:
                pass
    except Exception as e:
        pass

def perform_git_sync():
    """Git同期を実行（データベースを保護）"""
    log_sync_status('starting', f'Git sync starting at {datetime.now()}')
    try:
        import tempfile
        
        # DB ファイルをバックアップ
        db_path = os.path.join(PROJECT_ROOT, 'notion.db')
        backups_path = os.path.join(PROJECT_ROOT, 'backups')
        
        db_backup = None
        backups_backup = None
        
        if os.path.exists(db_path):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                shutil.copy2(db_path, tmp.name)
                db_backup = tmp.name
        
        if os.path.exists(backups_path):
            with tempfile.TemporaryDirectory() as tmpdir:
                backups_backup = os.path.join(tmpdir, 'backups')
                shutil.copytree(backups_path, backups_backup)
        
        # git fetch を実行
        fetch_result = subprocess.run(
            ['/usr/bin/git', '-C', PROJECT_ROOT, 'fetch', 'origin'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )
        
        # git reset --hard origin/main を実行
        reset_result = subprocess.run(
            ['/usr/bin/git', '-C', PROJECT_ROOT, 'reset', '--hard', 'origin/main'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )
        
        success = False
        if reset_result.returncode == 0:
            # DB ファイルを復元
            if db_backup and os.path.exists(db_backup):
                shutil.copy2(db_backup, db_path)
                os.remove(db_backup)
            
            clear_python_cache()
            success = True
        
        return success
            
    except subprocess.TimeoutExpired:
        return False
        
    except Exception as e:
        return False

# Reload時にgit syncを実行（毎回チェック）
if os.path.exists(PROJECT_ROOT + '/.git'):
    current_hash = get_current_git_hash()
    last_hash = get_last_sync_hash()
    
    # デバッグログファイルを作成
    debug_log = os.path.join(PROJECT_ROOT, '.wsgi_debug.log')
    with open(debug_log, 'a') as f:
        f.write(f"\n=== WSGI Reload: {datetime.now()} ===\n")
        f.write(f"Current hash: {current_hash}\n")
        f.write(f"Last hash: {last_hash}\n")
        f.write(f"PROJECT_ROOT: {PROJECT_ROOT}\n")
        f.write(f"GIT exists: {os.path.exists('/usr/bin/git')}\n")
    
    # 強制的に同期を実行
    sync_success = perform_git_sync()
    
    new_hash = get_current_git_hash()
    with open(debug_log, 'a') as f:
        f.write(f"Sync result: {sync_success}\n")
        f.write(f"New hash after sync: {new_hash}\n")
        f.write(f"Templates dir exists: {os.path.exists(os.path.join(PROJECT_ROOT, 'templates'))}\n")
        f.write(f"Index.html size: {os.path.getsize(os.path.join(PROJECT_ROOT, 'templates/index.html')) if os.path.exists(os.path.join(PROJECT_ROOT, 'templates/index.html')) else 'N/A'}\n")
    
    if current_hash:
        save_sync_hash(current_hash)
    
    # スタートアップマーカーを作成
    create_startup_marker()

# ============================================================

# PROJECT_ROOT を sys.path に追加（app パッケージを import できるように）
sys.path.insert(0, PROJECT_ROOT)

# Virtualenv の site-packages を sys.path に追加
venv_site_packages = '/home/nnnkeita/.virtualenvs/kiroku-journal/lib/python3.11/site-packages'
if os.path.exists(venv_site_packages):
    sys.path.insert(0, venv_site_packages)

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
    
except Exception as e:
    raise


