import os
import json

def write_files_from_json(json_path, root_dir='.'):
    with open(json_path, 'r', encoding='utf-8') as f:
        filemap = json.load(f)

    for rel_path, code in filemap.items():
        full_path = os.path.join(root_dir, rel_path)
        dir_path = os.path.dirname(full_path)
        os.makedirs(dir_path, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as out:
            out.write(code)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python write_files_from_json.py <input.json>")
        exit(1)
    write_files_from_json(sys.argv[1])
    print("Done.")
