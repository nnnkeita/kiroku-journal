#!/bin/bash

# =====================================================
# 統合デプロイ＆リロードスクリプト
# =====================================================
# 機能：
# 1. ローカル変更をテスト
# 2. GitHubへコミット・プッシュ
# 3. PythonAnywhereをリモート同期
# 4. Webアプリをリロード
# 5. 接続確認
# =====================================================

set -e  # エラーで即座に終了

# === カラー定義 ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# === ログ関数 ===
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠️]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# === 設定ファイル読み込み ===
if [ -f "config/.env" ]; then
    set -a
    source config/.env
    set +a
    log_success ".env ファイルから環境変数を読み込みました"
else
    log_warn "config/.env ファイルが見つかりません"
fi

# === メイン処理開始 ===
echo ""
echo "=================================================="
echo "  🚀  Kiroku Journal 統合デプロイスクリプト"
echo "=================================================="
echo ""

# 1. ローカル変更確認
echo -e "${BLUE}[STEP 1]${NC} ローカル変更を確認中..."
CHANGED_FILES=$(git diff --name-only 2>/dev/null || true)

if [ -z "$CHANGED_FILES" ]; then
    log_warn "コミットする変更がありません"
else
    echo "🔄 変更ファイル:"
    echo "$CHANGED_FILES" | sed 's/^/   - /'
    echo ""
fi

# 2. ローカルテスト（Python構文チェック）
echo -e "${BLUE}[STEP 2]${NC} Pythonファイルの構文チェック中..."
PYTHON_FILES=$(find . -name "*.py" -path "./app/*" ! -path "./venv/*" ! -path "./.venv/*" 2>/dev/null || true)

if [ -n "$PYTHON_FILES" ]; then
    while IFS= read -r py_file; do
        if python3 -m py_compile "$py_file" 2>/dev/null; then
            log_success "$(basename $py_file) - OK"
        else
            log_error "$(basename $py_file) - 構文エラー"
            exit 1
        fi
    done <<< "$PYTHON_FILES"
else
    log_info "Pythonファイルが見つかりません"
fi

echo ""

# 3. Gitコミット・プッシュ
echo -e "${BLUE}[STEP 3]${NC} GitHubへコミット・プッシュ中..."

if [ -n "$CHANGED_FILES" ]; then
    COMMIT_MSG="🔄 Update: $(date '+%Y-%m-%d %H:%M:%S')"
    git add -A
    
    if git commit -m "$COMMIT_MSG" 2>/dev/null; then
        log_success "ローカルコミット完了"
    else
        log_warn "コミット対象なし"
    fi
    
    if git push origin main 2>/dev/null; then
        log_success "GitHub push 完了"
    else
        log_error "GitHub push に失敗しました"
        exit 1
    fi
else
    log_warn "GitHubへのpush をスキップ（変更なし）"
fi

echo ""

# 4. wsgi.py タイムスタンプ更新
echo -e "${BLUE}[STEP 4]${NC} WSGI タイムスタンプを更新中..."
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

if [ -f "wsgi.py" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
    else
        sed -i "s/# WSGI VERSION:.*/# WSGI VERSION: $TIMESTAMP/" wsgi.py
    fi
    log_success "WSGI タイムスタンプを更新: $TIMESTAMP"
fi

# 5. PythonAnywhere リモート同期
echo ""
echo -e "${BLUE}[STEP 5]${NC} PythonAnywhere をリモート同期中..."

# SSH 接続情報取得
if [ -z "$PYTHONANYWHERE_USER" ]; then
    PYTHONANYWHERE_USER="nnnkeita"
fi

if [ -z "$PYTHONANYWHERE_HOST" ]; then
    PYTHONANYWHERE_HOST="bash.pythonanywhere.com"
fi

ssh_command() {
    ssh "${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST}" "$1" 2>/dev/null || return 1
}

if ssh_command "cd ~/kiroku-journal && git pull origin main > /dev/null 2>&1"; then
    log_success "PythonAnywhere でコード更新完了"
    
    # WSGI ファイルをコピー
    if ssh_command "cp wsgi.py /var/www/${PYTHONANYWHERE_USER}_pythonanywhere_com_wsgi.py && touch /var/www/${PYTHONANYWHERE_USER}_pythonanywhere_com_wsgi.py"; then
        log_success "WSGI ファイルをコピー・リロード完了"
    else
        log_warn "WSGI ファイルのコピーに失敗しました（APIリロードを試行）"
    fi
else
    log_warn "SSH 接続失敗。API でリロードを試行中..."
    
    # API トークンが設定されている場合
    if [ -n "$PYTHONANYWHERE_API_TOKEN" ]; then
        WEBAPP_NAME="${PYTHONANYWHERE_USER}.pythonanywhere.com"
        
        if curl -s -H "Authorization: Token $PYTHONANYWHERE_API_TOKEN" \
            "https://www.pythonanywhere.com/api/v0/user/${PYTHONANYWHERE_USER}/webapps/${WEBAPP_NAME}/reload/" \
            -X POST > /dev/null 2>&1; then
            log_success "API でアプリをリロード"
        else
            log_warn "PythonAnywhere API リロール失敗（手動リロードが必要な場合あり）"
        fi
    else
        log_warn "PYTHONANYWHERE_API_TOKEN が設定されていません"
    fi
fi

echo ""

# 6. 接続確認
echo -e "${BLUE}[STEP 6]${NC} 接続状況を確認中..."

if [ -f "app/flask_app.py" ]; then
    if python3 -c "from app.flask_app import app; print('✓ Flask アプリケーション接続成功')" 2>/dev/null; then
        log_success "ローカル Flask 接続 OK"
    else
        log_warn "ローカル Flask 接続テストに失敗"
    fi
fi

echo ""

# === 完了 ===
echo "=================================================="
echo -e "${GREEN}✅ デプロイ＆リロード完了${NC}"
echo "=================================================="
echo ""
echo "📋 デプロイサマリー："
echo "  • ローカルコミット: $(git log --oneline -1)"
echo "  • リモートホスト: ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST}"
echo "  • タイムスタンプ: $TIMESTAMP"
echo ""

if command -v open &> /dev/null; then
    echo "💡 Tip: ブラウザで確認できます → http://localhost:5000 または https://${PYTHONANYWHERE_USER}.pythonanywhere.com"
fi

echo ""
