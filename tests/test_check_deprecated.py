"""Tests for check_deprecated.py"""
import tempfile
from pathlib import Path
from solt_pre_commit.check_deprecated import check_deprecated_usage, main


def test_deprecated_api_one():
    """Test detection of deprecated @api.one."""
    code = """
from odoo import api, models

class TestModel(models.Model):
    _name = 'test.model'
    
    @api.one
    def some_method(self):
        pass
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        
        issues = check_deprecated_usage(Path(f.name))
        assert len(issues) > 0
        assert any('@api.one' in msg for _, msg in issues)
        
        Path(f.name).unlink()


def test_deprecated_openerp_import():
    """Test detection of deprecated openerp import."""
    code = """
from openerp import models, fields
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        
        issues = check_deprecated_usage(Path(f.name))
        assert len(issues) > 0
        assert any('openerp' in msg for _, msg in issues)
        
        Path(f.name).unlink()


def test_no_deprecated_usage():
    """Test file with no deprecated usage."""
    code = """
from odoo import api, models, fields

class TestModel(models.Model):
    _name = 'test.model'
    _description = 'Test Model'
    
    name = fields.Char(string='Name')
    
    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        
        issues = check_deprecated_usage(Path(f.name))
        assert len(issues) == 0
        
        Path(f.name).unlink()


def test_main_function():
    """Test the main function."""
    code = """
from odoo import models

class TestModel(models.Model):
    _name = 'test.model'
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = main([f.name])
        assert result == 0
        
        Path(f.name).unlink()
