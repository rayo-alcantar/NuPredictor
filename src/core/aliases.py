from sqlmodel import Session, select
from src.core.database import MerchantAlias, engine

# Lista de ejemplos genéricos para que el usuario pueda personalizar su limpieza
ALIASES = [
    {"raw": "Electrónicos Openai *Chatgpt Subscr", "clean": "ChatGPT", "category": "Suscripción Digital"},
    {"raw": "Restaurante Uber *Eats Help.Uber.C", "clean": "Uber Eats", "category": "Comida a Domicilio"},
    {"raw": "Transporte Uber *Trip Help.Uber.C", "clean": "Uber", "category": "Transporte"},
    {"raw": "Servicio Amazon Mexico", "clean": "Amazon", "category": "Compras Online"}
]

def init_aliases():
    with Session(engine) as session:
        for a in ALIASES:
            # Evitar duplicados
            existing = session.exec(select(MerchantAlias).where(MerchantAlias.raw_name == a['raw'])).first()
            if not existing:
                session.add(MerchantAlias(raw_name=a['raw'], clean_name=a['clean'], category=a['category']))
        session.commit()

if __name__ == "__main__":
    init_aliases()
    print("Capa de Aliases inicializada.")
