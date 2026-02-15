# Kiroku Journal

**Notion風ブロックエディタを備えたSaaS日記アプリケーション**

個人向けの高機能日記・記録アプリケーション。マークダウン対応のブロックエディタ、ページ階層管理、全文検索、テンプレート機能を搭載。

---

## 📁 フォルダ構成

```
kiroku-journal/
├── app/                          # メインアプリケーション
│   ├── flask_app.py             # Flask初期化・ページルート
│   ├── routes.py                # APIエンドポイント (40+ ルート)
│   ├── database.py              # DB接続・スキーマ管理
│   ├── utils.py                 # ユーティリティ関数
│   ├── backup_scheduler.py      # 自動バックアップスケジューラ
│   └── __init__.py              # Pythonパッケージ設定
│
├── scripts/                      # ユーティリティスクリプト
│   ├── backup_scheduler.py      # 自動バックアップ
│   ├── daily_backup.py          # 日次バックアップ
│   ├── restore_full_db.py       # 完全復元スクリプト
│   ├── restore_morning_db.py    # 朝のバックアップから復元
│   └── test_webhook.py          # Webhook テスト
│
├── templates/                    # Jinja2 テンプレート (HTML)
│   ├── index.html               # メインアプリケーション UI
│   ├── login.html               # ログイン画面
│   ├── setup.html               # 初期設定画面
│   ├── billing.html             # 課金管理画面
│   └── ...                      # その他テンプレート
│
├── static/                       # JS・CSS・画像
│   ├── manifest.json            # PWA設定
│   ├── sw.js                    # Service Worker
│   ├── calorie.js               # カロリー機能
│   ├── tts.js                   # テキスト音声化機能
│   └── ...                      # その他静的ファイル
│
├── uploads/                      # ユーザーアップロード画像
│
├── backups/                      # データベースバックアップ
│   └── backup_*.json            # 自動バックアップ (JSON形式)
│
├── docs/                         # ドキュメント
│   ├── README.md                # 概要・導入手順
│   ├── SYSTEM_OVERVIEW.md       # システム全体構造
│   ├── MODULE_GUIDE.md          # モジュール仕様
│   ├── MODULARIZATION_GUIDE.md  # 分割設計
│   ├── DEPLOY.md                # デプロイ手順
│   ├── SAAS_SETUP.md            # SaaS機能設定
│   ├── WEBHOOK_SETUP.md         # Webhook設定
│   └── SALES_CHECKLIST.md       # 営業チェックリスト
│
├── config/                       # 設定ファイル
│   ├── .env                     # 環境変数 (本番機密)
│   ├── .env.example             # 環境変数テンプレート
│   └── com.npicture.daily.backup.plist  # macOS LaunchAgent設定
│
├── .git/                         # Git履歴
├── .venv/                        # Python仮想環境
├── run.py                        # エントリーポイント
├── deploy.sh                     # デプロイスクリプト
├── requirements.txt              # Python依存パッケージ
├── .gitignore                    # Git無視ファイル設定
└── notion.db                     # SQLiteデータベース
```

---

## 🚀 クイックスタート

### 1. リポジトリをクローン
```bash
git clone <repo-url>
cd kiroku-journal
```

### 2. 仮想環境を有効化
```bash
source .venv/bin/activate      # macOS/Linux
# または
.venv\Scripts\activate         # Windows
```

### 3. 依存関係をインストール
```bash
pip install -r requirements.txt
```

### 4. 環境変数を設定
```bash
cp config/.env.example config/.env
# config/.env を編集して設定値を入力
```

### 5. 起動
```bash
python run.py
```

ブラウザで http://127.0.0.1:5000 にアクセス

---

## 📄 ドキュメント体系

| ドキュメント | 内容 | 対象 |
|----------|------|------|
| [docs/README.md](docs/README.md) | アプリ概要と基本機能 | 全員 |
| [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) | システム構造・アーキテクチャ | 開発者 |
| [docs/MODULE_GUIDE.md](docs/MODULE_GUIDE.md) | 各モジュールの関数リスト | 開発者 |
| [docs/MODULARIZATION_GUIDE.md](docs/MODULARIZATION_GUIDE.md) | コード分割の詳細設計 | 開発者 |
| [docs/DEPLOY.md](docs/DEPLOY.md) | 本番デプロイ手順 | DevOps |
| [docs/SAAS_SETUP.md](docs/SAAS_SETUP.md) | 認証・課金設定 | DevOps |
| [docs/WEBHOOK_SETUP.md](docs/WEBHOOK_SETUP.md) | Stripe Webhook構成 | DevOps |
| [docs/SALES_CHECKLIST.md](docs/SALES_CHECKLIST.md) | 顧客対応チェックリスト | 営業・サポート |

---

## 💾 主要機能

### エディタ
- ✅ Notion風ブロックエディタ
- ✅ テキスト、見出し、Todo、カロリー記録など複数ブロックタイプ
- ✅ ドラッグ&ドロップでページ・ブロック移動
- ✅ ページ階層管理（フォルダ構造）

### 検索・表示
- ✅ 全文検索（FTS - Full Text Search）
- ✅ カレンダー表示
- ✅ ダークモード

### ユーザー機能
- ✅ ユーザー登録・ログイン
- ✅ 14日間無料トライアル
- ✅ Stripe決済（サブスクリプション）
- ✅ パスワード再設定

### データ管理
- ✅ テンプレート機能
- ✅ ページのエクスポート（JSON・Markdown）
- ✅ ページのインポート
- ✅ 自動バックアップ（5分ごと）
- ✅ 復元スクリプト

### 追加機能
- ✅ カロリー計算・管理
- ✅ テキスト音声化 (TTS)
- ✅ 画像アップロード
- ✅ PWA対応（モバイルアプリ化）

---

## 🗄️ データベース

**型**: SQLite  
**ファイル**: `notion.db`

**テーブル**:
- `pages` - ページ・フォルダ
- `blocks` - テキストブロック・見出しなど
- `templates` - テンプレート
- `users` - ユーザー情報
- `password_reset_tokens` - パスワード再設定
- `healthplanet_tokens` - 健康プラットフォーム連携

**インデックス**:
- `idx_blocks_page_position` - ブロック検索
- `idx_pages_parent_position` - ページ階層
- `idx_pages_is_deleted` - 削除状態フィルタ
- `blocks_fts` - 全文検索 (FTS5)

---

## ⚙️ 環境変数

`config/.env` をテンプレートから作成して設定：

```env
# アプリケーション
APP_SECRET=ランダムな長い文字列
APP_BASE_URL=https://your-domain.com

# 認証
AUTH_ENABLED=1

# Stripe決済
STRIPE_SECRET_KEY=sk_live_xxx...
STRIPE_WEBHOOK_SECRET=whsec_xxx...
STRIPE_PRICE_ID=price_xxx...

# 機能フラグ
CALORIE_ENABLED=1
TTS_ENABLED=0
```

詳細は [docs/SAAS_SETUP.md](docs/SAAS_SETUP.md) を参照。

---

## 🔄 自動バックアップ

### 開発環境
アプリ起動時に自動的にバックアップスケジューラが起動。5分ごとに `backups/backup_*.json` を作成。

### 本番環境（macOS）
```bash
# 以下ファイルをセットアップ
config/com.npicture.daily.backup.plist
```

### 本番環境（Linux）
cron設定：
```bash
0 3 * * * cd /path/to/kiroku-journal && python scripts/daily_backup.py
```

---

## 🔧 復元手順

### 最新バックアップから復元

```bash
source .venv/bin/activate
python scripts/restore_full_db.py
```

### 特定の朝のバックアップから復元

```bash
python scripts/restore_morning_db.py
```

---

## 📊 システム状態

**最終確認（2026年2月15日）**:
- ✅ ページ: 252個
- ✅ ブロック: 1,245個
- ✅ テンプレート: 3個
- ✅ Flask: 正常動作中
- ✅ コード: c70d114 (朝の状態)

---

## 🛠️ 開発ガイド

### コード構造
- `app/flask_app.py` - Flask初期化 (81行)
- `app/routes.py` - API定義 (1,086行)
- `app/database.py` - DB管理 (170行)
- `app/utils.py` - ユーティリティ (332行)

### モジュール追加時
1. `app/` フォルダに追加
2. `flask_app.py` または `routes.py` でインポート
3. 必要に応じてドキュメント更新

---

## 📞 サポート

詳細は [docs/](docs/) フォルダのドキュメントを参照してください。

