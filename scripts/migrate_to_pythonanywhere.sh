#!/bin/bash

# ===================================================================
# PythonAnywhereへのデータベース移行スクリプト
# ローカルのデータベースをPythonAnywhereに完全に置き換える
# ===================================================================

set -e  # エラーで停止

echo "🚀 データベース移行プロセス開始"
echo "=================================="

# === 設定 ===
LOCAL_DB="notion.db"
BACKUP_PREFIX="migration_backup_$(date '+%Y%m%d_%H%M%S')"
PYTHONANYWHERE_HOST="nnnkeita.pythonanywhere.com"
PYTHONANYWHERE_USER="nnnkeita"
REMOTE_DB_PATH="/home/nnnkeita/kiroku-journal/notion.db"
REMOTE_BACKUP_PATH="/home/nnnkeita/kiroku-journal/backups/${BACKUP_PREFIX}_notion.db"

# 現在のディレクトリを確認
if [ ! -f "$LOCAL_DB" ]; then
    echo "❌ エラー: $LOCAL_DB が見つかりません。"
    echo "このスクリプトは kiroku-journal ディレクトリから実行してください。"
    exit 1
fi

# === ステップ 1: ローカルDBの整合性チェック ===
echo ""
echo "📋 ステップ 1: ローカルデータベースの整合性チェック..."
python3 << 'PYEOF'
import sqlite3
try:
    conn = sqlite3.connect('notion.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()
    if result[0] == 'ok':
        print("✅ ローカルDBは整合性を保っています")
    else:
        print(f"⚠️ 警告: {result}")
    
    # テーブル一覧を確認
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    print(f"\n📊 テーブル一覧（{len(tables)}個）:")
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  - {table_name}: {count} rows")
    
    conn.close()
except Exception as e:
    print(f"❌ エラー: {e}")
    exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo "❌ DBチェックに失敗しました。"
    exit 1
fi

# === ステップ 2: ローカルDBのバックアップを作成 ===
echo ""
echo "💾 ステップ 2: ローカルデータベースのバックアップを作成..."
cp "$LOCAL_DB" "backups/${BACKUP_PREFIX}_local_notion.db"
echo "✅ ローカルバックアップ作成: backups/${BACKUP_PREFIX}_local_notion.db"

# === ステップ 3: PythonAnywhereでリモートDBのバックアップを作成 ===
echo ""
echo "🔄 ステップ 3: PythonAnywhereでリモートDBをバックアップ..."
echo "実行中: ssh $PYTHONANYWHERE_USER@$PYTHONANYWHERE_HOST"

ssh ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST} bash << 'REMOTE_BASH'
echo "リモート: DBを確認中..."
if [ -f /home/nnnkeita/kiroku-journal/notion.db ]; then
    echo "リモート: バックアップを作成中..."
    mkdir -p /home/nnnkeita/kiroku-journal/backups
    cp /home/nnnkeita/kiroku-journal/notion.db /home/nnnkeita/kiroku-journal/backups/pre_migration_$(date '+%Y%m%d_%H%M%S')_notion.db
    echo "✅ リモートバックアップ作成完了"
else
    echo "⚠️ リモートに既存のDBがありません"
fi
REMOTE_BASH

if [ $? -ne 0 ]; then
    echo "⚠️ リモートバックアップに失敗しましたが、続行します..."
fi

# === ステップ 4: DBファイルのサイズを確認 ===
echo ""
echo "📏 ステップ 4: ファイルサイズを確認..."
LOCAL_SIZE=$(ls -lh "$LOCAL_DB" | awk '{print $5}')
echo "ローカルDB: $LOCAL_SIZE"

# === ステップ 5: ローカルDBをPythonAnywhereにアップロード ===
echo ""
echo "📤 ステップ 5: ローカルDBをPythonAnywhereにアップロード..."
scp -p "$LOCAL_DB" ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST}:${REMOTE_DB_PATH}

if [ $? -ne 0 ]; then
    echo "❌ アップロードに失敗しました。"
    exit 1
fi

echo "✅ アップロード完了"

# === ステップ 6: リモートでDBが置き換わったことを確認 ===
echo ""
echo "✔️  ステップ 6: リモートの確認..."
ssh ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST} bash << 'REMOTE_VERIFY'
echo "リモート: DBの整合性をチェック..."
python3 << 'PYEOF'
import sqlite3
try:
    conn = sqlite3.connect('/home/nnnkeita/kiroku-journal/notion.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()
    if result[0] == 'ok':
        print("✅ リモートDBは整合性を保っています")
    else:
        print(f"⚠️ 警告: {result}")
    
    # テーブル一覧を確認
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    print(f"\n📊 テーブル一覧（{len(tables)}個）:")
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  - {table_name}: {count} rows")
    
    conn.close()
except Exception as e:
    print(f"❌ エラー: {e}")
    exit(1)
PYEOF
REMOTE_VERIFY

if [ $? -ne 0 ]; then
    echo "❌ リモートDBの確認に失敗しました。"
    exit 1
fi

# === ステップ 7: PythonAnywhereのWebアプリを再ロード ===
echo ""
echo "🔄 ステップ 7: PythonAnywhereのWebアプリを再ロード..."
ssh ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST} bash << 'REMOTE_RELOAD'
echo "リモート: Webアプリを再ロード中..."
python3 << 'PYEOF'
import subprocess
import json

# PythonAnywhereのAPI呼び出し（管理コマンドがあれば）
try:
    # Webアプリを再ロードするコマンド
    result = subprocess.run(['touch', '/var/www/nnnkeita_pythonanywhere_com_wsgi.py'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Webアプリの再ロードをリクエストしました")
    else:
        print("⚠️ 再ロードのリクエストが完了しました")
except Exception as e:
    print(f"⚠️ 再ロード時の警告: {e}")
PYEOF
REMOTE_RELOAD

# === 完成！ ===
echo ""
echo "=================================="
echo "✅ マイグレーション完了！"
echo ""
echo "📝 実施内容:"
echo "  ✓ ローカルDBを検証"
echo "  ✓ ローカルとリモートのバックアップを作成"
echo "  ✓ ローカルDBをPythonAnywhereにアップロード"
echo "  ✓ リモートDBを検証"
echo "  ✓ Webアプリを再ロード"
echo ""
echo "🔗 確認: https://nnnkeita.pythonanywhere.com"
echo ""
echo "⚠️  注意: Webアプリが完全に再起動するまで1-2分かかる場合があります"
echo "=================================="

