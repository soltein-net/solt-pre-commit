# Ruff Configuration Levels for Odoo Projects

This document explains the different Ruff configuration levels available in solt-pre-commit.

## Overview

Ruff rules are organized into three levels of strictness:

| Level | Name | Use Case | Rules Enabled |
|-------|------|----------|---------------|
| 1 | Essential | Legacy codebases, quick adoption | E, F, W (errors only) |
| 2 | Standard | Most Odoo projects (DEFAULT) | + I, B, C4 |
| 3 | Strict | New projects, high standards | + N, UP, SIM, RUF |

## Level 1: Essential

**For**: Legacy codebases with significant technical debt, quick CI setup.

**What it catches**:
- Syntax errors (E9xx)
- Undefined names and unused imports (F)
- Deprecated features (W6xx)

**Configuration**:
```toml
[tool.ruff.lint]
select = ["E9", "F", "W6"]
ignore = []
```

**Typical issues found**: 5-20 per large module

---

## Level 2: Standard (DEFAULT)

**For**: Most Odoo projects. Safe, non-breaking rules.

**What it catches**:
- All Level 1 issues
- Import sorting issues (I)
- Common bugs and design problems (B)
- Unnecessary list/dict comprehensions (C4)

**Configuration**:
```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "W",   # pycodestyle warnings
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]
ignore = [
    "E501",  # line too long (handled by formatter)
    "E731",  # lambda assignment
    "B008",  # function call in default argument (Odoo pattern)
    "B904",  # raise without from
]
```

**Typical issues found**: 20-100 per large module

---

## Level 3: Strict

**For**: New projects, teams with high code quality standards.

**What it catches**:
- All Level 2 issues
- Naming conventions (N) - function/variable naming
- Python version upgrades (UP) - modernize syntax
- Code simplification (SIM) - reduce complexity
- Ruff-specific rules (RUF) - additional checks

**Configuration**:
```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # Pyflakes
    "W",   # pycodestyle warnings
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "SIM", # flake8-simplify
    "RUF", # Ruff-specific rules
]
ignore = [
    "E501",   # line too long
    "E731",   # lambda assignment
    "B008",   # function call in default argument
    "B904",   # raise without from
    "N802",   # function name should be lowercase
    "N803",   # argument name should be lowercase
    "N806",   # variable in function should be lowercase
    "N815",   # mixedCase variable
    "N999",   # invalid module name
    "SIM102", # nested if statements
    "SIM108", # ternary operator
    "UP007",  # Use X | Y for type union
    "RUF012", # mutable class attributes
]
```

**Typical issues found**: 50-300 per large module

---

## Migration Path

### Starting from scratch (new project)
Use **Level 2** or **Level 3**

### Existing codebase with no linting
1. Start with **Level 1**
2. Fix all issues (~1-2 hours for most modules)
3. Upgrade to **Level 2**
4. Gradually fix issues
5. Optionally upgrade to **Level 3**

### Existing codebase already using pylint/flake8
Start with **Level 2**, should be mostly compatible

---

## Rule Categories Explained

### E - pycodestyle errors
- Indentation, whitespace, syntax
- **Safe to enable**: Always

### F - Pyflakes
- Undefined names, unused imports/variables
- **Safe to enable**: Always

### W - pycodestyle warnings
- Line breaks, whitespace, deprecated features
- **Safe to enable**: Always

### I - isort
- Import sorting and organization
- **Safe to enable**: Yes (autofix available)

### B - flake8-bugbear
- Common bugs and design problems
- **Safe to enable**: Yes, with Odoo-specific ignores

### C4 - flake8-comprehensions
- Unnecessary list/dict/set calls
- **Safe to enable**: Yes

### N - pep8-naming
- Function/variable/class naming conventions
- **Safe to enable**: With ignores for Odoo patterns

### UP - pyupgrade
- Python version-specific syntax improvements
- **Safe to enable**: If targeting Python 3.10+

### SIM - flake8-simplify
- Code simplification suggestions
- **Safe to enable**: With some ignores

### RUF - Ruff-specific
- Additional checks unique to Ruff
- **Safe to enable**: With Odoo-specific ignores

---

## Odoo-Specific Ignores (Why)

| Rule | Reason |
|------|--------|
| E501 | Handled by formatter (black/ruff format) |
| E731 | Lambda assignments common in Odoo defaults |
| B008 | `fields.Char(default=lambda self: ...)` pattern |
| B904 | `raise ValidationError(...)` without `from` is common |
| N802 | Odoo uses specific naming like `_compute_*` |
| N999 | Module names like `solt_budget` are valid |
| RUF012 | Odoo fields are intentionally mutable class attributes |

---

## How to Change Level

Edit your `pyproject.toml`:

```toml
[tool.ruff.lint]
# Change this line to use different levels
select = [
    # Level 1 (Essential)
    "E", "F", "W",

    # Level 2 (Standard) - add these
    "I", "B", "C4",

    # Level 3 (Strict) - add these
    # "N", "UP", "SIM", "RUF",
]
```