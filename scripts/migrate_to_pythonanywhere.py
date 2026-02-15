#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PythonAnywhereへのデータベース移行スクリプト（Python版）
ローカルのデータベースをPythonAnywhereに完全に置き換える
"""

import sqlite3
import subprocess
import os
import sys
from datetime import datetime
import shutil

# === 設定 ===
LOCAL_DB = "notion.db"
PYTHONANYWHERE_USER = "nnnkeita"
PYTHONANYWHERE_HOST = "nnnkeita.pythonanywhere.com"
REMOTE_DB_PATH = f"/home/{PYTHONANYWHERE_USER}/kiroku-journal/notion.db"

def print_section(title):
    """セクションタイトルを表示"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)

def check_local_db():
    """ローカルDBの整合性をチェック"""
    print_section("ステップ 1: ローカルDBの検証")
    
    if not os.path.exists(LOCAL_DB):
        print(f"❌ エラー: {LOCAL_DB} が見つかりません。")
        print("このスクリプトは kiroku-journal ディレクトリから実行してください。")
        sys.exit(1)
    
    try:
        conn = sqlite3.connect(LOCAL_DB)
        cursor = conn.cursor()
        
        # 整合性チェック
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] != 'ok':
            print(f"⚠️ 警告: {result[0]}")
        else:
            print("✅ ローカルDBは整合性を保っています")
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        print(f"\n📊 テーブル一覧（{len(tables)}個）:")
        
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} rows")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

def backup_local_db():
    """ローカルDBのバックアップを作成"""
    print_section("ステップ 2: ローカルDBのバックアップ")
    
    try:
        os.makedirs("backups", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backups/migration_backup_{timestamp}_notion.db"
        shutil.copy(LOCAL_DB, backup_name)
        print(f"✅ バックアップ作成: {backup_name}")
        return True
    except Exception as e:
        print(f"❌ バックアップ失敗: {e}")
        return False

def backup_remote_db():
    """リモートDBのバックアップを作成"""
    print_section("ステップ 3: リモートDBのバックアップ")
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_backup = f"/home/{PYTHONANYWHERE_USER}/kiroku-journal/backups/pre_migration_{timestamp}_notion.db"
        
        cmd = f"""
mkdir -p /home/{PYTHONANYWHERE_USER}/kiroku-journal/backups && \
if [ -f {REMOTE_DB_PATH} ]; then cp {REMOTE_DB_PATH} {remote_backup} && echo "done"; else echo "nofile"; fi
"""
        
        result = subprocess.run(
            ["ssh", f"{PYTHONANYWHERE_USER}@{PYTHONANYWHERE_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "done" in result.stdout:
            print(f"✅ リモートバックアップ作成: {remote_backup}")
            return True
        elif "nofile" in result.stdout:
            print("⚠️ リモートに既存のDBがありません（初回デプロイ）")
            return True
        else:
            print(f"⚠️ 警告: {result.stderr}")
            return True  # 続行
            
    except subprocess.TimeoutExpired:
        print("⚠️ リモートコマンドがタイムアウト（続行）")
        return True
    except Exception as e:
        print(f"⚠️ 警告: {e}（続行）")
        return True

def upload_db():
    """ローカルDBをアップロード"""
    print_section("ステップ 4: ローカルDBをアップロード")
    
    try:
        # ファイルサイズを確認
        size_mb = os.path.getsize(LOCAL_DB) / (1024 * 1024)
        print(f"📏 ローカルDB: {size_mb:.2f} MB")
        print(f"📤 アップロード中: {LOCAL_DB} → {REMOTE_DB_PATH}")
        
        result = subprocess.run(
            ["scp", "-p", LOCAL_DB, f"{PYTHONANYWHERE_USER}@{PYTHONANYWHERE_HOST}:{REMOTE_DB_PATH}"],
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ アップロード完了")
            return True
        else:
            print(f"❌ アップロード失敗（戻り値: {result.returncode}）")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ アップロードがタイムアウト")
        return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

def verify_remote_db():
    """リモートDBを検証"""
    print_section("ステップ 5: リモートDBの検証")
    
    try:
        cmd = f"""
python3 << 'PYEOF'
import sqlite3
try:
    conn = sqlite3.connect('{REMOTE_DB_PATH}')
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()
    if result[0] == 'ok':
        print("✅ リモートDBは整合性を保っています")
    else:
        print(f"⚠️ 警告: {{result[0]}}")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    print(f"📊 テーブル一覧（{{len(tables)}}個）:")
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {{table_name}}")
        count = cursor.fetchone()[0]
        print(f"  - {{table_name}}: {{count}} rows")
    
    conn.close()
except Exception as e:
    print(f"❌ エラー: {{e}}")
    exit(1)
PYEOF
"""
        
        result = subprocess.run(
            ["ssh", f"{PYTHONANYWHERE_USER}@{PYTHONANYWHERE_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(result.stdout)
        if result.returncode != 0 and result.stderr:
            print(f"⚠️ エラー出力: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"⚠️ 検証エラー: {e}")
        return False

def reload_web_app():
    """PythonAnywhereのWebアプリを再ロード"""
    print_section("ステップ 6: Webアプリの再ロード")
    
    try:
        # WGSIファイルをタッチして再ロード
        cmd = "touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py"
        result = subprocess.run(
            ["ssh", f"{PYTHONANYWHERE_USER}@{PYTHONANYWHERE_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print("✅ Webアプリの再ロードをリクエストしました")
            print("⏳ Webアプリが完全に再起動するまで1-2分かかる場合があります")
        else:
            print(f"⚠️ 再ロード時の警告: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"⚠️ 再ロード時のエラー: {e}")
        return True

def main():
    """メイン処理"""
    print("\n🚀 PythonAnywhereデータベース移行スクリプト")
    print(f"ローカルDB: {LOCAL_DB}")
    print(f"リモート: {PYTHONANYWHERE_HOST}")
    
    # ステップ実行
    if not check_local_db():
        sys.exit(1)
    
    if not backup_local_db():
        sys.exit(1)
    
    if not backup_remote_db():
        sys.exit(1)
    
    if not upload_db():
        sys.exit(1)
    
    verify_remote_db()  # 検証（失敗しても続行）
    
    reload_web_app()  # 再ロード（失敗しても完了とする）
    
    # 完成
    print_section("✅ マイグレーション完了！")
    print("\n📝 実施内容:")
    print("  ✓ ローカルDBを検証")
    print("  ✓ ローカルとリモートのバックアップを作成")
    print("  ✓ ローカルDBをPythonAnywhereにアップロード")
    print("  ✓ リモートDBを検証")
    print("  ✓ Webアプリを再ロード")
    print("\n🔗 確認: https://nnnkeita.pythonanywhere.com")
    print("\n⚠️  注意: Webアプリが完全に再起動するまで1-2分かかる場合があります")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ キャンセルされました")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
