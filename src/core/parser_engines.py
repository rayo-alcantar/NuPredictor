import os
import re
from typing import Optional, Dict, List, Tuple
from pypdf import PdfReader
import pdfplumber
import fitz # PyMuPDF

class ExtractionResult:
    def __init__(self, engine_name: str, text: str, score: int):
        self.engine_name = engine_name
        self.text = text
        self.score = score # Cantidad de palabras clave encontradas

class PDFParserEngines:
    """Gestiona múltiples motores de extracción y evalúa su calidad."""
    
    KEYWORDS = [
        "Periodo:", "Saldo total del periodo", "Pago para no generar intereses",
        "Límite de crédito", "TRANSACCIONES", "RESUMEN", "SALDO A MESES",
        "Pago mínimo", "IVA:", "Intereses:"
    ]

    def _calculate_score(self, text: str) -> int:
        if not text: return 0
        return sum(1 for kw in self.KEYWORDS if kw.lower() in text.lower())

    def extract_all(self, file_path: str) -> Dict[str, ExtractionResult]:
        """Extrae texto con los 3 motores y devuelve sus resultados y puntajes."""
        results = {}
        
        # 1. PyPDF
        try:
            reader = PdfReader(file_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            results['pypdf'] = ExtractionResult('pypdf', text, self._calculate_score(text))
        except Exception as e:
            results['pypdf'] = ExtractionResult('pypdf', "", 0)

        # 2. PDFPlumber
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            results['pdfplumber'] = ExtractionResult('pdfplumber', text, self._calculate_score(text))
        except Exception as e:
            results['pdfplumber'] = ExtractionResult('pdfplumber', "", 0)

        # 3. PyMuPDF (fitz)
        try:
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
            results['pymupdf'] = ExtractionResult('pymupdf', text, self._calculate_score(text))
        except Exception as e:
            results['pymupdf'] = ExtractionResult('pymupdf', "", 0)

        return results

    def get_best_text(self, file_path: str) -> Tuple[str, str]:
        """Retorna (mejor_texto, nombre_motor)."""
        results = self.extract_all(file_path)
        best = max(results.values(), key=lambda x: x.score)
        
        if best.score < 3:
            raise Exception(f"Calidad de extracción insuficiente para {file_path}")
            
        return self._normalize(best.text), best.engine_name

    def _normalize(self, text: str) -> str:
        """Normalización base de texto."""
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()
