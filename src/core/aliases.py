from sqlmodel import Session, select
from src.core.database import MerchantAlias, engine

ALIASES = [
    {"raw": "Electrónicos Openai *Chatgpt Subscr", "clean": "ChatGPT", "category": "Suscripción Digital"},
    {"raw": "Educación Google Youtubepremium", "clean": "YouTube Premium", "category": "Suscripción Digital"},
    {"raw": "Servicio Google Youtubepremium", "clean": "YouTube Premium", "category": "Suscripción Digital"},
    {"raw": "Servicio Ebanx 1*Musicspotify1", "clean": "Spotify", "category": "Suscripción Digital"},
    {"raw": "Servicio Mercadopago *Pillofon", "clean": "Pillofon", "category": "Telecomunicaciones"},
    {"raw": "Electrónicos Servarica* Servarica.C", "clean": "Servarica", "category": "Servicios Web"},
    {"raw": "Servicio Google One", "clean": "Google One", "category": "Suscripción Digital"},
    {"raw": "Restaurante Uber *Eats Help.Uber.C", "clean": "Uber Eats", "category": "Comida a Domicilio"},
    {"raw": "Transporte Uber *Trip Help.Uber.C", "clean": "Uber", "category": "Transporte"},
    {"raw": "Servicio Amazon Mexico", "clean": "Amazon", "category": "Compras Online"},
    {"raw": "Otros Paypal *Platzi Mx", "clean": "Platzi", "category": "Educación"},
    {"raw": "Educación Uaa Mu", "clean": "Uaa Mu", "category": "Educación"},
    {"raw": "Otros Merpago*Melimas", "clean": "Meli+", "category": "Suscripción Digital"},
    {"raw": "Otros Paypal*Freygeth", "clean": "Freygeth", "category": "Otros"}
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
