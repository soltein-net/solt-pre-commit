# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module_xml.py: ChecksOdooModuleXML's record/field
duplicate detection and its per-record-model validation visitors."""

from solt_pre_commit.checks_odoo_module_xml import ChecksOdooModuleXML


def _manifest_data(path, data_section="default"):
    return {"filename": str(path), "data_section": data_section}


def _write_xml(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return path


class TestInit:
    def test_valid_xml_populates_node_with_no_file_error(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", "<odoo/>")
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["node"] is not None
        assert manifest_data["file_error"] is None
        assert checks.checks_errors == {}

    def test_malformed_xml_records_syntax_error_and_uses_empty_placeholder_node(self, tmp_path):
        path = _write_xml(tmp_path, "bad.xml", "<odoo><unclosed>")
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["node"].tag == "__empty__"
        assert manifest_data["file_error"] is not None
        (message,) = checks.checks_errors["xml_syntax_error"]
        assert str(path) in message

    def test_missing_file_records_syntax_error_and_uses_empty_placeholder_node(self, tmp_path):
        missing = tmp_path / "does_not_exist.xml"
        checks = ChecksOdooModuleXML([_manifest_data(missing)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["node"].tag == "__empty__"
        (message,) = checks.checks_errors["xml_syntax_error"]
        assert str(missing) in message

    def test_all_checks_are_no_ops_on_the_empty_placeholder_node(self, tmp_path):
        missing = tmp_path / "does_not_exist.xml"
        checks = ChecksOdooModuleXML([_manifest_data(missing)], "my_module")
        checks.check_xml_records()
        checks.check_xml_deprecated_data_node()
        checks.check_xml_deprecated_openerp_node()
        checks.check_xml_deprecated_qweb_directive()
        checks.check_xml_not_valid_char_link()
        # Only the init-time syntax error - none of the record-based checks
        # add anything on top of it.
        assert list(checks.checks_errors.keys()) == ["xml_syntax_error"]


class TestCheckXmlRecordsDuplicateIds:
    def test_same_id_in_same_file_and_data_section_is_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><record id="rec1" model="res.partner"/><record id="rec1" model="res.partner"/></odoo>',
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_duplicate_record_id"]
        assert 'Duplicate xml record id "default/rec1' in message

    def test_same_id_across_different_files_in_same_data_section_is_a_duplicate(self, tmp_path):
        path_a = _write_xml(tmp_path, "a.xml", '<odoo><record id="rec1" model="x"/></odoo>')
        path_b = _write_xml(tmp_path, "b.xml", '<odoo><record id="rec1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path_a, "data"), _manifest_data(path_b, "data")], "my_module")
        checks.check_xml_records()
        assert len(checks.checks_errors["xml_duplicate_record_id"]) == 1

    def test_same_id_in_different_data_sections_is_not_a_duplicate(self, tmp_path):
        path_a = _write_xml(tmp_path, "a.xml", '<odoo><record id="rec1" model="x"/></odoo>')
        path_b = _write_xml(tmp_path, "b.xml", '<odoo><record id="rec1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path_a, "data"), _manifest_data(path_b, "demo")], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_same_id_under_different_noupdate_values_is_not_a_duplicate(self, tmp_path):
        # The dedup key includes the enclosing <data noupdate="..."> value, so
        # the same id loaded once at install time and once at update time
        # isn't flagged as colliding with itself.
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <data noupdate="1"><record id="rec1" model="x"/></data>
                <data noupdate="0"><record id="rec1" model="x"/></data>
            </odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestCheckXmlRecordsDuplicateFields:
    def test_same_field_name_twice_in_same_record_is_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo><record id="rec1" model="res.partner">
                <field name="name">a</field>
                <field name="name">b</field>
            </record></odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_duplicate_fields"]
        assert 'Duplicate xml field "name"' in message

    def test_same_field_name_in_different_records_is_not_a_duplicate(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo>
                <record id="rec1" model="res.partner"><field name="name">a</field></record>
                <record id="rec2" model="res.partner"><field name="name">b</field></record>
            </odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_records_with_inherit_id_are_exempt_from_duplicate_field_check(self, tmp_path):
        # A view that inherits another legitimately repeats <field name="arch">
        # (once per xpath-replace block) - checking those for duplicates would
        # be all false positives, so records with inherit_id are skipped
        # entirely.
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo><record id="rec1" model="ir.ui.view">
                <field name="inherit_id" ref="base.x"/>
                <field name="arch" type="xml">a</field>
                <field name="arch" type="xml">b</field>
            </record></odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestVisitXmlRecordRedundantModuleName:
    def test_record_id_prefixed_with_own_module_name_is_redundant(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="my_module.rec1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_redundant_module_name"]
        assert 'id="my_module.rec1"' in message

    def test_record_id_prefixed_with_another_module_is_not_redundant(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="other_module.rec1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_record_id_without_a_dot_is_not_redundant(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="rec1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_record_id_with_more_than_one_dot_splits_on_the_first_dot_only(self, tmp_path):
        # xmlid_module/xmlid_name split with maxsplit=1: an xmlid is
        # "<module>.<identifier>", and the identifier itself may legitimately
        # contain further dots (e.g. "a.b.c" -> module "a", identifier "b.c").
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="a.b.c" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "a")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_redundant_module_name"]
        assert 'id="b.c"' in message

    def test_record_id_with_more_than_one_dot_and_no_module_match_is_not_redundant(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="a.b.c" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "other_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestVisitXmlRecordView:
    def test_deprecated_tree_attribute_is_reported(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo><record id="rec1" model="ir.ui.view">
                <field name="arch" type="xml">
                    <tree string="Partners"><field name="name"/></tree>
                </field>
            </record></odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_deprecated_tree_attribute"]
        assert "Deprecated" in message

    def test_tree_without_deprecated_attributes_is_not_reported(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            """<odoo><record id="rec1" model="ir.ui.view">
                <field name="arch" type="xml"><tree><field name="name"/></tree></field>
            </record></odoo>""",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_non_view_model_is_not_checked_for_tree_attributes(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><record id="rec1" model="res.partner"><tree string="x"/></record></odoo>',
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestVisitXmlRecordUser:
    def test_res_users_without_no_reset_password_is_reported(self, tmp_path):
        path = _write_xml(
            tmp_path, "a.xml", '<odoo><record id="u1" model="res.users"><field name="name">x</field></record></odoo>'
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_create_user_wo_reset_password"]
        assert "no_reset_password" in message

    def test_res_users_with_no_reset_password_is_not_reported(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><record id="u1" model="res.users" context="{\'no_reset_password\': True}">'
            '<field name="name">x</field></record></odoo>',
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_non_user_model_is_not_checked(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="r1" model="res.partner"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestVisitXmlRecordFilter:
    def test_ir_filters_without_user_id_is_reported(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><record id="f1" model="ir.filters"><field name="name">x</field></record></odoo>',
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        (message,) = checks.checks_errors["xml_dangerous_filter_wo_user"]
        assert "without explicit" in message

    def test_ir_filters_with_user_id_is_not_reported(self, tmp_path):
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><record id="f1" model="ir.filters">'
            '<field name="name">x</field><field name="user_id" ref="base.user_admin"/>'
            "</record></odoo>",
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}

    def test_non_filter_model_is_not_checked(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="r1" model="res.partner"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_records()
        assert checks.checks_errors == {}


class TestCheckXmlDeprecatedDataNode:
    def test_odoo_wrapping_a_single_data_child_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><data><record id="r1" model="x"/></data></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_data_node()
        (message,) = checks.checks_errors["xml_deprecated_data_node"]
        assert "Use <odoo> instead of <odoo><data>" in message

    def test_reported_regardless_of_how_many_records_data_wraps(self, tmp_path):
        # The check only counts <odoo>'s direct children (always 1 when the
        # sole child is <data>) - it does NOT look inside <data> itself, so
        # this fires the same way whether <data> wraps one record or many,
        # despite the docstring's "when there's only one child" framing.
        path = _write_xml(
            tmp_path,
            "a.xml",
            '<odoo><data><record id="r1" model="x"/><record id="r2" model="x"/></data></odoo>',
        )
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_data_node()
        assert len(checks.checks_errors["xml_deprecated_data_node"]) == 1

    def test_odoo_without_a_data_wrapper_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="r1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_data_node()
        assert checks.checks_errors == {}


class TestCheckXmlDeprecatedOpenerpNode:
    def test_openerp_root_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<openerp><data><record id="r1" model="x"/></data></openerp>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_openerp_node()
        (message,) = checks.checks_errors["xml_deprecated_openerp_xml_node"]
        assert "Deprecated <openerp>" in message

    def test_odoo_root_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><record id="r1" model="x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_openerp_node()
        assert checks.checks_errors == {}


class TestCheckXmlDeprecatedQwebDirective:
    def test_deprecated_directive_inside_template_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><template id="t1"><span t-field-options="{}"/></template></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_qweb_directive()
        (message,) = checks.checks_errors["xml_deprecated_qweb_directive"]
        assert "t-field-options" in message
        assert "t-options" in message

    def test_deprecated_looking_attribute_outside_a_template_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><span t-field-options="{}"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_qweb_directive()
        assert checks.checks_errors == {}

    def test_template_without_deprecated_directives_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><template id="t1"><span t-field="x"/></template></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_deprecated_qweb_directive()
        assert checks.checks_errors == {}


class TestCheckXmlNotValidCharLink:
    def test_absolute_href_without_a_file_extension_is_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><link href="/my_module/static/src/css/style"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_not_valid_char_link()
        (message,) = checks.checks_errors["xml_not_valid_char_link"]
        assert "invalid character" in message

    def test_absolute_href_with_a_file_extension_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><link href="/my_module/static/src/css/style.css"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_not_valid_char_link()
        assert checks.checks_errors == {}

    def test_non_absolute_src_is_not_reported(self, tmp_path):
        path = _write_xml(tmp_path, "a.xml", '<odoo><script src="https://cdn.example.com/x"/></odoo>')
        checks = ChecksOdooModuleXML([_manifest_data(path)], "my_module")
        checks.check_xml_not_valid_char_link()
        assert checks.checks_errors == {}
