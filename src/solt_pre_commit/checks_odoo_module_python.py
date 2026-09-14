# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Python validations for Odoo modules.

Supports Odoo versions: 17.0, 18.0, 19.0

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

from .config_loader import DEFAULT_ODOO_VERSION, MAIL_MIXINS_BY_VERSION


class OdooFieldVisitor(ast.NodeVisitor):
    """AST visitor to extract Odoo field and method information."""

    # Base field types available in all supported Odoo versions
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

    # Field types added in specific Odoo versions
    # Can be extended when new versions add new field types
    FIELD_TYPES_BY_VERSION = {
        "17.0": set(),
        "18.0": set(),
        "19.0": set(),
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

    def __init__(self, filename: str, odoo_version: str = DEFAULT_ODOO_VERSION):
        self.filename = filename
        self.odoo_version = odoo_version
        self.current_class: Optional[str] = None
        self.current_class_lineno: int = 0
        self.models: Dict[str, dict] = {}
        self.fields: Dict[str, List[dict]] = defaultdict(list)
        self.methods: Dict[str, List[dict]] = defaultdict(list)

        # Get field types for this version
        self.field_types = self.FIELD_TYPES.copy()
        version_types = self.FIELD_TYPES_BY_VERSION.get(odoo_version, set())
        self.field_types.update(version_types)

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
            "is_abstract_model": False,
        }

        # _name first, in its own pass - `_inherit = [..., _name]` (extend an
        # existing model by the name you already assigned two lines up,
        # without retyping the string - a real, documented Odoo idiom, see
        # e.g. solt_l10n_mx_edi_pos's PosOrder) needs _name's own literal
        # value resolved before _inherit is processed, regardless of which
        # assignment appears first in the class body.
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "_name" and isinstance(item.value, ast.Constant):
                        model_info["_name"] = item.value.value
                        model_info["is_odoo_model"] = True

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "_inherit":
                            model_info["_inherit"] = self._extract_inherit(item.value, model_info["_name"])
                            model_info["is_odoo_model"] = True
                        elif target.id == "_description" and isinstance(item.value, ast.Constant):
                            model_info["_description"] = item.value.value

        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if base.attr in ("Model", "TransientModel", "AbstractModel"):
                    model_info["is_odoo_model"] = True
                    if base.attr == "AbstractModel":
                        model_info["is_abstract_model"] = True

        model_info["has_mail_thread"] = self._check_mail_thread(model_info["_inherit"])
        self.models[node.name] = model_info

        self.generic_visit(node)
        self.current_class = None

    def _extract_inherit(self, node, own_name: Optional[str] = None) -> List[str]:
        """Extract _inherit values.

        Handles the `_inherit = [..., _name]` idiom: a bare `ast.Name` node
        referencing the class's own already-assigned `_name` (rather than
        repeating the string) is substituted with `own_name` when its id is
        `_name`. Without this, that element was silently dropped (it isn't
        an ast.Constant) - which then misclassified a plain `_inherit`-only
        extension of an existing model as a brand-new model definition
        downstream (check_tracking_without_mail_thread's own `is_new_model`
        test is exactly "_name not in _inherit", which a dropped element
        defeats).
        """
        if isinstance(node, ast.Constant):
            return [node.value]
        elif isinstance(node, ast.List):
            values = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant):
                    values.append(elt.value)
                elif isinstance(elt, ast.Name) and elt.id == "_name" and own_name is not None:
                    values.append(own_name)
            return values
        return []

    def _check_mail_thread(self, inherit_list: List[str]) -> bool:
        """Check if model inherits from mail.thread.

        Uses version-specific mail mixins from config.
        """
        mail_mixins = MAIL_MIXINS_BY_VERSION.get(self.odoo_version, MAIL_MIXINS_BY_VERSION[DEFAULT_ODOO_VERSION])
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

        # Variable reference: MY_CONSTANT (assume it holds a valid string)
        if isinstance(node, ast.Name):
            return node.id

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

    def __init__(self, manifest_datas: List[dict], module_name: str, config=None, odoo_version: str = None):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.config = config
        self.odoo_version = odoo_version or DEFAULT_ODOO_VERSION
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

        # Built after every file in the module has been parsed (not
        # incrementally per-file) - resolving an _inherit chain needs every
        # model this module declares to already be registered, regardless of
        # which file defines which link in the chain. Only models with a
        # `_name` are registrable targets; a plain `_inherit`-only extension
        # doesn't introduce a new resolvable name.
        self._name_to_model: Dict[str, dict] = {mi["_name"]: mi for mi in self.all_models.values() if mi.get("_name")}

    def _parse_python_file(self, manifest_data: dict):
        """Parse a Python file and extract information."""
        filename = manifest_data["filename"]
        try:
            with open(filename, "r", encoding="UTF-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=filename)
            visitor = OdooFieldVisitor(filename, odoo_version=self.odoo_version)
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

    def _resolves_to_mail_thread(self, inherit_list: List[str], _visited: Optional[Set[str]] = None) -> Optional[bool]:
        """Whether `inherit_list` resolves to mail.thread, directly or
        transitively through another model this SAME module also declares.

        Returns True (has it), False (definitively does not - every name in
        the chain resolved to a model this module also declares, and none of
        them had it), or None (inconclusive - the chain includes a name this
        single-module scan cannot resolve: a mixin declared in a *different*
        module, or a bare Odoo core model this module never redeclares).

        None deliberately does NOT count as "flag it" - see
        check_tracking_without_mail_thread's own docstring for why treating
        an unresolvable name as "assume no mail.thread" produces exactly the
        false positives this method exists to stop (e.g. a custom mixin
        defined in a dependency module that itself inherits mail.thread,
        invisible to a scan scoped to one module's own files).
        """
        visited = _visited if _visited is not None else set()
        mail_mixins = MAIL_MIXINS_BY_VERSION.get(self.odoo_version, MAIL_MIXINS_BY_VERSION[DEFAULT_ODOO_VERSION])
        if set(inherit_list) & mail_mixins:
            return True

        inconclusive = False
        for name in inherit_list:
            if name in visited:
                continue  # cycle guard - shouldn't happen in real Odoo code, cheap to guard anyway
            target = self._name_to_model.get(name)
            if target is None:
                inconclusive = True
                continue
            visited.add(name)
            result = self._resolves_to_mail_thread(target.get("_inherit", []), visited)
            if result:
                return True
            if result is None:
                inconclusive = True
        return None if inconclusive else False

    def check_tracking_without_mail_thread(self):
        """Detect tracking=True on fields of models that don't inherit mail.thread.

        Odoo Warning: tracking value will be ignored

        Only applies to classes that declare a brand-new model: a
        `_inherit`-only extension of an existing core/other-module model
        (e.g. `_inherit = "sale.order"`) commonly doesn't repeat the mixin
        because the base model already provides it elsewhere, so flagging
        those would be mostly false positives from this file's perspective.

        This also covers the `_name = "x"` + `_inherit = ["x", "some.mixin"]`
        idiom used to extend an existing model while adding a new mixin: even
        though `_name` is set there, the class isn't defining a new model — it
        is re-declaring the same model it inherits, so it's an extension too.
        Only a `_name` that is NOT among the model's own `_inherit` values
        marks an actual new model definition (`_inherit` empty or naming
        something else entirely).

        Two further carve-outs, added after real false positives shipped
        (see soltein-net/solt-suite#660's review):

        - AbstractModel classes are skipped entirely, even when they declare
          a brand-new model name. An AbstractModel is never instantiated on
          its own - it only ever contributes fields to whatever OTHER
          concrete model composes it later via `_inherit` alongside
          something that may already have mail.thread. Whether tracking
          "works" depends entirely on that future composition, which this
          static, per-file scan cannot see - the common, deliberate pattern
          (a mixin doesn't declare mail.thread itself, expects the consumer
          to already have it) would otherwise dominate the findings.
        - `_resolves_to_mail_thread` (not a flat `has_mail_thread` lookup)
          walks the model's `_inherit` chain transitively through every
          other model this SAME module declares, and treats a name it can't
          resolve (e.g. a mixin from a *different* module) as inconclusive
          rather than "doesn't have it" - both are real cases that produced
          false positives before this fix: a same-module custom mixin that
          itself inherits mail.thread, and a cross-module one.
        """
        for model_key, fields in self.all_fields.items():
            model_info = self.all_models[model_key]
            filename = model_info["filename"]

            if model_info.get("is_abstract_model"):
                continue

            is_new_model = model_info.get("_name") and model_info["_name"] not in model_info.get("_inherit", [])
            if not is_new_model:
                continue

            if self._resolves_to_mail_thread(model_info.get("_inherit", [])) is not False:
                continue

            for field in fields:
                if field.get("tracking"):
                    self.checks_errors["python_tracking_without_mail_thread"].append(
                        f'{filename}:{field["lineno"]} Field "{field["name"]}" has tracking '
                        f'but model "{model_info["name"]}" does not inherit mail.thread (will be ignored)'
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
