
import os
import py_compile

def check_syntax(start_path):
    print(f"Checking syntax in {start_path}...")
    errors = []
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    py_compile.compile(full_path, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(str(e))
                    print(f"❌ Error in {full_path}: {e}")
                except Exception as e:
                    errors.append(f"{full_path}: {e}")
                    print(f"❌ Error in {full_path}: {e}")
    
    if not errors:
        print("✅ No syntax errors found.")
    else:
        print(f"❌ Found {len(errors)} errors.")

if __name__ == "__main__":
    check_syntax(".")
