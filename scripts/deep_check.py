import sys
import os
import importlib

def check_imports(start_dir):
    sys.path.insert(0, os.getcwd())
    
    error_count = 0
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.endswith(".py"):
                # Construct module name
                rel_path = os.path.relpath(os.path.join(root, file), os.getcwd())
                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"❌ Failed to import {module_name}: {e}")
                    error_count += 1
    
    if error_count == 0:
        print("✅ All modules imported successfully.")
    else:
        print(f"❌ Found {error_count} import errors.")
        sys.exit(1)

if __name__ == "__main__":
    check_imports("src")
