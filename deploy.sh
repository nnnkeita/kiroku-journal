#!/bin/bash

set -e  # エラーで終了

# .envファイルから環境変数を読み込み
if [ -f "config/.env" ]; then
    set -a
    source config/.env
    set +a
fi

echo "=== Kiroku Journal デプロイ開始 ==="

# 1. 変更をGitHubへpush
echo "🚀 GitHubへ送信中..."
COMMIT_MSG="Auto update: $(date "+%Y-%m-%d %H:%M:%S")"
git add .
if git commit -m "$COMMIT_MSG" 2>/dev/null; then
    echo "  ✓ コミット: $COMMIT_MSG"
else
    echo "  ℹ コミット対象がないため、pushのみ実行"
fi
git push origin main

echo "✅ GitHubへのpush完了"
echo ""

# 2. PythonAnywhereへ通知
echo "🔄 本番環境を更新中..."

if [ -z "$PYTHONANYWHERE_API_TOKEN" ]; then
    echo "⚠️ PYTHONANYWHERE_API_TOKEN が未設定です"
    echo ""
    echo "【手動対応】PythonAnywhereダッシュボードで以下を実行："
    echo "  1. https://www.pythonanywhere.com/dashboards/nnnkeita"
    echo "  2. Web app → Reload ボタンをクリック"
    exit 0
fi

# WebアプリをリロードしてWSGIでgit pullが自動実行される
RESPONSE=$(curl -s -X POST \
    -H "Authorization: Token $PYTHONANYWHERE_API_TOKEN" \
    "https://www.pythonanywhere.com/api/v0/user/nnnkeita/webapps/nnnkeita.pythonanywhere.com/reload/" 2>&1)

if echo "$RESPONSE" | grep -q "OK\|status"; then
    echo "✅ 本番環境が更新されました（WSGIでgit pull自動実行）"
else
    echo "⚠️ 更新結果: $RESPONSE"
fi

echo ""
echo "========================================="
echo "✅ デプロイ完了！"
echo "========================================="
echo ""
echo "処理内容："
echo "  • GitHub ✅ 最新コードをpush"
echo "  • 本番環境 ✅ Webアプリをリロード"
echo "  • Git同期 ✅ WSGIで自動的にgit pull実行"
echo ""
echo "ブラウザをリロード（Cmd+Shift+R）して反映を確認してください"
