#!/bin/bash

echo "=== Kiroku Journal デプロイ開始 ==="

# 1. wsgi.py のタイムスタンプを自動更新
echo "🔄 タイムスタンプを更新中..."
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# macOS と Linux 両対応（バックアップファイルなしで動作）
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
else
    sed -i "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
fi

# 2. 変更をGitHubへpush
echo "🚀 GitHubへ送信中..."
COMMIT_MSG="Deploy: $(date "+%Y-%m-%d %H:%M:%S")"
git add -A
if git commit -m "$COMMIT_MSG" 2>/dev/null; then
    echo "  ✓ コミット完了"
else
    echo "  ℹ コミット対象なし"
fi

git push origin main

echo "✅ GitHub へのpush完了"
echo ""

# 3. PythonAnywhere APIでWebアプリを自動リロード
echo "🔄 PythonAnywhere Webアプリをリロード中..."

# 環境変数からAPIトークンを読み込み
if [ -f config/.env ]; then
    # コメント行と空行を除いてAPIトークンのみを読み込む
    PYTHONANYWHERE_API_TOKEN=$(grep "^PYTHONANYWHERE_API_TOKEN=" config/.env | cut -d= -f2)
fi

if [ -z "$PYTHONANYWHERE_API_TOKEN" ]; then
    echo "❌ エラー: PYTHONANYWHERE_API_TOKEN が設定されていません"
    echo "  以下の手順でトークンを取得してください："
    echo "  1. https://www.pythonanywhere.com/user/nnnkeita/account/#api_token"
    echo "  2. APIトークンをコピー"
    echo "  3. config/.env に追加: PYTHONANYWHERE_API_TOKEN=xxxxx"
    echo ""
    echo "⚠️  本番環境は手動でリロードしてください"
    echo "  https://www.pythonanywhere.com → Web → Reload"
else
    # PythonAnywhere APIでWebアプリをリロード
    API_URL="https://www.pythonanywhere.com/api/v0/user/nnnkeita/webapps/nnnkeita.pythonanywhere.com/reload/"
    
    API_RESPONSE=$(curl -s -X POST "$API_URL" \
      -H "Authorization: Token $PYTHONANYWHERE_API_TOKEN" \
      -H "Content-Type: application/json" \
      2>&1)
    
    if echo "$API_RESPONSE" | grep -q '"status":.*success\|200\|201'; then
        echo "  ✓ Webアプリを自動リロード完了"
    elif echo "$API_RESPONSE" | grep -q '"error"'; then
        echo "  ⚠️  APIエラー: $API_RESPONSE"
    else
        echo "  ✓ リロードリクエスト送信完了"
    fi
fi

echo ""

echo ""
echo "========================================="
echo "✅ デプロイ完了！"
echo "========================================="
echo ""
echo "処理内容："
echo "  • GitHub ✅ 最新コードをpush"
echo "  • 本番環境 ✅ Webアプリを自動リロード"
echo ""
echo "📝 初回設定:"
echo "  APIトークンをまだ設定していない場合は以下を実行："
echo "  1. https://www.pythonanywhere.com/user/nnnkeita/account/#api_token"
echo "  2. APIトークンをコピー"
echo "  3. echo 'PYTHONANYWHERE_API_TOKEN=YOUR_TOKEN_HERE' >> config/.env"
echo ""
echo "その後、デプロイスクリプトを再度実行すると完全自動化されます"
echo ""
echo "ブラウザをリロード（Cmd+Shift+R）して反映を確認してください"
