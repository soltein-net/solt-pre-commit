# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Setup for solt-pre-commit."""

from setuptools import find_packages, setup


def read_requirements():
    with open("requirements.txt", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def read_readme():
    with open("README.md", encoding="utf-8") as f:
        return f.read()


setup(
    name="solt-pre-commit",
    version="1.0.0",
    license="LGPL-3.0-or-later",
    description="Custom pre-commit hooks for Odoo module validation - Soltein",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "solt-check-odoo=solt_pre_commit.checks_odoo_module:main",
            "solt-check-branch=solt_pre_commit.checks_branch_name:main",
        ]
    },
)