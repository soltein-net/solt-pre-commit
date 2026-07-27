# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for python_tracking_without_mail_thread: tracking=True on a field of a
newly-declared model (_name set) that doesn't inherit any mail.thread mixin
should be flagged, since Odoo silently ignores tracking in that case."""

import pytest

from solt_pre_commit.checks_odoo_module_python import ChecksOdooModulePython


def _run_checks(tmp_path, source):
    module_file = tmp_path / "models.py"
    module_file.write_text(source, encoding="utf-8")
    manifest_datas = [{"filename": str(module_file)}]
    checks = ChecksOdooModulePython(manifest_datas, "test_module", odoo_version="17.0")
    checks.check_tracking_without_mail_thread()
    return checks


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
