#!/usr/bin/env python3
import json
import glob

files = sorted(glob.glob('backups/backup_*.json'))

# すべてのバックアップで 304 を探す
found = False

for file in files[-50:]:
    try:
        with open(file) as f:
            data = json.load(f)
            blocks = [b for b in data.get('tables', {}).get('blocks', []) if b.get('page_id') == 304]
            
            if blocks and any(b.get('content', '').strip() for b in blocks):
                print(f"{file}: Found {len(blocks)} blocks")
                for b in blocks:
                    if b.get('content', '').strip():
                        print(f"  - {b.get('type')}: {b.get('content')[:80]}")
                found = True
    except Exception as e:
        pass

if not found:
    print("No data found for 2/16")
