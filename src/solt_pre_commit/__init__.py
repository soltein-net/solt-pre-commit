# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""
Solt Pre-commit Hooks
Custom hooks for Odoo module validation - Soltein

Checks included:
- XML: syntax, duplicates, deprecated nodes, active_id, alerts
- CSV: duplicate IDs
- PO/POT: translations, printf/format variables
- Python: missing string/help, docstrings, tracking, compute_sudo
"""

__version__ = "1.0.0"
__author__ = "Soltein"

from .checks_odoo_module import ChecksOdooModule, run as run_checks
from .checks_odoo_module_csv import ChecksOdooModuleCSV
from .checks_odoo_module_po import ChecksOdooModulePO
from .checks_odoo_module_python import ChecksOdooModulePython
from .checks_odoo_module_xml import ChecksOdooModuleXML
from .checks_odoo_module_xml_advanced import ChecksOdooModuleXMLAdvanced

__all__ = [
    "ChecksOdooModule",
    "ChecksOdooModuleXML",
    "ChecksOdooModuleXMLAdvanced",
    "ChecksOdooModuleCSV",
    "ChecksOdooModulePO",
    "ChecksOdooModulePython",
    "run_checks",
]