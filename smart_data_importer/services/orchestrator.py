from .file_reader import FileReader
from .mapper_hash import HashMapper
from .mapper_fuzzy import FuzzyMapper
from odoo.exceptions import UserError
from odoo import _

class PipelineOrchestrator:
    
    @classmethod
    def run_premapping(cls, session):
        """
        Coordinates reading -> header detection -> hash -> fuzzy.
        Creates import.column.mapping records.
        """
        # 1. Read file and extract headers/metadata
        try:
            file_info = FileReader.read(session.file, session.filename)
        except Exception as e:
            raise UserError(_("Error reading file: %s") % str(e))
            
        df = file_info['df']
        
        # Save metadata to session
        session.write({
            'encoding': file_info['encoding'],
            'delimiter': file_info['delimiter'],
            'header_row_index': file_info['header_row_index'],
            'total_rows': file_info['total_rows'],
            'state': 'analyzing'
        })
        
        # Clear existing mappings
        session.column_mapping_ids.unlink()
        
        # Ensure we have columns
        headers = list(df.columns)
        if not headers:
            return
            
        # 2. Hash Mapping
        hash_results = HashMapper.map(session.env, headers, model_name='res.partner')
        
        # Find unresolved headers
        unresolved_headers = [h for h in headers if h not in hash_results]
        
        # 3. Fuzzy Mapping
        # Get threshold from config
        threshold = int(session.env['ir.config_parameter'].sudo().get_param('smart_data_importer.fuzzy_threshold', default='85'))
        fuzzy_results = FuzzyMapper.map(session.env, unresolved_headers, model_name='res.partner', threshold=threshold)
        
        # 4. Build mapping records
        mapping_vals = []
        assigned_fields = {} # target_field_id -> list of headers
        
        for header in headers:
            val = {
                'session_id': session.id,
                'source_header': header,
                'source_header_normalized': FileReader.normalize_header(header),
                # sample_values: grab first 3 non-null values
                'sample_values': ', '.join([str(x) for x in df[header].dropna().head(3).tolist()])
            }
            
            if header in hash_results:
                val.update(hash_results[header])
            elif header in fuzzy_results:
                val.update(fuzzy_results[header])
                
            target_id = val.get('target_field_id')
            if target_id:
                if target_id not in assigned_fields:
                    assigned_fields[target_id] = []
                assigned_fields[target_id].append(header)
                
            mapping_vals.append(val)
            
        # 5. Detect conflicts
        for val in mapping_vals:
            target_id = val.get('target_field_id')
            if target_id and len(assigned_fields[target_id]) > 1:
                val['is_conflict'] = True
                
        # 6. Create records and update state
        session.env['import.column.mapping'].create(mapping_vals)
        session.state = 'mapped'
