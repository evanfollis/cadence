import os
import re

EXCLUDES = {'archive', 'temp', 'code_payloads', '.git', '.pytest_cache', '__pycache__'}
ROOT = os.getcwd()

CONTEXT_HEADER_TEMPLATE = '''"""# MODULE CONTEXT SUMMARY 
filepath: {filepath}
purpose: "" 
public_api: [] 
depends_on: [] 
used_by: []
direct_imports: []      
related_schemas: []                 
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY""" 
'''

def relpath(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")

def has_context_header(lines):
    """Return (start, end) of context header block if found, else (None, None)."""
    start = None
    end = None
    for i, line in enumerate(lines):
        if line.strip().startswith('"""# MODULE CONTEXT SUMMARY'):
            start = i
        if start is not None and line.strip().endswith('# END MODULE CONTEXT SUMMARY"""'):
            end = i
            break
    return (start, end) if start is not None and end is not None else (None, None)

def fix_module_context_header(py_path):
    rel = relpath(py_path)
    header = CONTEXT_HEADER_TEMPLATE.format(filepath=rel)
    with open(py_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    start, end = has_context_header(lines)
    if start == 0 and end is not None:
        existing_header = "".join(lines[start:end+1])
        if existing_header == header:
            return False  # Already present and correct
        # Replace existing header
        lines = [header] + lines[end+1:]
    else:
        # Insert at top
        lines = [header] + lines
    with open(py_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True

def main():
    modified = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDES]
        for fname in filenames:
            if fname.endswith(".py") and fname not in EXCLUDES:
                fpath = os.path.join(dirpath, fname)
                if fix_module_context_header(fpath):
                    print(f"Updated context summary: {relpath(fpath)}")
                    modified += 1
    print(f"Done. {modified} file(s) updated.")

if __name__ == "__main__":
    main()
