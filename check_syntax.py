import py_compile
try:
    py_compile.compile('src/bot/handlers/user_commands.py', doraise=True)
    print("Syntax OK")
except Exception as e:
    print(f"Syntax Error: {e}")
