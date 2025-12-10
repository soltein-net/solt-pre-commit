# Contributing to Solt Pre-commit Hooks

Thank you for your interest in contributing to the Solt Pre-commit Hooks project! This document provides guidelines for contributing.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/soltein-net/solt-pre-commit.git
   cd solt-pre-commit
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   pip install pytest
   ```

3. Install pre-commit (optional, for testing):
   ```bash
   pip install pre-commit
   ```

## Running Tests

Run the test suite:
```bash
pytest tests/ -v
```

Run tests with coverage:
```bash
pytest tests/ --cov=solt_pre_commit --cov-report=html
```

## Adding a New Hook

1. Create a new Python file in `solt_pre_commit/` (e.g., `check_security.py`)
2. Implement the checker with a `main()` function that:
   - Takes a list of file paths as arguments
   - Returns 0 on success, 1 on failure
   - Prints clear error messages
3. Add the hook to `.pre-commit-hooks.yaml`
4. Add the entry point to `setup.py`
5. Write tests in `tests/test_check_security.py`
6. Update the README.md with documentation

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write clear, descriptive docstrings
- Keep functions focused and small

## Testing Guidelines

- Write unit tests for all new functionality
- Test both success and failure cases
- Use temporary files for file-based tests
- Clean up test files after tests complete

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-hook`)
3. Make your changes
4. Run tests to ensure they pass
5. Commit your changes with clear messages
6. Push to your fork
7. Create a Pull Request

## Reporting Issues

When reporting issues, please include:
- Python version
- Odoo version (if relevant)
- Steps to reproduce
- Expected vs actual behavior
- Any error messages or logs

## Questions?

Feel free to open an issue for any questions or discussions.
