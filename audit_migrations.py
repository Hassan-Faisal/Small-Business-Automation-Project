import sys
sys.path.insert(0, 'g:\\whatsapp-ai-assistant')
from app.core.database import initialize_database

try:
    initialize_database()
    print('DB_MIGRATION_OK')
except Exception as exc:
    print(f'DB_MIGRATION_FAIL: {exc}')
