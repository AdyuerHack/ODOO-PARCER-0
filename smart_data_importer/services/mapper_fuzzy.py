from rapidfuzz import process, fuzz
from .file_reader import FileReader

class FuzzyMapper:
    """Approximate mapper using Levenshtein distance."""

    @classmethod
    def map(cls, env, headers, model_name='res.partner', threshold=85):
        """
        Returns a dictionary for headers that matched above the threshold.
        """
        # Fetch available fields for the model
        fields_records = env['ir.model.fields'].search([('model_id.model', '=', model_name)])
        
        # Build lookup: normalized_field_string -> field_id
        field_choices = {}
        for f in fields_records:
            norm_desc = FileReader.normalize_header(f.field_description)
            norm_name = FileReader.normalize_header(f.name)
            
            if norm_desc:
                field_choices[norm_desc] = f.id
            if norm_name:
                field_choices[norm_name] = f.id
                
        choices_list = list(field_choices.keys())
        
        results = {}
        for header in headers:
            norm_header = FileReader.normalize_header(header)
            # Find best match
            match = process.extractOne(norm_header, choices_list, scorer=fuzz.WRatio)
            
            if match:
                best_string, score, _ = match
                if score >= threshold:
                    results[header] = {
                        'target_field_id': field_choices[best_string],
                        'confidence': round(score / 100.0, 2),
                        'source': 'fuzzy'
                    }
                    
        return results
