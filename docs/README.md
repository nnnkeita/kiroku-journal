# SaaS日記アプリ - README

個人向けSaaS日記アプリケーション（Notion風）。認証、14日間トライアル、Stripe課金を実装済み。

## 機能

### コア機能
- Notion風のブロックエディタ（テキスト、見出し、Todo、カロリー記録など）
- ページ階層管理（フォルダ、ドラッグ&ドロップ）
- カレンダー表示
- テンプレート機能
- 全文検索
- バックアップ/復元
- ダークモード

### 認証・課金
- ユーザー登録・ログイン
- **14日間無料トライアル**
- Stripe決済（サブスクリプション）
- パスワード再設定（メール送信対応）
- アクティブなサブスク必須（トライアル期間後）

## クイックスタート

```bash
# 1. リポジトリクローン
git clone <repo-url>
cd npicture-site

# 2. 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 依存関係インストール
pip install -r requirements.txt

# 4. 環境変数設定
cp .env.example .env
# .envを編集（最低限APP_SECRETを変更）

# 5. 起動
python flask_app.py
```

ブラウザで http://127.0.0.1:5000 にアクセス → 初期ユーザー作成画面。

## 本番環境デプロイ

詳細は [DEPLOY.md](DEPLOY.md) を参照。

必須の環境変数:
- `APP_SECRET`（強固なランダム文字列）
- `APP_BASE_URL`（https://your-domain.com）
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`

## 販売前チェックリスト

[SALES_CHECKLIST.md](SALES_CHECKLIST.md) を参照。

必須:
- 利用規約
- プライバシーポリシー
- 特定商取引法表記（日本）
- セキュリティ監査
- 負荷テスト

## プロジェクト構成

```
.
├── flask_app.py          # メインアプリ（認証・課金含む）
├── database.py           # DB管理（users, pages, blocks, templates）
├── routes.py             # APIルート
├── utils.py              # ユーティリティ関数
├── templates/            # HTML
│   ├── index.html       # メインアプリ
│   ├── login.html       # ログイン
│   ├── setup.html       # 初期セットアップ
│   ├── forgot.html      # パスワード再設定依頼
│   ├── reset.html       # パスワード再設定
│   └── billing.html     # サブスク管理
├── static/              # CSS/JS
├── uploads/             # ユーザーアップロード画像
└── backups/             # 自動バックアップ
```

## ライセンス

（販売用に適切なライセンスを記載）

## サポート

（問い合わせ先を記載）
