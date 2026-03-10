import hashlib
import os
from typing import List, Tuple
from sqlmodel import Session, select
from src.core.database import Statement, engine

def calculate_sha256(file_path: str) -> str:
    """Calcula el hash SHA-256 de un archivo para detección de duplicados."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_unprocessed_files(directory: str) -> List[Tuple[str, str]]:
    """
    Escanea el directorio y devuelve una lista de (ruta_archivo, hash) 
    para archivos que no han sido procesados aún.
    """
    unprocessed = []
    if not os.path.exists(directory):
        os.makedirs(directory)
        return []

    with Session(engine) as session:
        # Obtener todos los hashes ya registrados
        processed_hashes = session.exec(select(Statement.file_hash)).all()
        processed_hashes_set = set(processed_hashes)

    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            path = os.path.join(directory, filename)
            file_hash = calculate_sha256(path)
            
            if file_hash not in processed_hashes_set:
                unprocessed.append((path, file_hash))
    
    # Ordenar por nombre (generalmente ayuda a procesar cronológicamente si el nombre tiene el mes/año)
    unprocessed.sort(key=lambda x: x[0])
    return unprocessed

if __name__ == "__main__":
    # Test simple
    files = get_unprocessed_files("estados-de-cuenta")
    print(f"Archivos nuevos detectados: {len(files)}")
    for f, h in files:
        print(f" - {f} [{h[:8]}...]")
