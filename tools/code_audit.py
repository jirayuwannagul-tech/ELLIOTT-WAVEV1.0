import ast
import os
from collections import defaultdict

APP_DIR = "app"

def get_all_py_files(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)

def find_all_definitions(root):
    defs = defaultdict(list)
    for path in get_all_py_files(root):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs[node.name].append(path)
    return defs

def find_all_imports(root):
    imported_modules = set()
    for path in get_all_py_files(root):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
    return imported_modules

def find_all_calls(root):
    calls = set()
    for path in get_all_py_files(root):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
    return calls

def module_path_to_dotted(path, root):
    rel = os.path.relpath(path, os.path.dirname(root))
    return rel.replace(os.sep, ".").removesuffix(".py")

def audit(root=APP_DIR):
    print("=" * 60)
    print("🔍 CODE AUDIT REPORT")
    print("=" * 60)

    defs = find_all_definitions(root)
    print("\n📌 [1] ฟังก์ชัน/คลาสชื่อซ้ำข้ามไฟล์:")
    found_dup = False
    for name, files in defs.items():
        if len(files) > 1 and not name.startswith("_"):
            print(f"  ⚠️  '{name}' พบใน {len(files)} ไฟล์:")
            for f in files:
                print(f"       → {f}")
            found_dup = True
    if not found_dup:
        print("  ✅ ไม่พบชื่อซ้ำ")

    calls = find_all_calls(root)
    print("\n📌 [2] ฟังก์ชันที่อาจไม่มีใครเรียก (dead function):")
    found_dead = False
    skip_names = {"__init__", "main", "setUp", "tearDown"}
    for name, files in defs.items():
        if name not in calls and not name.startswith("_") and name not in skip_names:
            for f in files:
                print(f"  ⚠️  '{name}' → {f}")
            found_dead = True
    if not found_dead:
        print("  ✅ ไม่พบ dead function ชัดเจน")

    imported = find_all_imports(root)
    print("\n📌 [3] ไฟล์ที่อาจไม่มีใคร import (dead file):")
    found_dead_file = False
    for path in get_all_py_files(root):
        dotted = module_path_to_dotted(path, root)
        if not any(dotted.endswith(imp) or imp.endswith(dotted) or dotted in imp for imp in imported):
            if "__init__" not in path and "main" not in path:
                print(f"  ⚠️  {path}")
                found_dead_file = True
    if not found_dead_file:
        print("  ✅ ไม่พบ dead file ชัดเจน")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    audit()
