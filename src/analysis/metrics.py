from sqlmodel import Session, select, func
from src.core.database import Statement, Transaction, DeferredInstallment, MerchantAlias, engine
from typing import Dict, List, Any
import pandas as pd
import math

SOURCE_PREFIXES = (
    "ELECTRÓNICOS ", "ELECTRONICOS ", "SERVICIO ", "EDUCACIÓN ",
    "EDUCACION ", "RESTAURANTE ", "TRANSPORTE ", "OTROS ",
)

def _strip_source_prefix(name: str) -> str:
    """Quita etiquetas de categoría que algunos formatos de Nu anteponen."""
    clean = " ".join(name.strip().split())
    upper = clean.upper()
    for prefix in SOURCE_PREFIXES:
        if upper.startswith(prefix):
            return clean[len(prefix):].strip()
    return clean

def _canonical_merchant(name: str) -> str:
    """Une variantes obvias del mismo proveedor entre formatos de Nu."""
    clean = _strip_source_prefix(name)
    upper = clean.upper()
    families = (
        ("CHATGPT", "ChatGPT"),
        ("OPENAI", "ChatGPT"),
        ("YOUTUBEPREMIUM", "YouTube Premium"),
        ("GOOGLE YOUTUBE", "YouTube Premium"),
        ("SPOTIFY", "Spotify"),
        ("PILLOFON", "Pillofon"),
        ("MELIMAS", "Melimas"),
    )
    for token, canonical in families:
        if token in upper:
            return canonical
    return clean

class FinancialAnalyzer:
    def __init__(self, db_engine=engine):
        self.engine = db_engine

    def _get_aliases(self) -> Dict[str, str]:
        with Session(self.engine) as session:
            aliases = session.exec(select(MerchantAlias)).all()
            result = {}
            for a in aliases:
                value = (a.clean_name, a.category)
                raw = a.raw_name.strip().upper()
                result[raw] = value
                result.setdefault(_strip_source_prefix(a.raw_name).upper(), value)
            return result

    def upsert_alias(self, raw_name: str, clean_name: str, category: str):
        """Añade o actualiza un alias de comercio."""
        with Session(self.engine) as session:
            statement = select(MerchantAlias).where(MerchantAlias.raw_name == raw_name.upper())
            alias = session.exec(statement).first()
            if alias:
                alias.clean_name = clean_name
                alias.category = category
            else:
                alias = MerchantAlias(raw_name=raw_name.upper(), clean_name=clean_name, category=category)
            session.add(alias)
            session.commit()

    def _auto_categorize(self, merchant_name: str) -> str:
        """Reglas básicas de auto-categorización por palabras clave."""
        m = merchant_name.upper()
        rules = {
            "Comida": ["UBER EATS", "RAPPI", "RESTAURANT", "STARBUCKS", "TACOS", "BURGER", "CAFE"],
            "Transporte": ["UBER *", "DIDI", "TAXI", "GASOLINERA", "MOBILITY", "SHELL", "OXXOGAS"],
            "Suscripciones": ["NETFLIX", "SPOTIFY", "CHATGPT", "OPENAI", "YOUTUBE", "DISNEY+", "APPLE.COM", "PRIME VIDEO", "GOOGLE STORAGE", "GOOGLE ONE"],
            "Compras": ["AMAZON", "MERCADO LIBRE", "MERCADOPAGO", "PAYPAL", "WALMART", "COSTCO", "CHEDRAUI", "SORIANA", "ZARA"],
            "Servicios": ["CFE", "TELMEX", "IZZI", "TOTALPLAY", "NATURGY", "PILLOFON", "SERVARICA", "GOOGLE CLOUD", "SERV AGUASCALIENTES"],
            "Educación": ["PLATZI", "UAA"]
        }
        for cat, keywords in rules.items():
            if any(k in m for k in keywords):
                return cat
        return "Otros"

    def get_monthly_breakdown(self) -> pd.DataFrame:
        """Desglose avanzado de tipos de gasto por mes."""
        with Session(self.engine) as session:
            statements = session.exec(select(Statement).order_by(Statement.period_end)).all()
            data = []
            aliases_map = self._get_aliases()
            
            # Detectar suscripciones
            subs = self.detect_subscriptions()
            sub_names = [sub['merchant'] for sub in subs]

            for s in statements:
                trans = session.exec(select(Transaction).where(Transaction.statement_id == s.id)).all()
                fixed_recurring = 0.0
                variable = 0.0
                
                for t in trans:
                    # Intentar alias, luego auto-categorizar
                    clean_info = aliases_map.get(_strip_source_prefix(t.merchant).upper())
                    clean_name = clean_info[0] if clean_info else _canonical_merchant(t.merchant)
                    
                    if t.type == "ordinary":
                        if clean_name in sub_names:
                            fixed_recurring += t.amount
                        else:
                            variable += t.amount

                data.append({
                    "Periodo": s.period_end.strftime("%Y-%m"),
                    "Fijo Recurrente": fixed_recurring,
                    "Variable": variable,
                    "Diferido (MSI)": s.msi_period_total,
                    "Intereses": s.interest_charged,
                    "Ajustes/Dev": s.returns_total,
                    "TOTAL": s.total_balance
                })
            return pd.DataFrame(data)

    def get_all_transactions_clean(self) -> pd.DataFrame:
        """Obtiene todas las transacciones con nombres y categorías normalizadas."""
        with Session(self.engine) as session:
            query = select(Transaction, Statement).join(Statement)
            results = session.exec(query).all()
            
            aliases_map = self._get_aliases()
            data = []
            for trans, stmt in results:
                m_upper = trans.merchant.upper()
                clean_info = aliases_map.get(_strip_source_prefix(trans.merchant).upper())
                
                if clean_info:
                    c_name, c_cat = clean_info
                else:
                    c_name = _canonical_merchant(trans.merchant)
                    c_cat = self._auto_categorize(m_upper)
                
                data.append({
                    "fecha": trans.transaction_date,
                    "periodo": stmt.period_end.strftime("%Y-%m"),
                    "merchant_raw": trans.merchant,
                    "merchant_clean": c_name,
                    "categoria": c_cat,
                    "tipo_transaccion": trans.type,
                    "monto": trans.amount,
                    "archivo_origen": stmt.filename
                })
            return pd.DataFrame(data)

    def get_top_merchants_clean(self, limit: int = 10) -> pd.DataFrame:
        """Top comercios con nombres normalizados."""
        aliases_map = self._get_aliases()
        with Session(self.engine) as session:
            query = select(Transaction.merchant, func.sum(Transaction.amount).label("total"), func.count(Transaction.id).label("count"))\
                    .where(Transaction.type == "ordinary")\
                    .group_by(Transaction.merchant)
            results = session.exec(query).all()
            
            clean_data = {}
            for raw, total, count in results:
                name = aliases_map.get(_strip_source_prefix(raw).upper(), (_canonical_merchant(raw), ""))[0]
                if name not in clean_data:
                    clean_data[name] = {"total": 0.0, "count": 0}
                clean_data[name]["total"] += total
                clean_data[name]["count"] += count
            
            sorted_data = sorted(clean_data.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
            return pd.DataFrame([{"merchant": k, "total": v['total'], "frequency": v['count']} for k, v in sorted_data])

    def detect_subscriptions(self) -> List[Dict[str, Any]]:
        """Detecta cargos recurrentes con frecuencia y monto estables.

        Se usan estados observados, no meses calendario: algunos estados pueden
        faltar. La frecuencia se conserva para no convertir un cargo intermitente
        en un gasto fijo mensual completo.
        """
        aliases_map = self._get_aliases()
        with Session(self.engine) as session:
            n_statements = session.exec(select(func.count(Statement.id))).one()
            if n_statements < 3: return []
            
            trans = session.exec(select(Transaction).where(Transaction.type == "ordinary")).all()
            occurrences = {}
            for t in trans:
                name = aliases_map.get(_strip_source_prefix(t.merchant).upper(), (_canonical_merchant(t.merchant), ""))[0]
                if name not in occurrences:
                    occurrences[name] = {"statements": set(), "amounts": []}
                occurrences[name]["statements"].add(t.statement_id)
                occurrences[name]["amounts"].append(t.amount)
            
            results = []
            for name, info in occurrences.items():
                count = len(info["statements"])
                amounts = info["amounts"]
                avg_amount = sum(amounts) / len(amounts)
                mean_abs = abs(avg_amount) or 1.0
                relative_spread = (max(amounts) - min(amounts)) / mean_abs
                min_occurrences = max(3, math.ceil(n_statements * 0.40))
                if count >= min_occurrences and relative_spread <= 0.35 and avg_amount <= 1000:
                    results.append({
                        "merchant": name,
                        "occurrence_count": count,
                        "observed_statements": n_statements,
                        "avg_amount": round(avg_amount, 2),
                        "monthly_amount": round(avg_amount * count / n_statements, 2),
                    })
            return sorted(results, key=lambda x: x['occurrence_count'], reverse=True)

    def get_active_msi_burden(self) -> pd.DataFrame:
        """Obtiene el desglose de pagos a meses (MSI) pendientes."""
        aliases_map = self._get_aliases()
        with Session(self.engine) as session:
            last_stmt = session.exec(select(Statement).order_by(Statement.period_end.desc())).first()
            if not last_stmt: return pd.DataFrame()
            msi_items = session.exec(select(DeferredInstallment).where(DeferredInstallment.statement_id == last_stmt.id)).all()
            
            projections = []
            for item in msi_items:
                projections.append({
                    "merchant": aliases_map.get(_strip_source_prefix(item.merchant).upper(), (_canonical_merchant(item.merchant), ""))[0],
                    "monthly_payment": item.installment_amount,
                    "months_left": item.total_installments - item.current_installment,
                    "total_remaining": item.installment_amount * (item.total_installments - item.current_installment)
                })
            return pd.DataFrame(projections)

    def get_unaliased_merchants(self, limit: int = 5) -> List[str]:
        """Obtiene los comercios más frecuentes que no tienen alias aún."""
        aliases_map = self._get_aliases()
        with Session(self.engine) as session:
            query = select(Transaction.merchant, func.count(Transaction.id).label("count"))\
                    .where(Transaction.type == "ordinary")\
                    .group_by(Transaction.merchant)
            results = session.exec(query).all()
            
            unaliased = []
            for raw, count in results:
                if _strip_source_prefix(raw).upper() not in aliases_map:
                    unaliased.append((raw, count))
            
            # Ordenar por frecuencia
            unaliased.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in unaliased[:limit]]
