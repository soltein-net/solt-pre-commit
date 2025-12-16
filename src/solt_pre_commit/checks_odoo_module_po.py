# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""PO/POT validations for Odoo modules."""

import re
import string
from collections import defaultdict
from typing import List

import polib

PRINTF_PATTERN = re.compile(
    r"""
        %(                          # initial %
        (?P<boost_ord>\d+)%         # boost::format style variable order
        |
              (?:(?P<ord>\d+)\$|    # variable order, like %1$s
              \((?P<key>\w+)\))?    # Python style variables, like %(var)s
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w@]))        # type (%s, %d, etc.)
        )""",
    re.VERBOSE,
)


class StringParseError(TypeError):
    """Base error for string parsing."""

    pass


class PrintfStringParseError(StringParseError):
    """Error in printf parsing."""

    pass


class FormatStringParseError(StringParseError):
    """Error in format parsing."""

    pass


class ChecksOdooModulePO:
    """PO/POT validator for Odoo modules."""

    def __init__(self, manifest_datas: List[dict], module_name: str):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.checks_errors = defaultdict(list)

        for manifest_data in manifest_datas:
            try:
                polib_file = polib.pofile(manifest_data["filename"])
                manifest_data.update(
                    {
                        "po": polib_file,
                        "file_error": None,
                    }
                )
            except OSError as po_err:
                manifest_data.update(
                    {
                        "po": None,
                        "file_error": po_err,
                    }
                )
                msg = str(po_err).replace(f"{manifest_data['filename']} ", "").strip()
                self.checks_errors["po_syntax_error"].append(
                    f"{manifest_data['filename']} {msg}"
                )

    @staticmethod
    def _get_printf_str_args_kwargs(printf_str):
        """Extract dummy args/kwargs from a printf string."""
        args = []
        kwargs = {}
        printf_str = re.sub("%%", "", printf_str)

        for line in printf_str.splitlines():
            for match in PRINTF_PATTERN.finditer(line):
                match_items = match.groupdict()
                var = "" if match_items["type"] == "s" else 0
                if match_items["key"] is None:
                    args.append(var)
                else:
                    kwargs[match_items["key"]] = var

        return tuple(args) or kwargs

    @staticmethod
    def _get_format_str_args_kwargs(format_str):
        """Extract dummy args/kwargs from a format string."""
        format_str_args = []
        format_str_kwargs = {}

        for line in format_str.splitlines():
            try:
                placeholders = [
                    name
                    for _, name, _, _ in string.Formatter().parse(line)
                    if name is not None
                ]
            except ValueError:
                continue

            for placeholder in placeholders:
                if placeholder == "":
                    format_str_args.append(0)
                elif placeholder.isdigit():
                    format_str_args.append(int(placeholder) + 1)
                else:
                    format_str_kwargs[placeholder] = 0

        if format_str_args:
            max_val = max(format_str_args)
            format_str_args = (
                range(len(format_str_args)) if max_val == 0 else range(max_val)
            )

        return format_str_args, format_str_kwargs

    @staticmethod
    def parse_printf(main_str, secondary_str):
        """Validate that secondary_str can be parsed with args from main_str."""
        printf_args = ChecksOdooModulePO._get_printf_str_args_kwargs(main_str)
        if not printf_args:
            return

        try:
            main_str % printf_args
        except Exception:
            return

        try:
            secondary_str % printf_args
        except Exception as exc:
            raise PrintfStringParseError(repr(exc)) from exc

    @staticmethod
    def parse_format(main_str, secondary_str):
        """Validate that secondary_str can be parsed with args from main_str."""
        msgid_args, msgid_kwargs = ChecksOdooModulePO._get_format_str_args_kwargs(
            main_str
        )
        if not msgid_args and not msgid_kwargs:
            return

        try:
            main_str.format(*msgid_args, **msgid_kwargs)
        except Exception:
            return

        try:
            secondary_str.format(*msgid_args, **msgid_kwargs)
        except Exception as exc:
            raise FormatStringParseError(repr(exc)) from exc

    @staticmethod
    def _get_po_line_number(po_entry):
        """Get line number of msgid (like msgfmt output)."""
        linenum = po_entry.linenum
        for line in str(po_entry).split("\n"):
            if not line.startswith("#"):
                break
            linenum += 1
        return linenum

    def _visit_entry(self, manifest_data, entry):
        """Validate an individual PO entry."""
        # Verify module comment
        match = re.match(r"(module[s]?): (\w+)", entry.comment)
        if not match:
            self.checks_errors["po_requires_module"].append(
                f"{manifest_data['filename']}:{entry.linenum} "
                "Translation requires comment '#. module: MODULE'"
            )

        # Verify variables in translation
        if entry.msgstr and "python-format" in entry.flags:
            try:
                self.parse_printf(entry.msgid, entry.msgstr)
                self.parse_format(entry.msgid, entry.msgstr)
            except PrintfStringParseError as exc:
                linenum = self._get_po_line_number(entry)
                self.checks_errors["po_python_parse_printf"].append(
                    f"{manifest_data['filename']}:{linenum} "
                    f"Translation parse error (printf): {exc}"
                )
            except FormatStringParseError as exc:
                linenum = self._get_po_line_number(entry)
                self.checks_errors["po_python_parse_format"].append(
                    f"{manifest_data['filename']}:{linenum} "
                    f"Translation parse error (format): {exc}"
                )

    def check_po(self):
        """Validate PO files: duplicates and individual entries."""
        for manifest_data in self.manifest_datas:
            if manifest_data.get("po") is None:
                continue

            duplicated = defaultdict(list)

            for entry in manifest_data["po"]:
                if entry.obsolete:
                    continue

                duplicated[hash(entry.msgid)].append(entry)
                self._visit_entry(manifest_data, entry)

            # Report duplicates
            for entries in duplicated.values():
                if len(entries) >= 2:
                    linenum = self._get_po_line_number(entries[0])
                    dup_lines = ", ".join(
                        map(str, map(self._get_po_line_number, entries[1:]))
                    )
                    msg_short = re.sub(r"[\n\t]*", "", entries[0].msgid[:40]).strip()
                    if len(entries[0].msgid) > 40:
                        msg_short = f"{msg_short}..."

                    self.checks_errors["po_duplicate_message_definition"].append(
                        f"{manifest_data['filename']}:{linenum} "
                        f'Duplicate PO message "{msg_short}" in lines {dup_lines}'
                    )
