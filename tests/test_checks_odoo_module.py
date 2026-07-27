# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Regression test for the empty-diff fallback fix (CHANGELOG 1.1.0):
`pre-commit run --all-files` with nothing staged used to fall back to
validating the repo root itself as a fake module and fail with a confusing
"could not be loaded" error. It should now skip cleanly instead."""

from unittest import mock

import pytest

from solt_pre_commit import checks_odoo_module as mod


def _run_main(argv=None):
    with mock.patch("sys.argv", ["solt-check-odoo"] + (argv or [])):
        try:
            mod.main()
        except SystemExit as e:
            return e.code
    return None


class TestEmptyDiffFallback:
    def test_no_staged_modules_skips_cleanly_not_root_fallback(self, capsys):
        with mock.patch.object(mod, "_detect_modules_from_staged_files", return_value=[]):
            rc = _run_main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "No Odoo modules detected from staged files" in out

    def test_explicit_paths_with_no_modules_also_skips_cleanly(self, capsys):
        with mock.patch.object(mod, "_is_file_list", return_value=True), mock.patch.object(
            mod, "_detect_modules_from_paths", return_value=[]
        ):
            rc = _run_main(["some_file.md"])
        assert rc == 0
        assert "No Odoo modules detected from provided files" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
