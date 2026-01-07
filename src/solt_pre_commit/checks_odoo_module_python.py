# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Python validations for Odoo modules.

Detects patterns that generate runtime warnings:
- Fields with same string/label in the same model
- Inconsistent compute_sudo on related computed fields
- tracking=True on models without mail.thread
- selection on related fields
- Fields without string or help
- Public methods without docstring
"""

import ast
from collections import defaultdict
from typing import Dict, List, Optional, Set


class OdooFieldVisitor(ast.NodeVisitor):
    """AST visitor to extract Odoo field and method information."""

    FIELD_TYPES = {
        "Char",
        "Text",
        "Html",
        "Integer",
        "Float",
        "Monetary",
        "Boolean",
        "Date",
        "Datetime",
        "Binary",
        "Selection",
        "Many2one",
        "One2many",
        "Many2many",
        "Reference",
        "Image",
        "Json",
        "Properties",
        "PropertiesDefinition",
    }

    DEFAULT_SKIP_DOCSTRING_METHODS = {
        "__init__",
        "__str__",
        "__repr__",
        "__len__",
        "__bool__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__iter__",
        "__next__",
        "__contains__",
        "__call__",
        "__enter__",
        "__exit__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__hash__",
        "__format__",
    }

    def __init__(self, filename: str):
        self.filename = filename
        self.current_class: Optional[str] = None
        self.current_class_lineno: int = 0
        self.models: Dict[str, dict] = {}
        self.fields: Dict[str, List[dict]] = defaultdict(list)
        self.methods: Dict[str, List[dict]] = defaultdict(list)

    def visit_ClassDef(self, node: ast.ClassDef):  # noqa: N802
        """Visit class definitions to detect Odoo models."""
        self.current_class = node.name
        self.current_class_lineno = node.lineno

        model_info = {
            "name": node.name,
            "lineno": node.lineno,
            "_name": None,
            "_inherit": [],
            "_description": None,
            "has_mail_thread": False,
            "is_odoo_model": False,
        }

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "_name" and isinstance(item.value, ast.Constant):
                            model_info["_name"] = item.value.value
                            model_info["is_odoo_model"] = True
                        elif target.id == "_inherit":
                            model_info["_inherit"] = self._extract_inherit(item.value)
                            model_info["is_odoo_model"] = True
                        elif target.id == "_description" and isinstance(item.value, ast.Constant):
                            model_info["_description"] = item.value.value

        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr in ("Model", "TransientModel", "AbstractModel"):
                    model_info["is_odoo_model"] = True

        model_info["has_mail_thread"] = self._check_mail_thread(model_info["_inherit"])
        self.models[node.name] = model_info

        self.generic_visit(node)
        self.current_class = None

    def _extract_inherit(self, node) -> List[str]:
        """Extract _inherit values."""
        if isinstance(node, ast.Constant):
            return [node.value]
        elif isinstance(node, ast.List):
            return [elt.value for elt in node.elts if isinstance(elt, ast.Constant)]
        return []

    def _check_mail_thread(self, inherit_list: List[str]) -> bool:
        """Check if model inherits from mail.thread."""
        mail_mixins = {
            "mail.thread",
            "mail.activity.mixin",
            "mail.thread.main.attachment",
            "mail.thread.cc",
            "mail.thread.blacklist",
        }
        return bool(set(inherit_list) & mail_mixins)

    def visit_FunctionDef(self, node: ast.FunctionDef):  # noqa: N802
        self._process_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # noqa: N802
        self._process_function(node)
        self.generic_visit(node)

    def _process_function(self, node):
        """Process a function/method node."""
        if not self.current_class:
            return

        method_info = {
            "name": node.name,
            "lineno": node.lineno,
            "is_private": node.name.startswith("_"),
            "is_magic": node.name.startswith("__") and node.name.endswith("__"),
            "has_docstring": False,
            "docstring": None,
            "decorators": [],
        }

        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            method_info["has_docstring"] = True
            method_info["docstring"] = node.body[0].value.value

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                method_info["decorators"].append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                method_info["decorators"].append(decorator.attr)
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    method_info["decorators"].append(decorator.func.id)
                elif isinstance(decorator.func, ast.Attribute):
                    method_info["decorators"].append(decorator.func.attr)

        self.methods[self.current_class].append(method_info)

    def visit_Assign(self, node: ast.Assign):  # noqa: N802
        """Visit assignments to detect Odoo fields."""
        if not self.current_class:
            self.generic_visit(node)
            return

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            field_info = self._extract_field_info(target.id, node.value, node.lineno)
            if field_info:
                self.fields[self.current_class].append(field_info)

        self.generic_visit(node)

    def _extract_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node.

        Handles:
        - Direct string: "My String"
        - Translation call: _("My String")
        - Lazy translation: _lt("My String")

        Does NOT handle:
        - Variables: MY_CONSTANT
        - Complex expressions
        """
        # Direct string constant
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        # Translation function call: _("string") or _lt("string")
        if isinstance(node, ast.Call):
            func = node.func
            # Check if it's a translation function
            is_translation = False
            if isinstance(func, ast.Name) and func.id in ("_", "_lt"):
                is_translation = True
            elif isinstance(func, ast.Attribute) and func.attr in ("_", "_lt"):
                is_translation = True

            if is_translation and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    return first_arg.value

        return None

    def _extract_field_info(self, field_name: str, value_node, lineno: int) -> Optional[dict]:
        """Extract information from an Odoo field."""
        if not isinstance(value_node, ast.Call):
            return None

        func = value_node.func
        field_type = None

        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "fields":
                field_type = func.attr
        elif isinstance(func, ast.Name) and func.id in self.FIELD_TYPES:
            field_type = func.id

        if not field_type or field_type not in self.FIELD_TYPES:
            return None

        field_info = {
            "name": field_name,
            "type": field_type,
            "lineno": lineno,
            "string": None,
            "help": None,
            "related": None,
            "compute": None,
            "compute_sudo": None,
            "tracking": None,
            "selection": None,
            "comodel_name": None,
            "is_private": field_name.startswith("_"),
        }

        # Handle positional arguments
        # For relational fields: first arg is comodel_name, second arg is string
        # For other fields: first arg is string
        if value_node.args:
            first_arg = value_node.args[0]
            first_value = self._extract_string_value(first_arg)

            if first_value is not None:
                if field_type in ("Many2one", "One2many", "Many2many"):
                    field_info["comodel_name"] = first_value
                    # Check for second positional argument (string) in relational fields
                    if len(value_node.args) >= 2:
                        second_arg = value_node.args[1]
                        second_value = self._extract_string_value(second_arg)
                        if second_value is not None:
                            field_info["string"] = second_value
                else:
                    field_info["string"] = first_value

        # Handle keyword arguments
        for kw in value_node.keywords:
            if kw.arg == "string":
                string_value = self._extract_string_value(kw.value)
                if string_value is not None:
                    field_info["string"] = string_value
            elif kw.arg == "help":
                help_value = self._extract_string_value(kw.value)
                if help_value is not None:
                    field_info["help"] = help_value
            elif kw.arg == "related" and isinstance(kw.value, ast.Constant):
                field_info["related"] = kw.value.value
            elif kw.arg == "compute":
                if isinstance(kw.value, ast.Constant):
                    field_info["compute"] = kw.value.value
                elif isinstance(kw.value, ast.Name):
                    field_info["compute"] = kw.value.id
            elif kw.arg == "compute_sudo":
                field_info["compute_sudo"] = self._get_bool_value(kw.value)
            elif kw.arg == "tracking":
                field_info["tracking"] = self._get_bool_value(kw.value, default=True)
            elif kw.arg == "selection":
                field_info["selection"] = True
            elif kw.arg == "comodel_name":
                comodel_value = self._extract_string_value(kw.value)
                if comodel_value is not None:
                    field_info["comodel_name"] = comodel_value

        return field_info

    def _get_bool_value(self, node, default=None):
        if isinstance(node, ast.Constant):
            return node.value
        return default


class ChecksOdooModulePython:
    """Python validator for Odoo modules."""

    DEFAULT_SKIP_STRING_FIELDS: Set[str] = {
        "active",
        "name",
        "display_name",
        "sequence",
        "company_id",
        "currency_id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "message_ids",
        "message_follower_ids",
        "activity_ids",
    }

    DEFAULT_SKIP_HELP_FIELDS: Set[str] = {
        "active",
        "name",
        "display_name",
        "sequence",
        "company_id",
        "currency_id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "message_ids",
        "message_follower_ids",
        "activity_ids",
    }

    def __init__(self, manifest_datas: List[dict], module_name: str, config=None):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.config = config
        self.checks_errors = defaultdict(list)
        self.all_models: Dict[str, dict] = {}
        self.all_fields: Dict[str, List[dict]] = defaultdict(list)
        self.all_methods: Dict[str, List[dict]] = defaultdict(list)

        # Load settings from config or use defaults
        if config:
            self.skip_string_fields = config.skip_string_fields
            self.skip_help_fields = config.skip_help_fields
            self.skip_docstring_methods = (
                config.skip_docstring_methods | OdooFieldVisitor.DEFAULT_SKIP_DOCSTRING_METHODS
            )
            self.min_docstring_length = config.min_docstring_length
        else:
            self.skip_string_fields = self.DEFAULT_SKIP_STRING_FIELDS
            self.skip_help_fields = self.DEFAULT_SKIP_HELP_FIELDS
            self.skip_docstring_methods = OdooFieldVisitor.DEFAULT_SKIP_DOCSTRING_METHODS
            self.min_docstring_length = 10

        for manifest_data in manifest_datas:
            self._parse_python_file(manifest_data)

    def _parse_python_file(self, manifest_data: dict):
        """Parse a Python file and extract information."""
        filename = manifest_data["filename"]
        try:
            with open(filename, "r", encoding="UTF-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=filename)
            visitor = OdooFieldVisitor(filename)
            visitor.visit(tree)

            for class_name, model_info in visitor.models.items():
                key = f"{filename}:{class_name}"
                model_info["filename"] = filename
                self.all_models[key] = model_info
                self.all_fields[key] = visitor.fields.get(class_name, [])
                self.all_methods[key] = visitor.methods.get(class_name, [])

            manifest_data.update(
                {
                    "models": visitor.models,
                    "fields": visitor.fields,
                    "methods": visitor.methods,
                    "parse_error": None,
                }
            )

        except SyntaxError as err:
            manifest_data.update(
                {
                    "models": {},
                    "fields": {},
                    "methods": {},
                    "parse_error": err,
                }
            )
            self.checks_errors["python_syntax_error"].append(f"{filename}:{err.lineno} {err.msg}")

    def check_duplicate_field_labels(self):
        """Detect fields with same string/label in the same model.

        Odoo Warning: Two fields (field1, field2) have the same label
        """
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            labels: Dict[str, List[dict]] = defaultdict(list)
            for field in fields:
                label = field.get("string")
                if label:
                    labels[label].append(field)

            for label, label_fields in labels.items():
                if len(label_fields) >= 2:
                    field_names = ", ".join(f["name"] for f in label_fields)
                    first_field = label_fields[0]
                    self.checks_errors["python_duplicate_field_label"].append(
                        f'{filename}:{first_field["lineno"]} Fields ({field_names}) have the same label: "{label}"'
                    )

    def check_inconsistent_compute_sudo(self):
        """Detect inconsistent compute_sudo on fields with same compute.

        Odoo Warning: inconsistent 'compute_sudo' for computed fields
        """
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            compute_groups: Dict[str, List[dict]] = defaultdict(list)
            for field in fields:
                compute = field.get("compute")
                if compute:
                    compute_groups[compute].append(field)

            for compute_method, compute_fields in compute_groups.items():
                if len(compute_fields) < 2:
                    continue

                sudo_values = {f.get("compute_sudo") for f in compute_fields}

                if len(sudo_values) > 1:
                    field_names = ", ".join(f["name"] for f in compute_fields)
                    first_field = compute_fields[0]
                    self.checks_errors["python_inconsistent_compute_sudo"].append(
                        f"{filename}:{first_field['lineno']} "
                        f"Inconsistent 'compute_sudo' for fields ({field_names}) "
                        f"using compute='{compute_method}'"
                    )

    def check_selection_on_related_field(self):
        """Detect selection on related fields.

        Odoo Warning: selection attribute will be ignored as field is related
        """
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            for field in fields:
                if field.get("related") and field.get("selection"):
                    self.checks_errors["python_selection_on_related"].append(
                        f"{filename}:{field['lineno']} "
                        f'Field "{field["name"]}" is related but has selection '
                        f"(will be ignored)"
                    )

    def check_field_missing_string(self):
        """Detect fields without string attribute."""
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            if not model_info.get("is_odoo_model"):
                continue

            for field in fields:
                if field.get("is_private"):
                    continue
                if field["name"] in self.skip_string_fields:
                    continue
                if field.get("related"):
                    continue

                if not field.get("string"):
                    self.checks_errors["python_field_missing_string"].append(
                        f'{filename}:{field["lineno"]} Field "{field["name"]}" is missing string attribute'
                    )

    def check_field_missing_help(self):
        """Detect fields without help attribute."""
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            if not model_info.get("is_odoo_model"):
                continue

            for field in fields:
                if field.get("is_private"):
                    continue
                if field["name"] in self.skip_help_fields:
                    continue
                if field.get("related"):
                    continue

                if not field.get("help"):
                    self.checks_errors["python_field_missing_help"].append(
                        f'{filename}:{field["lineno"]} Field "{field["name"]}" is missing help attribute'
                    )

    def check_public_method_missing_docstring(self):
        """Detect public methods without docstring."""
        for model_key, methods in self.all_methods.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            if not model_info.get("is_odoo_model"):
                continue

            for method in methods:
                if method.get("is_private"):
                    continue
                if method["name"] in self.skip_docstring_methods:
                    continue

                if not method.get("has_docstring"):
                    self.checks_errors["python_method_missing_docstring"].append(
                        f'{filename}:{method["lineno"]} Public method "{method["name"]}" is missing docstring'
                    )

    def check_docstring_quality(self):
        """Verify basic docstring quality."""
        for model_key, methods in self.all_methods.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            if not model_info.get("is_odoo_model"):
                continue

            for method in methods:
                if method.get("is_private"):
                    continue
                if not method.get("has_docstring"):
                    continue

                docstring = method.get("docstring", "")

                if len(docstring.strip()) < self.min_docstring_length:
                    self.checks_errors["python_docstring_too_short"].append(
                        f"{filename}:{method['lineno']} "
                        f'Method "{method["name"]}" has too short docstring '
                        f"(min {self.min_docstring_length} chars)"
                    )

                method_name_clean = method["name"].replace("_", " ").strip().lower()
                docstring_clean = docstring.strip().lower().rstrip(".")
                if docstring_clean == method_name_clean:
                    self.checks_errors["python_docstring_uninformative"].append(
                        f'{filename}:{method["lineno"]} Method "{method["name"]}" has uninformative docstring'
                    )
