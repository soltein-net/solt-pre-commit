"""Tests for check_manifest.py"""
import tempfile
from pathlib import Path
import pytest
from solt_pre_commit.check_manifest import check_manifest_structure, main


def test_valid_manifest():
    """Test a valid manifest file."""
    manifest_content = """
{
    'name': 'Test Module',
    'version': '16.0.1.0.0',
    'category': 'Test',
    'author': 'Soltein',
    'depends': ['base'],
    'installable': True,
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        errors = check_manifest_structure(Path(f.name))
        assert len(errors) == 0
        
        Path(f.name).unlink()


def test_missing_required_fields():
    """Test manifest with missing required fields."""
    manifest_content = """
{
    'name': 'Test Module',
    'depends': ['base'],
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        errors = check_manifest_structure(Path(f.name))
        assert len(errors) > 0
        assert any('Missing required keys' in err for err in errors)
        
        Path(f.name).unlink()


def test_invalid_version_format():
    """Test manifest with invalid version format."""
    manifest_content = """
{
    'name': 'Test Module',
    'version': '1.0',
    'category': 'Test',
    'author': 'Soltein',
    'depends': ['base'],
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        errors = check_manifest_structure(Path(f.name))
        assert any('Invalid version format' in err for err in errors)
        
        Path(f.name).unlink()


def test_unknown_keys():
    """Test manifest with unknown keys (typos)."""
    manifest_content = """
{
    'name': 'Test Module',
    'version': '16.0.1.0.0',
    'category': 'Test',
    'author': 'Soltein',
    'depends': ['base'],
    'licence': 'LGPL-3',  # Should be 'license'
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        errors = check_manifest_structure(Path(f.name))
        assert any('Unknown keys' in err for err in errors)
        
        Path(f.name).unlink()


def test_main_function():
    """Test the main function."""
    manifest_content = """
{
    'name': 'Test Module',
    'version': '16.0.1.0.0',
    'category': 'Test',
    'author': 'Soltein',
    'depends': ['base'],
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        result = main([f.name])
        assert result == 0
        
        Path(f.name).unlink()


def test_main_function_with_errors():
    """Test the main function with errors."""
    manifest_content = """
{
    'name': 'Test Module',
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='__manifest__.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()
        
        result = main([f.name])
        assert result == 1
        
        Path(f.name).unlink()
