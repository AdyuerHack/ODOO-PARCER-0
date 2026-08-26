import pandas as pd
import chardet
import csv
import base64
import io
import unicodedata
from odoo.exceptions import UserError
from odoo import _

class FileReader:
    """Service to read and parse Excel and CSV files."""

    @staticmethod
    def normalize_header(header):
        """Shared normalization: trim, lowercase, remove diacritics."""
        if not header:
            return ''
        header = str(header).strip().lower()
        # Remove diacritics
        header = ''.join(c for c in unicodedata.normalize('NFD', header)
                         if unicodedata.category(c) != 'Mn')
        return header

    @classmethod
    def read(cls, file_base64, filename):
        """Reads file and returns a DataFrame, along with metadata."""
        if not file_base64:
            raise UserError(_("No file content found."))
            
        file_content = base64.b64decode(file_base64)
        
        if filename.lower().endswith('.csv'):
            return cls._read_csv(file_content)
        elif filename.lower().endswith(('.xls', '.xlsx')):
            return cls._read_excel(file_content)
        else:
            raise UserError(_("Unsupported file format."))

    @classmethod
    def _read_csv(cls, file_content):
        # Detect encoding
        result = chardet.detect(file_content[:10000])
        encoding = result['encoding'] or 'utf-8'
        
        # Decode text
        try:
            text = file_content.decode(encoding)
        except UnicodeDecodeError:
            encoding = 'latin-1'
            text = file_content.decode(encoding)
            
        # Detect delimiter
        try:
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(text[:4096]).delimiter
        except csv.Error:
            delimiter = ',' # fallback
            
        # Find header row
        # Simple heuristic: assume first row is header for CSV for MVP
        df = pd.read_csv(io.StringIO(text), sep=delimiter)
        
        return {
            'df': df,
            'encoding': encoding,
            'delimiter': delimiter,
            'header_row_index': 0,
            'total_rows': len(df)
        }
        
    @classmethod
    def _read_excel(cls, file_content):
        df = pd.read_excel(io.BytesIO(file_content))
        return {
            'df': df,
            'encoding': 'utf-8',
            'delimiter': False,
            'header_row_index': 0,
            'total_rows': len(df)
        }
