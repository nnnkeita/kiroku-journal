#!/bin/bash

# .envファイルから環境変数を読み込み
if [ -f "config/.env" ]; then
    set -a
    source config/.env
    set +a
fi

# データベースバックアップを作成
echo "📦 Creating database backup..."
python3 scripts/backup_db.py
if [ $? -ne 0 ]; then
    echo "⚠️ Backup failed, but continuing with deployment..."
fi

# 1. 自動でコミットメッセージを作る（日付と時刻）
COMMIT_MSG="Auto update: $(date "+%Y-%m-%d %H:%M:%S")"

# 2. GitHubへ送信
echo "🚀 GitHubへ送信中..."
git add .
git commit -m "$COMMIT_MSG"
git push

# 3. PythonAnywhereの更新トリガーを引く
echo "🔄 サーバーを更新中..."

# API tokenで WebApp をリロード
if [ -n "$PYTHONANYWHERE_API_TOKEN" ]; then
    API_TOKEN="$PYTHONANYWHERE_API_TOKEN"
    USERNAME="${PYTHONANYWHERE_USERNAME:-nnnkeita}"
    DOMAIN="nnnkeita.pythonanywhere.com"
    
    # PythonAnywhere API でWebアプリをリロード
    RELOAD_OUTPUT=$(curl -s -X POST \
        -H "Authorization: Token $API_TOKEN" \
        "https://www.pythonanywhere.com/api/v0/user/$USERNAME/webapps/$DOMAIN/reload/" \
        -w "\n%{http_code}" 2>/dev/null)
    
    HTTP_CODE=$(echo "$RELOAD_OUTPUT" | tail -n1)
    RESPONSE=$(echo "$RELOAD_OUTPUT" | head -n-1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ PythonAnywhereサーバーをリロードしました"
    else
        echo "⚠️ PythonAnywhereのリロード失敗 (HTTP $HTTP_CODE)"
        echo "   レスポンス: $RESPONSE"
        echo "   ダッシュボードで手動リロードしてください"
    fi
else
    echo "⚠️ PYTHONANYWHERE_API_TOKEN が設定されていません"
    echo "   PythonAnywhereのダッシュボードでWebアプリを手動でリロードしてください"
fi

echo ""
echo "✅ 更新完了！"
