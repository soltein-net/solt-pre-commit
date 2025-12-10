# Examples of Issues Caught by Solt Pre-commit Hooks

This document provides concrete examples of issues that the hooks will catch.

## 1. Manifest Validation (`check-odoo-manifest`)

### ❌ Invalid Manifest
```python
# __manifest__.py
{
    'name': 'My Module',
    'version': '1.0',  # Invalid version format
    'licence': 'LGPL-3',  # Typo: should be 'license'
}
```

**Errors:**
- Missing required keys: author, category, depends
- Unknown keys (possible typo): licence
- Invalid version format '1.0'. Expected format: X.Y.Z.W.X (e.g., 16.0.1.0.0)

### ✓ Valid Manifest
```python
# __manifest__.py
{
    'name': 'My Module',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'author': 'My Company',
    'depends': ['base', 'sale'],
    'license': 'LGPL-3',
    'installable': True,
}
```

## 2. Deprecated API Detection (`check-odoo-deprecated`)

### ❌ Deprecated APIs
```python
# Old-style imports
from openerp import models, fields, api  # ❌ Use 'odoo' instead

class MyModel(models.Model):
    _name = 'my.model'
    
    # Old API decorators
    @api.one  # ❌ Deprecated
    def my_method(self):
        pass
    
    # Old API methods
    def another_method(self):
        records = self.browse(cr, uid, ids)  # ❌ Old API
```

**Errors:**
- Line 2: Import from "openerp" is deprecated, use "odoo" instead
- Line 8: @api.one is deprecated, use other decorators or remove
- Line 13: Old API browse() is deprecated, use self.env[model].browse()

### ✓ Modern APIs
```python
from odoo import models, fields, api

class MyModel(models.Model):
    _name = 'my.model'
    
    @api.depends('field_a')
    def _compute_field_b(self):
        for record in self:
            record.field_b = record.field_a * 2
    
    def another_method(self):
        records = self.env['my.model'].browse([1, 2, 3])
```

## 3. XML Validation (`check-odoo-xml`)

### ❌ Invalid XML
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Missing id attribute -->
    <record model="ir.ui.view">
        <field name="name">My View</field>
    </record>
    
    <!-- Duplicate IDs -->
    <record id="my_view" model="ir.ui.view">
        <field name="model">res.partner</field>
    </record>
    
    <record id="my_view" model="ir.ui.view">
        <field name="model">res.partner</field>
    </record>
</odoo>
```

**Errors:**
- Record without 'id' attribute (model: ir.ui.view)
- Duplicate ID in file: 'my_view'

### ✓ Valid XML
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_partner_form_custom" model="ir.ui.view">
        <field name="name">res.partner.form.custom</field>
        <field name="model">res.partner</field>
        <field name="inherit_id" ref="base.view_partner_form"/>
        <field name="arch" type="xml">
            <field name="email" position="after">
                <field name="custom_field"/>
            </field>
        </field>
    </record>
</odoo>
```

## 4. Model Validation (`check-odoo-models`)

### ❌ Model Issues
```python
from odoo import models, fields

class MyModel(models.Model):
    _name = 'my.model'  # Missing _description
    
    def unsafe_query(self):
        # SQL injection risk
        self.env.cr.execute("DELETE FROM table WHERE id = %s" % self.id)
```

**Errors:**
- Class 'MyModel': Model with '_name' should have '_description' for better UX
- Class 'MyModel': Line 8: Potential SQL injection risk. Use parameterized queries

### ✓ Valid Model
```python
from odoo import models, fields

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    
    name = fields.Char(string='Name', required=True)
    
    def safe_query(self):
        # Safe parameterized query
        self.env.cr.execute(
            "DELETE FROM table WHERE id = %s",
            (self.id,)
        )
```

## 5. Common Odoo Patterns

### Model Inheritance

```python
# Inherit existing model
class PartnerExtension(models.Model):
    _inherit = 'res.partner'
    _description = 'Partner Extension'
    
    custom_field = fields.Char(string='Custom Field')
```

### Computing Fields

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    total_discount = fields.Float(
        string='Total Discount',
        compute='_compute_total_discount',
        store=True
    )
    
    @api.depends('order_line.discount')
    def _compute_total_discount(self):
        for order in self:
            order.total_discount = sum(
                line.price_subtotal * line.discount / 100
                for line in order.order_line
            )
```

### Security Rules

```python
# Good: Using domain for security
def _get_allowed_records(self):
    return self.env['my.model'].search([
        ('company_id', '=', self.env.company.id)
    ])

# Bad: Relying on record rules without domain
def _get_all_records(self):
    return self.env['my.model'].search([])
```

## Benefits

These hooks help you:

1. **Catch errors early** - Before you even start the Odoo server
2. **Maintain consistency** - Enforce coding standards across your team
3. **Prevent security issues** - Detect SQL injection vulnerabilities
4. **Stay up-to-date** - Identify deprecated APIs that need updating
5. **Improve quality** - Ensure manifest files are complete and XML is valid
6. **Save time** - Reduce debugging time by catching issues before runtime

## Integration with CI/CD

These hooks can be integrated into your CI/CD pipeline:

```yaml
# .github/workflows/pre-commit.yml
name: Pre-commit

on: [push, pull_request]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Run pre-commit
        uses: pre-commit/action@v3.0.0
```

This ensures all commits pass validation before being merged.
