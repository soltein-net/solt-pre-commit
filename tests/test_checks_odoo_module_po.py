# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module_po.py: ChecksOdooModulePO's PO/POT file
parsing, module-comment requirement, printf/format placeholder validation,
and duplicate msgid detection."""

from solt_pre_commit.checks_odoo_module_po import (
    ChecksOdooModulePO,
    FormatStringParseError,
    PrintfStringParseError,
)

_PO_HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'


def _manifest_data(path):
    return {"filename": str(path)}


def _write_po(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(_PO_HEADER + body)
    return path


class TestInit:
    def test_valid_po_file_populates_po_with_no_file_error(self, tmp_path):
        path = _write_po(tmp_path, "good.po", '#. module: my_module\nmsgid "Hello"\nmsgstr "Hola"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["po"] is not None
        assert manifest_data["file_error"] is None
        assert checks.checks_errors == {}

    def test_missing_file_records_po_syntax_error(self, tmp_path):
        missing = tmp_path / "does_not_exist.po"
        checks = ChecksOdooModulePO([_manifest_data(missing)], "my_module")
        manifest_data = checks.manifest_datas[0]
        assert manifest_data["po"] is None
        assert manifest_data["file_error"] is not None
        (message,) = checks.checks_errors["po_syntax_error"]
        assert str(missing) in message

    def test_malformed_po_content_records_po_syntax_error(self, tmp_path):
        path = tmp_path / "bad.po"
        path.write_text("this is not a po file at all {{{")
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        assert checks.manifest_datas[0]["po"] is None
        assert "po_syntax_error" in checks.checks_errors

    def test_check_po_is_a_no_op_when_file_failed_to_parse(self, tmp_path):
        missing = tmp_path / "does_not_exist.po"
        checks = ChecksOdooModulePO([_manifest_data(missing)], "my_module")
        checks.check_po()
        # Only the init-time syntax error - check_po() adds nothing further.
        assert list(checks.checks_errors.keys()) == ["po_syntax_error"]


class TestCheckPoModuleComment:
    def test_missing_module_comment_is_reported(self, tmp_path):
        path = _write_po(tmp_path, "a.po", 'msgid "Hello"\nmsgstr "Hola"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_requires_module"]
        assert "requires comment" in message

    def test_singular_module_comment_is_accepted(self, tmp_path):
        path = _write_po(tmp_path, "a.po", '#. module: my_module\nmsgid "Hello"\nmsgstr "Hola"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_plural_modules_comment_is_accepted(self, tmp_path):
        path = _write_po(tmp_path, "a.po", '#. modules: my_module\nmsgid "Hello"\nmsgstr "Hola"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}


class TestCheckPoPrintfFormatValidation:
    def test_printf_type_mismatch_is_reported(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\n#, python-format\nmsgid "Value: %s"\nmsgstr "Valor: %d"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_python_parse_printf"]
        assert "Translation parse error (printf)" in message

    def test_matching_printf_placeholders_are_not_reported(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\n#, python-format\nmsgid "Value: %s"\nmsgstr "Valor: %s"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_format_placeholder_out_of_range_is_reported(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\n#, python-format\nmsgid "Value: {}"\nmsgstr "Valor: {1}"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_python_parse_format"]
        assert "Translation parse error (format)" in message

    def test_mismatch_without_python_format_flag_is_not_checked(self, tmp_path):
        path = _write_po(tmp_path, "a.po", '#. module: my_module\nmsgid "Value: %s"\nmsgstr "Valor: %d"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_untranslated_entry_is_not_checked(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\n#, python-format\nmsgid "Value: %s"\nmsgstr ""\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_unparseable_msgid_is_silently_skipped_rather_than_blamed_on_msgstr(self, tmp_path):
        # If main_str (msgid) itself can't be formatted with its own
        # extracted args, parse_printf/parse_format both return early - a
        # broken msgid isn't reported as if msgstr were the problem.
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\n#, python-format\nmsgid "%(name)s and %s"\nmsgstr "anything %d"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}


class TestCheckPoDuplicates:
    def test_duplicate_msgid_is_reported(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\nmsgid "Hello"\nmsgstr "Hola"\n\n'
            '#. module: my_module\nmsgid "Hello"\nmsgstr "Hola2"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_duplicate_message_definition"]
        assert 'Duplicate PO message "Hello"' in message

    def test_unique_msgids_are_not_reported(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\nmsgid "Hello"\nmsgstr "Hola"\n\n'
            '#. module: my_module\nmsgid "Goodbye"\nmsgstr "Adios"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_obsolete_entries_are_ignored_entirely(self, tmp_path):
        # Obsolete entries are skipped before both the duplicate check and
        # _visit_entry - they don't get flagged for a missing module
        # comment either, even though they have none here.
        path = _write_po(tmp_path, "a.po", '#~ msgid "Old"\n#~ msgstr "Viejo"\n')
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        assert checks.checks_errors == {}

    def test_long_msgid_is_truncated_at_forty_characters(self, tmp_path):
        long_msg = "This is a very long message that exceeds forty characters easily"
        path = _write_po(
            tmp_path,
            "a.po",
            f'#. module: my_module\nmsgid "{long_msg}"\nmsgstr "a"\n\n'
            f'#. module: my_module\nmsgid "{long_msg}"\nmsgstr "b"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_duplicate_message_definition"]
        assert long_msg[:40] + "..." in message
        assert long_msg not in message

    def test_short_msgid_is_not_truncated(self, tmp_path):
        path = _write_po(
            tmp_path,
            "a.po",
            '#. module: my_module\nmsgid "Hi"\nmsgstr "a"\n\n#. module: my_module\nmsgid "Hi"\nmsgstr "b"\n',
        )
        checks = ChecksOdooModulePO([_manifest_data(path)], "my_module")
        checks.check_po()
        (message,) = checks.checks_errors["po_duplicate_message_definition"]
        assert 'message "Hi"' in message
        assert "..." not in message


class TestPrintfArgExtraction:
    def test_multiple_unnamed_placeholders(self):
        assert ChecksOdooModulePO._get_printf_str_args_kwargs("%s and %d") == ("", 0)

    def test_named_placeholder(self):
        assert ChecksOdooModulePO._get_printf_str_args_kwargs("%(name)s") == {"name": ""}

    def test_no_placeholders_returns_empty_dict(self):
        assert ChecksOdooModulePO._get_printf_str_args_kwargs("no placeholders here") == {}

    def test_escaped_percent_is_not_a_placeholder(self):
        assert ChecksOdooModulePO._get_printf_str_args_kwargs("literal %% percent") == {}


class TestFormatArgExtraction:
    def test_unnamed_placeholders_become_a_range(self):
        args, kwargs = ChecksOdooModulePO._get_format_str_args_kwargs("{} and {}")
        assert list(args) == [0, 1]
        assert kwargs == {}

    def test_named_placeholder(self):
        args, kwargs = ChecksOdooModulePO._get_format_str_args_kwargs("{name}")
        assert args == []
        assert kwargs == {"name": 0}

    def test_indexed_placeholders_become_a_range(self):
        args, kwargs = ChecksOdooModulePO._get_format_str_args_kwargs("{0} and {1}")
        assert list(args) == [0, 1]
        assert kwargs == {}

    def test_no_placeholders(self):
        assert ChecksOdooModulePO._get_format_str_args_kwargs("no placeholders") == ([], {})

    def test_unparseable_line_with_unmatched_brace_is_skipped(self):
        # string.Formatter().parse() raises ValueError on an unmatched "{" -
        # that line is skipped rather than propagating the error.
        assert ChecksOdooModulePO._get_format_str_args_kwargs("unmatched { brace") == ([], {})


class TestParsePrintfAndFormatDirectly:
    def test_parse_printf_raises_on_mismatch(self):
        try:
            ChecksOdooModulePO.parse_printf("Value: %s", "Valor: %d")
        except PrintfStringParseError:
            pass
        else:
            raise AssertionError("expected PrintfStringParseError")

    def test_parse_printf_returns_none_when_main_str_has_no_placeholders(self):
        assert ChecksOdooModulePO.parse_printf("no placeholders", "tambien ninguno") is None

    def test_parse_format_raises_on_mismatch(self):
        try:
            ChecksOdooModulePO.parse_format("Value: {}", "Valor: {1}")
        except FormatStringParseError:
            pass
        else:
            raise AssertionError("expected FormatStringParseError")

    def test_parse_format_returns_none_when_main_str_has_no_placeholders(self):
        assert ChecksOdooModulePO.parse_format("no placeholders", "tampoco ninguno") is None

    def test_parse_format_returns_none_when_main_str_itself_cannot_be_formatted(self):
        # "{} and {0}" mixes automatic and manual field numbering, which
        # main_str.format() itself rejects with a ValueError - parse_format
        # returns early instead of blaming secondary_str for that.
        assert ChecksOdooModulePO.parse_format("{} and {0}", "anything") is None
