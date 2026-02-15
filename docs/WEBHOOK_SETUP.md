# Webhook設定ガイド

## ローカル開発環境でのWebhookテスト

### Stripe CLIを使う方法（推奨）

1. Stripe CLIをインストール:
```bash
brew install stripe/stripe-cli/stripe
```

2. Stripeにログイン:
```bash
stripe login
```

3. Webhookリスナーを起動:
```bash
stripe listen --forward-to http://localhost:5000/webhook/stripe
```

4. 表示される Webhook Secret (`whsec_...`) を `.env` に設定:
```
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

5. Flaskアプリを再起動

6. テスト決済を実行すると、自動的にWebhookが送信され、ステータスが `active` に更新されます

## 本番環境でのWebhook設定

### 1. Stripeダッシュボードで設定

1. https://dashboard.stripe.com/webhooks にアクセス
2. 「エンドポイントを追加」をクリック
3. 設定:
   - **エンドポイントURL**: `https://your-domain.com/webhook/stripe`
   - **送信するイベント**:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
4. 「エンドポイントを追加」をクリック
5. 表示される **Webhook署名シークレット** (`whsec_...`) をコピー
6. 本番環境の `.env` に設定:
```
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

### 2. Webhookテスト

Stripeダッシュボードの Webhook 画面で「テストイベントを送信」でテストできます。

## トラブルシューティング

- **Webhookが届かない**: エンドポイントURLが正しいか確認
- **署名検証エラー**: `STRIPE_WEBHOOK_SECRET` が正しく設定されているか確認
- **ローカルで動かない**: ngrokやStripe CLIを使用

## 手動でステータス更新（緊急用）

開発中、Webhookなしで手動更新する場合:

```python
# データベースに直接アクセス
sqlite3 notion.db
UPDATE users SET subscription_status = 'active' WHERE id = 1;
.quit
```

アプリを再起動すれば、すぐにアクセスできます。
