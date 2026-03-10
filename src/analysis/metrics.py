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
            return {a.raw_name: a.clean_name for a in aliases}

    def get_monthly_breakdown(self) -> pd.DataFrame:
        """Desglose avanzado de tipos de gasto por mes."""
        with Session(self.engine) as session:
            statements = session.exec(select(Statement).order_by(Statement.period_end)).all()
            data = []
            for s in statements:
                # 1. Gasto Diferido (MSI/Planes fijos ya reportados en este periodo)
                msi_period = s.msi_period_total
                
                # 2. Intereses
                interests = s.interest_charged
                
                # 3. Ajustes y Devoluciones
                adjustments = s.returns_total
                
                # 4. Gasto Fijo vs Variable de las transacciones ordinarias
                # Detectar suscripciones recurrentes (esto es una lógica dinámica)
                subs = self.detect_subscriptions()
                sub_names = [sub['merchant'] for sub in subs]
                
                # Consultar transacciones de este statement
                trans = session.exec(select(Transaction).where(Transaction.statement_id == s.id)).all()
                aliases = self._get_aliases()
                
                fixed_recurring = 0.0
                variable = 0.0
                
                for t in trans:
                    # Normalizar nombre para ver si es suscripción
                    clean_name = aliases.get(t.merchant, t.merchant)
                    if t.type == "ordinary":
                        if clean_name in sub_names:
                            fixed_recurring += t.amount
                        else:
                            variable += t.amount

                data.append({
                    "Periodo": s.period_end.strftime("%Y-%m"),
                    "Fijo Recurrente": fixed_recurring,
                    "Variable": variable,
                    "Diferido (MSI)": msi_period,
                    "Intereses": interests,
                    "Ajustes/Dev": adjustments,
                    "TOTAL": s.total_balance
                })
            return pd.DataFrame(data)

    def get_top_merchants_clean(self, limit: int = 10) -> pd.DataFrame:
        """Top comercios con nombres normalizados."""
        aliases = self._get_aliases()
        with Session(self.engine) as session:
            query = select(Transaction.merchant, func.sum(Transaction.amount).label("total"), func.count(Transaction.id).label("count"))\
                    .where(Transaction.type == "ordinary")\
                    .group_by(Transaction.merchant)
            results = session.exec(query).all()
            
            # Agrupar en memoria usando aliases
            clean_data = {}
            for raw, total, count in results:
                name = aliases.get(raw, raw)
                if name not in clean_data:
                    clean_data[name] = {"total": 0.0, "count": 0}
                clean_data[name]["total"] += total
                clean_data[name]["count"] += count
            
            sorted_data = sorted(clean_data.items(), key=lambda x: x[1]['total'], reverse=True)[:limit]
            return pd.DataFrame([{"merchant": k, "total": v['total'], "frequency": v['count']} for k, v in sorted_data])

    def detect_subscriptions(self) -> List[Dict[str, Any]]:
        """Detecta suscripciones recurrentes normalizadas."""
        aliases = self._get_aliases()
        with Session(self.engine) as session:
            n_statements = session.exec(select(func.count(Statement.id))).one()
            if n_statements < 2: return []
            
            # Consultar transacciones ordinarias
            trans = session.exec(select(Transaction).where(Transaction.type == "ordinary")).all()
            
            # Agrupar por nombre normalizado y contar estados distintos
            occurrences = {} # {clean_name: {statement_ids: set, amounts: list}}
            for t in trans:
                name = aliases.get(t.merchant, t.merchant)
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
        """Carga MSI limpia."""
        aliases = self._get_aliases()
        with Session(self.engine) as session:
            last_stmt = session.exec(select(Statement).order_by(Statement.period_end.desc())).first()
            if not last_stmt: return pd.DataFrame()
            msi_items = session.exec(select(DeferredInstallment).where(DeferredInstallment.statement_id == last_stmt.id)).all()
            
            projections = []
            for item in msi_items:
                projections.append({
                    "merchant": aliases.get(item.merchant, item.merchant),
                    "monthly_payment": item.installment_amount,
                    "months_left": item.total_installments - item.current_installment,
                    "total_remaining": item.installment_amount * (item.total_installments - item.current_installment)
                })
            return pd.DataFrame(projections)
