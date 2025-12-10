"""Check for deprecated Odoo APIs and methods."""
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# Deprecated API patterns and their replacements
DEPRECATED_PATTERNS = [
    # Old API decorators
    (r'@api\.one', '@api.one is deprecated, use other decorators or remove'),
    (r'@api\.v7', '@api.v7 is deprecated, use new API methods'),
    (r'@api\.v8', '@api.v8 is deprecated, use new API methods'),
    (r'@api\.cr', '@api.cr is deprecated'),
    (r'@api\.uid', '@api.uid is deprecated'),
    (r'@api\.context', '@api.context is deprecated'),
    
    # Old API methods
    (r'\.browse\(cr,', 'Old API browse() is deprecated, use self.env[model].browse()'),
    (r'\.search\(cr,', 'Old API search() is deprecated, use self.env[model].search()'),
    (r'\.create\(cr,', 'Old API create() is deprecated, use self.env[model].create()'),
    (r'\.write\(cr,', 'Old API write() is deprecated, use record.write()'),
    (r'\.unlink\(cr,', 'Old API unlink() is deprecated, use record.unlink()'),
    
    # Deprecated field methods
    (r'fields\.related\(', 'fields.related() is deprecated, use related= parameter'),
    (r'fields\.function\(', 'fields.function() is deprecated, use @api.depends and compute='),
    
    # Deprecated imports
    (r'from openerp import', 'Import from "openerp" is deprecated, use "odoo" instead'),
    (r'import openerp\.', 'Import from "openerp" is deprecated, use "odoo" instead'),
    
    # Deprecated osv
    (r'from odoo\.osv import osv', 'osv is deprecated, use odoo.models instead'),
    (r'osv\.osv', 'osv.osv is deprecated, use models.Model'),
    (r'osv\.osv_memory', 'osv.osv_memory is deprecated, use models.TransientModel'),
    (r'osv\.except_osv', 'osv.except_osv is deprecated, use exceptions.UserError'),
    
    # Other deprecated patterns
    (r'\.sudo\(user_id\)', '.sudo(user_id) is deprecated, use .with_user(user_id)'),
    (r'\.suspend_security\(', '.suspend_security() is deprecated'),
    (r'pooler\.get_pool', 'pooler.get_pool is deprecated, use env registry'),
]


def check_deprecated_usage(file_path: Path) -> List[Tuple[int, str]]:
    """Check file for deprecated API usage."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [(0, f"Error reading file: {e}")]
    
    for line_num, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        
        for pattern, message in DEPRECATED_PATTERNS:
            if re.search(pattern, line):
                issues.append((line_num, f"{message} (found: '{line.strip()}')"))
    
    return issues


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the deprecated API checker."""
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
        
        issues = check_deprecated_usage(file_path)
        
        if issues:
            print(f"\n{file_path}:")
            for line_num, message in issues:
                print(f"  ❌ Line {line_num}: {message}")
            return_code = 1
        else:
            print(f"✓ {file_path}")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())
