# -*- coding: utf-8 -*-
"""
メインアプリケーション - Flask アプリケーション初期化

【モジュール分割構成】
- database.py: DB接続とテーブル管理
- utils.py: ユーティリティ関数（カロリー計算、エクスポート/インポート等）
- routes.py: APIエンドポイント定義（40+ルート）

このファイルは Flask アプリケーションの初期化とベースルートのみを管理します。
"""
from flask import Flask, render_template, send_from_directory, request, redirect, session, url_for, jsonify, make_response, g, abort
import os
import sys
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import click
import stripe
from contextlib import closing, nullcontext
from sqlite3 import IntegrityError
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
try:
    from flask_compress import Compress
    COMPRESS_AVAILABLE = True
except ImportError:
    COMPRESS_AVAILABLE = False

from functools import wraps, lru_cache
from datetime import datetime, timedelta

from .database import (
    get_db, init_db, get_or_create_inbox, get_or_create_finished, get_user_count, get_user_by_username, create_user,
    get_user_by_id, update_user_password, set_password_reset_token, get_password_reset_token,
    mark_password_reset_token_used, update_user_stripe_customer, update_user_subscription,
    get_user_by_stripe_customer
)

from .routes import register_routes
from .workspaces import use_workspace, uploads_folder
from .backup_scheduler import init_backup_scheduler

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
OWNER_USERNAME = os.getenv('JOURNAL_OWNER_USERNAME', '').strip()
AUTH_ENABLED = bool(OWNER_USERNAME) or os.getenv('AUTH_ENABLED', '0') == '1'
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', '')
STRIPE_ANNUAL_PRICE_ID = os.getenv('STRIPE_ANNUAL_PRICE_ID', '')
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

# === パフォーマンス最適化 ===
# gzip 圧縮を有効化
if COMPRESS_AVAILABLE:
    Compress(app)

app.config['JOURNAL_OWNER_CONFIGURED'] = bool(OWNER_USERNAME)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
secret = os.getenv('APP_SECRET')
if not secret:
    print('Warning: APP_SECRET is not set. Set APP_SECRET for production use.')
    secret = os.urandom(24)
app.secret_key = secret

# === キャッシュコントロール設定 ===
# レスポンスキャッシュ（APIレスポンス用）
_response_cache = {}
_cache_timestamps = {}

def cache_api_response(timeout_seconds=60):
    """APIレスポンスをキャッシュするデコレータ"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # キャッシュキーを生成
            cache_key = f"{request.path}:{request.query_string.decode('utf-8')}"
            
            # キャッシュを確認
            if cache_key in _response_cache:
                cached_time = _cache_timestamps.get(cache_key, datetime.now())
                if datetime.now() - cached_time < timedelta(seconds=timeout_seconds):
                    # キャッシュが有効
                    cached_response = _response_cache[cache_key]
                    return cached_response
            
            # キャッシュなし、関数を実行
            result = f(*args, **kwargs)
            _response_cache[cache_key] = result
            _cache_timestamps[cache_key] = datetime.now()
            
            # 古いキャッシュを削除（メモリ節約）
            if len(_response_cache) > 100:
                oldest_key = min(_cache_timestamps, key=_cache_timestamps.get)
                del _response_cache[oldest_key]
                del _cache_timestamps[oldest_key]
            
            return result
        return decorated_function
    return decorator

@app.after_request
def set_cache_headers(response):
    """キャッシュコントロールヘッダーを設定"""
    if request.path == '/static/sw.js':
        # Service Worker 自体を長期キャッシュすると、修正版の配信が遅れる。
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.public = False
        response.cache_control.private = True
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.startswith('/static/'):
        # 静的ファイル: 1年キャッシュ
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    elif AUTH_ENABLED or request.path.startswith('/api/') or request.path.endswith('.html') or request.path == '/':
        # API と HTML は常に最新を取得する。
        # 特に編集 API の GET 応答をキャッシュすると、保存成功後の再読込で
        # 保存前の本文が表示され、自動保存が失敗したように見えてしまう。
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.public = False
        response.cache_control.private = True
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        # その他の動的レスポンスも共有キャッシュには保存しない。
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.private = True
    
    # gzip 圧縮の有効化確認
    if 'gzip' not in response.headers.get('Content-Encoding', ''):
        response.headers['Vary'] = 'Accept-Encoding'
    
    # DNSプリフェッチの設定
    response.headers['X-UA-Compatible'] = 'IE=edge'
    
    return response

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

# These routes operate on the installation, not on the selected journal.
OWNER_ENDPOINTS = {
    'download_db', 'list_backups', 'restore_backup', 'upload_db',
    'reload_app', 'get_system_status', 'health_check', 'admin_cleanup_running_records',
    'admin_journals', 'admin_attachment',
}
PUBLIC_ENDPOINTS = {
    'static', 'login', 'pricing', 'setup', 'webhook_deploy', 'stripe_webhook',
    'reset_password', 'forgot_password', 'terms', 'privacy', 'tokusho', 'tokutei', 'tokutei_html',
}


def is_journal_owner(user):
    return bool(OWNER_USERNAME and user and user['username'] == OWNER_USERNAME)


@app.before_request
def require_login():
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return
    if not AUTH_ENABLED:
        if request.endpoint in OWNER_ENDPOINTS:
            abort(403)
        return

    user = get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    if not user:
        session.clear()
        return redirect(url_for('login'))
    g.journal_owner = is_journal_owner(user)
    if request.endpoint in OWNER_ENDPOINTS:
        if not g.journal_owner:
            abort(403)
        if request.endpoint in {'restore_backup', 'upload_db'}:
            abort(403)  # An account database replacement could reassign workspace IDs.
        return
    if request.endpoint in {'billing', 'billing_checkout', 'billing_portal', 'logout'}:
        return
    if not g.journal_owner and not _is_subscription_active(dict(user)):
        return redirect(url_for('billing'))

    if not g.journal_owner:
        # A single authenticated legacy account may keep using the original journal.
        if not OWNER_USERNAME:
            if get_user_count() != 1:
                abort(503)
            return
        workspace = use_workspace(user['id'])
        workspace.__enter__()
        g.journal_context = workspace


@app.teardown_request
def release_workspace(error):
    workspace = g.pop('journal_context', None)
    if workspace is not None:
        workspace.__exit__(None, None, None)


@app.cli.command('create-journal-user')
@click.argument('username')
@click.password_option()
def create_journal_user(username, password):
    """Provision a private journal account with a 14-day trial."""
    if not OWNER_USERNAME or not get_user_by_username(OWNER_USERNAME):
        raise click.ClickException('Configure JOURNAL_OWNER_USERNAME for the existing owner first.')
    username = username.strip()
    if not username or len(username) > 100 or len(password) < 12:
        raise click.ClickException('Enter a username and a password of at least 12 characters.')
    try:
        create_user(
            username, generate_password_hash(password),
            trial_ends_at=(datetime.utcnow() + timedelta(days=14)).isoformat(),
        )
    except IntegrityError:
        raise click.ClickException('That username already exists.') from None
    click.echo(f'Created journal account {username}.')


def admin_workspace(user):
    return nullcontext() if is_journal_owner(user) else use_workspace(user['id'])


@app.get('/admin/journals')
def admin_journals():
    with closing(get_db(accounts=True)) as conn:
        users = conn.execute('SELECT id, username FROM users ORDER BY username').fetchall()
    user_id = request.args.get('user', type=int)
    page_id = request.args.get('page', type=int)
    target = get_user_by_id(user_id) if user_id is not None else None
    if user_id is not None and target is None:
        abort(404)
    pages, page, blocks = [], None, []
    if target:
        app.logger.warning('Journal admin view actor=%s account=%s page=%s',
                           session['user_id'], user_id, page_id)
        with admin_workspace(target):
            conn = get_db()
            try:
                pages = conn.execute('SELECT id, title, is_deleted FROM pages ORDER BY updated_at DESC, id DESC').fetchall()
                if page_id is not None:
                    page = conn.execute('SELECT * FROM pages WHERE id = ?', (page_id,)).fetchone()
                    if page is None:
                        abort(404)
                    blocks = conn.execute('SELECT * FROM blocks WHERE page_id = ? ORDER BY position', (page_id,)).fetchall()
            finally:
                conn.close()
    return render_template('admin_journals.html', users=users, target=target, pages=pages, page=page, blocks=blocks)


@app.get('/admin/journals/<int:user_id>/attachments/<filename>')
def admin_attachment(user_id, filename):
    target = get_user_by_id(user_id)
    if target is None:
        abort(404)
    app.logger.warning('Journal admin attachment actor=%s account=%s', session['user_id'], user_id)
    with admin_workspace(target):
        return send_from_directory(uploads_folder(UPLOAD_FOLDER), filename, as_attachment=True)


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

@app.route('/healthplanet')
def healthplanet_page():
    """Health Planet 連携ページ"""
    return render_template('healthplanet.html', current_user=session.get('username'))

@app.route('/uploads/<filename>')
def download_file(filename):
    response = send_from_directory(uploads_folder(UPLOAD_FOLDER), filename)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_user_count() == 0:
        return redirect(url_for('setup'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        return render_template('login.html', error='ユーザー名またはパスワードが違います。')
    return render_template('login.html')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if OWNER_USERNAME and not get_user_count():
        abort(503)
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
        trial_ends = (datetime.utcnow() + timedelta(days=14)).isoformat()
        create_user(username, password_hash, trial_ends_at=trial_ends)
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

@app.route('/tokutei.html')
def tokutei_html():
    """Stripe 審査対応: 特定商取引法ページ（.html形式）"""
    return redirect(url_for('tokusho'))

@app.route('/tokutei')
def tokutei():
    """特定商取引法ページ"""
    return redirect(url_for('tokusho'))

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/billing')
def billing():
    user = get_user_by_id(session.get('user_id')) if session.get('user_id') else None
    user = dict(user) if user else None
    status = user['subscription_status'] if user else 'inactive'
    token = session.setdefault('billing_token', secrets.token_urlsafe(32))
    return render_template('billing.html', status=status, token=token, annual=bool(STRIPE_ANNUAL_PRICE_ID))

@app.route('/billing/checkout', methods=['POST'])
def billing_checkout():
    token = session.get('billing_token')
    if not token or token != request.form.get('token'):
        return 'Invalid form token', 403
    price = {'monthly': STRIPE_PRICE_ID, 'annual': STRIPE_ANNUAL_PRICE_ID}.get(request.form.get('plan'))
    if not AUTH_ENABLED or not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET or not price:
        return '決済は現在利用できません。', 503
    user = get_user_by_id(session.get('user_id'))
    user = dict(user) if user else None
    if not user:
        return redirect(url_for('login'))
    customer_id = user.get('stripe_customer_id')
    if customer_id and user.get('subscription_status') in {'active', 'trialing', 'past_due', 'unpaid', 'incomplete', 'paused'}:
        return redirect(url_for('billing_portal'))
    if not customer_id:
        customer = stripe.Customer.create()
        customer_id = customer['id']
        update_user_stripe_customer(user['id'], customer_id)
    session_obj = stripe.checkout.Session.create(
        mode='subscription',
        customer=customer_id,
        line_items=[{'price': price, 'quantity': 1}],
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
    
    if not STRIPE_WEBHOOK_SECRET:
        return jsonify({'error': 'Webhook not configured'}), 503
    if not sig_header:
        return jsonify({'error': 'Missing signature'}), 400
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({'error': 'Invalid webhook'}), 400

    event_type = event.get('type')
    data = event.get('data', {}).get('object', {})

    if event_type in ['customer.subscription.updated', 'customer.subscription.created']:
        customer_id = data.get('customer')
        status = data.get('status')
        period_end = data.get('trial_end') if status == 'trialing' else data.get('current_period_end')
        if not period_end and status == 'active':
            periods = [item['current_period_end'] for item in data.get('items', {}).get('data', []) if item.get('current_period_end')]
            period_end = min(periods, default=None)
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
