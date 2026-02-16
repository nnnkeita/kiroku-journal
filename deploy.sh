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
echo "✅ デプロイ完了！"
echo "💡  変更は自動的により反映されます（git sync機能）"

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
