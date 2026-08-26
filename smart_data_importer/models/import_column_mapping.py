from odoo import models, fields

class ImportColumnMapping(models.Model):
    _name = 'import.column.mapping'
    _description = 'Import Column Mapping'

    session_id = fields.Many2one('import.session', string='Session', required=True, ondelete='cascade')
    source_header = fields.Char(string='Original Header', required=True)
    source_header_normalized = fields.Char(string='Normalized Header', required=True)
    sample_values = fields.Char(string='Sample Values')
    
    target_field_id = fields.Many2one('ir.model.fields', string='Target Field', domain="[('model_id.model', '=', 'res.partner')]")
    
    confidence = fields.Float(string='Confidence Score', help="From 0.0 to 1.0")
    source = fields.Selection([
        ('hash', 'Hash'),
        ('fuzzy', 'Fuzzy'),
        ('llm', 'LLM'),
        ('manual', 'Manual')
    ], string='Source')
    
    is_ignored = fields.Boolean(string='Ignore', default=False)
    is_conflict = fields.Boolean(string='Conflict', help="Target field is assigned to multiple columns", default=False)
