# parsers/__init__.py

import pkgutil
import importlib
from pathlib import Path

_parsers = {}

# Busca todos los módulos que terminen en *_parser.py
for finder, name, ispkg in pkgutil.iter_modules([Path(__file__).parent]):
    if name.endswith("_parser"):
        key = name.replace("_parser", "")
        module = importlib.import_module(f"parsers.{name}")
        _parsers[key] = f"parsers.{name}"

def get_parser(name: str):
    module_path = _parsers.get(name)
    if not module_path:
        raise ValueError(f"Banco '{name}' no soportado. Opciones: {list(_parsers)}")
    module = __import__(module_path, fromlist=["parse"])
    return module