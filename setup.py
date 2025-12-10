"""Setup configuration for solt-pre-commit hooks."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="solt-pre-commit",
    version="1.0.0",
    author="Soltein",
    description="Pre-commit hooks for Odoo module development",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/soltein-net/solt-pre-commit",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "lxml>=4.6.0",
    ],
    entry_points={
        "console_scripts": [
            "check-odoo-manifest=solt_pre_commit.check_manifest:main",
            "check-odoo-init=solt_pre_commit.check_init:main",
            "check-odoo-xml=solt_pre_commit.check_xml:main",
            "check-odoo-models=solt_pre_commit.check_models:main",
            "check-odoo-deprecated=solt_pre_commit.check_deprecated:main",
        ],
    },
)
