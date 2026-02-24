#!/bin/bash
# PythonAnywhereで自動実行するスクリプト
# Cronjobで定期実行: 0 * * * * /home/nnnkeita/kiroku-journal/scripts/auto-deploy.sh

LOG_FILE="/home/nnnkeita/kiroku-journal/.deploy.log"
REPO_PATH="/home/nnnkeita/kiroku-journal"

# ログ開始
echo "========================================" >> "$LOG_FILE"
echo "Auto-deploy check: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

cd "$REPO_PATH" || exit 1

# Git 状態確認
REMOTE_SHA=$(git ls-remote origin main | awk '{print $1}')
LOCAL_SHA=$(git rev-parse HEAD)

echo "Remote SHA: $REMOTE_SHA" >> "$LOG_FILE"
echo "Local SHA: $LOCAL_SHA" >> "$LOG_FILE"

# リモートが更新されている場合のみ実行
if [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
    echo "✅ New changes detected, pulling..." >> "$LOG_FILE"
    
    # Git pull実行
    git fetch origin main >> "$LOG_FILE" 2>&1
    git reset --hard origin/main >> "$LOG_FILE" 2>&1
    
    echo "✅ Git pull completed at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    
    # WSGI touch（リロードトリガー）
    WSGI_FILE="/var/www/nnnkeita_pythonanywhere_com_wsgi.py"
    if [ -f "$WSGI_FILE" ]; then
        touch "$WSGI_FILE"
        echo "✅ WSGI reloaded at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    fi
else
    echo "⏭️  No changes detected" >> "$LOG_FILE"
fi

echo "========================================" >> "$LOG_FILE"
