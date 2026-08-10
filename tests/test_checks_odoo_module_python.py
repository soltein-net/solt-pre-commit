# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module_python.py: ChecksOdooModulePython's Odoo-model
AST extraction (OdooFieldVisitor) and its field/method quality checks -
duplicate labels, inconsistent compute_sudo, tracking without mail.thread,
selection on related fields, missing string/help, and docstring quality."""

from types import SimpleNamespace

import pytest

from solt_pre_commit.checks_odoo_module_python import ChecksOdooModulePython


def _run_checks(tmp_path, source):
    module_file = tmp_path / "models.py"
    module_file.write_text(source, encoding="utf-8")
    manifest_datas = [{"filename": str(module_file)}]
    checks = ChecksOdooModulePython(manifest_datas, "test_module", odoo_version="17.0")
    checks.check_tracking_without_mail_thread()
    return checks


def _make_checks(tmp_path, source, config=None, odoo_version="17.0"):
    module_file = tmp_path / "models.py"
    module_file.write_text(source, encoding="utf-8")
    manifest_datas = [{"filename": str(module_file)}]
    return ChecksOdooModulePython(manifest_datas, "test_module", config=config, odoo_version=odoo_version)


def _only_model(checks):
    (model_key,) = checks.all_models.keys()
    return model_key, checks.all_models[model_key]


class TestTrackingWithoutMailThread:
    def test_tracking_without_mail_thread_flagged(self, tmp_path):
        checks = _run_checks(
            tmp_path,
            """
from odoo import fields, models


class MyModel(models.Model):
    _name = "my.model"
    _description = "My Model"

    state = fields.Selection([("draft", "Draft")], tracking=True)
""",
        )
        errors = checks.checks_errors["python_tracking_without_mail_thread"]
        assert len(errors) == 1
        assert "state" in errors[0]
        assert "my.model" in errors[0] or "MyModel" in errors[0]

    def test_tracking_with_mail_thread_not_flagged(self, tmp_path):
        checks = _run_checks(
            tmp_path,
            """
from odoo import fields, models


class MyModel(models.Model):
    _name = "my.model"
    _inherit = ["mail.thread"]
    _description = "My Model"

    state = fields.Selection([("draft", "Draft")], tracking=True)
""",
        )
        assert checks.checks_errors["python_tracking_without_mail_thread"] == []

    def test_inherit_only_extension_not_flagged(self, tmp_path):
        # `_inherit`-only classes extend an existing model that may already
        # provide mail.thread elsewhere - this file's view alone can't tell,
        # so it's excluded to avoid false positives.
        checks = _run_checks(
            tmp_path,
            """
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    my_field = fields.Char(tracking=True)
""",
        )
        assert checks.checks_errors["python_tracking_without_mail_thread"] == []

    def test_name_and_inherit_self_extension_not_flagged(self, tmp_path):
        # `_name = "x"` + `_inherit = ["x", "some.mixin"]` is the idiom used
        # to extend an existing model while adding a new mixin (e.g. crm.lead
        # + a tracking mixin). It re-declares the same model it inherits, so
        # it's an extension, not a new model - same as `_inherit`-only above.
        checks = _run_checks(
            tmp_path,
            """
from odoo import fields, models


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ["crm.lead", "some.mixin"]

    my_field = fields.Char(tracking=True)
""",
        )
        assert checks.checks_errors["python_tracking_without_mail_thread"] == []

    def test_no_tracking_not_flagged(self, tmp_path):
        checks = _run_checks(
            tmp_path,
            """
from odoo import fields, models


class MyModel(models.Model):
    _name = "my.model"
    _description = "My Model"

    state = fields.Selection([("draft", "Draft")])
""",
        )
        assert checks.checks_errors["python_tracking_without_mail_thread"] == []


class TestParsePythonFile:
    def test_valid_file_populates_models_fields_and_methods(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    name = fields.Char()\n\n    def do_x(self):\n        pass\n',
        )
        key, model_info = _only_model(checks)
        assert model_info["_name"] == "m"
        assert checks.checks_errors == {}
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["parse_error"] is None
        assert len(checks.all_fields[key]) == 1
        assert len(checks.all_methods[key]) == 1

    def test_syntax_error_records_python_syntax_error_and_empty_structures(self, tmp_path):
        checks = _make_checks(tmp_path, "def broken(:\n    pass\n")
        (message,) = checks.checks_errors["python_syntax_error"]
        assert "models.py" in message
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["parse_error"] is not None
        assert manifest_data["models"] == {}
        assert checks.all_models == {}


class TestOdooModelDetection:
    def test_name_attribute_marks_model_as_odoo_model(self, tmp_path):
        checks = _make_checks(tmp_path, 'class M:\n    _name = "m"\n')
        _, model_info = _only_model(checks)
        assert model_info["is_odoo_model"] is True

    def test_inherit_string_marks_model_and_sets_inherit_list(self, tmp_path):
        checks = _make_checks(tmp_path, 'class M:\n    _inherit = "mail.thread"\n')
        _, model_info = _only_model(checks)
        assert model_info["is_odoo_model"] is True
        assert model_info["_inherit"] == ["mail.thread"]
        assert model_info["has_mail_thread"] is True

    def test_inherit_list_with_multiple_mixins(self, tmp_path):
        checks = _make_checks(tmp_path, 'class M:\n    _inherit = ["mail.thread", "mail.activity.mixin"]\n')
        _, model_info = _only_model(checks)
        assert model_info["_inherit"] == ["mail.thread", "mail.activity.mixin"]

    def test_inherit_from_an_unsupported_expression_still_marks_odoo_model(self, tmp_path):
        # _extract_inherit only understands a string constant or a list of
        # constants - `_inherit = SOME_CONST` (a Name) falls through to [],
        # but is_odoo_model is still set True unconditionally just because
        # `_inherit` was assigned at all.
        checks = _make_checks(tmp_path, 'class M:\n    _name = "m"\n    _inherit = SOME_CONST\n')
        _, model_info = _only_model(checks)
        assert model_info["is_odoo_model"] is True
        assert model_info["_inherit"] == []

    def test_transient_model_base_class_marks_odoo_model_without_name_or_inherit(self, tmp_path):
        checks = _make_checks(tmp_path, "from odoo import models\n\n\nclass M(models.TransientModel):\n    pass\n")
        _, model_info = _only_model(checks)
        assert model_info["is_odoo_model"] is True

    def test_plain_class_with_no_odoo_indicators_is_not_an_odoo_model(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    x = 5\n")
        _, model_info = _only_model(checks)
        assert model_info["is_odoo_model"] is False


class TestFieldExtraction:
    def test_bare_field_type_call_without_fields_prefix_is_recognized(self, tmp_path):
        checks = _make_checks(tmp_path, "from odoo.fields import Char\n\n\nclass M:\n    x = Char()\n")
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["type"] == "Char"

    def test_non_call_assignment_is_not_a_field(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    x = 5\n    y = some_var\n")
        key, _ = _only_model(checks)
        assert checks.all_fields[key] == []

    def test_call_to_a_non_field_function_is_not_a_field(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    x = some_function()\n")
        key, _ = _only_model(checks)
        assert checks.all_fields[key] == []

    def test_translation_call_extracts_the_string_argument(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            'from odoo import fields\n\n\nclass M:\n    x = fields.Char(_("Name"))\n',
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["string"] == "Name"

    def test_lazy_translation_call_via_keyword_extracts_the_string_argument(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            'from odoo import fields\n\n\nclass M:\n    x = fields.Char(string=_lt("Name"))\n',
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["string"] == "Name"

    def test_variable_reference_is_returned_as_its_name(self, tmp_path):
        # _extract_string_value assumes a bare Name holds a valid string and
        # returns the variable's own name, not its runtime value.
        checks = _make_checks(tmp_path, "from odoo import fields\n\n\nclass M:\n    x = fields.Char(SOME_LABEL)\n")
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["string"] == "SOME_LABEL"

    def test_many2one_first_positional_is_comodel_second_is_string(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            'from odoo import fields\n\n\nclass M:\n    partner_id = fields.Many2one("res.partner", "Partner")\n',
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["comodel_name"] == "res.partner"
        assert field["string"] == "Partner"

    def test_comodel_name_keyword_is_also_recognized(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            'from odoo import fields\n\n\nclass M:\n    partner_id = fields.Many2many(comodel_name="res.partner")\n',
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["comodel_name"] == "res.partner"

    def test_compute_as_string_constant(self, tmp_path):
        checks = _make_checks(
            tmp_path, 'from odoo import fields\n\n\nclass M:\n    x = fields.Char(compute="_compute_x")\n'
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["compute"] == "_compute_x"

    def test_compute_as_name_reference(self, tmp_path):
        checks = _make_checks(
            tmp_path, "from odoo import fields\n\n\nclass M:\n    x = fields.Char(compute=_compute_x)\n"
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["compute"] == "_compute_x"

    def test_tracking_present_without_a_value_defaults_to_true(self, tmp_path):
        # tracking=True is the overwhelmingly common form, but tracking
        # given as a non-constant (e.g. tracking=SOME_FLAG) still defaults
        # to True via _get_bool_value's `default=True` for this keyword.
        checks = _make_checks(
            tmp_path, "from odoo import fields\n\n\nclass M:\n    x = fields.Char(tracking=SOME_FLAG)\n"
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["tracking"] is True

    def test_compute_sudo_present_without_a_value_defaults_to_none(self, tmp_path):
        checks = _make_checks(
            tmp_path, "from odoo import fields\n\n\nclass M:\n    x = fields.Char(compute_sudo=SOME_FLAG)\n"
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["compute_sudo"] is None

    def test_private_field_name_is_marked_private(self, tmp_path):
        checks = _make_checks(tmp_path, "from odoo import fields\n\n\nclass M:\n    _x = fields.Char()\n")
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["is_private"] is True


class TestMethodExtraction:
    def test_name_decorator(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    @some_decorator\n    def do_x(self):\n        pass\n")
        key, _ = _only_model(checks)
        (method,) = checks.all_methods[key]
        assert method["decorators"] == ["some_decorator"]

    def test_attribute_decorator(self, tmp_path):
        checks = _make_checks(
            tmp_path, "from odoo import api\n\n\nclass M:\n    @api.model\n    def do_x(self):\n        pass\n"
        )
        key, _ = _only_model(checks)
        (method,) = checks.all_methods[key]
        assert method["decorators"] == ["model"]

    def test_call_wrapping_a_name_decorator(self, tmp_path):
        checks = _make_checks(tmp_path, 'class M:\n    @parametrized("x")\n    def do_x(self):\n        pass\n')
        key, _ = _only_model(checks)
        (method,) = checks.all_methods[key]
        assert method["decorators"] == ["parametrized"]

    def test_call_wrapping_an_attribute_decorator(self, tmp_path):
        checks = _make_checks(
            tmp_path, 'from odoo import api\n\n\nclass M:\n    @api.depends("x")\n    def do_x(self):\n        pass\n'
        )
        key, _ = _only_model(checks)
        (method,) = checks.all_methods[key]
        assert method["decorators"] == ["depends"]

    def test_async_method_is_extracted(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    async def do_x(self):\n        pass\n")
        key, _ = _only_model(checks)
        (method,) = checks.all_methods[key]
        assert method["name"] == "do_x"

    def test_module_level_assignment_outside_any_class_does_not_crash(self, tmp_path):
        checks = _make_checks(tmp_path, "MODULE_CONST = 5\n\n\nclass M:\n    pass\n")
        assert checks.checks_errors == {}

    def test_module_level_function_outside_any_class_is_not_a_method(self, tmp_path):
        checks = _make_checks(tmp_path, "def helper():\n    pass\n\n\nclass M:\n    pass\n")
        key, _ = _only_model(checks)
        assert checks.all_methods[key] == []

    def test_tuple_unpacking_assignment_target_is_not_a_field(self, tmp_path):
        # visit_Assign only extracts fields from a plain `name = ...` target -
        # a tuple-unpacking assignment's targets aren't ast.Name nodes, so
        # they're skipped rather than raising.
        checks = _make_checks(
            tmp_path, "from odoo import fields\n\n\nclass M:\n    a, b = fields.Char(), fields.Char()\n"
        )
        key, _ = _only_model(checks)
        assert checks.all_fields[key] == []

    def test_dotted_attribute_translation_call_extracts_the_string_argument(self, tmp_path):
        # The Attribute-func branch of the translation check (e.g. a
        # dotted `mod._("text")` call) is a separate code path from the
        # bare-Name `_("text")` call.
        checks = _make_checks(
            tmp_path, 'from odoo import fields\n\n\nclass M:\n    x = fields.Char(translate_mod._("Name"))\n'
        )
        key, _ = _only_model(checks)
        (field,) = checks.all_fields[key]
        assert field["string"] == "Name"


class TestCheckDuplicateFieldLabels:
    def test_two_fields_with_the_same_label_are_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            '    a = fields.Char(string="Same Label")\n'
            '    b = fields.Char(string="Same Label")\n',
        )
        checks.check_duplicate_field_labels()
        (message,) = checks.checks_errors["python_duplicate_field_label"]
        assert "a, b" in message
        assert '"Same Label"' in message

    def test_fields_with_different_labels_are_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            '    a = fields.Char(string="One")\n'
            '    b = fields.Char(string="Two")\n',
        )
        checks.check_duplicate_field_labels()
        assert checks.checks_errors == {}


class TestCheckInconsistentComputeSudo:
    def test_differing_compute_sudo_on_same_compute_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            '    a = fields.Char(compute="_compute_x", compute_sudo=True)\n'
            '    b = fields.Char(compute="_compute_x", compute_sudo=False)\n',
        )
        checks.check_inconsistent_compute_sudo()
        (message,) = checks.checks_errors["python_inconsistent_compute_sudo"]
        assert "_compute_x" in message

    def test_matching_compute_sudo_on_same_compute_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            '    a = fields.Char(compute="_compute_x", compute_sudo=True)\n'
            '    b = fields.Char(compute="_compute_x", compute_sudo=True)\n',
        )
        checks.check_inconsistent_compute_sudo()
        assert checks.checks_errors == {}

    def test_single_field_using_a_compute_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    a = fields.Char(compute="_compute_x", compute_sudo=True)\n',
        )
        checks.check_inconsistent_compute_sudo()
        assert checks.checks_errors == {}


class TestCheckSelectionOnRelatedField:
    def test_related_field_with_selection_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            '    a = fields.Selection(related="partner_id.title", selection=[("x", "X")])\n',
        )
        checks.check_selection_on_related_field()
        (message,) = checks.checks_errors["python_selection_on_related"]
        assert "will be ignored" in message

    def test_related_field_without_selection_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    a = fields.Char(related="partner_id.name")\n',
        )
        checks.check_selection_on_related_field()
        assert checks.checks_errors == {}


class TestCheckFieldMissingString:
    def test_field_without_string_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    custom_field = fields.Char()\n',
        )
        checks.check_field_missing_string()
        (message,) = checks.checks_errors["python_field_missing_string"]
        assert "custom_field" in message

    def test_default_skip_field_name_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    name = fields.Char()\n',
        )
        checks.check_field_missing_string()
        assert checks.checks_errors == {}

    def test_private_field_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    _custom_field = fields.Char()\n',
        )
        checks.check_field_missing_string()
        assert checks.checks_errors == {}

    def test_related_field_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    custom_field = fields.Char(related="partner_id.name")\n',
        )
        checks.check_field_missing_string()
        assert checks.checks_errors == {}

    def test_field_on_a_non_odoo_model_is_not_reported(self, tmp_path):
        checks = _make_checks(tmp_path, "from odoo import fields\n\n\nclass M:\n    custom_field = fields.Char()\n")
        checks.check_field_missing_string()
        assert checks.checks_errors == {}


class TestCheckFieldMissingHelp:
    def test_field_without_help_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    custom_field = fields.Char()\n',
        )
        checks.check_field_missing_help()
        (message,) = checks.checks_errors["python_field_missing_help"]
        assert "custom_field" in message

    def test_field_with_help_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    custom_field = fields.Char(help="Explains the field")\n',
        )
        checks.check_field_missing_help()
        assert checks.checks_errors == {}

    def test_default_skip_field_name_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    name = fields.Char()\n',
        )
        checks.check_field_missing_help()
        assert checks.checks_errors == {}

    def test_private_field_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    _custom_field = fields.Char()\n',
        )
        checks.check_field_missing_help()
        assert checks.checks_errors == {}

    def test_related_field_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    custom_field = fields.Char(related="partner_id.name")\n',
        )
        checks.check_field_missing_help()
        assert checks.checks_errors == {}

    def test_field_on_a_non_odoo_model_is_not_reported(self, tmp_path):
        checks = _make_checks(tmp_path, "from odoo import fields\n\n\nclass M:\n    custom_field = fields.Char()\n")
        checks.check_field_missing_help()
        assert checks.checks_errors == {}


class TestCheckPublicMethodMissingDocstring:
    def test_public_method_without_docstring_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_x(self):\n        pass\n',
        )
        checks.check_public_method_missing_docstring()
        (message,) = checks.checks_errors["python_method_missing_docstring"]
        assert "do_x" in message

    def test_public_method_with_docstring_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_x(self):\n        """Does x."""\n        pass\n',
        )
        checks.check_public_method_missing_docstring()
        assert checks.checks_errors == {}

    def test_private_method_without_docstring_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def _do_x(self):\n        pass\n',
        )
        checks.check_public_method_missing_docstring()
        assert checks.checks_errors == {}

    def test_dunder_method_without_docstring_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def __str__(self):\n        pass\n',
        )
        checks.check_public_method_missing_docstring()
        assert checks.checks_errors == {}

    def test_method_on_non_odoo_model_is_not_reported(self, tmp_path):
        checks = _make_checks(tmp_path, "class M:\n    def do_x(self):\n        pass\n")
        checks.check_public_method_missing_docstring()
        assert checks.checks_errors == {}


class TestCheckDocstringQuality:
    def test_docstring_shorter_than_minimum_is_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_x(self):\n        """short"""\n        pass\n',
        )
        checks.check_docstring_quality()
        (message,) = checks.checks_errors["python_docstring_too_short"]
        assert "too short" in message

    def test_docstring_matching_the_method_name_is_uninformative(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_other_thing(self):\n        """Do other thing."""\n        pass\n',
        )
        checks.check_docstring_quality()
        (message,) = checks.checks_errors["python_docstring_uninformative"]
        assert "do_other_thing" in message

    def test_descriptive_docstring_is_not_reported(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_good(self):\n'
            '        """This has a properly descriptive docstring."""\n        pass\n',
        )
        checks.check_docstring_quality()
        assert checks.checks_errors == {}

    def test_method_without_a_docstring_is_not_checked_here(self, tmp_path):
        # check_docstring_quality only judges docstrings that exist -
        # missing docstrings are check_public_method_missing_docstring's job.
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_x(self):\n        pass\n',
        )
        checks.check_docstring_quality()
        assert checks.checks_errors == {}

    def test_private_method_docstring_is_not_checked(self, tmp_path):
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def _do_x(self):\n        """short"""\n        pass\n',
        )
        checks.check_docstring_quality()
        assert checks.checks_errors == {}

    def test_method_on_non_odoo_model_is_not_checked(self, tmp_path):
        checks = _make_checks(tmp_path, 'class M:\n    def do_x(self):\n        """short"""\n        pass\n')
        checks.check_docstring_quality()
        assert checks.checks_errors == {}


class TestConfigOverrides:
    def test_config_skip_string_fields_replaces_the_default_set(self, tmp_path):
        # skip_string_fields/skip_help_fields are replaced outright by a
        # provided config, not merged with the class defaults - "name" is in
        # DEFAULT_SKIP_STRING_FIELDS but not in this custom set, so it's
        # flagged, while the custom set's own entry is skipped.
        config = SimpleNamespace(
            skip_string_fields={"custom_skip"},
            skip_help_fields={"custom_skip"},
            skip_docstring_methods=set(),
            min_docstring_length=10,
        )
        checks = _make_checks(
            tmp_path,
            "from odoo import fields, models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            "    custom_skip = fields.Char()\n"
            "    name = fields.Char()\n",
            config=config,
        )
        checks.check_field_missing_string()
        (message,) = checks.checks_errors["python_field_missing_string"]
        assert '"name"' in message

    def test_config_skip_docstring_methods_is_merged_with_defaults(self, tmp_path):
        # Unlike skip_string_fields, skip_docstring_methods is unioned with
        # OdooFieldVisitor.DEFAULT_SKIP_DOCSTRING_METHODS, so __init__ etc.
        # remain exempt even when the config only adds its own method name.
        config = SimpleNamespace(
            skip_string_fields=set(),
            skip_help_fields=set(),
            skip_docstring_methods={"custom_exempt"},
            min_docstring_length=10,
        )
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n'
            "    def custom_exempt(self):\n        pass\n\n"
            "    def __init__(self):\n        pass\n",
            config=config,
        )
        checks.check_public_method_missing_docstring()
        assert checks.checks_errors == {}

    def test_config_min_docstring_length_is_applied(self, tmp_path):
        config = SimpleNamespace(
            skip_string_fields=set(),
            skip_help_fields=set(),
            skip_docstring_methods=set(),
            min_docstring_length=100,
        )
        checks = _make_checks(
            tmp_path,
            "from odoo import models\n\n\nclass M(models.Model):\n"
            '    _name = "m"\n\n    def do_x(self):\n'
            '        """This docstring is nowhere near a hundred characters long."""\n        pass\n',
            config=config,
        )
        checks.check_docstring_quality()
        (message,) = checks.checks_errors["python_docstring_too_short"]
        assert "min 100 chars" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
