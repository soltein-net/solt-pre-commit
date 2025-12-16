# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""CSV validations for Odoo modules."""

import csv
import os
from collections import defaultdict
from typing import List


class ChecksOdooModuleCSV:
    """CSV validator for Odoo modules."""

    def __init__(self, manifest_datas: List[dict], module_name: str):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        self.checks_errors = defaultdict(list)

        for manifest_data in manifest_datas:
            manifest_data.update(
                {
                    "model": os.path.splitext(os.path.basename(manifest_data["filename"]))[0],
                }
            )

    def check_csv(self):
        """Detect duplicate IDs in CSV files."""
        csvids = defaultdict(list)

        for manifest_data in self.manifest_datas:
            try:
                with open(manifest_data["filename"], "r", encoding="UTF-8") as f_csv:
                    csv_reader = csv.DictReader(f_csv)

                    if not csv_reader or "id" not in (csv_reader.fieldnames or []):
                        continue

                    for record in csv_reader:
                        record_id = record.get("id", "")
                        if not record_id:
                            continue

                        csvid = f"{manifest_data['data_section']}/{record_id}"
                        csvids[csvid].append(
                            (
                                manifest_data["filename"],
                                csv_reader.line_num,
                                manifest_data["model"],
                            )
                        )

            except (FileNotFoundError, csv.Error) as csv_err:
                self.checks_errors["csv_syntax_error"].append(f"{manifest_data['filename']} {csv_err}")

        # Report duplicates
        for csvid, records in csvids.items():
            if len(records) >= 2:
                first = records[0]
                others = ", ".join(f"{r[0]}:{r[1]}" for r in records[1:])
                self.checks_errors["csv_duplicate_record_id"].append(
                    f'{first[0]}:{first[1]} Duplicate CSV record id "{csvid}" in {others}'
                )
