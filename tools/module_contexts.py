
import os
import json
import ast
import re

EXCLUDES = {'archive', 'temp', 'code_payloads', '.git', '.pytest_cache', '__pycache__'}
ROOT = os.getcwd()
CONTEXT_JSON = "module_contexts.json"

DEFAULT_CONTEXT = dict(
    purpose="",
    public_api=[],
    depends_on=[],
    used_by=[],
    direct_imports=[],
    related_schemas=[],
    context_window_expected="",
    escalation_review="",
)

def relpath(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")

def get_module_import_path(rel_path):
    # "cadence/dev/executor.py" -> "cadence.dev.executor"
    p = rel_path
    if p.endswith(".py"):
        p = p[:-3]
    if p.endswith("/__init__"):
        p = p[:-9]
    return p.replace("/", ".")

def extract_and_strip_shebang_and_futures(lines):
    shebang = None
    futures = []
    body = []
    for line in lines:
        if shebang is None and line.startswith("#!"):
            shebang = line
            continue
        m = re.match(r"\s*from __future__ import", line)
        if m:
            # Avoid duplicates, but preserve order
            if line not in futures:
                futures.append(line)
            continue
        body.append(line)
    return shebang, futures, body

def strip_duplicate_headers_at_top(lines):
    """Remove all context summary header blocks at the file top (before any code)."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Allow blank lines and comments to stay at top
        if line.strip() == "" or line.strip().startswith("#"):
            out.append(line)
            i += 1
            continue
        # Remove all context headers at the top
        if "# MODULE CONTEXT SUMMARY" in line:
            while i < n and "# END MODULE CONTEXT SUMMARY" not in lines[i]:
                i += 1
            if i < n:
                i += 1  # Skip END marker
            # Keep going in case of further headers
            continue
        break  # Non-header, non-blank, non-comment: stop removing
    out.extend(lines[i:])
    # Remove extra blank lines at the start
    while len(out) > 1 and out[0].strip() == "" and out[1].strip() == "":
        out = out[1:]
    return out


def find_existing_context(lines):
    start = None
    end = None
    for i, line in enumerate(lines):
        if "MODULE CONTEXT SUMMARY" in line:
            start = i
        if start is not None and "END MODULE CONTEXT SUMMARY" in line:
            end = i
            break
    return (start, end) if start is not None and end is not None else (None, None)

def render_pretty_list(lst, indent=4):
    if not lst:
        return "[]"
    pad = " " * indent
    return "[\n" + "".join(f"{pad}{repr(x)},\n" for x in lst) + "]"

def render_context_block(rel, context):
    def pretty(key):
        val = context[key]
        if isinstance(val, list):
            return f"{key}: {render_pretty_list(val)}"
        return f'{key}: "{val}"' if isinstance(val, str) else f"{key}: {val}"

    lines = [
        '"""# MODULE CONTEXT SUMMARY',
        f'filepath: {rel}',
        pretty("purpose"),
        pretty("public_api"),
        pretty("depends_on"),
        pretty("used_by"),
        pretty("direct_imports"),
        pretty("related_schemas"),
        pretty("context_window_expected"),
        pretty("escalation_review"),
        '# END MODULE CONTEXT SUMMARY"""',
        ''
    ]
    return "\n".join(lines) + "\n"

def load_all_contexts():
    if os.path.exists(CONTEXT_JSON):
        with open(CONTEXT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def write_all_contexts(contexts):
    with open(CONTEXT_JSON, "w", encoding="utf-8") as f:
        json.dump(contexts, f, indent=2, ensure_ascii=False)

def scan_python_modules():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDES]
        for fname in filenames:
            if fname.endswith(".py") and fname not in EXCLUDES:
                abspath = os.path.join(dirpath, fname)
                yield relpath(abspath), abspath

def scan_all_internal_modules(root_dir):
    internal = set()
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(".py"):
                abs_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(abs_path, root_dir).replace(os.sep, "/")
                mod_path = get_module_import_path(rel)
                internal.add(mod_path)
    return internal

def parse_module(path, rel_path, all_internal_modules):
    """Returns (public_api, depends_on, direct_imports) for a python module.
       - public_api: list of fully qualified names for top-level defs/classes in this file
       - depends_on: internal modules imported (as import paths)
       - direct_imports: all directly imported packages/modules (raw names, incl. external)
    """
    public_api = []
    depends_on = set()
    direct_imports = set()

    module_import_path = get_module_import_path(rel_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=path)
    except Exception:
        return public_api, depends_on, direct_imports

    # Top-level functions/classes
    for n in node.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            public_api.append(f"{module_import_path}.{n.name}")

    # Imports
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                direct_imports.add(alias.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            mod = n.module
            if mod:
                mod_path = mod.replace(".", "/") + ".py"
                mod_import_path = mod.replace("/", ".")
                direct_imports.add(mod.split(".")[0])
                # Internal module dependency as import path (e.g. cadence.dev.executor)
                if mod_import_path in all_internal_modules:
                    depends_on.add(mod_import_path)
    return sorted(public_api), sorted(depends_on), sorted(direct_imports)

def sync_contexts():
    all_internal_modules = scan_all_internal_modules(ROOT)
    all_contexts = load_all_contexts()
    updated_contexts = {}
    modified = 0
    for rel, abspath in scan_python_modules():
        context = dict(DEFAULT_CONTEXT)
        context.update(all_contexts.get(rel, {}))
        context['filepath'] = rel
        public_api, depends_on, direct_imports = parse_module(abspath, rel, all_internal_modules)
        context['public_api'] = public_api
        context['depends_on'] = depends_on
        context['direct_imports'] = direct_imports
        with open(abspath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Extract and remove all shebang/future imports anywhere in the file
        shebang, futures, lines_no_shebang = extract_and_strip_shebang_and_futures(lines)
        # Remove all context header blocks at the top
        code_body = strip_duplicate_headers_at_top(lines_no_shebang)
        block = render_context_block(rel, context)
        new_lines = []
        if shebang:
            new_lines.append(shebang)
        if futures:
            new_lines.extend(futures)
        new_lines.append(block)
        new_lines.extend(code_body)
        # Ensure only one blank line after header
        i = 1
        while i < len(new_lines) and new_lines[i].strip() == "":
            i += 1
        if i > 2:
            new_lines = [new_lines[0], "\n"] + new_lines[i:]
        with open(abspath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        updated_contexts[rel] = context
        modified += 1
    write_all_contexts(updated_contexts)
    print(f"Updated {modified} file(s) and wrote {CONTEXT_JSON}.")



def print_context(module):
    contexts = load_all_contexts()
    ctx = contexts.get(module)
    if not ctx:
        print(f"No context found for {module}")
        return
    for k, v in ctx.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "sync":
        sync_contexts()
    elif len(sys.argv) == 3 and sys.argv[1] == "show":
        print_context(sys.argv[2])
    else:
        print("Usage:")
        print("  python module_context.py sync         # Update headers and JSON for all modules")
        print("  python module_context.py show path/to/module.py   # Print context for a module")
