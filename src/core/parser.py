import os
from typing import Optional, List
from pypdf import PdfReader
import pdfplumber
import fitz # PyMuPDF
import re

class PDFExtractionError(Exception):
    """Excepción para errores de extracción de PDF."""
    pass

class PDFParserEngine:
    """Motor de extracción con fallback y validación de calidad."""
    
    CRITICAL_KEYWORDS = [
        "Periodo", "Saldo total del periodo", "Pago para no generar intereses",
        "Límite de crédito", "TRANSACCIONES", "RESUMEN"
    ]

    @staticmethod
    def _validate_text(text: str) -> bool:
        """Valida que el texto extraído contenga elementos mínimos del estado Nu."""
        if not text or len(text) < 100:
            return False
        
        matches = [kw for kw in PDFParserEngine.CRITICAL_KEYWORDS if kw in text]
        # Si contiene al menos 2 palabras clave críticas, consideramos que la extracción fue útil.
        return len(matches) >= 2

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Limpia el texto para facilitar el parseo posterior."""
        # Normalizar espacios múltiples y saltos de línea redundantes
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\n{2,}', '\n', text)
        # Asegurar que los montos con coma se normalicen si es necesario (ej. $2,232.05)
        # Pero mantendremos el texto crudo para que el extractor de regex decida.
        return text.strip()

    def extract_with_pypdf(self, file_path: str) -> Optional[str]:
        try:
            reader = PdfReader(file_path)
            text = "\n".join(page.extract_text() for page in reader.pages)
            return text if self._validate_text(text) else None
        except Exception:
            return None

    def extract_with_pdfplumber(self, file_path: str) -> Optional[str]:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text if self._validate_text(text) else None
        except Exception:
            return None

    def extract_with_pymupdf(self, file_path: str) -> Optional[str]:
        try:
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
            return text if self._validate_text(text) else None
        except Exception:
            return None

    def get_text(self, file_path: str) -> str:
        """Intenta extraer texto usando fallbacks secuenciales."""
        
        # 1. Intentar PyPDF
        text = self.extract_with_pypdf(file_path)
        if text:
            return self._normalize_text(text)
        
        # 2. Intentar PDFPlumber
        text = self.extract_with_pdfplumber(file_path)
        if text:
            return self._normalize_text(text)
        
        # 3. Intentar PyMuPDF
        text = self.extract_with_pymupdf(file_path)
        if text:
            return self._normalize_text(text)
        
        raise PDFExtractionError(f"No se pudo extraer texto válido de {file_path} con ningún motor.")

if __name__ == "__main__":
    # Test simple de extracción y validación
    import sys
    engine = PDFParserEngine()
    test_file = "estados-de-cuenta/octubre 2025.pdf"
    if os.path.exists(test_file):
        try:
            text = engine.get_text(test_file)
            print(f"Éxito en la extracción. Longitud del texto: {len(text)}")
            print("Fragmento inicial:")
            print(text[:200])
        except PDFExtractionError as e:
            print(f"Error: {e}")
    else:
        print(f"Archivo de prueba no encontrado: {test_file}")
