"""A flag alone must not enable live charging against ephemeral SQLite."""
import os
from pathlib import Path

def mounted_database(db_path):
 root=Path(os.getenv('PERSISTENT_DATA_DIR','/var/data')).resolve()
 db=Path(db_path).resolve()
 try:db.relative_to(root)
 except ValueError:return False
 return os.path.ismount(root) and root.is_dir()
