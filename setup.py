# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Setup for solt-pre-commit."""

import re

from setuptools import find_packages, setup


def read_dependencies():
    """Single source of truth is pyproject.toml's [project].dependencies -
    parsed as plain text (not tomllib) so this doesn't need a TOML-parsing
    dependency just to read one array, and still works on Python 3.10
    (tomllib is 3.11+)."""
    with open("pyproject.toml", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not match:
        raise RuntimeError("dependencies not found in pyproject.toml")
    return re.findall(r'"([^"]+)"', match.group(1))


def read_readme():
    with open("README.md", encoding="utf-8") as f:
        return f.read()


def read_version():
    """Single source of truth is pyproject.toml's [project].version - parsed as
    plain text (not tomllib) so this doesn't need a TOML-parsing dependency just
    to read one line, and still works on Python 3.10 (tomllib is 3.11+)."""
    with open("pyproject.toml", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("version not found in pyproject.toml")


setup(
    name="solt-pre-commit",
    version=read_version(),
    license="LGPL-3.0-or-later",
    description="Custom pre-commit hooks for Odoo module validation - Soltein (supports Odoo 17.0, 18.0, 19.0)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Soltein SA de CV",
    author_email="dev@soltein.mx",
    url="https://github.com/soltein-net/solt-pre-commit",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
        "Framework :: Odoo",
    ],
    python_requires=">=3.10",
    install_requires=read_dependencies(),
    entry_points={
        "console_scripts": [
            "solt-check-odoo=solt_pre_commit.checks_odoo_module:main",
            "solt-check-branch=solt_pre_commit.checks_branch_name:main",
            "solt-check-requirements=solt_pre_commit.checks_requirements:main",
            "solt-test-changed-modules=solt_pre_commit.checks_test_changed_modules:main",
            "solt-test-module=solt_pre_commit.odoo_test_runner:main",
        ]
    },
)
