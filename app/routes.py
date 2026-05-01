"""
Flask アプリケーション - APIルート定義
ページ、ブロック、テンプレート、インポート/エクスポート機能など
"""

from flask import request, jsonify, send_file, redirect
import re
from datetime import datetime, timedelta
import os
import io
import json
import zipfile
import shutil
import sqlite3
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from werkzeug.utils import secure_filename

from .database import (
    get_db, get_next_position, get_block_next_position,
    mark_tree_deleted, hard_delete_tree,
    save_healthplanet_token, get_healthplanet_token, clear_healthplanet_token,
    archive_old_diary_pages
)
from .utils import (
    allowed_file, estimate_calories, estimate_calories_items, export_page_to_dict,
    page_to_markdown, create_page_from_dict, copy_page_tree,
    backup_database_to_json, get_or_create_date_page,
    cleanup_accumulated_running_records
)

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATABASE = os.path.join(PROJECT_ROOT, 'notion.db')
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
BACKUP_FOLDER = os.path.join(PROJECT_ROOT, 'backups')


def register_routes(app):
    """全APIルートをアプリに登録"""

    def _get_healthplanet_config():
        client_id = os.getenv('HEALTHPLANET_CLIENT_ID', '')
        client_secret = os.getenv('HEALTHPLANET_CLIENT_SECRET', '')
        redirect_uri = os.getenv('HEALTHPLANET_REDIRECT_URI', '')
        if not redirect_uri:
            base_url = os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000')
            redirect_uri = f"{base_url}/api/healthplanet/callback"
        scope = os.getenv('HEALTHPLANET_SCOPE', 'innerscan')
        return client_id, client_secret, redirect_uri, scope

    def _parse_healthplanet_token_response(raw_text):
        try:
            return json.loads(raw_text)
        except Exception:
            parsed = urllib.parse.parse_qs(raw_text)
            return {k: v[0] for k, v in parsed.items()}

    def _healthplanet_urlopen(req, timeout=30):
        proxy_url = os.getenv('HEALTHPLANET_PROXY_URL', '').strip()
        if not proxy_url and os.getenv('PYTHONANYWHERE_DOMAIN'):
            proxy_url = 'http://proxy.server:3128'
        if proxy_url:
            handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            opener = urllib.request.build_opener(handler)
            return opener.open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)

    def _fetch_healthplanet_innerscan(access_token, from_str, to_str, tags):
        params = {
            'access_token': access_token,
            'date': '1',
            'from': from_str,
            'to': to_str,
            'tag': ','.join(tags)
        }
        url = 'https://www.healthplanet.jp/status/innerscan.json?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method='GET')
        print(f"[DEBUG] Health Planet API Request URL: {url}")
        try:
            with _healthplanet_urlopen(req, timeout=30) as resp:
                status_code = resp.status
                print(f"[DEBUG] Health Planet API Response Status: {status_code}")
                resp_text = resp.read().decode('utf-8')
                print(f"[DEBUG] Health Planet API Response Body: {resp_text[:500]}")
                data = json.loads(resp_text)
                print(f"[DEBUG] Health Planet API Parsed Data: {data}")
                return data
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='ignore')
            print(f"[ERROR] HTTP Error: {e.code}")
            print(f"[ERROR] Response Body: {error_body[:500]}")
            raise Exception(f"Health Planet HTTP Error {e.code}")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parse Error: {e}")
            print(f"[ERROR] Response was: {resp_text[:200] if 'resp_text' in locals() else 'unknown'}")
            raise Exception(f"Invalid JSON response")
        except Exception as e:
            print(f"[ERROR] Health Planet Request Failed: {e}")
            raise

    def _format_healthplanet_line(measurements):
        """Health Planetのすべての測定項目をフォーマット"""
        # Health Planetのタグマッピング
        tags_display = {
            '6021': '体重',
            '6022': '体脂肪率',
            '6023': '筋肉量',
            '6024': '筋肉スコア',
            '6025': '推定骨量',
            '6026': '体水分率',
            '6027': '推定基礎代謝量',
            '6028': '体内年齢',
            '6029': '体脂肪量'
        }
        
        # 単位のマッピング
        tags_unit = {
            '6021': 'kg',
            '6022': '%',
            '6023': 'kg',
            '6024': '点',
            '6025': 'kg',
            '6026': '%',
            '6027': 'kcal/day',
            '6028': '才',
            '6029': 'kg'
        }
        
        parts = []
        # 表示順序を固定
        ordered_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
        for tag in ordered_tags:
            value = measurements.get(tag)
            if value:
                display_name = tags_display.get(tag, tag)
                unit = tags_unit.get(tag, '')
                parts.append(f"{display_name} {value}{unit}")
        
        return ' / '.join(parts)

    def _upsert_healthplanet_block(cursor, page_id, content):
        cursor.execute('SELECT id, position, props FROM blocks WHERE page_id = ? ORDER BY position ASC', (page_id,))
        rows = cursor.fetchall()
        target_id = None
        for row in rows:
            props = row['props'] or '{}'
            try:
                props_json = json.loads(props) if isinstance(props, str) else props
            except Exception:
                props_json = {}
            if props_json.get('source') == 'healthplanet':
                target_id = row['id']
                break

        if target_id:
            cursor.execute('UPDATE blocks SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (content, target_id))
            return

        if rows:
            min_pos = min(row['position'] for row in rows)
            new_pos = min_pos - 1000.0
        else:
            new_pos = 1000.0

        props = json.dumps({'source': 'healthplanet', 'type': 'body'})
        cursor.execute(
            "INSERT INTO blocks (page_id, type, content, position, props) VALUES (?, 'text', ?, ?, ?)",
            (page_id, content, new_pos, props)
        )

    def _parse_healthplanet_datetime(date_value):
        """Health Planet の YYYYMMDDHHMM/ YYYYMMDDHHMMSS をJSTのdatetimeにする"""
        text = str(date_value or '').strip()
        for fmt in ('%Y%m%d%H%M%S', '%Y%m%d%H%M'):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
        return None

    def _healthplanet_db_timestamp(date_value):
        measured_jst = _parse_healthplanet_datetime(date_value)
        if not measured_jst:
            return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        measured_utc = measured_jst - timedelta(hours=9)
        return measured_utc.strftime('%Y-%m-%d %H:%M:%S')

    def _group_healthplanet_measurements_by_date(data):
        """Health Planet のレスポンスを測定日ごと・タグごとに最新値へまとめる"""
        grouped = {}
        for entry in data.get('data', []) if isinstance(data, dict) else []:
            print(f"[DEBUG] Processing Entry: {entry}")
            tag = str(entry.get('tag', ''))
            keydata = str(entry.get('keydata', '')).strip()
            date_value = str(entry.get('date', '')).strip()
            measured_dt = _parse_healthplanet_datetime(date_value)
            if not tag or not keydata or not measured_dt:
                print(f"[DEBUG] Skipping Entry: {entry}")
                continue
            date_key = measured_dt.strftime('%Y-%m-%d')
            grouped.setdefault(date_key, {})
            current = grouped[date_key].get(tag)
            if not current or date_value > current.get('date', ''):
                grouped[date_key][tag] = {'value': keydata, 'date': date_value}
        return grouped

    def _save_healthplanet_measurements(cursor, date_str, measurements):
        latest_values = {k: v.get('value') for k, v in measurements.items()}
        latest_date_value = max((v.get('date', '') for v in measurements.values()), default='')
        content = _format_healthplanet_line(latest_values)
        if not content:
            return False

        page = get_or_create_date_page(cursor, date_str)
        if not page:
            return False
        _upsert_healthplanet_block(cursor, page['id'], content)

        weight_val = latest_values.get('6021')
        body_fat_val = latest_values.get('6022')
        try:
            weight_float = float(weight_val) if weight_val else None
        except (ValueError, TypeError):
            weight_float = None
        try:
            body_fat_float = float(body_fat_val) if body_fat_val else None
        except (ValueError, TypeError):
            body_fat_float = None
        if weight_float is not None or body_fat_float is not None:
            cursor.execute(
                'UPDATE pages SET weight = ?, body_fat = ?, weight_at = ? WHERE id = ?',
                (weight_float, body_fat_float, _healthplanet_db_timestamp(latest_date_value), page['id'])
            )
        return True

    def sync_healthplanet_for_date(target_date=None, days=None):
        """指定日付または直近期間のHealthPlanetデータを測定日ごとに同期
        
        Args:
            target_date (str, optional): 同期対象日付 (YYYY-MM-DD形式). Noneなら直近期間
            days (int, optional): target_dateなしの場合、直近何日分を同期するか
            
        Returns:
            tuple: (成功フラグ, メッセージ)
        """
        token_row = get_healthplanet_token()
        if not token_row:
            return False, 'HealthPlanetが未連携です。'

        access_token = token_row['access_token']
        expires_at = token_row['expires_at']
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    return False, 'トークン期限切れです。再連携してください。'
            except Exception:
                pass

        # 対象期間を決定
        jst_now = datetime.utcnow() + timedelta(hours=9)
        if target_date:
            try:
                target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                date_str = target_date
                start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                end = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError:
                return False, f'日付形式が正しくありません: {target_date}'
        else:
            try:
                sync_days = max(1, min(int(days or 30), 90))
            except (ValueError, TypeError):
                sync_days = 30
            date_str = f'直近{sync_days}日'
            start = (jst_now - timedelta(days=sync_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = jst_now

        from_str = start.strftime('%Y%m%d%H%M%S')
        to_str = end.strftime('%Y%m%d%H%M%S')

        print(f"[DEBUG] Token Row: {token_row}")
        print(f"[DEBUG] Access Token: {token_row['access_token']}, Expires At: {token_row['expires_at']}")
        print(f"[DEBUG] Time Range: From {from_str} To {to_str} (Date: {date_str})")

        try:
            # === Health Planetから全測定項目を取得 ===
            all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
            try:
                data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, all_tags)
                print(f"[DEBUG] Fetched Data with all tags: {data}")
            except Exception as e1:
                print(f"[WARN] Failed to fetch all tags, trying core tags only: {e1}")
                # フォールバック：コアタグだけで試す
                core_tags = ['6021', '6022']
                data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, core_tags)
                print(f"[DEBUG] Fetched Data with core tags: {data}")
        except Exception as e:
            print(f"[ERROR] Fetch HealthPlanet Data Failed: {e}")
            return False, f'Health Planetの取得に失敗しました: {str(e)[:100]}'

        grouped_measurements = _group_healthplanet_measurements_by_date(data)
        if not grouped_measurements:
            if target_date:
                return False, f'{target_date} のHealth Planetデータが見つかりませんでした。'
            return False, '指定期間のHealth Planetデータが見つかりませんでした。'

        conn = get_db()
        cursor = conn.cursor()
        synced_dates = []
        for measured_date, measurements in sorted(grouped_measurements.items()):
            if _save_healthplanet_measurements(cursor, measured_date, measurements):
                synced_dates.append(measured_date)

        conn.commit()
        conn.close()
        if not synced_dates:
            return False, '日付ページの作成または保存に失敗しました。'
        if len(synced_dates) == 1:
            return True, f'{synced_dates[0]} のHealth Planetデータを同期しました。'
        return True, f'{len(synced_dates)}日分のHealth Planetデータを同期しました: ' + '、'.join(synced_dates)

    def sync_healthplanet_today():
        """今日のHealthPlaneデータを同期 (従来互換性)"""
        return sync_healthplanet_for_date(None)

    @app.route('/api/inbox', methods=['GET'])
    def get_inbox():
        """'あとで調べる'ページを取得"""
        from database import get_or_create_inbox
        inbox = get_or_create_inbox()
        return jsonify(inbox if inbox else {'error': 'Failed to create inbox'}), 200 if inbox else 500

    @app.route('/api/inbox/resolve', methods=['POST'])
    def resolve_inbox_item():
        """チェック済みの項目を知識の宝庫へ保存"""
        data = request.json or {}
        block_id = data.get('block_id')
        note = (data.get('note') or '').strip()
        if not block_id:
            return jsonify({'error': 'block_id is required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, p.title AS page_title, p.id AS page_id
            FROM blocks b
            JOIN pages p ON b.page_id = p.id
            WHERE b.id = ?
        ''', (block_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Block not found'}), 404

        page_title = row['page_title'] or ''
        if page_title != '🔖 あとで調べる':
            conn.close()
            return jsonify({'error': 'Only inbox items can be resolved'}), 400

        raw_props = row['props'] or '{}'
        try:
            props = json.loads(raw_props) if isinstance(raw_props, str) else dict(raw_props)
        except Exception:
            props = {}

        if props.get('resolved_at'):
            conn.close()
            return jsonify({'success': True, 'status': 'already_resolved'}), 200

        from database import get_or_create_knowledge_base
        knowledge = get_or_create_knowledge_base()
        if not knowledge:
            conn.close()
            return jsonify({'error': 'Failed to create knowledge base'}), 500

        resolved_date = datetime.now().strftime('%Y-%m-%d')
        original_content = (row['content'] or '').strip()
        content_lines = []
        if original_content:
            content_lines.append(original_content)
        if note:
            content_lines.append(f"解決メモ: {note}")
        content_lines.append(f"解決日: {resolved_date}")
        if not content_lines:
            content_lines = ['（無題）', f"解決日: {resolved_date}"]
        knowledge_content = '\n'.join(content_lines)

        knowledge_block_props = {
            'source_page_id': row['page_id'],
            'source_block_id': row['id'],
            'resolved_at': resolved_date,
            'resolution_note': note
        }
        new_pos = get_block_next_position(cursor, knowledge['id'])
        cursor.execute(
            'INSERT INTO blocks (page_id, type, content, checked, position, props) VALUES (?, ?, ?, ?, ?, ?)',
            (knowledge['id'], 'text', knowledge_content, 0, new_pos, json.dumps(knowledge_block_props, ensure_ascii=False))
        )
        knowledge_block_id = cursor.lastrowid

        cursor.execute('DELETE FROM blocks WHERE id = ?', (row['id'],))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'knowledge_block_id': knowledge_block_id}), 200

    @app.route('/api/inbox/unresolve', methods=['POST'])
    def unresolve_inbox_item():
        """誤チェック時に知識の宝庫から戻す"""
        data = request.json or {}
        block_id = data.get('block_id')
        if not block_id:
            return jsonify({'error': 'block_id is required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, p.title AS page_title
            FROM blocks b
            JOIN pages p ON b.page_id = p.id
            WHERE b.id = ?
        ''', (block_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Block not found'}), 404

        page_title = row['page_title'] or ''
        if page_title != '🔖 あとで調べる':
            conn.close()
            return jsonify({'error': 'Only inbox items can be un-resolved'}), 400

        raw_props = row['props'] or '{}'
        try:
            props = json.loads(raw_props) if isinstance(raw_props, str) else dict(raw_props)
        except Exception:
            props = {}

        knowledge_block_id = props.get('knowledge_block_id')
        if knowledge_block_id:
            cursor.execute('DELETE FROM blocks WHERE id = ?', (knowledge_block_id,))

        for key in ['resolved_at', 'knowledge_block_id', 'resolution_note']:
            if key in props:
                props.pop(key, None)

        cursor.execute(
            'UPDATE blocks SET props = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (json.dumps(props, ensure_ascii=False), row['id'])
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 200

    @app.route('/api/finished', methods=['GET'])
    def get_finished():
        """'読了'ページを取得"""
        from database import get_or_create_finished
        finished = get_or_create_finished()
        return jsonify(finished if finished else {'error': 'Failed to create finished'}), 200 if finished else 500

    @app.route('/api/pages', methods=['GET'])
    def get_pages():
        # 3日以上前の日記ページを自動アーカイブ
        archive_old_diary_pages()

        conn = get_db()
        cursor = conn.cursor()
        # インデックスを活用して高速化
        cursor.execute('''
            SELECT * FROM pages
            WHERE is_deleted = 0
            ORDER BY parent_id, position
        ''')
        all_pages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # フロントエンドで階層構造を構築（DBクエリを削減）
        page_map = {page['id']: {**page, 'children': []} for page in all_pages}
        roots = []
        for page in all_pages:
            if page['parent_id'] and page['parent_id'] in page_map:
                page_map[page['parent_id']]['children'].append(page_map[page['id']])
            else:
                roots.append(page_map[page['id']])
        return jsonify(roots)

    @app.route('/api/trash', methods=['GET'])
    def get_trash():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pages WHERE is_deleted = 1 ORDER BY updated_at DESC')
        trash_pages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(trash_pages)

    def get_items_by_category(category_title, parent_id=None):
        """指定されたカテゴリーのページとブロックを取得する汎用関数"""
        conn = get_db()
        cursor = conn.cursor()

        # 1. 指定されたカテゴリーページをすべて見つける（例：食事、筋トレ）
        if parent_id is not None:
            cursor.execute('''
                SELECT * FROM pages
                WHERE title = ? AND is_deleted = 0 AND parent_id = ?
                ORDER BY updated_at DESC
            ''', (category_title, parent_id))
        else:
            cursor.execute('''
                SELECT * FROM pages
                WHERE title = ? AND is_deleted = 0
                ORDER BY updated_at DESC
            ''', (category_title,))
        category_pages = [dict(row) for row in cursor.fetchall()]
        
        result = []
        for category_page in category_pages:
            # 2. カテゴリーページ自体のブロックを取得
            cursor.execute('''
                SELECT * FROM blocks 
                WHERE page_id = ?
                ORDER BY position
            ''', (category_page['id'],))
            blocks = [dict(row) for row in cursor.fetchall()]
            
            # 3. 親ページ情報（日記ページなど）を取得
            parent_page = None
            if category_page['parent_id']:
                cursor.execute('SELECT * FROM pages WHERE id = ?', (category_page['parent_id'],))
                parent_row = cursor.fetchone()
                if parent_row:
                    parent_page = dict(parent_row)
            
            result.append({
                'page': category_page,
                'parent_page': parent_page,
                'blocks': blocks
            })
        
        conn.close()
        return result

    @app.route('/api/all-workouts', methods=['GET'])
    def get_all_workouts():
        """全ての日記から筋トレページとそのブロックを取得"""
        parent_id = request.args.get('parent_id', type=int)
        return jsonify(get_items_by_category('筋トレ', parent_id=parent_id))

    @app.route('/api/all-english-learning', methods=['GET'])
    def get_all_english_learning():
        """全ての日記から英語学習ページとそのブロックを取得"""
        parent_id = request.args.get('parent_id', type=int)
        return jsonify(get_items_by_category('英語学習', parent_id=parent_id))

    @app.route('/api/all-meals', methods=['GET'])
    def get_all_meals():
        """全ての日記から食事ページとそのブロックを取得"""
        parent_id = request.args.get('parent_id', type=int)
        return jsonify(get_items_by_category('食事', parent_id=parent_id))

    @app.route('/api/today-highlights/<int:page_id>', methods=['GET'])
    def get_today_highlights(page_id):
        """指定ページ内で今日作成されたブロックを取得"""
        conn = get_db()
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT * FROM blocks 
            WHERE page_id = ? AND DATE(created_at) = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (page_id, today))
        highlights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(highlights)

    @app.route('/api/pages', methods=['POST'])
    def create_page():
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        parent_id = data.get('parent_id')
        new_pos = get_next_position(cursor, parent_id)
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       (data.get('title', ''), data.get('icon', '📄'), parent_id, new_pos))
        page_id = cursor.lastrowid
        cursor.execute("INSERT INTO blocks (page_id, type, content, position) VALUES (?, 'text', '', ?)", (page_id, get_block_next_position(cursor, page_id)))
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        page = dict(cursor.fetchone())
        conn.close()
        return jsonify(page)

    @app.route('/api/folders', methods=['POST'])
    def create_folder():
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        parent_id = data.get('parent_id')
        new_pos = get_next_position(cursor, parent_id)
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       (data.get('title', '新しいフォルダ'), '📁', parent_id, new_pos))
        folder_id = cursor.lastrowid
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (folder_id,))
        folder = dict(cursor.fetchone())
        conn.close()
        return jsonify(folder)

    @app.route('/api/pages/from-template', methods=['POST'])
    def create_page_from_template():
        data = request.json
        template_type = data.get('template')
        
        conn = get_db()
        cursor = conn.cursor()
        
        templates = {
            'daily': {
                'title': f'{datetime.now().strftime("%Y年%m月%d日")}の記録',
                'icon': '📝',
                'blocks': [
                    {'type': 'h1', 'content': '体調'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '天気'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': 'やったこと'},
                    {'type': 'todo', 'content': ''},
                    {'type': 'h1', 'content': '振り返り'},
                    {'type': 'text', 'content': ''},
                ]
            },
            'reading': {
                'title': '読書メモ',
                'icon': '📚',
                'blocks': [
                    {'type': 'h1', 'content': '本のタイトル'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '著者'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '読んだ日'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '感想・メモ'},
                    {'type': 'text', 'content': ''},
                ]
            },
            'meeting': {
                'title': '会議メモ',
                'icon': '💼',
                'blocks': [
                    {'type': 'h1', 'content': '日時'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '参加者'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '議題'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '決定事項'},
                    {'type': 'todo', 'content': ''},
                ]
            },
            'english': {
                'title': f'{datetime.now().strftime("%Y年%m月%d日")}の英語進捗',
                'icon': '🌍',
                'blocks': [
                    {'type': 'h1', 'content': '今日の学習内容'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '新しい単語'},
                    {'type': 'todo', 'content': ''},
                    {'type': 'h1', 'content': '発音練習'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': 'リスニング時間'},
                    {'type': 'text', 'content': ''},
                    {'type': 'h1', 'content': '気づいたこと'},
                    {'type': 'text', 'content': ''},
                ]
            }
        }
        
        template = templates.get(template_type, templates['daily'])
        new_pos = get_next_position(cursor, None)
        
        cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                       (template['title'], template['icon'], None, new_pos))
        page_id = cursor.lastrowid
        
        for i, block in enumerate(template['blocks']):
            cursor.execute(
                "INSERT INTO blocks (page_id, type, content, checked, position, props) VALUES (?, ?, ?, ?, ?, ?)",
                (page_id, block['type'], block['content'], block.get('checked', 0), (i + 1) * 1000.0, '{}')
            )
        
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        page = dict(cursor.fetchone())
        conn.close()
        return jsonify(page)

    @app.route('/api/pages/from-date', methods=['POST'])
    def create_page_from_date():
        """指定日付のページを作成（存在しない場合は前日をコピー）
        category が指定された場合はその日付の子ページを返す"""
        data = request.json
        date_str = data.get('date')
        category = data.get('category')  # 例: "筋トレ"

        if not date_str:
            return jsonify({'error': 'Invalid date format'}), 400

        conn = get_db()
        cursor = conn.cursor()
        date_page = get_or_create_date_page(cursor, date_str)
        if not date_page:
            conn.close()
            return jsonify({'error': 'Invalid date format'}), 400

        if category:
            # カテゴリサブページを取得または作成
            category_icons = {'食事': '🍽️', '読書': '📚'}
            if category not in category_icons:
                conn.close()
                return jsonify({'error': 'Unsupported category'}), 400
            icon = category_icons.get(category, '📄')
            cursor.execute(
                'SELECT * FROM pages WHERE parent_id = ? AND title = ? AND is_deleted = 0 LIMIT 1',
                (date_page['id'], category)
            )
            sub_row = cursor.fetchone()
            if sub_row:
                page = dict(sub_row)
            else:
                cursor.execute(
                    'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, 1.0)',
                    (category, icon, date_page['id'])
                )
                new_id = cursor.lastrowid
                cursor.execute('SELECT * FROM pages WHERE id = ?', (new_id,))
                page = dict(cursor.fetchone())
        else:
            page = date_page

        conn.commit()
        conn.close()
        return jsonify(page)

    @app.route('/api/pages/<int:page_id>', methods=['GET'])
    def get_page(page_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        page_row = cursor.fetchone()
        if not page_row:
            conn.close()
            return jsonify({'error': 'Page not found'}), 404
        page = dict(page_row)
        
        # === 親ページ情報を内含めて高速化 ===
        if page.get('parent_id'):
            cursor.execute('SELECT id, title, icon FROM pages WHERE id = ?', (page['parent_id'],))
            parent_row = cursor.fetchone()
            if parent_row:
                page['parent_page'] = dict(parent_row)
        
        # インデックスを活用してブロック取得を高速化
        cursor.execute('''
            SELECT * FROM blocks 
            WHERE page_id = ? 
            ORDER BY position
        ''', (page_id,))
        page['blocks'] = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(page)

    @app.route('/api/pages/<int:page_id>', methods=['PUT'])
    def update_page(page_id):
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        updates = []
        values = []
        fields = ['title', 'icon', 'parent_id', 'cover_image', 'is_pinned', 'is_deleted', 'position']
        for field in fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(data[field])
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(page_id)
            cursor.execute(f'UPDATE pages SET {", ".join(updates)} WHERE id = ?', values)
            conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        page = dict(cursor.fetchone())
        conn.close()
        return jsonify(page)

    @app.route('/api/pages/<int:page_id>/toggle-pin', methods=['POST'])
    def toggle_pin(page_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT is_pinned FROM pages WHERE id = ?', (page_id,))
        row = cursor.fetchone()
        new_pinned = 0 if row[0] else 1
        cursor.execute('UPDATE pages SET is_pinned = ? WHERE id = ?', (new_pinned, page_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_pinned': new_pinned})

    @app.route('/api/pages/<int:page_id>/move-to-trash', methods=['POST'])
    def move_to_trash(page_id):
        conn = get_db()
        cursor = conn.cursor()
        mark_tree_deleted(cursor, page_id, is_deleted=True)
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    @app.route('/api/pages/<int:page_id>/restore', methods=['POST'])
    def restore_page(page_id):
        conn = get_db()
        cursor = conn.cursor()
        mark_tree_deleted(cursor, page_id, is_deleted=False)
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    @app.route('/api/pages/<int:page_id>/copy', methods=['POST'])
    def copy_page(page_id):
        """ページをコピー（ツリー構造ごと）"""
        data = request.json or {}
        parent_id = data.get('parent_id')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT title FROM pages WHERE id = ?', (page_id,))
        original = cursor.fetchone()
        new_title = (dict(original)['title'] if original else '無題') + 'のコピー'
        
        new_page_id = copy_page_tree(cursor, page_id, new_parent_id=parent_id, new_title=new_title)
        
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (new_page_id,))
        new_page = dict(cursor.fetchone())
        conn.close()
        
        return jsonify(new_page)

    @app.route('/api/pages/<int:page_id>', methods=['DELETE'])
    def delete_page(page_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        hard_delete_tree(cursor, page_id)
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    @app.route('/api/search', methods=['GET'])
    def search():
        query = request.args.get('q', '')
        if not query: return jsonify([])
        conn = get_db()
        cursor = conn.cursor()
        search_query = f"{query}*"
        try:
            sql = '''
                SELECT blocks.id as block_id, blocks.page_id, pages.title as page_title, pages.icon, blocks.content, 
                       snippet(blocks_fts, 0, '<b>', '</b>', '...', 10) as snippet,
                       pages.parent_id
                FROM blocks_fts
                JOIN blocks ON blocks_fts.rowid = blocks.id
                JOIN pages ON blocks.page_id = pages.id
                WHERE blocks_fts MATCH ?
                ORDER BY rank
                LIMIT 20
            '''
            cursor.execute(sql, (search_query,))
            results = [dict(row) for row in cursor.fetchall()]
            
            for result in results:
                breadcrumb = []
                current_id = result.get('parent_id')
                while current_id:
                    cursor.execute('SELECT id, title, icon, parent_id FROM pages WHERE id = ?', (current_id,))
                    parent_row = cursor.fetchone()
                    if parent_row:
                        parent_dict = dict(parent_row)
                        breadcrumb.insert(0, {
                            'id': parent_dict['id'],
                            'title': parent_dict['title'],
                            'icon': parent_dict['icon']
                        })
                        current_id = parent_dict['parent_id']
                    else:
                        break
                result['breadcrumb'] = breadcrumb
        except Exception as e:
            results = []
        conn.close()
        return jsonify(results)

    @app.route('/api/ai/query', methods=['POST'])
    def ai_query():
        data = request.json or {}
        query = (data.get('query') or '').strip()
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY is not set'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # 先に特定の質問（例: 筋トレした日）をDBから直接回答
        if any(key in query for key in ['いつ', '何日', '日付', '日にち']):
            activity_titles = ['筋トレ', '英語学習', '食事', '読書', '日記']
            matched_activity = next((t for t in activity_titles if t in query), None)
            if matched_activity:
                cursor.execute('''
                    SELECT p.id, p.parent_id, parent.title as parent_title
                    FROM pages p
                    JOIN pages parent ON parent.id = p.parent_id
                    WHERE p.title = ? AND p.is_deleted = 0 AND parent.is_deleted = 0
                ''', (matched_activity,))
                rows = cursor.fetchall()

                date_titles = []
                for row in rows:
                    parent_title = row['parent_title'] or ''
                    if not re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', parent_title):
                        continue
                    cursor.execute('''
                        SELECT 1 FROM blocks
                        WHERE page_id = ? AND (
                            (content IS NOT NULL AND TRIM(content) != '') OR
                            (details IS NOT NULL AND TRIM(details) != '') OR
                            checked = 1 OR
                            (props IS NOT NULL AND TRIM(props) NOT IN ('', '{}'))
                        )
                        LIMIT 1
                    ''', (row['id'],))
                    if cursor.fetchone():
                        date_titles.append(parent_title)

                def _date_key(title):
                    m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', title)
                    if not m:
                        return (9999, 99, 99)
                    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

                date_titles = sorted(set(date_titles), key=_date_key)
                if date_titles:
                    conn.close()
                    return jsonify({'answer': f"{matched_activity}した日: " + '、'.join(date_titles)})

            # 一般的な「いつ」質問はキーワードから日付を抽出
            q = re.sub(r'[?？]', '', query)
            for stop_word in ['いつ', '何日', '日付', '日にち', '何曜日', '教えて', 'って', 'したっけ', 'した', 'して', 'する', 'ですか', 'です']:
                q = q.replace(stop_word, ' ')
            for stop_word in ['は', 'を', 'に', 'で', 'の', 'が', 'と', 'へ', 'から', 'まで']:
                q = q.replace(stop_word, ' ')
            keywords = [t for t in re.split(r'\s+', q) if t]

            if keywords:
                date_titles = set()
                for keyword in keywords:
                    pattern = f"%{keyword}%"
                    cursor.execute('''
                        SELECT blocks.page_id, pages.title as page_title, pages.parent_id
                        FROM blocks
                        JOIN pages ON blocks.page_id = pages.id
                        WHERE blocks.content LIKE ?
                           OR blocks.details LIKE ?
                           OR blocks.props LIKE ?
                           OR pages.title LIKE ?
                        LIMIT 200
                    ''', (pattern, pattern, pattern, pattern))
                    rows = cursor.fetchall()
                    for row in rows:
                        page_title = row['page_title'] or ''
                        parent_id = row['parent_id']
                        if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', page_title):
                            date_titles.add(page_title)
                            continue
                        current_id = parent_id
                        while current_id:
                            cursor.execute('SELECT title, parent_id FROM pages WHERE id = ?', (current_id,))
                            parent_row = cursor.fetchone()
                            if not parent_row:
                                break
                            parent_title = parent_row['title'] or ''
                            if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', parent_title):
                                date_titles.add(parent_title)
                                break
                            current_id = parent_row['parent_id']

                if date_titles:
                    def _date_key(title):
                        m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$', title)
                        if not m:
                            return (9999, 99, 99)
                        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    sorted_dates = sorted(date_titles, key=_date_key)
                    conn.close()
                    return jsonify({'answer': '該当しそうな日: ' + '、'.join(sorted_dates)})
        results = []
        try:
            search_query = f"{query}*"
            sql = '''
                SELECT blocks.id as block_id, blocks.page_id, pages.title as page_title, pages.icon, blocks.content,
                       snippet(blocks_fts, 0, '<b>', '</b>', '...', 10) as snippet,
                       pages.parent_id
                FROM blocks_fts
                JOIN blocks ON blocks_fts.rowid = blocks.id
                JOIN pages ON blocks.page_id = pages.id
                WHERE blocks_fts MATCH ?
                ORDER BY rank
                LIMIT 30
            '''
            cursor.execute(sql, (search_query,))
            results = [dict(row) for row in cursor.fetchall()]
        except Exception:
            results = []

        if not results:
            terms = [t for t in re.split(r'\s+', query) if t]
            like_terms = terms if terms else [query]
            like_sql = '''
                SELECT blocks.id as block_id, blocks.page_id, pages.title as page_title, pages.icon, blocks.content,
                       '' as snippet,
                       pages.parent_id
                FROM blocks
                JOIN pages ON blocks.page_id = pages.id
                WHERE blocks.content LIKE ? OR pages.title LIKE ?
                ORDER BY pages.updated_at DESC
                LIMIT 50
            '''
            combined = []
            for term in like_terms:
                pattern = f"%{term}%"
                cursor.execute(like_sql, (pattern, pattern))
                combined.extend([dict(row) for row in cursor.fetchall()])
            seen = set()
            results = []
            for row in combined:
                key = row.get('block_id') or row.get('page_id')
                if key in seen:
                    continue
                seen.add(key)
                results.append(row)

        page_candidates = []
        if len(results) < 5:
            terms = [t for t in re.split(r'\s+', query) if t]
            like_terms = terms if terms else [query]
            for term in like_terms[:5]:
                pattern = f"%{term}%"
                cursor.execute('''
                    SELECT id, title, icon, parent_id
                    FROM pages
                    WHERE is_deleted = 0 AND title LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT 10
                ''', (pattern,))
                page_candidates.extend([dict(row) for row in cursor.fetchall()])

        for result in results:
            breadcrumb = []
            current_id = result.get('parent_id')
            while current_id:
                cursor.execute('SELECT id, title, icon, parent_id FROM pages WHERE id = ?', (current_id,))
                parent_row = cursor.fetchone()
                if parent_row:
                    parent_dict = dict(parent_row)
                    breadcrumb.insert(0, {
                        'id': parent_dict['id'],
                        'title': parent_dict['title'],
                        'icon': parent_dict['icon']
                    })
                    current_id = parent_dict['parent_id']
                else:
                    break
            result['breadcrumb'] = breadcrumb

        if not results:
            conn.close()
            return jsonify({'answer': '見つかりませんでした。'}), 200

        max_context_len = 12000
        context_lines = []

        def _append_line(line):
            current = '\n'.join(context_lines)
            if len(current) + len(line) + 1 > max_context_len:
                return False
            context_lines.append(line)
            return True

        _append_line('検索候補:')
        for result in results:
            breadcrumb_text = ' / '.join([f"{b['icon']} {b['title']}" for b in result.get('breadcrumb', [])])
            page_title = result.get('page_title') or ''
            snippet = result.get('snippet') or result.get('content') or ''
            snippet = re.sub(r'<[^>]+>', '', snippet)
            if result.get('content'):
                snippet = (result.get('content') or '')[:400]
            if breadcrumb_text:
                location = f"{breadcrumb_text} / {page_title}"
            else:
                location = page_title
            if not _append_line(f"- {location}: {snippet}"):
                break

        page_ids = []
        page_seen = set()
        for result in results:
            page_id = result.get('page_id')
            if page_id and page_id not in page_seen:
                page_seen.add(page_id)
                page_ids.append(page_id)
        for page in page_candidates:
            page_id = page.get('id')
            if page_id and page_id not in page_seen:
                page_seen.add(page_id)
                page_ids.append(page_id)

        if page_ids:
            _append_line('')
            _append_line('関連ページ:')
        for page_id in page_ids[:12]:
            cursor.execute('SELECT id, title, icon, parent_id FROM pages WHERE id = ?', (page_id,))
            page_row = cursor.fetchone()
            if not page_row:
                continue
            page = dict(page_row)
            breadcrumb = []
            current_id = page.get('parent_id')
            while current_id:
                cursor.execute('SELECT id, title, icon, parent_id FROM pages WHERE id = ?', (current_id,))
                parent_row = cursor.fetchone()
                if parent_row:
                    parent_dict = dict(parent_row)
                    breadcrumb.insert(0, f"{parent_dict['icon']} {parent_dict['title']}")
                    current_id = parent_dict['parent_id']
                else:
                    break
            breadcrumb_text = ' / '.join(breadcrumb)
            header = f"- {page.get('icon', '')} {page.get('title', '')}"
            if breadcrumb_text:
                header = f"{header} ({breadcrumb_text})"
            if not _append_line(header):
                break

            cursor.execute('''
                SELECT type, content, details
                FROM blocks
                WHERE page_id = ?
                ORDER BY position
                LIMIT 25
            ''', (page_id,))
            blocks = [dict(row) for row in cursor.fetchall()]
            for block in blocks:
                content = (block.get('content') or '').strip()
                details = (block.get('details') or '').strip()
                if not content and not details:
                    continue
                line = content if content else ''
                if details:
                    line = f"{line} / 詳細: {details}" if line else f"詳細: {details}"
                line = re.sub(r'\s+', ' ', line)
                line = line[:300]
                if not _append_line(f"  - {line}"):
                    break

        context = '\n'.join(context_lines)[:max_context_len]
        conn.close()
        system_prompt = (
            'あなたは日記アプリの検索アシスタントです。'
            '与えられたノートの情報だけを根拠に、簡潔に答えてください。'
            '不明な点は推測せず「見つかりませんでした。」と答えてください。'
            '可能なら日付やページ名を明記し、最後に「根拠:」の後に関連ページ名を列挙してください。'
        )
        user_prompt = f"質問: {query}\n\nノート:\n{context}"

        payload = {
            'model': 'gpt-4o',
            'input': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.2
        }

        try:
            req = urllib.request.Request(
                'https://api.openai.com/v1/responses',
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
            answer = resp_data.get('output_text')
            if not answer:
                parts = []
                for item in resp_data.get('output', []):
                    if item.get('type') == 'message':
                        for content in item.get('content', []):
                            if content.get('type') == 'output_text':
                                parts.append(content.get('text', ''))
                answer = '\n'.join([p for p in parts if p]).strip()
            if not answer:
                answer = '見つかりませんでした。'
        except urllib.error.HTTPError as e:
            return jsonify({'error': f'OpenAI API error: {e.code}'}), 502
        except Exception:
            return jsonify({'error': 'OpenAI API request failed'}), 502

        return jsonify({'answer': answer})

    @app.route('/api/ai/chat', methods=['POST'])
    def ai_chat():
        data = request.json or {}
        messages = data.get('messages') or []
        if not isinstance(messages, list) or not messages:
            return jsonify({'error': 'Messages are required'}), 400

        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key:
            return jsonify({'error': 'OPENAI_API_KEY is not set'}), 400

        # 直近ユーザー発話から簡易コンテキストを取得
        last_user = None
        for msg in reversed(messages):
            if msg.get('role') == 'user' and msg.get('content'):
                last_user = msg.get('content')
                break

        context_text = ''
        if last_user:
            conn = get_db()
            cursor = conn.cursor()
            results = []
            try:
                search_query = f"{last_user}*"
                sql = '''
                    SELECT blocks.id as block_id, blocks.page_id, pages.title as page_title, pages.icon, blocks.content,
                           snippet(blocks_fts, 0, '<b>', '</b>', '...', 10) as snippet,
                           pages.parent_id
                    FROM blocks_fts
                    JOIN blocks ON blocks_fts.rowid = blocks.id
                    JOIN pages ON blocks.page_id = pages.id
                    WHERE blocks_fts MATCH ?
                    ORDER BY rank
                    LIMIT 15
                '''
                cursor.execute(sql, (search_query,))
                results = [dict(row) for row in cursor.fetchall()]
            except Exception:
                results = []

            if not results:
                terms = [t for t in re.split(r'\s+', last_user) if t]
                like_sql = '''
                    SELECT blocks.id as block_id, blocks.page_id, pages.title as page_title, pages.icon, blocks.content,
                           '' as snippet,
                           pages.parent_id
                    FROM blocks
                    JOIN pages ON blocks.page_id = pages.id
                    WHERE blocks.content LIKE ? OR pages.title LIKE ?
                    ORDER BY pages.updated_at DESC
                    LIMIT 20
                '''
                combined = []
                for term in terms[:5]:
                    pattern = f"%{term}%"
                    cursor.execute(like_sql, (pattern, pattern))
                    combined.extend([dict(row) for row in cursor.fetchall()])
                seen = set()
                results = []
                for row in combined:
                    key = row.get('block_id') or row.get('page_id')
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(row)

            context_lines = []
            for result in results:
                breadcrumb = []
                current_id = result.get('parent_id')
                while current_id:
                    cursor.execute('SELECT id, title, icon, parent_id FROM pages WHERE id = ?', (current_id,))
                    parent_row = cursor.fetchone()
                    if parent_row:
                        parent_dict = dict(parent_row)
                        breadcrumb.insert(0, {
                            'id': parent_dict['id'],
                            'title': parent_dict['title'],
                            'icon': parent_dict['icon']
                        })
                        current_id = parent_dict['parent_id']
                    else:
                        break
                breadcrumb_text = ' / '.join([f"{b['icon']} {b['title']}" for b in breadcrumb])
                page_title = result.get('page_title') or ''
                snippet = result.get('snippet') or result.get('content') or ''
                snippet = re.sub(r'<[^>]+>', '', snippet)
                if result.get('content'):
                    snippet = (result.get('content') or '')[:400]
                location = f"{breadcrumb_text} / {page_title}" if breadcrumb_text else page_title
                context_lines.append(f"- {location}: {snippet}")

            context_text = '\n'.join(context_lines)[:8000]
            conn.close()

        system_prompt = (
            'あなたは日記アプリのAIアシスタントです。'
            '会話に自然に答えてください。'
            'ノート文脈が与えられた場合はそれを優先して根拠にしてください。'
            '根拠がない内容は断定しないでください。'
        )

        input_messages = [{'role': 'system', 'content': system_prompt}]
        if context_text:
            input_messages.append({'role': 'system', 'content': f"ノート文脈:\n{context_text}"})

        trimmed = messages[-12:]
        input_messages.extend(trimmed)

        payload = {
            'model': 'gpt-4o',
            'input': input_messages,
            'temperature': 0.7
        }

        try:
            req = urllib.request.Request(
                'https://api.openai.com/v1/responses',
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
            answer = resp_data.get('output_text')
            if not answer:
                parts = []
                for item in resp_data.get('output', []):
                    if item.get('type') == 'message':
                        for content in item.get('content', []):
                            if content.get('type') == 'output_text':
                                parts.append(content.get('text', ''))
                answer = '\n'.join([p for p in parts if p]).strip()
            if not answer:
                answer = '回答を生成できませんでした。'
        except urllib.error.HTTPError as e:
            return jsonify({'error': f'OpenAI API error: {e.code}'}), 502
        except Exception:
            return jsonify({'error': 'OpenAI API request failed'}), 502

        return jsonify({'answer': answer})

    @app.route('/api/healthplanet/auth', methods=['GET'])
    def healthplanet_auth():
        client_id, _, redirect_uri, scope = _get_healthplanet_config()
        if not client_id or not redirect_uri:
            return jsonify({'error': 'HEALTHPLANET_CLIENT_ID/REDIRECT_URI is not set'}), 400
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'response_type': 'code'
        }
        url = 'https://www.healthplanet.jp/oauth/auth?' + urllib.parse.urlencode(params)
        return redirect(url)

    @app.route('/api/healthplanet/callback', methods=['GET'])
    def healthplanet_callback():
        code = request.args.get('code', '')
        if not code:
            return '認可に失敗しました。', 400

        client_id, client_secret, redirect_uri, scope = _get_healthplanet_config()
        if not client_id or not client_secret or not redirect_uri:
            return '設定が不足しています。', 400

        payload = urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'code': code,
            'grant_type': 'authorization_code'
        }).encode('utf-8')

        try:
            req = urllib.request.Request(
                'https://www.healthplanet.jp/oauth/token',
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with _healthplanet_urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
            token_data = _parse_healthplanet_token_response(raw)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode('utf-8')
            except Exception:
                body = ''
            detail = f'{e.code} {body}'.strip()
            return f'トークン取得に失敗しました: {detail}', 502
        except Exception as e:
            return f'トークン取得に失敗しました。{type(e).__name__}', 502

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        expires_at = None
        if expires_in:
            try:
                expires_at = (datetime.utcnow() + timedelta(seconds=int(expires_in))).isoformat()
            except Exception:
                expires_at = None

        if not access_token:
            return 'トークンが取得できませんでした。', 502

        save_healthplanet_token(access_token, refresh_token, expires_at, scope)
        return 'HealthPlanetの連携が完了しました。'

    @app.route('/api/healthplanet/status', methods=['GET'])
    def healthplanet_status():
        """Health Planet の連携状況を確認"""
        token_row = get_healthplanet_token()
        if not token_row:
            return jsonify({'connected': False}), 200
        
        # トークンの有効期限を確認
        expires_at = token_row['expires_at']
        is_expired = False
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    is_expired = True
            except Exception:
                pass
        
        return jsonify({
            'connected': True,
            'expires_at': expires_at,
            'is_expired': is_expired
        }), 200

    @app.route('/api/healthplanet/disconnect', methods=['POST'])
    def healthplanet_disconnect():
        """Health Planet の連携を解除"""
        try:
            clear_healthplanet_token()
            return jsonify({'message': '連携を解除しました'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/healthplanet/sync', methods=['GET', 'POST'])
    def healthplanet_sync():
        # POSTパラメータまたはGETパラメータから日付を取得
        if request.method == 'POST':
            data = request.json or {}
            target_date = data.get('date')
            days = data.get('days')
        else:
            target_date = request.args.get('date')
            days = request.args.get('days')
        
        ok, message = sync_healthplanet_for_date(target_date, days=days)
        status = 200 if ok else 400
        return jsonify({'message': message}), status

    @app.route('/api/healthplanet/latest-weight', methods=['GET'])
    def healthplanet_latest_weight():
        """Health Planet から最新の体重データを取得"""
        token_row = get_healthplanet_token()
        if not token_row:
            return jsonify({'error': 'HealthPlanetが未連携です。先にフロー著してください'}), 400
        
        access_token = token_row['access_token']
        expires_at = token_row['expires_at']
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    return jsonify({'error': 'トークン期限切れです。再度認可してください'}), 400
            except Exception:
                pass
        
        jst_now = datetime.utcnow() + timedelta(hours=9)
        range_start = (jst_now - timedelta(days=30)).strftime('%Y%m%d%H%M%S')
        to_str = jst_now.strftime('%Y%m%d%H%M%S')
        
        try:
            all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
            data = _fetch_healthplanet_innerscan(access_token, range_start, to_str, all_tags)
        except Exception as e:
            error_msg = str(e)
            if 'Expecting value' in error_msg or 'JSON' in error_msg:
                return jsonify({
                    'error': 'Health Planet API からエラーが返されました。トークンが無効の可能性があります。再度認可をお試しください',
                    'detail': error_msg
                }), 400
            return jsonify({'error': f'データ取得失敗: {error_msg}'}), 400
        
        if not isinstance(data, dict) or 'data' not in data:
            return jsonify({
                'error': 'Health Planet から無効なレスポンスが返されました',
                'detail': str(data)[:200]
            }), 400
        
        weight = None
        weight_date = None
        for entry in data.get('data', []):
            tag = str(entry.get('tag', ''))
            keydata = entry.get('keydata', '')
            if tag == '6021' and keydata:
                try:
                    weight = float(keydata)
                    weight_date = entry.get('date', '')
                    break
                except (ValueError, TypeError):
                    continue
        
        if weight is None:
            return jsonify({'error': 'この 30 日間に体重データが見つかりません。Health Planet デバイスで計測してください'}), 404
        
        return jsonify({
            'weight': weight,
            'date': weight_date,
            'timestamp': datetime.utcnow().isoformat()
        }), 200

    @app.route('/api/healthplanet/body-age/<date>', methods=['GET'])
    def healthplanet_body_age(date):
        """指定日付の体内年齢をHealth Planetから取得"""
        try:
            # 日付形式の確認
            try:
                target_dt = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': '日付形式が正しくありません（YYYY-MM-DD）'}), 400
            
            token_row = get_healthplanet_token()
            if not token_row:
                return jsonify({'error': 'HealthPlanetが未連携です'}), 400
            
            access_token = token_row['access_token']
            expires_at = token_row['expires_at']
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) < datetime.utcnow():
                        return jsonify({'error': 'トークン期限切れです'}), 400
                except Exception:
                    pass
            
            # その日の開始〜終了時刻で検索
            start_time = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            from_str = start_time.strftime('%Y%m%d%H%M%S')
            to_str = end_time.strftime('%Y%m%d%H%M%S')
            
            try:
                all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
                hp_data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, all_tags)
            except Exception as e:
                error_msg = str(e)
                if 'Expecting value' in error_msg or 'JSON' in error_msg:
                    return jsonify({'error': 'Health Planet から有効なデータを取得できません'}), 400
                return jsonify({'error': f'取得失敗: {error_msg}'}), 400
            
            if not isinstance(hp_data, dict) or 'data' not in hp_data:
                return jsonify({'error': '無効なレスポンス形式です'}), 400
            
            body_age = None
            body_age_date = None
            for entry in hp_data.get('data', []):
                tag = str(entry.get('tag', ''))
                keydata = entry.get('keydata', '')
                if tag == '6028' and keydata:
                    try:
                        body_age = int(float(keydata))
                        body_age_date = entry.get('date', date)
                        break
                    except (ValueError, TypeError):
                        continue
            
            if body_age is None:
                return jsonify({
                    'found': False,
                    'date': date,
                    'message': f'{date} に体内年齢データが見つかりません'
                }), 404
            
            return jsonify({
                'body_age': body_age,
                'date': date,
                'data_date': body_age_date,
                'found': True,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/healthplanet/body-weight/<date>', methods=['GET'])
    def healthplanet_body_weight(date):
        """指定日付の体重をHealth Planetから取得"""
        try:
            # 日付形式の確認
            try:
                target_dt = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': '日付形式が正しくありません（YYYY-MM-DD）'}), 400
            
            token_row = get_healthplanet_token()
            if not token_row:
                return jsonify({'error': 'HealthPlanetが未連携です'}), 400
            
            access_token = token_row['access_token']
            expires_at = token_row['expires_at']
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) < datetime.utcnow():
                        return jsonify({'error': 'トークン期限切れです'}), 400
                except Exception:
                    pass
            
            # その日の開始〜終了時刻で検索
            start_time = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            from_str = start_time.strftime('%Y%m%d%H%M%S')
            to_str = end_time.strftime('%Y%m%d%H%M%S')
            
            try:
                all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
                hp_data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, all_tags)
            except Exception as e:
                error_msg = str(e)
                if 'Expecting value' in error_msg or 'JSON' in error_msg:
                    return jsonify({'error': 'Health Planet から有効なデータを取得できません'}), 400
                return jsonify({'error': f'取得失敗: {error_msg}'}), 400
            
            if not isinstance(hp_data, dict) or 'data' not in hp_data:
                return jsonify({'error': '無効なレスポンス形式です'}), 400
            
            weight = None
            weight_date = None
            for entry in hp_data.get('data', []):
                tag = str(entry.get('tag', ''))
                keydata = entry.get('keydata', '')
                if tag == '6021' and keydata:
                    try:
                        weight = float(keydata)
                        weight_date = entry.get('date', date)
                        break
                    except (ValueError, TypeError):
                        continue
            
            if weight is None:
                return jsonify({
                    'found': False,
                    'date': date,
                    'message': f'{date} に体重データが見つかりません'
                }), 404
            
            return jsonify({
                'weight': weight,
                'date': date,
                'data_date': weight_date,
                'found': True,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pages/<int:page_id>/weight', methods=['GET'])
    def get_page_weight(page_id):
        """ページの体重データを取得"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT weight, body_fat, weight_at FROM pages WHERE id = ?', (page_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return jsonify({'error': 'Page not found'}), 404

            return jsonify({
                'weight': row['weight'],
                'body_fat': row['body_fat'],
                'weight_at': row['weight_at']
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pages/<int:page_id>/weight', methods=['PUT'])
    def update_page_weight(page_id):
        """ページの体重データを更新（手動入力または Health Planet から取得）"""
        try:
            data = request.json or {}
            weight = data.get('weight')
            
            if weight is not None:
                try:
                    weight = float(weight)
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid weight value'}), 400
            
            conn = get_db()
            cursor = conn.cursor()
            
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE pages SET weight = ?, weight_at = ? WHERE id = ?',
                (weight, now, page_id)
            )
            conn.commit()
            
            cursor.execute('SELECT weight, weight_at FROM pages WHERE id = ?', (page_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return jsonify({'error': 'Page not found'}), 404
            
            return jsonify({
                'weight': row['weight'],
                'weight_at': row['weight_at']
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pages/<int:page_id>/sync-weight-from-health-planet', methods=['POST'])
    def sync_weight_from_health_planet(page_id):
        """Health Planet から最新の体重をこのページに同期"""
        try:
            # 任意の日付か、今日のデータか
            data = request.json or {}
            target_date = data.get('date')  # YYYY-MM-DD 形式、省略時は今日
            
            if target_date:
                # 指定日付のデータを取得
                try:
                    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                except ValueError:
                    return jsonify({'error': '日付形式が正しくありません（YYYY-MM-DD）'}), 400
            else:
                target_dt = datetime.utcnow() + timedelta(hours=9)
                target_date = target_dt.strftime('%Y-%m-%d')
            
            # その日の開始〜終了時刻で検索
            start_time = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            from_str = start_time.strftime('%Y%m%d%H%M%S')
            to_str = end_time.strftime('%Y%m%d%H%M%S')
            
            token_row = get_healthplanet_token()
            if not token_row:
                return jsonify({'error': 'HealthPlanetが未連携です'}), 400
            
            access_token = token_row['access_token']
            
            try:
                all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
                hp_data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, all_tags)
            except Exception as e:
                error_msg = str(e)
                if 'Expecting value' in error_msg or 'JSON' in error_msg:
                    return jsonify({
                        'error': 'Health Planet から有効なデータを取得できません',
                        'detail': '再度認可をお試しください'
                    }), 400
                return jsonify({'error': f'取得失敗: {error_msg}'}), 400
            
            if not isinstance(hp_data, dict) or 'data' not in hp_data:
                return jsonify({'error': '無効なレスポンス形式です'}), 400
            
            weight = None
            body_fat = None
            for entry in hp_data.get('data', []):
                tag = str(entry.get('tag', ''))
                keydata = entry.get('keydata', '')
                if tag == '6021' and keydata and weight is None:
                    try:
                        weight = float(keydata)
                    except (ValueError, TypeError):
                        pass
                elif tag == '6022' and keydata and body_fat is None:
                    try:
                        body_fat = float(keydata)
                    except (ValueError, TypeError):
                        pass

            if weight is None:
                return jsonify({
                    'error': f'{target_date} に体重データが見つかりません',
                    'detail': 'この日付の計測記録がない可能性があります'
                }), 404

            # ページに保存
            conn = get_db()
            cursor = conn.cursor()

            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE pages SET weight = ?, body_fat = ?, weight_at = ? WHERE id = ?',
                (weight, body_fat, now, page_id)
            )
            conn.commit()

            cursor.execute('SELECT weight, body_fat, weight_at FROM pages WHERE id = ?', (page_id,))
            row = cursor.fetchone()
            conn.close()

            return jsonify({
                'success': True,
                'weight': row['weight'],
                'weight_at': row['weight_at'],
                'date': target_date,
                'message': f'{target_date} の {weight}kg を同期しました'
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pages/<int:page_id>/get-weight-for-date', methods=['GET'])
    def get_weight_for_date(page_id):
        """指定日付の Health Planet データを取得（ページに保存せず）"""
        try:
            target_date = request.args.get('date')  # YYYY-MM-DD
            if not target_date:
                return jsonify({'error': '日付を指定してください'}), 400
            
            try:
                target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': '日付形式が正しくありません'}), 400
            
            token_row = get_healthplanet_token()
            if not token_row:
                return jsonify({'error': 'HealthPlanetが未連携です'}), 400
            
            access_token = token_row['access_token']
            
            start_time = target_dt.replace(hour=0, minute=0, second=0)
            end_time = target_dt.replace(hour=23, minute=59, second=59)
            from_str = start_time.strftime('%Y%m%d%H%M%S')
            to_str = end_time.strftime('%Y%m%d%H%M%S')
            
            try:
                all_tags = ['6021', '6022', '6023', '6024', '6025', '6026', '6027', '6028', '6029']
                hp_data = _fetch_healthplanet_innerscan(access_token, from_str, to_str, all_tags)
            except Exception as e:
                return jsonify({'error': f'取得失敗: {str(e)}'}), 400
            
            if not isinstance(hp_data, dict):
                return jsonify({'error': '無効なレスポンス'}), 400
            
            weight = None
            for entry in hp_data.get('data', []):
                tag = str(entry.get('tag', ''))
                keydata = entry.get('keydata', '')
                if tag == '6021' and keydata:
                    try:
                        weight = float(keydata)
                        break
                    except (ValueError, TypeError):
                        continue
            
            return jsonify({
                'date': target_date,
                'weight': weight,
                'found': weight is not None
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pages/<int:page_id>/blocks', methods=['POST'])
    def create_block(page_id):
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        if data.get('position') is not None:
            new_pos = float(data.get('position'))
        else:
            new_pos = get_block_next_position(cursor, page_id)
        cursor.execute('INSERT INTO blocks (page_id, type, content, checked, position, props) VALUES (?, ?, ?, ?, ?, ?)',
                       (page_id, data.get('type', 'text'), data.get('content', ''), data.get('checked', False), new_pos, data.get('props', '{}')))
        block_id = cursor.lastrowid
        conn.commit()
        cursor.execute('SELECT * FROM blocks WHERE id = ?', (block_id,))
        block = dict(cursor.fetchone())
        conn.close()
        return jsonify(block)

    @app.route('/api/blocks/<int:block_id>', methods=['PUT'])
    def update_block(block_id):
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        updates = []
        values = []
        fields = ['type', 'content', 'checked', 'position', 'collapsed', 'details', 'props']
        for field in fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(data[field])
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(block_id)
            cursor.execute(f'UPDATE blocks SET {", ".join(updates)} WHERE id = ?', values)
            conn.commit()
        cursor.execute('SELECT * FROM blocks WHERE id = ?', (block_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Block not found'}), 404
        block = dict(row)
        conn.close()
        
        import time
        current_time = time.time()
        last_backup_time = getattr(update_block, '_last_backup', 0)
        if current_time - last_backup_time > 300:
            backup_database_to_json()
            update_block._last_backup = current_time
        
        return jsonify(block)

    @app.route('/api/pages/<int:page_id>/mood', methods=['PUT'])
    def update_page_mood(page_id):
        """ページの感情（ムード）を更新"""
        try:
            data = request.json
            mood = data.get('mood', 0)
            
            if not (0 <= mood <= 5):
                return jsonify({'error': 'Mood must be between 0 and 5'}), 400
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE pages SET mood = ? WHERE id = ?', (mood, page_id))
            conn.commit()
            
            cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
            page = dict(cursor.fetchone()) if cursor.fetchone() else None
            conn.close()
            
            if page:
                return jsonify({'success': True, 'mood': mood})
            else:
                return jsonify({'error': 'Page not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/pages/<int:page_id>/gratitude', methods=['PUT'])
    def update_page_gratitude(page_id):
        """ページの感謝日記を更新"""
        try:
            data = request.json
            gratitude_text = data.get('gratitude_text', '')
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE pages SET gratitude_text = ? WHERE id = ?', (gratitude_text, page_id))
            conn.commit()
            
            cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
            page = dict(cursor.fetchone()) if cursor.fetchone() else None
            conn.close()
            
            if page:
                return jsonify({'success': True, 'gratitude_text': gratitude_text})
            else:
                return jsonify({'error': 'Page not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/blocks/<int:block_id>', methods=['DELETE'])
    def delete_block(block_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM blocks WHERE id = ?', (block_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    @app.route('/api/calc-calories', methods=['POST'])
    def calc_calories():
        """メニュー文字列から概算カロリーを返す"""
        data = request.json or {}
        items = data.get('items')
        if isinstance(items, list):
            result = estimate_calories_items(items)
        else:
            raw_lines = data.get('lines', data.get('text', ''))
            if isinstance(raw_lines, list):
                lines = raw_lines
            else:
                lines = str(raw_lines).splitlines()
            result = estimate_calories(lines)
        return jsonify(result)

    @app.route('/api/books/reading-delta', methods=['POST'])
    def reading_delta():
        """前日との差分読書ページ数を取得"""
        data = request.json or {}
        current_page_id = data.get('current_page_id')
        title = (data.get('title') or '').strip()
        current_page = data.get('current_page')

        if not current_page_id or not title:
            return jsonify({'prev_page': None, 'delta': None})

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT id, title, parent_id FROM pages WHERE id = ?', (current_page_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'prev_page': None, 'delta': None})

        page = dict(row)
        date_title = page.get('title') or ''
        date_page_id = page['id']

        if not re.match(r'\d{4}年\d{1,2}月\d{1,2}日', date_title):
            if page.get('parent_id'):
                cursor.execute('SELECT id, title FROM pages WHERE id = ?', (page['parent_id'],))
                parent = cursor.fetchone()
                if parent:
                    date_page_id = parent['id']
                    date_title = parent['title'] or ''

        match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_title)
        if not match:
            conn.close()
            return jsonify({'prev_page': None, 'delta': None})

        year, month, day = map(int, match.groups())
        prev_date = datetime(year, month, day) - timedelta(days=1)
        prev_title = f"{prev_date.year}年{prev_date.month}月{prev_date.day}日"

        cursor.execute('SELECT id FROM pages WHERE title = ? AND is_deleted = 0 LIMIT 1', (prev_title,))
        prev_date_row = cursor.fetchone()
        if not prev_date_row:
            conn.close()
            return jsonify({'prev_page': None, 'delta': None})

        target_page_id = prev_date_row['id']
        if page.get('parent_id') and page.get('parent_id') != target_page_id:
            cursor.execute(
                'SELECT id FROM pages WHERE parent_id = ? AND title = ? AND is_deleted = 0 ORDER BY position LIMIT 1',
                (target_page_id, page.get('title'))
            )
            child = cursor.fetchone()
            if not child:
                conn.close()
                return jsonify({'prev_page': None, 'delta': None})
            target_page_id = child['id']

        cursor.execute(
            'SELECT props FROM blocks WHERE page_id = ? AND type = ? AND props IS NOT NULL',
            (target_page_id, 'book')
        )
        prev_value = None
        for block_row in cursor.fetchall():
            try:
                props = json.loads(block_row['props'] or '{}')
            except Exception:
                props = {}
            if (props.get('title') or '').strip() == title:
                prev_value = props.get('currentPage')
                break

        conn.close()
        if prev_value is None:
            return jsonify({'prev_page': None, 'delta': None})

        delta = None
        if current_page is not None:
            try:
                delta = int(current_page) - int(prev_value)
            except Exception:
                delta = None

        return jsonify({'prev_page': prev_value, 'delta': delta})

    @app.route('/api/upload', methods=['POST'])
    def upload_file():
        if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        page_id = request.form.get('page_id')
        is_cover = request.form.get('is_cover') == 'true'
        if file.filename == '' or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400
        filename = secure_filename(file.filename)
        import uuid
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
        file_url = f'/uploads/{unique_filename}'
        conn = get_db()
        cursor = conn.cursor()
        if is_cover and page_id:
            cursor.execute('UPDATE pages SET cover_image = ? WHERE id = ?', (file_url, page_id))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'file_url': file_url, 'type': 'cover'})
        elif page_id:
            cursor.execute('SELECT MAX(position) FROM blocks WHERE page_id = ?', (page_id,))
            new_pos = (cursor.fetchone()[0] or -1) + 1
            block_type = 'image' if filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'} else 'file'
            cursor.execute('INSERT INTO blocks (page_id, type, content, position) VALUES (?, ?, ?, ?)',
                           (page_id, block_type, file_url, new_pos))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'file_url': file_url, 'block_type': block_type})
        return jsonify({'error': 'Page ID missing'}), 400

    @app.route('/api/export/all/json', methods=['GET'])
    def export_all_json():
        """全ページをJSON形式でエクスポート"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pages WHERE is_deleted = 0 AND parent_id IS NULL ORDER BY position')
        root_pages = [export_page_to_dict(cursor, row['id']) for row in cursor.fetchall()]
        conn.close()
        
        export_data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'pages': root_pages
        }
        
        response = send_file(
            io.BytesIO(json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=f"diary_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        return response

    @app.route('/api/export/pages/<int:page_id>/json', methods=['GET'])
    def export_page_json(page_id):
        """指定ページをJSON形式でエクスポート"""
        conn = get_db()
        cursor = conn.cursor()
        page = export_page_to_dict(cursor, page_id)
        conn.close()
        
        if not page:
            return jsonify({'error': 'Page not found'}), 404
        
        export_data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'page': page
        }
        
        response = send_file(
            io.BytesIO(json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=f"{page.get('title', 'page')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        return response

    @app.route('/api/export/pages/<int:page_id>/markdown', methods=['GET'])
    def export_page_markdown(page_id):
        """指定ページをMarkdown形式でエクスポート"""
        conn = get_db()
        cursor = conn.cursor()
        page = export_page_to_dict(cursor, page_id)
        conn.close()
        
        if not page:
            return jsonify({'error': 'Page not found'}), 404
        
        markdown_content = page_to_markdown(page, level=1)
        
        response = send_file(
            io.BytesIO(markdown_content.encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=f"{page.get('title', 'page')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        return response

    @app.route('/api/export/pages/<int:page_id>/zip', methods=['GET'])
    def export_page_zip(page_id):
        """指定ページを添付ファイル含めZIP化してエクスポート"""
        conn = get_db()
        cursor = conn.cursor()
        page = export_page_to_dict(cursor, page_id)
        conn.close()
        
        if not page:
            return jsonify({'error': 'Page not found'}), 404
        
        zip_buffer = io.BytesIO()
        
        def add_page_to_zip(z, pg, prefix=''):
            """ページとその子ページを再帰的にZIPに追加"""
            page_dir = f"{prefix}{pg.get('title', '無題')}_[{pg['id']}]"
            
            md_content = page_to_markdown(pg, level=1)
            z.writestr(f"{page_dir}/page.md", md_content.encode('utf-8'))
            
            metadata = {
                'id': pg['id'],
                'title': pg.get('title', ''),
                'icon': pg.get('icon', ''),
                'created_at': pg.get('created_at', ''),
                'updated_at': pg.get('updated_at', '')
            }
            z.writestr(f"{page_dir}/metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'))
            
            for block in pg.get('blocks', []):
                if block.get('type') in ['image', 'file']:
                    file_path = block.get('content', '')
                    if file_path and file_path.startswith('/uploads/'):
                        filename = file_path.split('/')[-1]
                        full_path = os.path.join(UPLOAD_FOLDER, filename)
                        if os.path.exists(full_path):
                            z.write(full_path, f"{page_dir}/files/{filename}")
            
            for child in pg.get('children', []):
                add_page_to_zip(z, child, f"{page_dir}/")
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            add_page_to_zip(zf, page)
        
        zip_buffer.seek(0)
        response = send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{page.get('title', 'page')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )
        return response

    @app.route('/api/import/json', methods=['POST'])
    def import_json():
        """JSONファイルをインポート"""
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.json'):
            return jsonify({'error': 'Invalid file format, expected JSON'}), 400
        
        try:
            import_data = json.loads(file.read().decode('utf-8'))
        except Exception as e:
            return jsonify({'error': f'Failed to parse JSON: {str(e)}'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            imported_ids = []
            
            pages_to_import = import_data.get('pages', [])
            if import_data.get('page'):
                pages_to_import = [import_data.get('page')]
            
            for page_dict in pages_to_import:
                new_id = create_page_from_dict(cursor, page_dict)
                imported_ids.append(new_id)
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'{len(imported_ids)} page(s) imported',
                'imported_ids': imported_ids
            })
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': f'Import failed: {str(e)}'}), 500

    @app.route('/api/import/zip', methods=['POST'])
    def import_zip():
        """ZIPファイルをインポート"""
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.zip'):
            return jsonify({'error': 'Invalid file format, expected ZIP'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            with zipfile.ZipFile(io.BytesIO(file.read()), 'r') as zf:
                metadata_files = [f for f in zf.namelist() if f.endswith('metadata.json') and f.count('/') == 1]
                
                if not metadata_files:
                    return jsonify({'error': 'No valid ZIP structure found'}), 400
                
                imported_ids = []
                
                for metadata_file in metadata_files:
                    metadata = json.loads(zf.read(metadata_file).decode('utf-8'))
                    
                    cursor.execute('SELECT MAX(position) FROM pages WHERE parent_id IS NULL')
                    max_pos = cursor.fetchone()[0]
                    position = (max_pos if max_pos is not None else -1) + 1
                    
                    cursor.execute(
                        'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                        (metadata.get('title', ''), metadata.get('icon', '📄'), None, position)
                    )
                    new_page_id = cursor.lastrowid
                    imported_ids.append(new_page_id)
                    
                    page_dir = metadata_file.split('/')[0]
                    page_md_path = f"{page_dir}/page.md"
                    
                    if page_md_path in zf.namelist():
                        md_content = zf.read(page_md_path).decode('utf-8')
                        cursor.execute(
                            "INSERT INTO blocks (page_id, type, content, position) VALUES (?, 'text', ?, 0)",
                            (new_page_id, md_content)
                        )
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'{len(imported_ids)} page(s) imported from ZIP',
                'imported_ids': imported_ids
            })
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': f'ZIP import failed: {str(e)}'}), 500

    @app.route('/api/templates', methods=['GET'])
    def get_templates():
        """テンプレート一覧を取得"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM templates ORDER BY created_at DESC')
        templates = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(templates)

    @app.route('/api/templates', methods=['POST'])
    def create_template():
        """新しいテンプレートを作成"""
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO templates (name, icon, description, content_json) VALUES (?, ?, ?, ?)',
            (
                data.get('name', '新しいテンプレート'),
                data.get('icon', '📋'),
                data.get('description', ''),
                json.dumps(data.get('content', {}), ensure_ascii=False)
            )
        )
        template_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute('SELECT * FROM templates WHERE id = ?', (template_id,))
        template = dict(cursor.fetchone())
        conn.close()
        return jsonify(template)

    @app.route('/api/templates/<int:template_id>', methods=['PUT'])
    def update_template(template_id):
        """テンプレートを更新"""
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if 'name' in data:
            updates.append('name = ?')
            values.append(data['name'])
        if 'icon' in data:
            updates.append('icon = ?')
            values.append(data['icon'])
        if 'description' in data:
            updates.append('description = ?')
            values.append(data['description'])
        if 'content' in data:
            updates.append('content_json = ?')
            values.append(json.dumps(data['content'], ensure_ascii=False))
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.append(template_id)
            cursor.execute(f"UPDATE templates SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()
        
        cursor.execute('SELECT * FROM templates WHERE id = ?', (template_id,))
        template = dict(cursor.fetchone())
        conn.close()
        return jsonify(template)

    @app.route('/api/templates/<int:template_id>', methods=['DELETE'])
    def delete_template(template_id):
        """テンプレートを削除"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM templates WHERE id = ?', (template_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    @app.route('/api/pages/from-custom-template/<int:template_id>', methods=['POST'])
    def create_page_from_custom_template(template_id):
        """カスタムテンプレートからページを作成"""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM templates WHERE id = ?', (template_id,))
        template_row = cursor.fetchone()
        
        if not template_row:
            conn.close()
            return jsonify({'error': 'Template not found'}), 404
        
        template = dict(template_row)
        content = json.loads(template['content_json'])
        
        new_pos = get_next_position(cursor, None)
        cursor.execute(
            'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
            (content.get('title', template['name']), template['icon'], None, new_pos)
        )
        page_id = cursor.lastrowid
        
        for i, block in enumerate(content.get('blocks', [])):
            cursor.execute(
                'INSERT INTO blocks (page_id, type, content, checked, position, collapsed, details, props) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    page_id,
                    block.get('type', 'text'),
                    block.get('content', ''),
                    block.get('checked', 0),
                    (i + 1) * 1000.0,
                    block.get('collapsed', 0),
                    block.get('details', ''),
                    block.get('props', '{}')
                )
            )
        
        for i, child in enumerate(content.get('children', [])):
            child_pos = (i + 1) * 1000.0
            cursor.execute(
                'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                (child.get('title', ''), child.get('icon', '📄'), page_id, child_pos)
            )
            child_id = cursor.lastrowid
            
            for j, block in enumerate(child.get('blocks', [])):
                cursor.execute(
                    'INSERT INTO blocks (page_id, type, content, checked, position, props) VALUES (?, ?, ?, ?, ?, ?)',
                    (child_id, block.get('type', 'text'), block.get('content', ''), block.get('checked', 0), (j + 1) * 1000.0, '{}')
                )
        
        conn.commit()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        page = dict(cursor.fetchone())
        conn.close()
        return jsonify(page)

    @app.route('/api/pages/<int:page_id>/save-as-template', methods=['POST'])
    def save_page_as_template(page_id):
        """現在のページをテンプレートとして保存"""
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        page_dict = export_page_to_dict(cursor, page_id)
        if not page_dict:
            conn.close()
            return jsonify({'error': 'Page not found'}), 404
        
        template_content = {
            'title': page_dict.get('title', ''),
            'blocks': page_dict.get('blocks', []),
            'children': page_dict.get('children', [])
        }
        
        cursor.execute(
            'INSERT INTO templates (name, icon, description, content_json) VALUES (?, ?, ?, ?)',
            (
                data.get('name', page_dict.get('title', '新しいテンプレート')),
                page_dict.get('icon', '📋'),
                data.get('description', ''),
                json.dumps(template_content, ensure_ascii=False)
            )
        )
        template_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute('SELECT * FROM templates WHERE id = ?', (template_id,))
        template = dict(cursor.fetchone())
        conn.close()
        return jsonify(template)

    @app.route('/api/admin/cleanup-running-records', methods=['POST'])
    def admin_cleanup_running_records():
        """各日付ページに積み重なった前日以前のランニング記録を一括削除"""
        deleted = cleanup_accumulated_running_records()
        return jsonify({'success': True, 'deleted_blocks': deleted})

    @app.route('/webhook_deploy', methods=['POST'])
    def webhook_deploy():
        deploy_token = os.getenv('DEPLOY_WEBHOOK_TOKEN', '')
        provided = request.args.get('token') or request.headers.get('X-Deploy-Token') or ''
        if not deploy_token or provided != deploy_token:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        subprocess.run(['git', 'fetch', '--all'], cwd='/home/nnnkeita/mysite')
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd='/home/nnnkeita/mysite')
        subprocess.run(['touch', '/var/www/nnnkeita_pythonanywhere_com_wsgi.py'])
        return jsonify({'status': 'success', 'message': 'Deployed and Reloaded!'})

    @app.route('/download_db', methods=['GET'])
    def download_db():
        """データベースファイルをダウンロード"""
        try:
            return send_file(DATABASE, as_attachment=True, download_name='notion.db')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/list_backups', methods=['GET'])
    def list_backups():
        """利用可能なバックアップファイルをリストアップ"""
        try:
            import glob
            json_backups = sorted(glob.glob(os.path.join(BACKUP_FOLDER, 'backup_*.json')))
            backups = []
            for backup_file in json_backups:
                stat = os.stat(backup_file)
                backups.append({
                    'name': os.path.basename(backup_file),
                    'path': backup_file,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return jsonify({'backups': backups})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/restore_backup/<backup_name>', methods=['POST'])
    def restore_backup(backup_name):
        """バックアップファイルからデータベースを復元"""
        try:
            backup_file = os.path.join(BACKUP_FOLDER, backup_name)
            
            if not os.path.exists(backup_file) or not backup_file.startswith(BACKUP_FOLDER):
                return jsonify({'error': 'Backup file not found'}), 404
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            backup_path = DATABASE + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
            if os.path.exists(DATABASE):
                shutil.copy2(DATABASE, backup_path)
            
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            
            for table_name, rows in backup_data['tables'].items():
                if not rows:
                    continue
                
                cursor.execute(f'DELETE FROM {table_name}')
                
                if rows:
                    first_row = rows[0]
                    columns = list(first_row.keys())
                    placeholders = ', '.join(['?' for _ in columns])
                    insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    for row in rows:
                        values = [row.get(col) for col in columns]
                        cursor.execute(insert_sql, values)
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'status': 'success',
                'message': f'Database restored from {backup_name}',
                'backup_created': backup_path
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/upload_db', methods=['POST'])
    def upload_db():
        """データベースファイルをアップロード（復元用）"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            backup_path = DATABASE + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
            if os.path.exists(DATABASE):
                shutil.copy2(DATABASE, backup_path)
            
            file.save(DATABASE)
            
            return jsonify({
                'status': 'success', 
                'message': 'Database restored successfully',
                'backup': backup_path
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/weather', methods=['GET'])
    def get_weather():
        """天気情報を取得 - Open-Meteo アーカイブAPIを使用（過去90日+将来7日）
        Query params:
        - latitude: 緯度（デフォルト: 40.5150 - 八戸）
        - longitude: 経度（デフォルト: 141.4921 - 八戸）
        - date: YYYY-MM-DD形式（オプション、指定時はその日の天気を返す）
        """
        try:
            import time
            
            latitude = request.args.get('latitude', '40.5150')  # 八戸のデフォルト座標
            longitude = request.args.get('longitude', '141.4921')
            date_str = request.args.get('date', None)
            
            # キャッシュキーを生成
            cache_key = f"{latitude}_{longitude}"
            
            # キャッシュを確認（1時間有効）
            current_time = time.time()
            if (hasattr(get_weather, '_cache') and cache_key in get_weather._cache and 
                current_time - get_weather._cache_time < 3600):
                weather_data = get_weather._cache[cache_key]
            else:
                # 過去90日と今日のデータを取得
                today = datetime.now()
                start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')  # アーカイブAPIは将来のデータには非対応
                
                # Open-Meteo アーカイブAPIを使用（URLはシンプルに）
                # URLエンコーディングなし（curlと同じフォーマット）
                api_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={latitude}&longitude={longitude}&start_date={start_date}&end_date={end_date}&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=Asia/Tokyo"
                
                # curlを使用してAPI呼び出し（Python urllibより確実）
                try:
                    result = subprocess.run(['curl', '-s', api_url], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0 and result.stdout:
                        weather_data = json.loads(result.stdout)
                        # キャッシュに保存
                        if not hasattr(get_weather, '_cache'):
                            get_weather._cache = {}
                        get_weather._cache[cache_key] = weather_data
                        get_weather._cache_time = current_time
                    else:
                        return jsonify({'error': 'Failed to fetch weather data'}), 503
                except FileNotFoundError:
                    # curlが使えない場合はurllibを使用
                    req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        weather_data = json.loads(response.read().decode('utf-8'))
                        # キャッシュに保存
                        if not hasattr(get_weather, '_cache'):
                            get_weather._cache = {}
                        get_weather._cache[cache_key] = weather_data
                        get_weather._cache_time = current_time
            
            # 指定された日付または今日のデータを抽出
            daily = weather_data.get('daily', {})
            times = daily.get('time', [])
            temps_max = daily.get('temperature_2m_max', [])
            temps_min = daily.get('temperature_2m_min', [])
            weather_codes = daily.get('weather_code', [])
            
            # インデックスを決定
            index = 0
            if date_str:
                if date_str in times:
                    index = times.index(date_str)
                else:
                    # 日付が見つからない場合は最も近い日付を探す
                    try:
                        target = datetime.strptime(date_str, '%Y-%m-%d')
                        closest_diff = float('inf')
                        for i, t in enumerate(times):
                            curr_date = datetime.strptime(t, '%Y-%m-%d')
                            diff = abs((curr_date - target).days)
                            if diff < closest_diff:
                                closest_diff = diff
                                index = i
                    except ValueError:
                        index = 0
            else:
                # 今日のデータを取得
                today_str = datetime.now().strftime('%Y-%m-%d')
                if today_str in times:
                    index = times.index(today_str)
                else:
                    index = 0
            
            # WMO天気コードを天気アイコン/説明に変換
            weather_code = weather_codes[index] if index < len(weather_codes) else 0
            weather_icon, weather_desc = decode_wmo_code(weather_code)
            
            result = {
                'date': times[index] if index < len(times) else (date_str or datetime.now().strftime('%Y-%m-%d')),
                'temp_max': temps_max[index] if index < len(temps_max) else None,
                'temp_min': temps_min[index] if index < len(temps_min) else None,
                'weather_code': weather_code,
                'weather_icon': weather_icon,
                'weather_desc': weather_desc,
                'latitude': latitude,
                'longitude': longitude
            }
            
            return jsonify(result), 200
            
        except urllib.error.URLError as e:
            return jsonify({'error': f'Failed to fetch weather data: {str(e)}'}), 503
        except Exception as e:
            return jsonify({'error': f'Error: {str(e)}'}), 500

    # =====================================================
    # 【システム管理エンドポイント】
    # =====================================================
    
    @app.route('/api/system/status', methods=['GET'])
    def get_system_status():
        """システムの接続状況を確認"""
        try:
            status_info = {
                'timestamp': datetime.now().isoformat(),
                'app_name': 'Kiroku Journal',
                'app_version': '1.0.0',
                'environment': os.getenv('ENVIRONMENT', 'local'),
                'database': {
                    'connected': os.path.exists(DATABASE),
                    'path': DATABASE,
                    'size_mb': round(os.path.getsize(DATABASE) / (1024 * 1024), 2) if os.path.exists(DATABASE) else 0
                },
                'upload_folder': {
                    'exists': os.path.exists(UPLOAD_FOLDER),
                    'path': UPLOAD_FOLDER
                },
                'backup_folder': {
                    'exists': os.path.exists(BACKUP_FOLDER),
                    'path': BACKUP_FOLDER
                },
                'python_version': os.sys.version.split()[0],
                'flask_app': 'Running',
                'features': {
                    'tts_enabled': os.getenv('TTS_ENABLED', '1') == '1',
                    'calorie_enabled': os.getenv('CALORIE_ENABLED', '1') == '1',
                    'auth_enabled': os.getenv('AUTH_ENABLED', '0') == '1'
                }
            }
            
            # ユーザー数を確認
            try:
                from .database import get_user_count
                user_count = get_user_count()
                status_info['users_count'] = user_count
            except:
                status_info['users_count'] = 'N/A'
            
            return jsonify(status_info), 200
            
        except Exception as e:
            return jsonify({'error': f'System status check failed: {str(e)}'}), 500
    
    @app.route('/api/system/reload', methods=['POST'])
    def reload_app():
        """アプリケーションをリロード（PythonAnywhere用）"""
        try:
            # WSGI ファイルのタイムスタンプを更新してリロードトリガー
            wsgi_path = os.path.join(PROJECT_ROOT, 'wsgi.py')
            if os.path.exists(wsgi_path):
                # ファイルを読み込み
                with open(wsgi_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # タイムスタンプを更新
                import re
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                content = re.sub(
                    r'# WSGI VERSION:.*',
                    f'# WSGI VERSION: {timestamp}',
                    content
                )
                
                # ファイルに書き込み
                with open(wsgi_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return jsonify({
                    'status': 'success',
                    'message': 'App reload triggered',
                    'timestamp': timestamp,
                    'wsgi_path': wsgi_path
                }), 200
            else:
                return jsonify({'error': 'wsgi.py not found'}), 404
                
        except Exception as e:
            return jsonify({'error': f'Reload failed: {str(e)}'}), 500
    
    @app.route('/api/system/health-check', methods=['GET'])
    def health_check():
        """ヘルスチェック（シンプル）"""
        try:
            # 最小限のチェック
            db_ok = os.path.exists(DATABASE)
            return jsonify({
                'status': 'healthy' if db_ok else 'degraded',
                'timestamp': datetime.now().isoformat(),
                'database_ok': db_ok
            }), 200 if db_ok else 503
        except Exception as e:
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


def decode_wmo_code(code):
    """WMO天気コードを日本語の天気説明とアイコンに変換"""
    weather_map = {
        0: ('☀️', '晴れ'),
        1: ('🌤️', 'ほぼ晴れ'),
        2: ('⛅', 'くもり'),
        3: ('☁️', 'くもり'),
        45: ('🌫️', '霧'),
        48: ('🌫️', '霧（結氷）'),
        51: ('🌧️', '小雨'),
        53: ('🌧️', '小雨'),
        55: ('🌧️', '小雨'),
        61: ('🌧️', '雨'),
        63: ('🌧️', '雨'),
        65: ('⛈️', '強い雨'),
        71: ('❄️', '小雪'),
        73: ('❄️', '小雪'),
        75: ('❄️', '大雪'),
        77: ('❄️', '雪粒'),
        80: ('🌧️', 'にわか雨'),
        81: ('🌧️', '強いにわか雨'),
        82: ('⛈️', '激しいにわか雨'),
        85: ('❄️', 'にわか雪'),
        86: ('❄️', '強いにわか雪'),
        95: ('⛈️', '雷雨'),
        96: ('⛈️', '雷雨（氷粒）'),
        99: ('⛈️', '雷雨（氷粒）'),
    }
    
    icon, desc = weather_map.get(code, ('❓', '不明'))
    return icon, desc
