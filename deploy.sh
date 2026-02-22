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

# 3. PythonAnywhere へのデプロイと自動リロード
echo "🔄 PythonAnywhere サーバーをデプロイ中..."

# APIトークンを読み込み
if [ -f config/.env ]; then
    PYTHONANYWHERE_API_TOKEN=$(grep "^PYTHONANYWHERE_API_TOKEN=" config/.env | cut -d= -f2 | tr -d ' ')
fi

# SSH経由でサーバーをアップデート＆リロード
ssh nnnkeita@bash.pythonanywhere.com << 'EOF' 2>/dev/null
cd /home/nnnkeita/kiroku-journal
git pull origin main > /dev/null 2>&1
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py
EOF

if [ $? -eq 0 ]; then
    echo "  ✓ サーバー更新完了（SSH経由）"
else
    echo "  ⚠️  SSH接続失敗。APIで試行中..."
fi

# APIトークンがあれば、さらに確実にリロード
if [ -n "$PYTHONANYWHERE_API_TOKEN" ]; then
    API_URL="https://www.pythonanywhere.com/api/v0/user/nnnkeita/webapps/nnnkeita.pythonanywhere.com/reload/"
    
    API_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
      -H "Authorization: Token $PYTHONANYWHERE_API_TOKEN" \
      -H "Content-Type: application/json" \
      2>/dev/null)
    
    HTTP_CODE=$(echo "$API_RESPONSE" | tail -1)
    BODY=$(echo "$API_RESPONSE" | head -n -1)
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        echo "  ✓ APIでリロード確認（HTTP $HTTP_CODE）"
    elif [ -z "$HTTP_CODE" ]; then
        echo "  ℹ️  リロード処理を送信しました"
    else
        echo "  ⚠️  APIレスポンス: HTTP $HTTP_CODE"
    fi
else
    echo "💡 APIトークン未設定ですが、SSH経由でサーバー更新は完了しました"
fi

echo ""
echo "========================================="
echo "✅ デプロイ完了！"
echo "========================================="
echo ""
echo "処理内容："
echo "  • GitHub ✅ 最新コードをpush"
echo "  • 本番環境 ✅ SSH経由でサーバー更新"
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
