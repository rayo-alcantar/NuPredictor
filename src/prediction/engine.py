from src.analysis.metrics import FinancialAnalyzer
import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Any

class PredictionEngine:
    def __init__(self, analyzer: FinancialAnalyzer):
        self.analyzer = analyzer

    def generate_forecast(self, months_ahead: int = 3, adjustments: Dict[int, float] = None) -> Dict[str, Any]:
        """
        Genera una proyección avanzada para los próximos meses.
        
        Args:
            months_ahead: Cuántos meses al futuro proyectar.
            adjustments: Diccionario {mes_offset: monto_extra} para gastos previstos.
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

        # 5. Generar Proyección Mes a Mes
        forecasts = []
        # Obtenemos la última fecha del historial
        last_period_str = history['Periodo'].iloc[-1]
        last_date = pd.to_datetime(last_period_str + "-01")
        
        for i in range(1, months_ahead + 1):
            target_date = last_date + pd.DateOffset(months=i)
            
            # MSI: Sumar pagos mensuales que aún tengan meses restantes
            active_msi = msi_burden[msi_burden['months_left'] >= i]['monthly_payment'].sum() if not msi_burden.empty else 0.0
            
            # Ajuste manual para este mes específico
            manual_adj = adjustments.get(i, 0.0)
            
            base_calc = monthly_fixed_base + active_msi + var_mean + manual_adj
            
            forecasts.append({
                "Mes": target_date.strftime("%Y-%m"),
                "Fijo (Conocido)": monthly_fixed_base,
                "Diferido (MSI)": active_msi,
                "Variable (Est.)": var_mean,
                "Ajuste Manual": manual_adj,
                "Escenario Optimista": base_calc - var_std,
                "Escenario Base": base_calc,
                "Escenario Conservador": base_calc + var_std,
            })

        return {
            "model_metadata": {
                "algorithm": "Weighted Moving Average (4m)",
                "historical_avg_variable": var_mean,
                "fixed_subscriptions": monthly_fixed_base,
                "confidence_std": var_std,
                "months_projected": months_ahead
            },
            "projections": forecasts
        }
