"""Check Odoo model files for common issues."""
import ast
import re
import sys
from pathlib import Path
from typing import List, Optional, Set


REQUIRED_MODEL_ATTRS = {"_name"}
VALID_MODEL_ATTRS = {
    "_name",
    "_description",
    "_inherit",
    "_inherits",
    "_table",
    "_order",
    "_rec_name",
    "_auto",
    "_abstract",
    "_transient",
    "_log_access",
    "_check_company_auto",
    "_parent_name",
    "_parent_store",
    "_date_name",
    "_fold_name",
}

FIELD_TYPES = {
    "Binary",
    "Boolean",
    "Char",
    "Date",
    "Datetime",
    "Float",
    "Html",
    "Integer",
    "Many2many",
    "Many2one",
    "Monetary",
    "One2many",
    "Reference",
    "Selection",
    "Text",
}


def check_model_file(file_path: Path) -> List[str]:
    """Check model file for common Odoo issues."""
    errors = []
    warnings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]
    
    # Find model classes
    model_classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if it inherits from models.Model or similar
            for base in node.bases:
                if isinstance(base, ast.Attribute):
                    if base.attr in ("Model", "TransientModel", "AbstractModel"):
                        model_classes.append(node)
                        break
    
    if not model_classes:
        # No model classes found, which is OK for some files
        return []
    
    for cls in model_classes:
        cls_errors = check_model_class(cls, content)
        errors.extend([f"Class '{cls.name}': {err}" for err in cls_errors])
    
    return errors


def check_model_class(cls: ast.ClassDef, content: str) -> List[str]:
    """Check a single model class."""
    errors = []
    
    # Check for _name or _inherit
    has_name = False
    has_inherit = False
    has_description = False
    
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "_name":
                        has_name = True
                    elif target.id == "_inherit":
                        has_inherit = True
                    elif target.id == "_description":
                        has_description = True
    
    # Model must have either _name or _inherit
    if not has_name and not has_inherit:
        errors.append("Must have either '_name' or '_inherit' attribute")
    
    # If model has _name, it should have _description
    if has_name and not has_description:
        errors.append(
            "Model with '_name' should have '_description' for better UX"
        )
    
    # Check for fields without string attribute
    for node in cls.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Check if this is a field assignment
                    if isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Attribute):
                            if node.value.func.attr in FIELD_TYPES:
                                field_name = target.id
                                has_string = False
                                
                                # Check for string parameter
                                for keyword in node.value.keywords:
                                    if keyword.arg == "string":
                                        has_string = True
                                        break
                                
                                # Some fields should have string for better UX
                                if not has_string and not field_name.startswith("_"):
                                    # This is a warning, not an error
                                    pass
    
    # Check for SQL injection risks (direct SQL usage)
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if 'self.env.cr.execute' in line or 'self._cr.execute' in line:
            # Check if using string formatting (potential SQL injection)
            if '%' in line or '.format(' in line or 'f"' in line or "f'" in line:
                errors.append(
                    f"Line {i}: Potential SQL injection risk. "
                    "Use parameterized queries with execute(query, params)"
                )
    
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the models checker."""
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
        
        errors = check_model_file(file_path)
        
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
