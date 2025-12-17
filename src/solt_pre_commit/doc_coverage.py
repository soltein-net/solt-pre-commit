# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Documentation coverage analysis for Odoo modules.

Generates structured metrics about documentation coverage:
- Method docstring coverage
- Field string/help attribute coverage
- Per-module and per-model breakdown
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class MethodMetrics:
    """Metrics for a single method."""

    name: str
    lineno: int
    has_docstring: bool
    is_public: bool
    docstring_length: int = 0


@dataclass
class FieldMetrics:
    """Metrics for a single field."""

    name: str
    lineno: int
    field_type: str
    has_string: bool
    has_help: bool
    is_related: bool = False


@dataclass
class ModelMetrics:
    """Metrics for a single Odoo model."""

    name: str
    model_name: str  # _name value
    filename: str
    methods: List[MethodMetrics] = field(default_factory=list)
    fields: List[FieldMetrics] = field(default_factory=list)

    @property
    def total_public_methods(self) -> int:
        return sum(1 for m in self.methods if m.is_public)

    @property
    def documented_methods(self) -> int:
        return sum(1 for m in self.methods if m.is_public and m.has_docstring)

    @property
    def method_coverage(self) -> float:
        total = self.total_public_methods
        return (self.documented_methods / total * 100) if total > 0 else 100.0

    @property
    def total_fields(self) -> int:
        return len([f for f in self.fields if not f.is_related])

    @property
    def fields_with_string(self) -> int:
        return sum(1 for f in self.fields if not f.is_related and f.has_string)

    @property
    def fields_with_help(self) -> int:
        return sum(1 for f in self.fields if not f.is_related and f.has_help)

    @property
    def string_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_string / total * 100) if total > 0 else 100.0

    @property
    def help_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_help / total * 100) if total > 0 else 100.0


@dataclass
class ModuleMetrics:
    """Metrics for a single Odoo module."""

    name: str
    path: str
    models: List[ModelMetrics] = field(default_factory=list)

    @property
    def total_models(self) -> int:
        return len(self.models)

    @property
    def total_public_methods(self) -> int:
        return sum(m.total_public_methods for m in self.models)

    @property
    def documented_methods(self) -> int:
        return sum(m.documented_methods for m in self.models)

    @property
    def method_coverage(self) -> float:
        total = self.total_public_methods
        return (self.documented_methods / total * 100) if total > 0 else 100.0

    @property
    def total_fields(self) -> int:
        return sum(m.total_fields for m in self.models)

    @property
    def fields_with_string(self) -> int:
        return sum(m.fields_with_string for m in self.models)

    @property
    def fields_with_help(self) -> int:
        return sum(m.fields_with_help for m in self.models)

    @property
    def string_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_string / total * 100) if total > 0 else 100.0

    @property
    def help_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_help / total * 100) if total > 0 else 100.0


@dataclass
class CoverageReport:
    """Complete coverage report for all modules."""

    modules: List[ModuleMetrics] = field(default_factory=list)
    errors_count: int = 0
    warnings_count: int = 0
    info_count: int = 0
    ruff_issues: int = 0
    pylint_issues: int = 0

    @property
    def total_models(self) -> int:
        return sum(m.total_models for m in self.modules)

    @property
    def total_public_methods(self) -> int:
        return sum(m.total_public_methods for m in self.modules)

    @property
    def documented_methods(self) -> int:
        return sum(m.documented_methods for m in self.modules)

    @property
    def method_coverage(self) -> float:
        total = self.total_public_methods
        return (self.documented_methods / total * 100) if total > 0 else 100.0

    @property
    def total_fields(self) -> int:
        return sum(m.total_fields for m in self.modules)

    @property
    def fields_with_string(self) -> int:
        return sum(m.fields_with_string for m in self.modules)

    @property
    def fields_with_help(self) -> int:
        return sum(m.fields_with_help for m in self.modules)

    @property
    def string_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_string / total * 100) if total > 0 else 100.0

    @property
    def help_coverage(self) -> float:
        total = self.total_fields
        return (self.fields_with_help / total * 100) if total > 0 else 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "modules_count": len(self.modules),
                "models_count": self.total_models,
                "methods": {
                    "total": self.total_public_methods,
                    "documented": self.documented_methods,
                    "coverage": round(self.method_coverage, 1),
                },
                "fields": {
                    "total": self.total_fields,
                    "with_string": self.fields_with_string,
                    "with_help": self.fields_with_help,
                    "string_coverage": round(self.string_coverage, 1),
                    "help_coverage": round(self.help_coverage, 1),
                },
                "issues": {
                    "errors": self.errors_count,
                    "warnings": self.warnings_count,
                    "info": self.info_count,
                    "ruff": self.ruff_issues,
                    "pylint": self.pylint_issues,
                },
            },
            "modules": [
                {
                    "name": mod.name,
                    "path": mod.path,
                    "models_count": mod.total_models,
                    "methods": {
                        "total": mod.total_public_methods,
                        "documented": mod.documented_methods,
                        "coverage": round(mod.method_coverage, 1),
                    },
                    "fields": {
                        "total": mod.total_fields,
                        "with_string": mod.fields_with_string,
                        "with_help": mod.fields_with_help,
                        "string_coverage": round(mod.string_coverage, 1),
                        "help_coverage": round(mod.help_coverage, 1),
                    },
                    "models": [
                        {
                            "class_name": model.name,
                            "model_name": model.model_name,
                            "filename": model.filename,
                            "method_coverage": round(model.method_coverage, 1),
                            "string_coverage": round(model.string_coverage, 1),
                            "help_coverage": round(model.help_coverage, 1),
                        }
                        for model in mod.models
                    ],
                }
                for mod in self.modules
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, filepath: str | Path) -> None:
        """Save report to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


class CoverageAnalyzer:
    """Analyzes Python files to extract documentation coverage metrics."""

    # Fields that don't need string/help
    SKIP_STRING_FIELDS = {
        "active",
        "name",
        "sequence",
        "company_id",
        "currency_id",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "message_ids",
        "message_follower_ids",
        "activity_ids",
    }

    SKIP_HELP_FIELDS = {
        "active",
        "name",
        "sequence",
        "company_id",
        "currency_id",
    }

    SKIP_DOCSTRING_METHODS = {
        "__init__",
        "__str__",
        "__repr__",
        "__len__",
        "__bool__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__iter__",
        "__next__",
        "__contains__",
        "__call__",
        "__enter__",
        "__exit__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__hash__",
        "__format__",
    }

    def __init__(self, config=None):
        self.config = config
        if config:
            self.skip_string_fields = config.skip_string_fields
            self.skip_help_fields = config.skip_help_fields
            self.skip_docstring_methods = config.skip_docstring_methods
        else:
            self.skip_string_fields = self.SKIP_STRING_FIELDS
            self.skip_help_fields = self.SKIP_HELP_FIELDS
            self.skip_docstring_methods = self.SKIP_DOCSTRING_METHODS

    def analyze_module(
        self,
        module_name: str,
        module_path: str,
        all_models: dict,
        all_fields: dict,
        all_methods: dict,
    ) -> ModuleMetrics:
        """Analyze a single module and return metrics."""
        module_metrics = ModuleMetrics(name=module_name, path=module_path)

        for model_key, model_info in all_models.items():
            if not model_info.get("is_odoo_model"):
                continue

            model_metrics = ModelMetrics(
                name=model_info["name"],
                model_name=model_info.get("_name") or model_info["name"],
                filename=model_info.get("filename", ""),
            )

            # Analyze methods
            for method in all_methods.get(model_key, []):
                if method["name"].startswith("_") and not method["name"].startswith("__"):
                    continue  # Skip private methods
                if method["name"] in self.skip_docstring_methods:
                    continue

                model_metrics.methods.append(
                    MethodMetrics(
                        name=method["name"],
                        lineno=method["lineno"],
                        has_docstring=method.get("has_docstring", False),
                        is_public=not method["name"].startswith("_"),
                        docstring_length=len(method.get("docstring") or ""),
                    )
                )

            # Analyze fields
            for fld in all_fields.get(model_key, []):
                if fld["name"].startswith("_"):
                    continue  # Skip private fields

                is_related = bool(fld.get("related"))

                # Check if field needs string/help
                needs_string = fld["name"] not in self.skip_string_fields and not is_related
                needs_help = fld["name"] not in self.skip_help_fields and not is_related

                model_metrics.fields.append(
                    FieldMetrics(
                        name=fld["name"],
                        lineno=fld["lineno"],
                        field_type=fld["type"],
                        has_string=bool(fld.get("string")) if needs_string else True,
                        has_help=bool(fld.get("help")) if needs_help else True,
                        is_related=is_related,
                    )
                )

            if model_metrics.methods or model_metrics.fields:
                module_metrics.models.append(model_metrics)

        return module_metrics


def build_coverage_report(
    checks_results: list,
    ruff_issues: int = 0,
    pylint_issues: int = 0,
) -> CoverageReport:
    """Build a coverage report from ChecksOdooModule results.

    Args:
        checks_results: List of (module_name, ChecksOdooModule) tuples
        ruff_issues: Number of Ruff issues found
        pylint_issues: Number of Pylint issues found

    Returns:
        CoverageReport with all metrics
    """
    report = CoverageReport(
        ruff_issues=ruff_issues,
        pylint_issues=pylint_issues,
    )

    analyzer = CoverageAnalyzer()

    for module_name, checks_obj in checks_results:
        # Get check result counts
        if hasattr(checks_obj, "check_result"):
            counts = checks_obj.check_result.get_counts()
            # Import Severity from the same package
            try:
                from .checks_odoo_module import Severity
            except ImportError:
                # Fallback for standalone usage
                class Severity:
                    ERROR = "error"
                    WARNING = "warning"
                    INFO = "info"

            report.errors_count += counts.get(Severity.ERROR, 0)
            report.warnings_count += counts.get(Severity.WARNING, 0)
            report.info_count += counts.get(Severity.INFO, 0)

        # Get all models/fields/methods from the python checker
        all_models = {}
        all_fields = {}
        all_methods = {}

        # The Python checker stores data per file, we need to aggregate
        for ext, files in checks_obj.manifest_referenced_files.items():
            if ext != ".py":
                continue
            for file_data in files:
                models = file_data.get("models", {})
                fields = file_data.get("fields", {})
                methods = file_data.get("methods", {})

                for class_name, model_info in models.items():
                    key = f"{file_data['filename']}:{class_name}"
                    model_info["filename"] = file_data["filename"]
                    all_models[key] = model_info
                    all_fields[key] = fields.get(class_name, [])
                    all_methods[key] = methods.get(class_name, [])

        module_metrics = analyzer.analyze_module(
            module_name=module_name,
            module_path=checks_obj.odoo_addon_path,
            all_models=all_models,
            all_fields=all_fields,
            all_methods=all_methods,
        )

        report.modules.append(module_metrics)

    return report


def generate_report_from_cli(
    module_paths: list,
    output_file: str,
    config_path: Optional[str] = None,
) -> CoverageReport:
    """Generate coverage report from CLI.

    This is a convenience function for generating reports without
    running the full validation.
    """
    # Import here to avoid circular imports
    from .checks_odoo_module import ChecksOdooModule, SeverityConfig

    severity_config = SeverityConfig(config_path)
    checks_objects = []

    for module_path in module_paths:
        checks_obj = ChecksOdooModule(
            module_path,
            verbose=False,
            severity_config=severity_config,
        )
        # Only run Python checks for coverage analysis
        checks_obj.check_python()
        checks_objects.append((checks_obj.odoo_addon_name, checks_obj))

    report = build_coverage_report(checks_objects)
    report.save(output_file)

    return report
