# PythonAnywhere デプロイ手順書

このドキュメントでは、Kiroku Journal を PythonAnywhere でデプロイする手順を説明します。

---

## 準備作業

### 1. GitHub にコードをプッシュ（まだの場合）

```bash
# ローカルで以下を実行
git add .
git commit -m "Deploy to PythonAnywhere"
git push origin main
```

---

## PythonAnywhere でのセットアップ

### 2. PythonAnywhere のコンソールを開く

1. [PythonAnywhere](https://www.pythonanywhere.com) にログイン
2. ダッシュボードから「Consoles」タブを開く
3. 「Bash console」を開く（新規作成）

### 3. リポジトリをクローン

PythonAnywhere のコンソールで：

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/kiroku-journal.git
cd kiroku-journal
```

**注意**: GitHub上のリポジトリURLに置き換えてください

### 4. Virtual Environment を作成

```bash
mkvirtualenv --python=/usr/bin/python3.11 kiroku-journal
pip install -r requirements.txt
```

要件：
- Python 3.9 以上（PythonAnywhere のコンソールに表示される利用可能バージョンを確認）

### 5. 環境変数を設定

```bash
cd /home/<your_username>/kiroku-journal
mkdir -p config
nano config/.env
```

`.env.example` を参考に、以下を設定：

```
FLASK_ENV=production
APP_SECRET=generate_random_secret_key_here
APP_BASE_URL=https://your_username.pythonanywhere.com
AUTH_ENABLED=1
TTS_ENABLED=1
CALORIE_ENABLED=1
```

**重要**:
- ファイルを保存したら `Ctrl+X`、`Y`、`Enter` を押す
- `APP_SECRET` には長いランダム文字列を設定（セキュリティが重要）
- `APP_BASE_URL` は実際のドメインに変更

### 6. データベース初期化

```bash
cd /home/<your_username>/kiroku-journal
source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
python -c "
import sys
sys.path.insert(0, 'app')
from database import init_db
init_db()
print('✅ Database initialized')
"
```

---

## Web アプリの設定

### 7. PythonAnywhere で Web アプリを作成

1. PythonAnywhere ダッシュボードから「Web」タブを開く
2. 「Add a new web app」をクリック
3. ドメイン名を選ぶ（`your_username.pythonanywhere.com`）
4. **Python のバージョン**: 3.11 を選択
5. 「Next」をクリック

### 8. WSGI ファイル設定

1. Web アプリ設定ページで、「WSGI configuration file」セクションを見つける
2. エディタを開いて、以下のパスのファイルを選択/作成：

```
/home/<your_username>/kiroku-journal/wsgi.py
```

3. 以下の内容に置き換え：

```python
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'app'))

from dotenv import load_dotenv
env_path = os.path.join(PROJECT_ROOT, 'config', '.env')
load_dotenv(env_path)

from app.flask_app import app

try:
    with app.app_context():
        from app.database import init_db
        init_db()
except Exception as e:
    print(f"Warning: Database initialization error: {e}", flush=True)

application = app
```

4. 保存（Ctrl+S）

### 9. Virtual Environment を設定

同じ Web アプリ設定ページで：

1. 「Virtualenv」セクションを見つける
2. パスを入力：

```
/home/<your_username>/.virtualenvs/kiroku-journal
```

3. 「Reload」ボタンをクリック

### 10. Static ファイルの設定

Web アプリ設定ページで、「Static files」セクションに以下を追加：

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/<your_username>/kiroku-journal/static` |
| `/uploads/` | `/home/<your_username>/kiroku-journal/uploads` |

### 11. Source code の設定

Web アプリ設定ページで、「Code」セクションを確認：

- Source code: `/home/<your_username>/kiroku-journal`
- Working directory: `/home/<your_username>/kiroku-journal`

---

## 検証

### 12. Web アプリを再起動

Web アプリ設定ページで「Reload」ボタンをクリック

### 13. アクセス確認

```
https://your_username.pythonanywhere.com
```

にアクセスして、アプリが正常に表示されるか確認

---

## トラブルシューティング

### エラーログの確認

PythonAnywhere のWeb アプリ設定で「Error log」をクリックして、エラーを確認できます。

### よくあるエラー

**1. `ModuleNotFoundError: No module named 'flask'`**
- Virtual environment が正しく設定されているか確認
- コンソールで `pip list` を実行してパッケージが入っているか確認

**2. `Permission denied` エラー**
- ファイルのパーミッションを確認：
  ```bash
  chmod 755 /home/<your_username>/kiroku-journal
  chmod 644 /home/<your_username>/kiroku-journal/wsgi.py
  ```

**3. データベースエラー**
- コンソールで以下を実行して再初期化：
  ```bash
  cd /home/<your_username>/kiroku-journal
  source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
  python -c "from app.database import init_db; init_db(); print('OK')"
  ```

**4. 静的ファイルが読み込まれない**
- Web アプリ設定で Static files のパスが正しいか確認
- キャッシュをクリア：ブラウザで Ctrl+Shift+Delete

---

## 更新手順（今後のデプロイ）

新しいバージョンをデプロイする場合：

```bash
# PythonAnywhere コンソールで
cd /home/<your_username>/kiroku-journal
git pull origin main

# 必要に応じて依存関係を更新
source /home/<your_username>/.virtualenvs/kiroku-journal/bin/activate
pip install -r requirements.txt --upgrade
```

その後、PythonAnywhere の Web アプリ設定で「Reload」をクリック

---

## セキュリティのベストプラクティス

1. **APP_SECRET を変更**
   - `.env` で長いランダム文字列を設定

2. **環境変数を管理**
   - Stripe キーなど秘密情報は `.env` に記載し、Git に上げない

3. **HTTPS を有効化**
   - PythonAnywhere は無料で HTTPS をサポート
   - Web アプリ設定で「Force HTTPS」を有効化

4. **定期バックアップ**
   - アプリは `backups/` フォルダに自動バックアップを作成
   - 定期的にダウンロードしてローカルプシン保存

---

## 参考

- [PythonAnywhere Python WAB フレームワーク](https://help.pythonanywhere.com/pages/PythonWhichVersionSubstitution)
- [Flask デプロイ](https://flask.palletsprojects.com/deployment/)
- [Flask WSGI](https://www.wsgi.org/)
