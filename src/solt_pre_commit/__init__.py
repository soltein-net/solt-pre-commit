# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""
Solt Pre-commit Hooks
Custom hooks for Odoo module validation - Soltein

Features:
- validation_scope: 'changed' (PR files only) or 'full' (entire repo)
- Configurable severity levels (error, warning, info)
- Skip lists for fields and methods
- Path exclusions

Checks included:
- XML: syntax, duplicates, deprecated nodes, active_id, alerts
- CSV: duplicate IDs
- PO/POT: translations, printf/format variables
- Python: fields (string, help), docstrings, tracking, compute_sudo
"""

__version__ = "1.0.0"
__author__ = "Soltein SA de CV"

from .checks_branch_name import BranchNameValidator
from .checks_odoo_module import ChecksOdooModule
from .checks_odoo_module import run as run_checks
from .checks_odoo_module_csv import ChecksOdooModuleCSV
from .checks_odoo_module_po import ChecksOdooModulePO
from .checks_odoo_module_python import ChecksOdooModulePython
from .checks_odoo_module_xml import ChecksOdooModuleXML
from .checks_odoo_module_xml_advanced import ChecksOdooModuleXMLAdvanced
from .config_loader import ChangedFilesDetector, Severity, SoltConfig

__all__ = [
    # Main classes
    "ChecksOdooModule",
    "ChecksOdooModuleXML",
    "ChecksOdooModuleXMLAdvanced",
    "ChecksOdooModuleCSV",
    "ChecksOdooModulePO",
    "ChecksOdooModulePython",
    "BranchNameValidator",
    # Config
    "SoltConfig",
    "Severity",
    "ChangedFilesDetector",
    # Functions
    "run_checks",
]
