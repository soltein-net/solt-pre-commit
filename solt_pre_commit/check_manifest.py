"""Check Odoo __manifest__.py files for validity and required fields."""
import ast
import sys
from pathlib import Path
from typing import List, Optional


# Required keys in Odoo manifest
REQUIRED_KEYS = {
    "name",
    "version",
    "category",
    "author",
    "depends",
}

# Valid keys in Odoo manifest
VALID_KEYS = {
    "name",
    "version",
    "summary",
    "description",
    "category",
    "author",
    "website",
    "license",
    "depends",
    "data",
    "demo",
    "qweb",
    "external_dependencies",
    "installable",
    "auto_install",
    "application",
    "sequence",
    "images",
    "price",
    "currency",
    "live_test_url",
    "support",
    "maintainers",
    "assets",
    "post_init_hook",
    "pre_init_hook",
    "uninstall_hook",
    "post_load",
    "development_status",
}


def check_manifest_structure(file_path: Path) -> List[str]:
    """Check manifest file structure and return list of errors."""
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [f"Syntax error in manifest: {e}"]
    
    # Find the manifest dictionary
    manifest_dict = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            manifest_dict = node
            break
    
    if manifest_dict is None:
        return ["No dictionary found in manifest file"]
    
    # Extract keys from the manifest
    manifest_keys = set()
    for key in manifest_dict.keys:
        if isinstance(key, ast.Constant):
            manifest_keys.add(key.value)
        elif isinstance(key, ast.Str):  # Python < 3.8 compatibility
            manifest_keys.add(key.s)
    
    # Check for required keys
    missing_keys = REQUIRED_KEYS - manifest_keys
    if missing_keys:
        errors.append(f"Missing required keys: {', '.join(sorted(missing_keys))}")
    
    # Check for unknown keys
    unknown_keys = manifest_keys - VALID_KEYS
    if unknown_keys:
        errors.append(f"Unknown keys (possible typo): {', '.join(sorted(unknown_keys))}")
    
    # Check version format
    for i, key in enumerate(manifest_dict.keys):
        if isinstance(key, (ast.Constant, ast.Str)):
            key_value = key.value if isinstance(key, ast.Constant) else key.s
            if key_value == "version":
                value = manifest_dict.values[i]
                if isinstance(value, (ast.Constant, ast.Str)):
                    version_str = value.value if isinstance(value, ast.Constant) else value.s
                    if not is_valid_version(version_str):
                        errors.append(
                            f"Invalid version format '{version_str}'. "
                            "Expected format: X.Y.Z.W.X (e.g., 16.0.1.0.0)"
                        )
    
    # Check depends is a list
    for i, key in enumerate(manifest_dict.keys):
        if isinstance(key, (ast.Constant, ast.Str)):
            key_value = key.value if isinstance(key, ast.Constant) else key.s
            if key_value == "depends":
                value = manifest_dict.values[i]
                if not isinstance(value, ast.List):
                    errors.append("'depends' must be a list")
    
    # Check installable is boolean if present
    for i, key in enumerate(manifest_dict.keys):
        if isinstance(key, (ast.Constant, ast.Str)):
            key_value = key.value if isinstance(key, ast.Constant) else key.s
            if key_value == "installable":
                value = manifest_dict.values[i]
                if not isinstance(value, (ast.Constant, ast.NameConstant)):
                    errors.append("'installable' must be a boolean (True/False)")
    
    return errors


def is_valid_version(version: str) -> bool:
    """Check if version follows Odoo version format."""
    parts = version.split('.')
    if len(parts) < 3:
        return False
    
    # Check if all parts are numeric
    try:
        [int(part) for part in parts]
    except ValueError:
        return False
    
    return True


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the manifest checker."""
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
        
        errors = check_manifest_structure(file_path)
        
        if errors:
            print(f"\n{file_path}:")
            for error in errors:
                print(f"  ❌ {error}")
            return_code = 1
        else:
            print(f"✓ {file_path}")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())
