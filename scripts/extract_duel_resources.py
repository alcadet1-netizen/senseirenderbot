import ast
import os

SOURCE_FILE = r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\services\duel_service.py"
DEST_FILE = r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\services\duel_resources.py"

def process():
    print(f"Processing {SOURCE_FILE}...")
    if not os.path.exists(SOURCE_FILE):
        print(f"Source file not found: {SOURCE_FILE}")
        return

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except Exception as e:
        print(f"Error parsing source file: {e}")
        return

    resources = {}
    target_names = ["ARENAS", "DODGE_GAGS_L", "DODGE_GAGS_R", "ATTACK_GAGS_L", "ATTACK_GAGS_R", "HIT_GAGS", "MISS_GAGS"]
    to_remove_ranges = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_names:
                    print(f"Found {target.id}")
                    try:
                        # ast.literal_eval is safe for basic types
                        value = ast.literal_eval(node.value)
                        seen = set()
                        deduped = []
                        for item in value:
                            item_key = item if isinstance(item, str) else tuple(item)
                            if item_key not in seen:
                                seen.add(item_key)
                                deduped.append(item)
                        
                        resources[target.id] = deduped
                        
                        # Use lineno and end_lineno
                        if hasattr(node, 'end_lineno'):
                            to_remove_ranges.append((node.lineno, node.end_lineno))
                        else:
                            # Fallback for older python if needed, though 3.13 should have it
                            print(f"Warning: node has no end_lineno: {node}")
                            
                    except Exception as e:
                        print(f"Error extracting {target.id}: {e}")

    # Create resources file content
    resources_content = '"""\nDuel resources (arenas, gags).\nAutomatically extracted and deduplicated.\n"""\n\n'
    
    for name in target_names:
        if name in resources:
            resources_content += f"{name} = [\n"
            for item in resources[name]:
                resources_content += f"    {repr(item)},\n"
            resources_content += "]\n\n"

    with open(DEST_FILE, "w", encoding="utf-8") as f:
        f.write(resources_content)
    print(f"Created {DEST_FILE}")

    # Remove from source file
    lines = content.splitlines(keepends=True)
    new_lines = []
    
    to_remove_ranges.sort()
    
    # We need to be careful not to remove lines multiple times or mess up indices.
    # We can use a set of line numbers to exclude.
    lines_to_exclude = set()
    for start, end in to_remove_ranges:
        for i in range(start, end + 1):
            lines_to_exclude.add(i)

    for i, line in enumerate(lines, start=1):
        if i not in lines_to_exclude:
            new_lines.append(line)
            
    # Write back to source file
    with open(SOURCE_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"Updated {SOURCE_FILE}")

if __name__ == "__main__":
    process()
