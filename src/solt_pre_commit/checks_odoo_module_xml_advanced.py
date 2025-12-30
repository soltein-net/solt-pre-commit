# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Advanced XML validations for Odoo modules.

Detects:
- Deprecated active_id, active_ids, active_model usage
- Alert elements without proper role
- Other problematic patterns in views
"""

import re
from collections import defaultdict
from typing import List

from lxml import etree


class ChecksOdooModuleXMLAdvanced:
    """Advanced XML validator for Odoo modules."""

    DEPRECATED_CONTEXT_VARS = {
        "active_id": "Use 'default_*' or pass via context explicitly",
        "active_ids": "Use 'default_*' or pass via context explicitly",
        "active_model": "Use 'default_*' or pass via context explicitly",
    }

    # Minimum ID value to report as potentially hardcoded
    # Small numbers (<=100) are often legitimate values like:
    # - Selection field values (1, 2, 3...)
    # - Month numbers (1-12)
    # - Limit values, percentages, etc.
    # Real record IDs in production databases are typically much larger
    HARDCODED_ID_THRESHOLD = 100

    def __init__(self, manifest_datas: List[dict], module_name: str):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.checks_errors = defaultdict(list)

        for manifest_data in manifest_datas:
            self._parse_xml_file(manifest_data)

    def _parse_xml_file(self, manifest_data: dict):
        """Parse an XML file."""
        filename = manifest_data["filename"]
        try:
            with open(filename, "rb") as f:
                manifest_data["tree"] = etree.parse(f)
                manifest_data["parse_error"] = None
        except (FileNotFoundError, etree.XMLSyntaxError) as err:
            manifest_data["tree"] = None
            manifest_data["parse_error"] = err

    def check_deprecated_active_id_usage(self):
        """Detect deprecated use of active_id, active_ids, active_model.

        Odoo Warning:
        Using active_id, active_ids and active_model in expressions is deprecated
        """
        pattern = re.compile(r"\b(active_id|active_ids|active_model)\b")

        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            search_attrs = [
                "context",
                "domain",
                "attrs",
                "options",
                "filter_domain",
                "default",
                "eval",
            ]

            for attr in search_attrs:
                for node in tree.xpath(f"//*[@{attr}]"):
                    value = node.get(attr, "")
                    matches = pattern.findall(value)

                    for match in matches:
                        self.checks_errors["xml_deprecated_active_id_usage"].append(
                            f'{filename}:{node.sourceline} Deprecated use of "{match}" in {attr}="{value[:50]}..."'
                        )

    def check_alert_missing_role(self):
        """Detect alert elements without proper role.

        Odoo Warning:
        An alert must have an alert, alertdialog or status role
        """
        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            for node in tree.xpath("//*[contains(@class, 'alert-')]"):
                classes = node.get("class", "")
                role = node.get("role", "")

                if "alert-link" in classes:
                    continue

                valid_roles = {"alert", "alertdialog", "status"}
                if role not in valid_roles:
                    self.checks_errors["xml_alert_missing_role"].append(
                        f"{filename}:{node.sourceline} "
                        f'Element with class "{classes}" should have '
                        f'role="alert", role="alertdialog", or role="status"'
                    )

    def check_button_without_type(self):
        """Detect buttons without type attribute.

        Buttons in Odoo views should have a type attribute to specify their behavior.
        However, buttons with special="cancel" are exempt because they use the special
        attribute instead of type to define their behavior (closing wizards/dialogs).

        Valid button patterns:
        - <button type="object" name="action_confirm"/>
        - <button type="action" name="%(action_id)d"/>
        - <button special="cancel" string="Cancel"/>  (exempt from check)
        - <button special="save" string="Save"/>  (exempt from check)
        """
        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            # Find buttons without type attribute AND without special attribute
            # Buttons with special="cancel" or special="save" don't need type
            for node in tree.xpath("//button[not(@type) and not(@special)]"):
                name = node.get("name", "unnamed")
                self.checks_errors["xml_button_without_type"].append(
                    f'{filename}:{node.sourceline} Button "{name}" is missing type attribute'
                )

    def check_t_raw_usage(self):
        """Detect use of t-raw (deprecated in favor of t-out)."""
        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            for node in tree.xpath("//*[@t-raw]"):
                value = node.get("t-raw", "")
                self.checks_errors["xml_deprecated_t_raw"].append(
                    f'{filename}:{node.sourceline} Deprecated t-raw="{value}", use t-out with markup() instead'
                )

    def check_hardcoded_ids(self):
        """Detect hardcoded IDs that should use ref().

        Only reports numbers greater than HARDCODED_ID_THRESHOLD (default: 100)
        to avoid false positives from:
        - Selection field values (1, 2, 3...)
        - Month numbers (1-12)
        - Limit values, percentages
        - Other legitimate small integer values in domains

        Real Odoo record IDs in production are typically much larger numbers.
        """
        id_pattern = re.compile(r"['\"](\d+)['\"]")

        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            for attr in ["domain", "context", "eval"]:
                for node in tree.xpath(f"//*[@{attr}]"):
                    value = node.get(attr, "")

                    if "ref(" not in value:
                        matches = id_pattern.findall(value)
                        for match in matches:
                            # Only report IDs larger than threshold
                            # Small numbers are usually selection values, not record IDs
                            if int(match) > self.HARDCODED_ID_THRESHOLD:
                                self.checks_errors["xml_hardcoded_id"].append(
                                    f"{filename}:{node.sourceline} "
                                    f'Possible hardcoded ID "{match}" in {attr}, '
                                    f"consider using ref()"
                                )

    def check_duplicate_view_priority(self):
        """Detect views with same priority inheriting same view."""
        for manifest_data in self.manifest_datas:
            tree = manifest_data.get("tree")
            if tree is None:
                continue

            filename = manifest_data["filename"]

            inherit_groups = defaultdict(list)

            for record in tree.xpath("//record[@model='ir.ui.view']"):
                inherit_node = record.xpath("field[@name='inherit_id']")
                priority_node = record.xpath("field[@name='priority']")

                if not inherit_node:
                    continue

                inherit_ref = inherit_node[0].get("ref", "")
                priority = "16"

                if priority_node:
                    priority = priority_node[0].get("eval", priority_node[0].text or "16")

                key = (inherit_ref, priority)
                inherit_groups[key].append(
                    {
                        "id": record.get("id"),
                        "lineno": record.sourceline,
                    }
                )

            for (inherit_ref, priority), views in inherit_groups.items():
                if len(views) >= 2:
                    view_ids = ", ".join(v["id"] for v in views)
                    self.checks_errors["xml_duplicate_view_priority"].append(
                        f"{filename}:{views[0]['lineno']} "
                        f'Views ({view_ids}) inherit from "{inherit_ref}" '
                        f"with same priority {priority}"
                    )