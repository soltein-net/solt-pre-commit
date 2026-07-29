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

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    # Derived from the installed distribution's metadata (itself computed by
    # setuptools_scm from the git tag at build time) - not a separate literal
    # here, so it can't drift from pyproject.toml's own version the way it
    # used to.
    __version__ = _pkg_version("solt-pre-commit")
except PackageNotFoundError:
    # Only hit when solt_pre_commit is imported without ever having been
    # pip-installed (e.g. ad hoc PYTHONPATH tricks against a bare checkout).
    __version__ = "0.0.0+unknown"

__author__ = "Soltein SA de CV"

from .checks_branch_name import BranchNameValidator
from .checks_odoo_module import ChecksOdooModule
from .checks_odoo_module import run as run_checks
from .checks_odoo_module_csv import ChecksOdooModuleCSV
from .checks_odoo_module_po import ChecksOdooModulePO
from .checks_odoo_module_python import ChecksOdooModulePython
from .checks_odoo_module_xml import ChecksOdooModuleXML
from .checks_odoo_module_xml_advanced import ChecksOdooModuleXMLAdvanced
from .config_loader import (
    DEFAULT_ODOO_VERSION,
    SUPPORTED_ODOO_VERSIONS,
    ChangedFilesDetector,
    OdooVersionDetector,
    Severity,
    SoltConfig,
)
from .doc_coverage import CoverageReport, build_coverage_report

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
    "OdooVersionDetector",
    # Constants
    "SUPPORTED_ODOO_VERSIONS",
    "DEFAULT_ODOO_VERSION",
    # Doc coverage
    "CoverageReport",
    "build_coverage_report",
    # Functions
    "run_checks",
]
