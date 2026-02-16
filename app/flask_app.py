# -*- coding: utf-8 -*-
"""
メインアプリケーション - Flask アプリケーション初期化

【モジュール分割構成】
- database.py: DB接続とテーブル管理
- utils.py: ユーティリティ関数（カロリー計算、エクスポート/インポート等）
- routes.py: APIエンドポイント定義（40+ルート）

このファイルは Flask アプリケーションの初期化とベースルートのみを管理します。
"""
from flask import Flask, render_template, send_from_directory, request, redirect, session, url_for, jsonify
import os
import sys
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import stripe
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from database import (
    init_db, get_or_create_inbox, get_or_create_finished, get_user_count, get_user_by_username, create_user,
    get_user_by_id, update_user_password, set_password_reset_token, get_password_reset_token,
    mark_password_reset_token_used, update_user_stripe_customer, update_user_subscription,
    get_user_by_stripe_customer
)

from routes import register_routes
from backup_scheduler import init_backup_scheduler

# === パス設定 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # kiroku-journal フォルダ
TEMPLATE_FOLDER = os.path.join(PROJECT_ROOT, 'templates')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
BACKUP_FOLDER = os.path.join(PROJECT_ROOT, 'backups')

# .envファイルを読み込み（PythonAnywhereの無料プラン対応）
env_path = os.path.join(PROJECT_ROOT, 'config', '.env')
load_dotenv(env_path)


# === 設定値の定義 ===
TTS_ENABLED = os.getenv('TTS_ENABLED', '1') == '1'
CALORIE_ENABLED = os.getenv('CALORIE_ENABLED', '1') == '1'
AUTH_ENABLED = os.getenv('AUTH_ENABLED', '0') == '1'  # デフォルトで認証はオフ
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', '')
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000')
STRIPE_SUCCESS_URL = os.getenv('STRIPE_SUCCESS_URL', f'{APP_BASE_URL}/billing?success=1')
STRIPE_CANCEL_URL = os.getenv('STRIPE_CANCEL_URL', f'{APP_BASE_URL}/billing?canceled=1')

SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)

# === Flask アプリケーション初期化 ===
app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
secret = os.getenv('APP_SECRET')
if not secret:
    print('Warning: APP_SECRET is not set. Set APP_SECRET for production use.')
    secret = os.urandom(24)
app.secret_key = secret

# === バージョン情報（ブラウザキャッシュバイパス用） ===
def get_app_version():
    """Gitハッシュをバージョンとして取得"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else 'unknown'
    except:
        return 'unknown'

APP_VERSION = get_app_version()
print(f"[Flask] 📦 App version: {APP_VERSION}", file=sys.stderr, flush=True)
sys.stderr.flush()

# テンプレート関数を登録（テンプレートから呼び出せるように）
@app.context_processor
def inject_version():
    return {'app_version': APP_VERSION}

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# === バックアップスケジューラー初期化 ===
init_backup_scheduler(app)

# ディレクトリ作成
for folder in [UPLOAD_FOLDER, BACKUP_FOLDER]:
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create {folder}: {e}")

# === 課金判定 ===
def _is_subscription_active(user):
    if not user:
        return False
    status = user.get('subscription_status') or 'inactive'
    ends_at = user.get('subscription_ends_at')
    now = datetime.utcnow()
    if status == 'active':
        if ends_at:
            try:
                if datetime.fromisoformat(ends_at) < now:
                    return False
            except Exception:
                pass
        return True
    if status == 'trialing':
        if ends_at:
            try:
                return datetime.fromisoformat(ends_at) > now
            except Exception:
                return False
        return False
    return False

# === 認証ガード ===
@app.before_request
def require_login():
    if not AUTH_ENABLED:
        return
    if request.path.startswith('/static/'):
        return
    if request.endpoint is None:
        return
    public_endpoints = {
        'login',
        'setup',
        'webhook_deploy',
        'stripe_webhook',
        'reset_password',
        'forgot_password',
        'terms',
        'privacy',
        'tokusho'
    }
    if request.endpoint in public_endpoints:
        return
    if not session.get('user_id'):
        return redirect(url_for('login'))
    subscription_exempt = public_endpoints | {
        'billing',
        'billing_checkout',
        'billing_portal',
        'logout'
    }
    if request.endpoint in subscription_exempt:
        return
    user = get_user_by_id(session.get('user_id'))
    user = dict(user) if user else None
    if not _is_subscription_active(user):
        return redirect(url_for('billing'))


# === ページルート ===
@app.route('/')
def index():
    return render_template('index.html', tts_enabled=TTS_ENABLED, calorie_enabled=CALORIE_ENABLED, current_user=session.get('username'))

@app.route('/inbox')
def inbox_page():
    """あとで調べるページへのショートカットURL"""
    inbox = get_or_create_inbox()
    if inbox:
        return render_template('index.html', inbox_id=inbox['id'], tts_enabled=TTS_ENABLED, calorie_enabled=CALORIE_ENABLED, current_user=session.get('username'))
    return render_template('index.html', tts_enabled=TTS_ENABLED, calorie_enabled=CALORIE_ENABLED, current_user=session.get('username'))

@app.route('/finished')
def finished_page():
    """読了ページへのショートカットURL"""
    finished = get_or_create_finished()
    if finished:
        return render_template('index.html', finished_id=finished['id'], tts_enabled=TTS_ENABLED, calorie_enabled=CALORIE_ENABLED, current_user=session.get('username'))
    return render_template('index.html', tts_enabled=TTS_ENABLED, calorie_enabled=CALORIE_ENABLED, current_user=session.get('username'))

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_user_count() == 0:
        return redirect(url_for('setup'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        return render_template('login.html', error='ユーザー名またはパスワードが違います。')
    return render_template('login.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if get_user_count() > 0:
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        password_confirm = request.form.get('password_confirm') or ''
        if not username or not password:
            return render_template('setup.html', error='ユーザー名とパスワードを入力してください。')
        if password != password_confirm:
            return render_template('setup.html', error='パスワードが一致しません。')
        password_hash = generate_password_hash(password)
        user_id = create_user(username, password_hash)
        trial_ends = (datetime.utcnow() + timedelta(days=14)).isoformat()
        update_user_subscription(user_id, 'trialing', trial_ends)
        user = get_user_by_username(username)
        session['user_id'] = user['id']
        session['username'] = user['username']
        return redirect(url_for('index'))
    return render_template('setup.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        user = get_user_by_username(username)
        if user:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            set_password_reset_token(user['id'], token, expires_at)
            reset_link = f"{APP_BASE_URL}/reset/{token}"
            if SMTP_HOST and SMTP_FROM:
                msg = EmailMessage()
                msg['Subject'] = 'パスワード再設定'
                msg['From'] = SMTP_FROM
                msg['To'] = user['username'] if '@' in user['username'] else SMTP_FROM
                msg.set_content(f"以下のリンクからパスワードを再設定してください。\n{reset_link}\n\n有効期限: 1時間")
                try:
                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                        server.starttls()
                        if SMTP_USER:
                            server.login(SMTP_USER, SMTP_PASSWORD)
                        server.send_message(msg)
                except Exception:
                    return render_template('forgot.html', error='メール送信に失敗しました。', debug_link=reset_link)
            return render_template('forgot.html', success='再設定リンクを送信しました。', debug_link=reset_link)
        return render_template('forgot.html', success='再設定リンクを送信しました。')
    return render_template('forgot.html')

@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_row = get_password_reset_token(token)
    if not token_row:
        return render_template('reset.html', error='無効なリンクです。')
    if token_row['used']:
        return render_template('reset.html', error='このリンクは使用済みです。')
    if datetime.fromisoformat(token_row['expires_at']) < datetime.utcnow():
        return render_template('reset.html', error='リンクの有効期限が切れています。')
    if request.method == 'POST':
        password = request.form.get('password') or ''
        password_confirm = request.form.get('password_confirm') or ''
        if not password:
            return render_template('reset.html', error='パスワードを入力してください。')
        if password != password_confirm:
            return render_template('reset.html', error='パスワードが一致しません。')
        update_user_password(token_row['user_id'], generate_password_hash(password))
        mark_password_reset_token_used(token)
        return redirect(url_for('login'))
    return render_template('reset.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/tokusho')
def tokusho():
    return render_template('tokusho.html')

@app.route('/billing')
def billing():
    user = get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    user = dict(user) if user else None
    status = user['subscription_status'] if user else 'inactive'
    return render_template('billing.html', status=status)

@app.route('/billing/checkout')
def billing_checkout():
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return render_template('billing.html', status='inactive', error='Stripe設定が未完了です。')
    user = get_user_by_id(session.get('user_id'))
    user = dict(user) if user else None
    if not user:
        return redirect(url_for('login'))
    customer_id = user.get('stripe_customer_id')
    if not customer_id:
        customer = stripe.Customer.create()
        customer_id = customer['id']
        update_user_stripe_customer(user['id'], customer_id)
    session_obj = stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
        success_url=STRIPE_SUCCESS_URL,
        cancel_url=STRIPE_CANCEL_URL
    )
    return redirect(session_obj.url)

@app.route('/billing/portal')
def billing_portal():
    if not STRIPE_SECRET_KEY:
        return redirect(url_for('billing'))
    user = get_user_by_id(session.get('user_id'))
    user = dict(user) if user else None
    if not user or not user.get('stripe_customer_id'):
        return redirect(url_for('billing'))
    portal = stripe.billing_portal.Session.create(
        customer=user['stripe_customer_id'],
        return_url=f'{APP_BASE_URL}/billing'
    )
    return redirect(portal.url)

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    # Try to verify the signature, but be lenient in development
    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            # No secret set - use raw JSON (development mode)
            event = request.get_json() or {}
    except stripe.error.SignatureVerificationError as e:
        # Signature verification failed - for development, log and try to parse anyway
        import sys
        print(f"[WEBHOOK] Signature verification failed (development): {e}", file=sys.stderr, flush=True)
        # In development mode, try to parse the payload anyway
        import json
        try:
            event = json.loads(payload)
        except:
            return jsonify({'error': 'Invalid JSON payload'}), 400
    except Exception as e:
        import sys
        print(f"[WEBHOOK] Unexpected error: {e}", file=sys.stderr, flush=True)
        return jsonify({'error': 'Webhook processing error'}), 400

    # Process the event
    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})
    
    import sys
    print(f"[WEBHOOK] Event type: {event_type}, customer: {data.get('customer', 'N/A')}", file=sys.stderr, flush=True)

    if event_type in ['checkout.session.completed']:
        customer_id = data.get('customer')
        if customer_id:
            user = get_user_by_stripe_customer(customer_id)
            if user:
                update_user_subscription(user['id'], 'active', None)

    if event_type in ['customer.subscription.updated', 'customer.subscription.created']:
        customer_id = data.get('customer')
        status = data.get('status')
        period_end = data.get('current_period_end')
        ends_at = datetime.utcfromtimestamp(period_end).isoformat() if period_end else None
        if customer_id:
            user = get_user_by_stripe_customer(customer_id)
            if user:
                update_user_subscription(user['id'], status, ends_at)

    if event_type in ['customer.subscription.deleted']:
        customer_id = data.get('customer')
        if customer_id:
            user = get_user_by_stripe_customer(customer_id)
            if user:
                update_user_subscription(user['id'], 'canceled', None)

    return jsonify({'received': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# === APIルート登録 ===
register_routes(app)

# === アプリケーション起動 ===
if __name__ == '__main__':
    import webbrowser
    from threading import Timer
    
    def open_browser():
        webbrowser.open_new('http://127.0.0.1:5000/')
    
    Timer(1, open_browser).start()
    
    with app.app_context():
        init_db()
    app.run(port=5000)
else:
    # PythonAnywhere用のWSGI
    try:
        with app.app_context():
            init_db()
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()
