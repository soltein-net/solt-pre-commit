"""Check Odoo XML files for syntax and common issues."""
import sys
from pathlib import Path
from typing import List, Optional

try:
    from lxml import etree
except ImportError:
    etree = None


ODOO_XML_ROOTS = {
    "odoo",
    "openerp",  # Legacy
    "data",
}

COMMON_ODOO_TAGS = {
    "record",
    "template",
    "menuitem",
    "report",
    "delete",
    "function",
    "act_window",
    "url",
}


def check_xml_file(file_path: Path) -> List[str]:
    """Check XML file for Odoo-specific issues."""
    errors = []
    
    if etree is None:
        return ["lxml is not installed. Install it with: pip install lxml"]
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    # Parse XML with secure defaults to prevent XXE attacks
    try:
        parser = etree.XMLParser(resolve_entities=False)
        tree = etree.fromstring(content, parser)
    except etree.XMLSyntaxError as e:
        return [f"XML syntax error: {e}"]
    
    # Check root element
    root_tag = tree.tag
    if root_tag not in ODOO_XML_ROOTS:
        errors.append(
            f"Root element is '{root_tag}', expected one of: {', '.join(ODOO_XML_ROOTS)}"
        )
    
    # Check for records without id
    for record in tree.findall(".//record"):
        if "id" not in record.attrib:
            model = record.attrib.get("model", "unknown")
            errors.append(f"Record without 'id' attribute (model: {model})")
        
        # Check for records without model
        if "model" not in record.attrib:
            record_id = record.attrib.get("id", "unknown")
            errors.append(f"Record without 'model' attribute (id: {record_id})")
    
    # Check for fields in records
    for record in tree.findall(".//record"):
        fields = record.findall("field")
        if not fields:
            record_id = record.attrib.get("id", "unknown")
            errors.append(f"Record '{record_id}' has no fields")
        
        # Check field attributes
        for field in fields:
            if "name" not in field.attrib:
                record_id = record.attrib.get("id", "unknown")
                errors.append(f"Field in record '{record_id}' missing 'name' attribute")
    
    # Check for templates without id
    for template in tree.findall(".//template"):
        if "id" not in template.attrib:
            errors.append("Template without 'id' attribute")
    
    # Check for menuitem without proper attributes
    for menuitem in tree.findall(".//menuitem"):
        if "id" not in menuitem.attrib:
            errors.append("Menuitem without 'id' attribute")
        
        # Check if it has name or action
        if "name" not in menuitem.attrib and "action" not in menuitem.attrib:
            menuitem_id = menuitem.attrib.get("id", "unknown")
            errors.append(
                f"Menuitem '{menuitem_id}' should have either 'name' or 'action' attribute"
            )
    
    # Check for duplicate IDs in the same file
    all_ids = []
    for elem in tree.iter():
        if "id" in elem.attrib:
            elem_id = elem.attrib["id"]
            if elem_id in all_ids:
                errors.append(f"Duplicate ID in file: '{elem_id}'")
            all_ids.append(elem_id)
    
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the XML checker."""
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
        
        errors = check_xml_file(file_path)
        
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
