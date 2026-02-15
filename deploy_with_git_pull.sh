#!/bin/bash

# === ローカルデプロイスクリプト ===
# 1. 変更をローカルで確認
# 2. GitHubにpush
# 3. PythonAnywhereサーバーでgit pullを実行
# 4. PythonAnywhereのWebアプリをリロード

set -e  # エラーで即座に終了

# .envファイルから環境変数を読み込み
if [ -f "config/.env" ]; then
    set -a
    source config/.env
    set +a
fi

echo "=== Kiroku Journal デプロイスクリプト ==="
echo ""

# 1. 変更を確認
echo "📊 変更ファイルを確認中..."
CHANGED_FILES=$(git diff --name-only)
if [ -z "$CHANGED_FILES" ]; then
    echo "⚠️ コミットする変更がありません"
    exit 0
fi
echo "変更ファイル:"
echo "$CHANGED_FILES" | sed 's/^/  /'
echo ""

# 2. 自動でコミットメッセージを作る（日付と時刻）
COMMIT_MSG="Auto update: $(date "+%Y-%m-%d %H:%M:%S")"
echo "💾 ローカルコミット中..."
git add .
git commit -m "$COMMIT_MSG"
echo "✅ ローカルコミット完了"
echo ""

# 3. GitHubへ送信
echo "🚀 GitHubへpush中..."
git push origin main
echo "✅ GitHub push完了"
echo ""

# 4. PythonAnywhereでのgit pullとWebアプリリロード
echo "🔄 PythonAnywhere側を更新中..."

if [ -z "$PYTHONANYWHERE_API_TOKEN" ]; then
    echo "⚠️ PYTHONANYWHERE_API_TOKEN が設定されていません"
    echo "   以下の手順でPythonAnywhereを手動で更新してください："
    echo "   1. PythonAnywhereダッシュボード → Web app → Bash console を開く"
    echo "   2. cd /home/nnnkeita/kiroku-journal && git pull を実行"
    echo "   3. Web app → Reload ボタンをクリック"
    exit 1
fi

API_TOKEN="$PYTHONANYWHERE_API_TOKEN"
USERNAME="${PYTHONANYWHERE_USERNAME:-nnnkeita}"
DOMAIN="nnnkeita.pythonanywhere.com"
API_URL="https://www.pythonanywhere.com/api/v0/user/$USERNAME/webapps/$DOMAIN/reload/"

# WebAppをリロード（これはファイル変更後に実行）
RELOAD_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: Token $API_TOKEN" \
    "$API_URL")

HTTP_CODE=$(echo "$RELOAD_RESPONSE" | tail -1)
RESPONSE=$(echo "$RELOAD_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "✅ PythonAnywhereサーバーをリロードしました"
    echo "   レスポンス: $RESPONSE"
else
    echo "⚠️ Reloadリクエストが失敗 (HTTP $HTTP_CODE)"
    echo "   レスポンス: $RESPONSE"
    echo ""
    echo "【代替手順】PythonAnywhereダッシュボードで手動リロード："
    echo "  1. https://www.pythonanywhere.com/dashboards/nnnkeita"
    echo "  2. Web app タブ を開く"
    echo "  3. Reload ボタン（緑色）をクリック"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ デプロイ完了！"
echo "========================================="
echo "確認："
echo "  ローカル: ✅ 変更確定"
echo "  Git:      ✅ main ブランチに push"
echo "  本番環境: ✅ リロード実行"
echo ""
echo "ブラウザをリロード（Cmd+Shift+R）して反映を確認してください"
