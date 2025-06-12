import os
import importlib
from fastapi import APIRouter

router = APIRouter()

# Auto-import all route files in this directory
route_dir = os.path.dirname(__file__)
for file in os.listdir(route_dir):
    if file.endswith(".py") and file not in ["__init__.py"]:
        module_name = file[:-3]
        module_path = f"routes.{module_name}"
        mod = importlib.import_module(module_path)
        if hasattr(mod, "router"):
            router.include_router(mod.router, prefix="/api")
