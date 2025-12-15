# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Basic XML validations for Odoo modules."""

import os
import re
from collections import defaultdict
from typing import List

from lxml import etree

DFTL_MIN_PRIORITY = 99


class ChecksOdooModuleXML:
    """Basic XML validator for Odoo modules."""

    def __init__(self, manifest_datas: List[dict], module_name: str):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.checks_errors = defaultdict(list)

        for manifest_data in manifest_datas:
            try:
                with open(manifest_data["filename"], "rb") as f_xml:
                    manifest_data.update({
                        "node": etree.parse(f_xml),
                        "file_error": None,
                    })
            except (FileNotFoundError, etree.XMLSyntaxError) as xml_err:
                manifest_data.update({
                    "node": etree.Element("__empty__"),
                    "file_error": xml_err,
                })
                self.checks_errors["xml_syntax_error"].append(
                    f'{manifest_data["filename"]} {xml_err}'
                )

    @staticmethod
    def _get_priority(view):
        try:
            priority_node = view.xpath("field[@name='priority'][1]")[0]
            return int(priority_node.get("eval", priority_node.text) or 0)
        except (IndexError, ValueError):
            return 0

    @staticmethod
    def _is_replaced_field(view):
        try:
            arch = view.xpath("field[@name='arch' and @type='xml'][1]")[0]
        except IndexError:
            return False
        replaces = arch.xpath(
            ".//field[@name='name' and @position='replace'][1] | "
            ".//*[@position='replace'][1]"
        )
        return bool(replaces)

    def check_xml_records(self):
        """Validate records: duplicates, duplicate fields."""
        xmlids_section = defaultdict(list)
        xml_fields = defaultdict(list)

        for manifest_data in self.manifest_datas:
            for record in manifest_data["node"].xpath(
                "/odoo//record[@id] | /openerp//record[@id]"
            ):
                record_id = record.get("id")

                # Detect duplicate xmlids
                xmlid_key = (
                    f"{manifest_data['data_section']}/{record_id}"
                    f"_noupdate_{record.getparent().get('noupdate', '0')}"
                )
                xmlids_section[xmlid_key].append((manifest_data, record))

                # Detect duplicate fields
                if not record.xpath('field[@name="inherit_id"]'):
                    for field in record.xpath(
                        "field[@name] | field/*/field[@name] | "
                        "field/*/field/tree/field[@name] | "
                        "field/*/field/form/field[@name]"
                    ):
                        field_key = (
                            field.get("name"),
                            field.get("context"),
                            field.get("filter_domain"),
                            field.getparent(),
                        )
                        xml_fields[field_key].append((manifest_data, field))

                self._visit_xml_record(manifest_data, record)
                self._visit_xml_record_view(manifest_data, record)
                self._visit_xml_record_user(manifest_data, record)
                self._visit_xml_record_filter(manifest_data, record)

        # Report duplicate xmlids
        for xmlid_key, records in xmlids_section.items():
            if len(records) >= 2:
                lines_str = ", ".join(
                    f"{r[0]['filename']}:{r[1].sourceline}" for r in records[1:]
                )
                self.checks_errors["xml_duplicate_record_id"].append(
                    f"{records[0][0]['filename']}:{records[0][1].sourceline} "
                    f'Duplicate xml record id "{xmlid_key}" in {lines_str}'
                )

        # Report duplicate fields
        for field_key, fields in xml_fields.items():
            if len(fields) >= 2:
                lines_str = ", ".join(f"{f[1].sourceline}" for f in fields[1:])
                self.checks_errors["xml_duplicate_fields"].append(
                    f"{fields[0][0]['filename']}:{fields[0][1].sourceline} "
                    f'Duplicate xml field "{field_key[0]}" in lines {lines_str}'
                )

    def _visit_xml_record(self, manifest_data, record):
        """Detect redundant module name in xmlid."""
        record_id = record.get("id")
        xmlid_module, xmlid_name = (
            record_id.split(".") if "." in record_id else ["", record_id]
        )
        if xmlid_module == self.module_name:
            self.checks_errors["xml_redundant_module_name"].append(
                f'{manifest_data["filename"]}:{record.sourceline} '
                f'Redundant module name <record id="{record_id}" '
                f'better using only <record id="{xmlid_name}"'
            )

    def _visit_xml_record_view(self, manifest_data, record):
        """Validate views: dangerous replace, deprecated attributes."""
        if record.get("model") != "ir.ui.view":
            return

        priority = self._get_priority(record)
        is_replaced = self._is_replaced_field(record)

        if is_replaced and priority < DFTL_MIN_PRIORITY:
            self.checks_errors["xml_view_dangerous_replace_low_priority"].append(
                f'{manifest_data["filename"]}:{record.sourceline} '
                f'Dangerous "replace" with priority {priority} < {DFTL_MIN_PRIORITY}'
            )

        # Deprecated attributes in tree
        deprecate_attrs = {"string", "colors", "fonts"}
        xpath = f".//tree[{'|'.join(f'@{a}' for a in deprecate_attrs)}]"
        for node in record.xpath(xpath):
            attrs_found = ", ".join(set(node.attrib.keys()) & deprecate_attrs)
            self.checks_errors["xml_deprecated_tree_attribute"].append(
                f'{manifest_data["filename"]}:{node.sourceline} '
                f'Deprecated "<tree {attrs_found}=..."'
            )

    def _visit_xml_record_user(self, manifest_data, record):
        """Validate user creation without no_reset_password."""
        if record.get("model") != "res.users":
            return
        if (
            record.xpath("field[@name='name'][1]") and
            "no_reset_password" not in (record.get("context") or "")
        ):
            self.checks_errors["xml_create_user_wo_reset_password"].append(
                f'{manifest_data["filename"]}:{record.sourceline} '
                "record res.users without context=\"{'no_reset_password': True}\""
            )

    def _visit_xml_record_filter(self, manifest_data, record):
        """Validate filters without assigned user."""
        if record.get("model") != "ir.filters":
            return
        fields = record.xpath("field[@name='name' or @name='user_id']")
        if fields and len(fields) == 1:
            self.checks_errors["xml_dangerous_filter_wo_user"].append(
                f'{manifest_data["filename"]}:{record.sourceline} '
                "Dangerous filter without explicit `user_id`"
            )

    def check_xml_deprecated_data_node(self):
        """Detect use of <odoo><data> when there's only one child."""
        for manifest_data in self.manifest_datas:
            for odoo_node in manifest_data["node"].xpath("/odoo|/openerp"):
                children = list(odoo_node.iterchildren())
                if len(children) == 1 and len(odoo_node.xpath("./data")) == 1:
                    self.checks_errors["xml_deprecated_data_node"].append(
                        f'{manifest_data["filename"]}:{odoo_node.sourceline} '
                        'Use <odoo> instead of <odoo><data>'
                    )

    def check_xml_deprecated_openerp_node(self):
        """Detect use of <openerp> instead of <odoo>."""
        for manifest_data in self.manifest_datas:
            for openerp_node in manifest_data["node"].xpath("/openerp"):
                self.checks_errors["xml_deprecated_openerp_xml_node"].append(
                    f'{manifest_data["filename"]}:{openerp_node.sourceline} '
                    "Deprecated <openerp> xml node, use <odoo>"
                )

    def check_xml_deprecated_qweb_directive(self):
        """Detect deprecated QWeb directives."""
        deprecated = {"t-esc-options", "t-field-options", "t-raw-options"}
        deprecated_attrs = "|".join(f"@{d}" for d in deprecated)
        xpath = (
            f"/odoo//template//*[{deprecated_attrs}] | "
            f"/openerp//template//*[{deprecated_attrs}]"
        )

        for manifest_data in self.manifest_datas:
            for node in manifest_data["node"].xpath(xpath):
                found = ", ".join(set(node.attrib) & deprecated)
                self.checks_errors["xml_deprecated_qweb_directive"].append(
                    f'{manifest_data["filename"]}:{node.sourceline} '
                    f'Deprecated QWeb directive "{found}". Use "t-options"'
                )

    def check_xml_not_valid_char_link(self):
        """Validate characters in link/script resources."""
        for manifest_data in self.manifest_datas:
            for name, attr in (("link", "href"), ("script", "src")):
                for node in manifest_data["node"].xpath(f".//{name}[@{attr}]"):
                    resource = node.get(attr, "")
                    ext = os.path.splitext(os.path.basename(resource))[1]
                    if resource.startswith("/") and not re.search(r"^\.[a-zA-Z]+$", ext):
                        self.checks_errors["xml_not_valid_char_link"].append(
                            f'{manifest_data["filename"]}:{node.sourceline} '
                            "Resource contains invalid character"
                        )