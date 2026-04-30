# -*- coding: utf-8 -*-
"""
ユーティリティ関数
- カロリー計算
- ページエクスポート/インポート
- バックアップ
"""
import json
import re
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from .database import get_db, get_next_position, get_block_next_position, mark_tree_deleted

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'zip', 'docx'}

# カロリー計算の簡易データベース
CALORIE_TABLE = [
    {'label': 'ご飯', 'keywords': ['ご飯', '白米', 'ライス'], 'kcal': 240, 'unit': '1杯(150g)'},
    {'label': '納豆', 'keywords': ['納豆'], 'kcal': 100, 'unit': '1パック'},
    {'label': 'パン', 'keywords': ['食パン', 'パン'], 'kcal': 180, 'unit': '1枚(6枚切)'},
    {'label': 'プロテイン', 'keywords': ['プロテイン'], 'kcal': 120, 'unit': '1杯(30g)'},
    {'label': '弁当', 'keywords': ['弁当'], 'kcal': 500, 'unit': '1個'},
    {'label': '卵', 'keywords': ['卵', 'たまご'], 'kcal': 80, 'unit': '1個'},
    {'label': '鶏むね肉', 'keywords': ['鶏むね', '鶏胸', 'ささみ'], 'kcal': 165, 'unit': '100g', 'per_grams': 100},
    {'label': '豚肉', 'keywords': ['豚肉'], 'kcal': 250, 'unit': '100g', 'per_grams': 100},
    {'label': '牛肉', 'keywords': ['牛肉'], 'kcal': 280, 'unit': '100g', 'per_grams': 100},
    {'label': '豆腐', 'keywords': ['豆腐'], 'kcal': 140, 'unit': '1丁(300g)', 'per_grams': 300},
    {'label': 'ヨーグルト', 'keywords': ['ヨーグルト'], 'kcal': 60, 'unit': '100g', 'per_grams': 100},
    {'label': 'バナナ', 'keywords': ['バナナ'], 'kcal': 90, 'unit': '1本'},
    {'label': 'そば', 'keywords': ['そば', '蕎麦'], 'kcal': 320, 'unit': '1人前'},
    {'label': 'うどん', 'keywords': ['うどん'], 'kcal': 280, 'unit': '1人前'},
    {'label': 'パスタ', 'keywords': ['パスタ', 'スパゲッティ'], 'kcal': 350, 'unit': '1人前'},
    {'label': '牛乳', 'keywords': ['牛乳', 'ミルク'], 'kcal': 130, 'unit': '200ml', 'per_ml': 200},
    {'label': 'サラダ', 'keywords': ['サラダ'], 'kcal': 80, 'unit': '1皿'},
    {'label': '汁物', 'keywords': ['汁', 'スープ', '味噌汁', 'みそ汁'], 'kcal': 80, 'unit': '1杯(180ml)', 'per_ml': 180},
]

DEFAULT_UNKNOWN_KCAL = 150
SERPAPI_KEY = os.getenv('SERPAPI_KEY', '')

def allowed_file(filename):
    """許可されたファイル拡張子かチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _extract_number(text, pattern):
    """テキストから数値を抽出"""
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None

def _fallback_estimate(line):
    """未知の食材の概算カロリーを推定"""
    if '汁' in line or 'スープ' in line:
        return {'label': '汁物(推定)', 'kcal': 80, 'is_estimated': True}
    if 'カレー' in line:
        return {'label': 'カレー(推定)', 'kcal': 500, 'is_estimated': True}
    if 'シチュー' in line:
        return {'label': 'シチュー(推定)', 'kcal': 350, 'is_estimated': True}
    if '煮込み' in line:
        return {'label': '煮込み(推定)', 'kcal': 300, 'is_estimated': True}
    if '炒め' in line or 'ソテー' in line:
        return {'label': '炒め物(推定)', 'kcal': 320, 'is_estimated': True}
    return {'label': '不明(推定)', 'kcal': DEFAULT_UNKNOWN_KCAL, 'is_estimated': True}

def estimate_calories(lines):
    """行ごとのメニュー文字列から概算カロリーを計算"""
    results = []
    total_kcal = 0.0

    for raw in lines:
        line = (raw or '').strip()
        if not line:
            continue

        matched_entry = None
        for entry in CALORIE_TABLE:
            if any(keyword in line for keyword in entry['keywords']):
                matched_entry = entry
                break

        amount = _extract_number(line, r'(\d+(?:\.\d+)?)') or 1.0
        gram_val = _extract_number(line, r'(\d+(?:\.\d+)?)\s*(?:g|グラム)')
        ml_val = _extract_number(line, r'(\d+(?:\.\d+)?)\s*(?:ml|mL|ML|㎖)')

        if matched_entry:
            kcal = matched_entry['kcal']
            unit = matched_entry.get('unit', '1食')

            if matched_entry.get('per_grams'):
                grams = gram_val if gram_val is not None else matched_entry['per_grams'] * amount
                kcal_total = (grams / matched_entry['per_grams']) * matched_entry['kcal']
                amount_label = f"{grams:.0f}g"
            elif matched_entry.get('per_ml'):
                ml = ml_val if ml_val is not None else matched_entry['per_ml'] * amount
                kcal_total = (ml / matched_entry['per_ml']) * matched_entry['kcal']
                amount_label = f"{ml:.0f}ml"
            else:
                kcal_total = amount * kcal
                amount_label = f"{amount:.1f}食" if amount != 1 else '1食'

            kcal_total = round(kcal_total, 1)
            total_kcal += kcal_total
            results.append({
                'input': line,
                'matched': matched_entry['label'],
                'unit': unit,
                'amount': amount_label,
                'kcal': kcal_total,
                'is_estimated': False
            })
        else:
            fallback = _fallback_estimate(line)
            kcal_total = round(fallback['kcal'], 1)
            total_kcal += kcal_total
            results.append({
                'input': line,
                'matched': fallback['label'],
                'unit': '推定',
                'amount': '-',
                'kcal': kcal_total,
                'is_estimated': True
            })

    return {
        'total_kcal': round(total_kcal, 1),
        'items': results,
        'note': '目安の計算です。食材や調理法で変動します。'
    }

def _normalize_unit(unit):
    return (unit or '').strip()

def _is_gram_unit(unit):
    return unit in {'g', 'G', 'グラム', 'g数', 'gram'}

def _is_ml_unit(unit):
    return unit in {'ml', 'mL', 'ML', '㎖'}

def _is_serving_unit(unit):
    return unit in {'杯', '人前', '個', '枚', '食', '皿'}

def _fetch_kcal_from_serpapi(query):
    if not SERPAPI_KEY:
        return None, None
    params = {
        'engine': 'google',
        'q': query,
        'hl': 'ja',
        'api_key': SERPAPI_KEY
    }
    url = 'https://serpapi.com/search.json?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None, None

    candidates = []
    answer_box = data.get('answer_box') or {}
    for key in ['answer', 'snippet', 'snippet_highlighted_words']:
        val = answer_box.get(key)
        if isinstance(val, list):
            candidates.extend([str(v) for v in val])
        elif val:
            candidates.append(str(val))

    for item in data.get('organic_results', [])[:5]:
        title = item.get('title') or ''
        snippet = item.get('snippet') or ''
        candidates.append(f"{title} {snippet}")

    kcal_pattern = re.compile(r'(\d{2,4})\s*kcal', re.IGNORECASE)
    for text in candidates:
        match = kcal_pattern.search(text)
        if match:
            return float(match.group(1)), text
    return None, None

def estimate_calories_items(items):
    """品名/量/単位の入力からカロリー推定（検索も併用）"""
    results = []
    total_kcal = 0.0

    for item in items:
        name = (item.get('name') or '').strip()
        if not name:
            continue
        amount_raw = item.get('amount')
        try:
            amount = float(amount_raw) if amount_raw not in (None, '') else 1.0
        except Exception:
            amount = 1.0
        unit = _normalize_unit(item.get('unit'))

        matched_entry = None
        for entry in CALORIE_TABLE:
            if any(keyword in name for keyword in entry['keywords']):
                matched_entry = entry
                break

        input_label = f"{name} {amount:g}{unit}" if unit else f"{name}"

        if matched_entry:
            kcal = matched_entry['kcal']
            unit_label = matched_entry.get('unit', '1食')

            if matched_entry.get('per_grams') and (_is_gram_unit(unit) or unit == ''):
                grams = amount if _is_gram_unit(unit) else matched_entry['per_grams'] * amount
                kcal_total = (grams / matched_entry['per_grams']) * matched_entry['kcal']
                amount_label = f"{grams:.0f}g"
            elif matched_entry.get('per_ml') and (_is_ml_unit(unit) or unit == ''):
                ml = amount if _is_ml_unit(unit) else matched_entry['per_ml'] * amount
                kcal_total = (ml / matched_entry['per_ml']) * matched_entry['kcal']
                amount_label = f"{ml:.0f}ml"
            else:
                servings = amount if amount > 0 else 1.0
                kcal_total = servings * kcal
                amount_label = f"{servings:g}{unit or '食'}"

            kcal_total = round(kcal_total, 1)
            total_kcal += kcal_total
            results.append({
                'input': input_label,
                'matched': matched_entry['label'],
                'unit': unit_label,
                'amount': amount_label,
                'kcal': kcal_total,
                'is_estimated': False,
                'source': 'db'
            })
            continue

        query = f"{name} {amount:g}{unit} kcal" if unit else f"{name} kcal"
        kcal_from_web, source_text = _fetch_kcal_from_serpapi(query)
        if kcal_from_web:
            kcal_total = kcal_from_web
            if amount > 1 and _is_serving_unit(unit):
                kcal_total = kcal_from_web * amount
            kcal_total = round(kcal_total, 1)
            total_kcal += kcal_total
            results.append({
                'input': input_label,
                'matched': name,
                'unit': unit or 'web',
                'amount': f"{amount:g}{unit}" if unit else '-',
                'kcal': kcal_total,
                'is_estimated': False,
                'source': 'web',
                'source_text': source_text
            })
            continue

        fallback = _fallback_estimate(name)
        kcal_total = round(fallback['kcal'], 1)
        total_kcal += kcal_total
        results.append({
            'input': input_label,
            'matched': fallback['label'],
            'unit': '推定',
            'amount': '- ',
            'kcal': kcal_total,
            'is_estimated': True,
            'source': 'fallback'
        })

    return {
        'total_kcal': round(total_kcal, 1),
        'items': results,
        'note': '目安の計算です。食材や調理法で変動します。検索結果は参考値です。'
    }

def export_page_to_dict(cursor, page_id):
    """ページとその全ブロック・子ページを辞書に変換（エクスポート用）"""
    cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
    page_row = cursor.fetchone()
    if not page_row:
        return None
    
    page = dict(page_row)
    cursor.execute('SELECT * FROM blocks WHERE page_id = ? ORDER BY position', (page_id,))
    page['blocks'] = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT * FROM pages WHERE parent_id = ? ORDER BY position', (page_id,))
    page['children'] = [export_page_to_dict(cursor, row['id']) for row in cursor.fetchall()]
    
    return page

def page_to_markdown(page, level=1):
    """ページをMarkdownフォーマットに変換（再帰的）"""
    lines = []
    
    # ページタイトルを見出しで表現
    heading = '#' * level
    lines.append(f"{heading} {page.get('icon', '📄')} {page.get('title', '無題')}")
    lines.append('')
    
    # ブロックをMarkdownに変換
    for block in page.get('blocks', []):
        block_type = block.get('type', 'text')
        content = block.get('content', '')
        
        if block_type == 'h1':
            lines.append(f"### {content}")
            lines.append('')
        elif block_type == 'todo':
            checked = '✓' if block.get('checked') else '☐'
            lines.append(f"- [{checked}] {content}")
        elif block_type == 'toggle':
            lines.append(f"**{content}**")
            details = block.get('details', '')
            if details:
                lines.append(details)
            lines.append('')
        elif block_type == 'image':
            lines.append(f"![Image]({content})")
            lines.append('')
        elif block_type == 'speak':
            lines.append(f"🔊 [読み上げ]: {content}")
            lines.append('')
        else:  # text
            if content:
                lines.append(content)
                lines.append('')
    
    # 子ページを再帰的に変換
    for child in page.get('children', []):
        lines.append(page_to_markdown(child, level + 1))
        lines.append('')
    
    return '\n'.join(lines)

def create_page_from_dict(cursor, page_dict, parent_id=None, position=None):
    """辞書からページを作成（インポート用）"""
    parent_id = parent_id if parent_id is not None else page_dict.get('parent_id')
    
    if position is None:
        position = get_next_position(cursor, parent_id)
    
    cursor.execute(
        'INSERT INTO pages (title, icon, cover_image, parent_id, position, is_pinned, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (
            page_dict.get('title', ''),
            page_dict.get('icon', '📄'),
            page_dict.get('cover_image', ''),
            parent_id,
            position,
            page_dict.get('is_pinned', 0),
            0
        )
    )
    new_page_id = cursor.lastrowid
    
    # ブロック追加
    for block in page_dict.get('blocks', []):
        cursor.execute(
            'INSERT INTO blocks (page_id, type, content, checked, position, collapsed, details, props) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                new_page_id,
                block.get('type', 'text'),
                block.get('content', ''),
                block.get('checked', 0),
                block.get('position', 1000.0),
                block.get('collapsed', 0),
                block.get('details', ''),
                block.get('props', '{}')
            )
        )
    
    # 子ページ追加
    for i, child in enumerate(page_dict.get('children', [])):
        child_pos = (i + 1) * 1000.0
        create_page_from_dict(cursor, child, parent_id=new_page_id, position=child_pos)
    
    return new_page_id

def get_or_create_date_page(cursor, date_str):
    """指定日付のページを取得または作成（存在しない場合は前日をコピー）"""
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        title = f"{target_date.year}年{target_date.month}月{target_date.day}日"
    except Exception:
        return None

    cursor.execute('SELECT * FROM pages WHERE title = ? AND is_deleted = 0 LIMIT 1', (title,))
    existing = cursor.fetchone()
    if existing:
        return dict(existing)

    prev_date = target_date - timedelta(days=1)
    prev_title = f"{prev_date.year}年{prev_date.month}月{prev_date.day}日"
    cursor.execute('SELECT id FROM pages WHERE title = ? AND is_deleted = 0 ORDER BY created_at DESC LIMIT 1', (prev_title,))
    prev_row = cursor.fetchone()

    if prev_row:
        previous_page_id = prev_row['id']
        new_page_id = copy_page_tree(cursor, previous_page_id, new_title=title, new_parent_id=None, override_icon='📅')

        # 前日のランニング記録・ワークアウト記録・体重ブロックは当日に引き継がない
        for pattern in ('🏃 ランニング記録%', '%GymTrack%', '💪 ワークアウト記録%', '体重%', '%体脂肪%'):
            cursor.execute(
                "DELETE FROM blocks WHERE page_id = ? AND content LIKE ?",
                (new_page_id, pattern)
            )

        # 前日の体重データも引き継がない
        cursor.execute(
            "UPDATE pages SET weight = NULL, body_fat = NULL, weight_at = NULL WHERE id = ?",
            (new_page_id,)
        )

        excluded_children = {'筋トレ', '英語学習'}
        cursor.execute(
            'SELECT id, title FROM pages WHERE parent_id = ? AND is_deleted = 0',
            (new_page_id,)
        )
        existing_titles = set()
        for row in cursor.fetchall():
            if row['title'] in excluded_children:
                mark_tree_deleted(cursor, row['id'], is_deleted=True)
            else:
                existing_titles.add(row['title'])

        required_children = [
            ('日記', '📝'),
            ('食事', '🍽️'),
            ('読書', '📚'),
        ]

        required_titles = {title_req for title_req, _ in required_children}
        cursor.execute(
            'SELECT id, title FROM pages WHERE parent_id = ? AND is_deleted = 0 ORDER BY position',
            (new_page_id,)
        )
        seen_titles = set()
        for row in cursor.fetchall():
            title_value = row['title']
            if title_value in required_titles:
                if title_value in seen_titles:
                    mark_tree_deleted(cursor, row['id'], is_deleted=True)
                else:
                    seen_titles.add(title_value)

        next_pos = get_next_position(cursor, new_page_id)
        for title_req, icon_req in required_children:
            if title_req not in existing_titles:
                cursor.execute(
                    'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                    (title_req, icon_req, new_page_id, next_pos)
                )
                next_pos += 1000.0

        cursor.execute('SELECT * FROM pages WHERE id = ?', (new_page_id,))
        page = dict(cursor.fetchone())
        return page

    new_pos = get_next_position(cursor, None)
    cursor.execute('INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
                   (title, '📅', None, new_pos))
    page_id = cursor.lastrowid

    cursor.execute("INSERT INTO blocks (page_id, type, content, position, props) VALUES (?, 'text', '', ?, ?)",
                   (page_id, 1000.0, '{}'))

    children_templates = [
        {
            'title': '日記',
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
        {
            'title': '食事',
            'icon': '🍽️',
            'blocks': [
                {'type': 'h1', 'content': '朝食'},
                {'type': 'text', 'content': ''},
                {'type': 'h1', 'content': '昼食'},
                {'type': 'text', 'content': ''},
                {'type': 'h1', 'content': '夕食'},
                {'type': 'text', 'content': ''},
            ]
        },
        {
            'title': '読書',
            'icon': '📚',
            'blocks': [
                {'type': 'h1', 'content': '本のタイトル'},
                {'type': 'text', 'content': ''},
                {'type': 'h1', 'content': '著者'},
                {'type': 'text', 'content': ''},
                {'type': 'h1', 'content': '感想・メモ'},
                {'type': 'text', 'content': ''},
            ]
        }
    ]

    for i, child in enumerate(children_templates):
        child_pos = (i + 1) * 1000.0
        cursor.execute(
            'INSERT INTO pages (title, icon, parent_id, position) VALUES (?, ?, ?, ?)',
            (child['title'], child['icon'], page_id, child_pos)
        )
        child_id = cursor.lastrowid
        for j, block in enumerate(child['blocks']):
            cursor.execute(
                "INSERT INTO blocks (page_id, type, content, checked, position, props) VALUES (?, ?, ?, ?, ?, ?)",
                (child_id, block['type'], block['content'], block.get('checked', 0), (j + 1) * 1000.0, '{}')
            )

    cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
    page = dict(cursor.fetchone())
    return page

def copy_page_tree(cursor, source_page_id, new_title=None, new_parent_id=None, position=None, override_icon=None):
    """ページとブロックを再帰的にコピー"""
    cursor.execute('SELECT * FROM pages WHERE id = ?', (source_page_id,))
    source_page = cursor.fetchone()
    if not source_page:
        return None

    src = dict(source_page)
    parent_id = new_parent_id if new_parent_id is not None else src['parent_id']
    if position is None:
        position = get_next_position(cursor, parent_id)

    cursor.execute(
        'INSERT INTO pages (title, icon, cover_image, parent_id, position, is_pinned, is_deleted) VALUES (?, ?, ?, ?, ?, ?, 0)',
        (
            new_title if new_title is not None else src.get('title', ''),
            override_icon if override_icon is not None else src.get('icon', '📄'),
            src.get('cover_image', ''),
            parent_id,
            position,
            src.get('is_pinned', 0)
        )
    )
    new_page_id = cursor.lastrowid

    # ブロックコピー
    cursor.execute('SELECT * FROM blocks WHERE page_id = ? ORDER BY position', (source_page_id,))
    for block in cursor.fetchall():
        block_dict = dict(block)
        cursor.execute(
            'INSERT INTO blocks (page_id, type, content, checked, position, collapsed, details, props) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                new_page_id,
                block_dict.get('type', 'text'),
                block_dict.get('content', ''),
                block_dict.get('checked', 0),
                block_dict.get('position', 0),
                block_dict.get('collapsed', 0),
                block_dict.get('details', ''),
                block_dict.get('props', '{}')
            )
        )

    # 子ページを再帰コピー
    cursor.execute('SELECT * FROM pages WHERE parent_id = ? ORDER BY position', (source_page_id,))
    for child in cursor.fetchall():
        copy_page_tree(cursor, child['id'], new_parent_id=new_page_id, position=child['position'])

    return new_page_id

def cleanup_accumulated_running_records():
    """各日付ページに積み重なった前日以前のランニング記録を削除する。
    日付順に処理し、過去ページで既出のブロック内容はコピー品として削除する。"""
    import re as _re
    from datetime import datetime as _dt

    conn = get_db()
    cursor = conn.cursor()

    date_pattern = _re.compile(r'^(\d{4})年(\d{1,2})月(\d{1,2})日$')

    # 全日付ページを取得
    cursor.execute('SELECT id, title FROM pages WHERE is_deleted = 0')
    date_pages = []
    for row in cursor.fetchall():
        m = date_pattern.match(row['title'])
        if not m:
            continue
        try:
            d = _dt(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            date_pages.append({'id': row['id'], 'date': d})
        except ValueError:
            pass

    # 日付昇順で処理
    date_pages.sort(key=lambda x: x['date'])

    seen_contents = set()   # これまでの日付ページで確認済みのランニング記録内容
    total_deleted = 0

    for page_info in date_pages:
        page_id = page_info['id']
        cursor.execute(
            "SELECT id, content FROM blocks WHERE page_id = ? AND content LIKE '🏃 ランニング記録%' ORDER BY id",
            (page_id,)
        )
        run_blocks = cursor.fetchall()
        if not run_blocks:
            continue

        to_delete = []
        for block in run_blocks:
            content = block['content']
            if content in seen_contents:
                # 前日以前にも存在 → コピー品なので削除
                to_delete.append(block['id'])
            else:
                # 初出 → このページ固有の記録として残す
                seen_contents.add(content)

        if to_delete:
            placeholders = ','.join('?' * len(to_delete))
            cursor.execute(f"DELETE FROM blocks WHERE id IN ({placeholders})", to_delete)
            total_deleted += len(to_delete)

    conn.commit()
    conn.close()
    return total_deleted


def backup_database_to_json():
    """データベースをJSONテキスト形式でバックアップ"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # テーブル一覧取得（FTSテーブルを除外）
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            AND name NOT LIKE '%_fts%'
            AND name NOT LIKE '%_config'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # バックアップデータ作成
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'database': 'notion.db',
            'tables': {}
        }
        
        # 各テーブルをエクスポート
        for table in tables:
            cursor.execute(f'SELECT * FROM {table}')
            rows = cursor.fetchall()
            backup_data['tables'][table] = [dict(row) for row in rows]
        
        conn.close()
        
        # JSONファイルに保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(BACKUP_FOLDER, f'backup_{timestamp}.json')
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # 最新のバックアップを latest.json にコピー
        latest_file = os.path.join(BACKUP_FOLDER, 'latest.json')
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"⚠️ Backup failed: {e}")
        return False
