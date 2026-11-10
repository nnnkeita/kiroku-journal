"""Storage paths for the active journal workspace."""
import os
from contextlib import contextmanager
from fcntl import LOCK_EX, flock
from pathlib import Path

from flask import g, has_app_context

from . import database


def workspace_path():
    return getattr(g, 'journal_workspace', None) if has_app_context() else None


def uploads_folder(legacy):
    workspace = workspace_path()
    return os.path.join(workspace, 'uploads') if workspace else legacy


@contextmanager
def use_workspace(user_id):
    root = Path(database.DATABASE).parent / 'journal_workspaces'
    folder = root / str(int(user_id))
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    (folder / 'uploads').mkdir(exist_ok=True, mode=0o700)
    previous = workspace_path()
    g.journal_workspace = str(folder)
    try:
        ready = folder / '.initialized'
        if not ready.exists():
            with (folder / '.init-lock').open('a') as lock:
                flock(lock, LOCK_EX)
                if not ready.exists():
                    database.init_db()
                    ready.touch()
        yield
    finally:
        g.journal_workspace = previous
