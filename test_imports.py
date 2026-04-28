import sys
import os
sys.path.append(os.getcwd())

try:
    from src.domain.model import User, DailyPonto
    print("Domain imports OK")
    from src.adapters.orm import start_mappers
    print("ORM imports OK")
    from src.adapters.repository import SqlAlchemyRepository
    print("Repository imports OK")
    from src.service_layer.services import register_user
    print("Services imports OK")
    from src.entrypoints.flask_app import app
    print("Flask app imports OK")
    print("ALL IMPORTS SUCCESSFUL")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
