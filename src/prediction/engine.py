from src.analysis.metrics import FinancialAnalyzer
from src.core.database import Prediction, Statement, Session
from sqlmodel import select
import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Any

class PredictionEngine:
    def __init__(self, analyzer: FinancialAnalyzer):
        self.analyzer = analyzer

    def validate_past_predictions(self) -> int:
        """
        Revisa predicciones pasadas donde el 'actual_amount' es None
        y lo actualiza si el estado de cuenta correspondiente ya existe.
        """
        validated_count = 0
        with Session(self.analyzer.engine) as session:
            # Traer predicciones sin validar
            unvalidated = session.exec(select(Prediction).where(Prediction.actual_amount == None)).all()
            if not unvalidated:
                return 0
            
            # Obtener los totales de los statements conocidos
            statements = session.exec(select(Statement)).all()
            statement_totals = {s.period_end.strftime("%Y-%m"): s.total_balance for s in statements}
            
            for p in unvalidated:
                if p.target_period in statement_totals:
                    actual = statement_totals[p.target_period]
                    p.actual_amount = actual
                    # Error margin: (predicho - real) / real
                    # Si error_margin > 0: sobreestimamos. Si < 0: subestimamos.
                    if actual > 0:
                        p.error_margin = (p.base_amount - actual) / actual
                    else:
                        p.error_margin = 0.0
                    validated_count += 1
            
            if validated_count > 0:
                session.commit()
                
        return validated_count

    def get_bias_correction_factor(self) -> float:
        """
        Calcula el factor de corrección basado en el error promedio histórico de las últimas 3 validaciones.
        Retorna un multiplicador (ej. 1.05 si el modelo tiende a subestimar un 5%).
        """
        with Session(self.analyzer.engine) as session:
            # Traer las últimas predicciones validadas ordenadas por periodo
            statement = select(Prediction).where(Prediction.actual_amount != None).order_by(Prediction.target_period.desc()).limit(3)
            valid_preds = session.exec(statement).all()
            
            if not valid_preds:
                return 1.0 # No hay datos suficientes para corregir sesgo
            
            ratios = []
            for p in valid_preds:
                if p.base_amount > 0 and p.actual_amount is not None:
                    # ratio = real / predicho
                    # Ej: si gastamos 110 y predijimos 100 -> ratio = 1.1
                    ratios.append(p.actual_amount / p.base_amount)
                    
            if ratios:
                return float(np.mean(ratios))
            return 1.0

    def generate_forecast(self, months_ahead: int = 3, adjustments: Dict[int, float] = None, save: bool = True) -> Dict[str, Any]:
        """
        Genera una proyección avanzada para los próximos meses con auto-ajuste de sesgo.
        
        Args:
            months_ahead: Cuántos meses al futuro proyectar.
            adjustments: Diccionario {mes_offset: monto_extra} para gastos previstos.
            save: Si True, guarda la proyección en la base de datos para futura validación.
        """
        adjustments = adjustments or {}
        
        # 1. Obtener datos históricos
        history = self.analyzer.get_monthly_breakdown()
        if history.empty: return {"error": "Historial insuficiente para generar predicción."}

        # 2. COMPONENTE FIJO (Suscripciones)
        subs = self.analyzer.detect_subscriptions()
        monthly_fixed_base = sum(s['avg_amount'] for s in subs)

        # 3. COMPONENTE MSI (Diferidos Activos)
        msi_burden = self.analyzer.get_active_msi_burden()
        
        # 4. COMPONENTE VARIABLE (WMA - Weighted Moving Average)
        # Damos más peso a los meses más recientes (4 meses: 40%, 30%, 20%, 10%)
        var_history = history['Variable'].tail(4).tolist()
        n = len(var_history)
        if n > 1:
            weights = np.arange(1, n + 1)
            var_mean = np.average(var_history, weights=weights)
            var_std = np.std(var_history)
        else:
            var_mean = var_history[0] if n == 1 else 0.0
            var_std = var_mean * 0.2

        # 5. Calcular Corrección de Sesgo (Feedback Loop)
        bias_factor = self.get_bias_correction_factor()

        # 6. Generar Proyección Mes a Mes
        forecasts = []
        # Obtenemos la última fecha del historial
        last_period_str = history['Periodo'].iloc[-1]
        last_date = pd.to_datetime(last_period_str + "-01")
        
        predictions_to_save = []
        
        for i in range(1, months_ahead + 1):
            target_date = last_date + pd.DateOffset(months=i)
            target_period_str = target_date.strftime("%Y-%m")
            
            # MSI: Sumar pagos mensuales que aún tengan meses restantes
            active_msi = msi_burden[msi_burden['months_left'] >= i]['monthly_payment'].sum() if not msi_burden.empty else 0.0
            
            # Ajuste manual para este mes específico
            manual_adj = adjustments.get(i, 0.0)
            
            raw_base_calc = monthly_fixed_base + active_msi + var_mean + manual_adj
            
            # Aplicar corrección de sesgo
            base_calc = raw_base_calc * bias_factor
            
            # Recalcular std para optimista/conservador
            adjusted_std = var_std * bias_factor
            
            opt_amount = base_calc - adjusted_std
            cons_amount = base_calc + adjusted_std
            
            forecasts.append({
                "Mes": target_period_str,
                "Fijo (Conocido)": monthly_fixed_base,
                "Diferido (MSI)": active_msi,
                "Variable (Est.)": var_mean * bias_factor,
                "Ajuste Manual": manual_adj,
                "Escenario Optimista": opt_amount,
                "Escenario Base": base_calc,
                "Escenario Conservador": cons_amount,
                "Bias Aplicado": bias_factor
            })
            
            if save:
                predictions_to_save.append(Prediction(
                    target_period=target_period_str,
                    base_amount=base_calc,
                    optimistic_amount=opt_amount,
                    conservative_amount=cons_amount
                ))

        # 7. Guardar predicciones en DB
        if save and predictions_to_save:
            with Session(self.analyzer.engine) as session:
                for p in predictions_to_save:
                    session.add(p)
                session.commit()

        return {
            "model_metadata": {
                "algorithm": "Weighted Moving Average (4m) + Bias Correction",
                "historical_avg_variable": var_mean,
                "fixed_subscriptions": monthly_fixed_base,
                "confidence_std": adjusted_std,
                "months_projected": months_ahead,
                "bias_correction_factor": bias_factor
            },
            "projections": forecasts
        }
