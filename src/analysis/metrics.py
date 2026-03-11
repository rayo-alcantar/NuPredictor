from sqlmodel import Session, select, func
from src.core.database import Statement, Transaction, DeferredInstallment, MerchantAlias, engine
from typing import Dict, List, Any
import pandas as pd

class FinancialAnalyzer:
    def __init__(self, db_engine=engine):
        self.engine = db_engine

    def _get_aliases(self) -> Dict[str, str]:
        with Session(self.engine) as session:
            aliases = session.exec(select(MerchantAlias)).all()
            return {a.raw_name.upper(): (a.clean_name, a.category) for a in aliases}

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
            "Suscripciones": ["NETFLIX", "SPOTIFY", "DISNEY+", "APPLE.COM", "PRIME VIDEO", "GOOGLE STORAGE"],
            "Compras": ["AMAZON", "MERCADO LIBRE", "WALMART", "COSTCO", "CHEDRAUI", "SORIANA", "ZARA"],
            "Servicios": ["CFE", "TELMEX", "IZZI", "TOTALPLAY", "NATURGY"]
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
                    clean_info = aliases_map.get(t.merchant.upper())
                    clean_name = clean_info[0] if clean_info else t.merchant
                    
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
                clean_info = aliases_map.get(m_upper)
                
                if clean_info:
                    c_name, c_cat = clean_info
                else:
                    c_name = trans.merchant
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
                name = aliases_map.get(raw, (raw, ""))[0]
                if name not in clean_data:
                    clean_data[name] = {"total": 0.0, "count": 0}
                clean_data[name]["total"] += total
                clean_data[name]["count"] += count
            
            sorted_data = sorted(clean_data.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
            return pd.DataFrame([{"merchant": k, "total": v['total'], "frequency": v['count']} for k, v in sorted_data])

    def detect_subscriptions(self) -> List[Dict[str, Any]]:
        """Detecta suscripciones recurrentes normalizadas."""
        aliases_map = self._get_aliases()
        with Session(self.engine) as session:
            n_statements = session.exec(select(func.count(Statement.id))).one()
            if n_statements < 2: return []
            
            trans = session.exec(select(Transaction).where(Transaction.type == "ordinary")).all()
            occurrences = {}
            for t in trans:
                name = aliases_map.get(t.merchant, (t.merchant, ""))[0]
                if name not in occurrences:
                    occurrences[name] = {"statements": set(), "amounts": []}
                occurrences[name]["statements"].add(t.statement_id)
                occurrences[name]["amounts"].append(t.amount)
            
            results = []
            for name, info in occurrences.items():
                count = len(info["statements"])
                if count >= (n_statements * 0.75):
                    results.append({
                        "merchant": name,
                        "occurrence_count": count,
                        "avg_amount": round(sum(info["amounts"]) / len(info["amounts"]), 2)
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
                    "merchant": aliases_map.get(item.merchant.upper(), (item.merchant, ""))[0],
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
                if raw.upper() not in aliases_map:
                    unaliased.append((raw, count))
            
            # Ordenar por frecuencia
            unaliased.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in unaliased[:limit]]
