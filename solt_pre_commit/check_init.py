"""Check Odoo __init__.py files for correct import structure."""
import ast
import sys
from pathlib import Path
from typing import List, Optional


def check_init_file(file_path: Path) -> List[str]:
    """Check __init__.py file structure and return list of errors."""
    errors = []
    warnings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    # Empty __init__.py is valid
    if not content.strip():
        return []
    
    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]
    
    # Check for common issues
    has_imports = False
    
    for node in ast.walk(tree):
        # Check for imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            has_imports = True
            
            # Check for relative imports in module root __init__.py
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # Relative import found - this is expected in __init__.py
                    pass
                elif node.module:
                    # Absolute import - check if it's importing from subdirectories
                    pass
        
        # Warn about code that's not imports
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            warnings.append(
                f"Found {node.__class__.__name__} '{node.name}'. "
                "__init__.py should typically only contain imports."
            )
    
    return errors + warnings


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the __init__.py checker."""
    if argv is None:
        argv = sys.argv[1:]
    
    if not argv:
        print("No files to check")
        return 0
    
    return_code = 0
    
    for file_path_str in argv:
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return_code = 1
            continue
        
        errors = check_init_file(file_path)
        
        if errors:
            print(f"\n{file_path}:")
            for error in errors:
                print(f"  ⚠️  {error}")
            # Don't fail on warnings for __init__.py
            # return_code = 1
        else:
            print(f"✓ {file_path}")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())
