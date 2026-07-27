# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module_xml_advanced.py: ChecksOdooModuleXMLAdvanced's
deprecated active_id/t-raw usage, alert-role, hardcoded-id, and
duplicate-view-priority detectors."""

from solt_pre_commit.checks_odoo_module_xml_advanced import ChecksOdooModuleXMLAdvanced


def _manifest_data(path):
    return {"filename": str(path)}


def _write_xml(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return path


class TestParseXmlFile:
    def test_valid_xml_populates_tree_with_no_parse_error(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", "<odoo/>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["tree"] is not None
        assert manifest_data["parse_error"] is None

    def test_malformed_xml_leaves_tree_none_and_records_parse_error(self, tmp_path):
        path = _write_xml(tmp_path, "bad.xml", "<odoo><unclosed>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["tree"] is None
        assert manifest_data["parse_error"] is not None

    def test_missing_file_leaves_tree_none_and_records_parse_error(self, tmp_path):
        missing = tmp_path / "does_not_exist.xml"
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(missing)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["tree"] is None
        assert manifest_data["parse_error"] is not None

    def test_all_checks_are_no_ops_when_file_failed_to_parse(self, tmp_path):
        missing = tmp_path / "does_not_exist.xml"
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(missing)], "my_module")
        checks.check_deprecated_active_id_usage()
        checks.check_alert_missing_role()
        checks.check_t_raw_usage()
        checks.check_hardcoded_ids()
        checks.check_duplicate_view_priority()
        assert checks.checks_errors == {}


class TestCheckDeprecatedActiveIdUsage:
    def test_detects_active_id_in_context_attribute(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><field name="x" context="{\'default_partner_id\': active_id}"/></odoo>',
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_deprecated_active_id_usage()
        (message,) = checks.checks_errors["xml_deprecated_active_id_usage"]
        assert 'Deprecated use of "active_id"' in message
        assert 'context="' in message

    def test_detects_active_ids_and_active_model_in_domain(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            "<odoo><field domain=\"[('id', 'in', active_ids), ('m', '=', active_model)]\"/></odoo>",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_deprecated_active_id_usage()
        messages = checks.checks_errors["xml_deprecated_active_id_usage"]
        assert len(messages) == 2

    def test_word_boundary_excludes_similarly_named_variables(self, tmp_path):
        # The regex is \b(active_id|active_ids|active_model)\b - "active_idx"
        # doesn't have a word-boundary between "id" and "x", so it's not a
        # false positive.
        path = _write_xml(tmp_path, "a.xml", "<odoo><field context=\"{'x': active_idx}\"/></odoo>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_deprecated_active_id_usage()
        assert checks.checks_errors == {}

    def test_attributes_outside_the_search_list_are_not_checked(self, tmp_path):
        # "context", "domain", "attrs", "options", "filter_domain", "default",
        # and "eval" are checked; an arbitrary attribute like "help" is not.
        path = _write_xml(tmp_path, "a.xml", '<odoo><field help="active_id is deprecated"/></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_deprecated_active_id_usage()
        assert checks.checks_errors == {}


class TestCheckAlertMissingRole:
    def test_alert_without_role_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><div class="alert alert-warning">x</div></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_alert_missing_role()
        (message,) = checks.checks_errors["xml_alert_missing_role"]
        assert "should have" in message

    def test_alert_with_valid_role_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><div class="alert alert-warning" role="alert">x</div></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_alert_missing_role()
        assert checks.checks_errors == {}

    def test_alert_with_invalid_role_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><div class="alert alert-warning" role="bogus">x</div></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_alert_missing_role()
        assert len(checks.checks_errors["xml_alert_missing_role"]) == 1

    def test_alert_link_is_exempt_even_without_role(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><div class="alert alert-link">x</div></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_alert_missing_role()
        assert checks.checks_errors == {}

    def test_element_without_alert_class_is_ignored(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><div class="btn btn-primary">x</div></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_alert_missing_role()
        assert checks.checks_errors == {}


class TestCheckTRawUsage:
    def test_t_raw_attribute_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><field t-raw="some_value"/></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_t_raw_usage()
        (message,) = checks.checks_errors["xml_deprecated_t_raw"]
        assert 't-raw="some_value"' in message
        assert "t-out" in message

    def test_no_t_raw_attribute_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><field t-out="some_value"/></odoo>')
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_t_raw_usage()
        assert checks.checks_errors == {}


class TestCheckHardcodedIds:
    def test_id_above_threshold_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", "<odoo><field domain=\"[('id', '=', '150')]\"/></odoo>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_hardcoded_ids()
        (message,) = checks.checks_errors["xml_hardcoded_id"]
        assert 'Possible hardcoded ID "150"' in message

    def test_id_at_or_below_threshold_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", "<odoo><field domain=\"[('id', '=', '100')]\"/></odoo>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_hardcoded_ids()
        assert checks.checks_errors == {}

    def test_value_using_ref_is_exempt_even_with_a_large_number_present(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            "<odoo><field domain=\"[('id', '=', ref('m.150')), ('x', '=', '999')]\"/></odoo>",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_hardcoded_ids()
        assert checks.checks_errors == {}

    def test_checks_context_and_eval_attributes_too(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", "<odoo><field context=\"{'x': '200'}\"/></odoo>")
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_hardcoded_ids()
        assert len(checks.checks_errors["xml_hardcoded_id"]) == 1


class TestCheckDuplicateViewPriority:
    def test_two_views_inheriting_same_view_with_default_priority_is_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <record id="v1" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_x"/>
                </record>
                <record id="v2" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_x"/>
                </record>
            </odoo>""",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_duplicate_view_priority()
        (message,) = checks.checks_errors["xml_duplicate_view_priority"]
        assert "v1, v2" in message
        assert 'inherit from "base.view_x"' in message
        assert "priority 16" in message

    def test_different_priority_via_eval_is_not_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <record id="v1" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_x"/>
                </record>
                <record id="v2" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_x"/>
                    <field name="priority" eval="20"/>
                </record>
            </odoo>""",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_duplicate_view_priority()
        assert checks.checks_errors == {}

    def test_matching_priority_given_as_plain_text_is_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <record id="v1" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_y"/>
                    <field name="priority">30</field>
                </record>
                <record id="v2" model="ir.ui.view">
                    <field name="inherit_id" ref="base.view_y"/>
                    <field name="priority">30</field>
                </record>
            </odoo>""",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_duplicate_view_priority()
        assert len(checks.checks_errors["xml_duplicate_view_priority"]) == 1

    def test_view_without_inherit_id_is_ignored(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <record id="v1" model="ir.ui.view">
                    <field name="name">a standalone view</field>
                </record>
            </odoo>""",
        )
        checks = ChecksOdooModuleXMLAdvanced([_manifest_data(path)], "my_module")
        checks.check_duplicate_view_priority()
        assert checks.checks_errors == {}
