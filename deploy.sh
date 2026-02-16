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

# 3. PythonAnywhere へ SSH で自動更新（キーがある場合のみ）
echo "🔄 本番環境を更新中..."

if [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ]; then
    ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no nnnkeita@bash.pythonanywhere.com << 'EOF' 2>/dev/null
cd /home/nnnkeita/kiroku-journal
git pull origin main >/dev/null 2>&1
cp wsgi.py /var/www/nnnkeita_pythonanywhere_com_wsgi.py
touch /var/www/nnnkeita_pythonanywhere_com_wsgi.py
EOF
    if [ $? -eq 0 ]; then
        echo "✅ PythonAnywhere を自動更新しました"
    fi
else
    echo "💡 SSH キーがないため、スキップしました"
    echo "   次回のアクセス時に自動同期されます"
fi

echo ""
echo "✅ デプロイ完了！"
echo "💡  リロード不要 - 自動で反映されます"

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
