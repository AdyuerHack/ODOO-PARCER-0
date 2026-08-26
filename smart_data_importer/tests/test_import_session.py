from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
import base64

@tagged('post_install', '-at_install')
class TestImportSession(TransactionCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env['import.session']
        cls.Config = cls.env['ir.config_parameter']
        
        # Ensure config parameters
        cls.Config.sudo().set_param('smart_data_importer.max_file_size_mb', '50')
        cls.Config.sudo().set_param('smart_data_importer.fuzzy_threshold', '85')
        
        # Test CSV content
        cls.csv_content = b"NIT,Correo electronico,Tel\xf3fno,Nombre\n123456,test@example.com,5551234,Test Company"
        cls.csv_b64 = base64.b64encode(cls.csv_content)
        
    def test_01_upload_and_validation(self):
        """Test file extension validation."""
        with self.assertRaises(ValidationError):
            self.Session.create({
                'filename': 'test.pdf',
                'file': base64.b64encode(b"dummy")
            })
            
        session = self.Session.create({
            'filename': 'test.csv',
            'file': self.csv_b64
        })
        self.assertEqual(session.state, 'draft')
        
    def test_02_analyze_and_mapping(self):
        """Test the file reader and mappers."""
        session = self.Session.create({
            'filename': 'test.csv',
            'file': self.csv_b64
        })
        session.action_analyze()
        
        self.assertEqual(session.state, 'mapped')
        self.assertEqual(session.total_rows, 1)
        
        mappings = session.column_mapping_ids
        self.assertEqual(len(mappings), 4)
        
        # 'NIT' should be Hash mapped to 'vat'
        nit_map = mappings.filtered(lambda m: m.source_header == 'NIT')
        self.assertEqual(nit_map.source, 'hash')
        self.assertEqual(nit_map.target_field_name, 'vat')
        
        # 'Correo electronico' should be Hash mapped to 'email'
        email_map = mappings.filtered(lambda m: m.source_header == 'Correo electronico')
        self.assertEqual(email_map.source, 'hash')
        self.assertEqual(email_map.target_field_name, 'email')
