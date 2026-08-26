from .file_reader import FileReader

class HashMapper:
    """Deterministic mapper with O(1) resolution against mapping.registry."""

    @classmethod
    def map(cls, env, headers, model_name='res.partner'):
        """
        Returns a dictionary: {original_header: {'target_field_id': id, 'confidence': 1.0, 'source': 'hash'}}
        """
        # Fetch the registry for the given model
        registry_records = env['mapping.registry'].search([('model_id.model', '=', model_name)], order='priority desc, id')
        
        # Build the O(1) lookup dictionary (normalized_synonym -> field_id)
        # Higher priority records are fetched first, but dictionary updates overwrite.
        # To respect priority, we should only insert if not already present.
        lookup = {}
        for reg in registry_records:
            norm_syn = FileReader.normalize_header(reg.synonym)
            if norm_syn not in lookup:
                lookup[norm_syn] = reg.field_id.id
                
        results = {}
        for header in headers:
            norm_header = FileReader.normalize_header(header)
            if norm_header in lookup:
                results[header] = {
                    'target_field_id': lookup[norm_header],
                    'confidence': 1.0,
                    'source': 'hash'
                }
                
        return results
