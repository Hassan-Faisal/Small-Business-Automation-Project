import importlib
import sys

sys.path.insert(0, 'g:\\whatsapp-ai-assistant')
modules = [
    'app.main',
    'app.core.database',
    'app.core.config',
    'app.services.chat_service',
    'app.services.product_service',
    'app.services.order_service',
    'app.services.whatsapp_service',
    'app.langgraph.workflow',
    'app.rag.rag_chain',
]
for name in modules:
    try:
        importlib.import_module(name)
        print(f'IMPORT_OK {name}')
    except Exception as exc:
        print(f'IMPORT_FAIL {name}: {exc}')
