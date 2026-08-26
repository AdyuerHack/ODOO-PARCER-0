from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64

class ImportSession(models.Model):
    _name = 'import.session'
    _description = 'Import Session'
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    file = fields.Binary(string='File', required=True, attachment=True)
    filename = fields.Char(string='Filename', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzing', 'Analyzing'),
        ('mapped', 'Mapped')
    ], string='Status', default='draft', required=True, copy=False)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, required=True)
    
    encoding = fields.Char(string='Encoding', readonly=True)
    delimiter = fields.Char(string='Delimiter', readonly=True)
    header_row_index = fields.Integer(string='Header Row Index', readonly=True)
    total_rows = fields.Integer(string='Total Rows', readonly=True)
    
    column_mapping_ids = fields.One2many('import.column.mapping', 'session_id', string='Column Mappings')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('import.session') or _('New')
        return super().create(vals_list)

    @api.constrains('filename', 'file')
    def _check_file_validity(self):
        max_size_mb = float(self.env['ir.config_parameter'].sudo().get_param('smart_data_importer.max_file_size_mb', default='50'))
        max_size_bytes = max_size_mb * 1024 * 1024
        
        for session in self:
            if not session.filename:
                continue
            
            # Check extension
            valid_extensions = ['.csv', '.xls', '.xlsx']
            if not any(session.filename.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError(_("Only CSV and Excel files (.csv, .xls, .xlsx) are supported."))
            
            # Check size
            if session.file:
                # Odoo stores binaries in base64. 
                # Length of base64 string * 3/4 is roughly the size in bytes.
                file_size = len(session.file) * 3 / 4
                if file_size > max_size_bytes:
                    raise ValidationError(_("File size exceeds the maximum limit of %s MB.") % max_size_mb)

    def action_analyze(self):
        self.ensure_one()
        from ..services.orchestrator import PipelineOrchestrator
        PipelineOrchestrator.run_premapping(self)
        return True

    preview_data = fields.Char(string='Preview', compute='_compute_preview_data', store=False)
    
    def _compute_preview_data(self):
        for rec in self:
            rec.preview_data = 'preview'

    def get_preview_rows(self):
        self.ensure_one()
        if not self.file:
            return []
        from ..services.file_reader import FileReader
        try:
            file_info = FileReader.read(self.file, self.filename)
            df = file_info['df']
            # Return first 10 rows as list of dicts. Handle NaNs.
            df = df.fillna('')
            return df.head(10).to_dict('records')
        except Exception:
            return []


