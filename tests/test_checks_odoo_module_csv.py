# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module_csv.py: ChecksOdooModuleCSV's duplicate
record-id detection across Odoo data-file CSVs."""

from solt_pre_commit.checks_odoo_module_csv import ChecksOdooModuleCSV


def _manifest_data(path, data_section="default"):
    return {"filename": str(path), "data_section": data_section}


def _write_csv(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return path


class TestInit:
    def test_derives_model_from_filename(self, tmp_path):
        path = _write_csv(tmp_path, "res_partner.csv", "id,name\n")
        manifest_data = _manifest_data(path)
        ChecksOdooModuleCSV([manifest_data], "my_module")
        assert manifest_data["model"] == "res_partner"

    def test_starts_with_no_errors(self, tmp_path):
        path = _write_csv(tmp_path, "a.csv", "id,name\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        assert checks.checks_errors == {}


class TestCheckCsvDuplicates:
    def test_unique_ids_report_no_errors(self, tmp_path):
        path = _write_csv(tmp_path, "unique.csv", "id,name\nrec1,a\nrec2,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        assert checks.checks_errors == {}

    def test_duplicate_id_within_same_file(self, tmp_path):
        path = _write_csv(tmp_path, "dup.csv", "id,name\nrec1,a\nrec1,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        (message,) = checks.checks_errors["csv_duplicate_record_id"]
        assert 'Duplicate CSV record id "default/rec1"' in message
        assert f"{path}:2" in message
        assert f"{path}:3" in message

    def test_duplicate_id_across_files_in_same_data_section(self, tmp_path):
        # Record ids are scoped per data_section, not per file - two files
        # both loaded into the "data" section that both define "rec1" is a
        # real Odoo module error even though neither file has an internal
        # duplicate on its own.
        path_a = _write_csv(tmp_path, "a.csv", "id,name\nrec1,a\n")
        path_b = _write_csv(tmp_path, "b.csv", "id,name\nrec1,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path_a, "data"), _manifest_data(path_b, "data")], "my_module")
        checks.check_csv()
        (message,) = checks.checks_errors["csv_duplicate_record_id"]
        assert 'Duplicate CSV record id "data/rec1"' in message

    def test_same_id_in_different_data_sections_is_not_a_duplicate(self, tmp_path):
        path_a = _write_csv(tmp_path, "a.csv", "id,name\nrec1,a\n")
        path_b = _write_csv(tmp_path, "b.csv", "id,name\nrec1,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path_a, "data"), _manifest_data(path_b, "demo")], "my_module")
        checks.check_csv()
        assert checks.checks_errors == {}

    def test_reports_one_duplicate_error_per_csvid_not_per_extra_row(self, tmp_path):
        path = _write_csv(tmp_path, "triple.csv", "id,name\nrec1,a\nrec1,b\nrec1,c\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        assert len(checks.checks_errors["csv_duplicate_record_id"]) == 1
        message = checks.checks_errors["csv_duplicate_record_id"][0]
        assert f"{path}:3" in message
        assert f"{path}:4" in message


class TestCheckCsvSkipsNonIdRows:
    def test_file_without_id_column_is_skipped_without_error(self, tmp_path):
        path = _write_csv(tmp_path, "no_id.csv", "name,value\na,1\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        assert checks.checks_errors == {}

    def test_rows_with_empty_id_value_are_not_counted(self, tmp_path):
        path = _write_csv(tmp_path, "blank_id.csv", "id,name\n,a\n,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        assert checks.checks_errors == {}

    def test_empty_file_is_skipped_without_error(self, tmp_path):
        path = _write_csv(tmp_path, "empty.csv", "")
        checks = ChecksOdooModuleCSV([_manifest_data(path)], "my_module")
        checks.check_csv()
        assert checks.checks_errors == {}


class TestCheckCsvFileErrors:
    def test_missing_file_reports_csv_syntax_error(self, tmp_path):
        missing = tmp_path / "does_not_exist.csv"
        checks = ChecksOdooModuleCSV([_manifest_data(missing)], "my_module")
        checks.check_csv()
        (message,) = checks.checks_errors["csv_syntax_error"]
        assert str(missing) in message

    def test_one_bad_file_does_not_block_checking_the_rest(self, tmp_path):
        missing = tmp_path / "does_not_exist.csv"
        good = _write_csv(tmp_path, "good.csv", "id,name\nrec1,a\nrec1,b\n")
        checks = ChecksOdooModuleCSV([_manifest_data(missing), _manifest_data(good)], "my_module")
        checks.check_csv()
        assert "csv_syntax_error" in checks.checks_errors
        assert "csv_duplicate_record_id" in checks.checks_errors
