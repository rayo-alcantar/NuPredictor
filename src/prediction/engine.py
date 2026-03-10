from src.analysis.metrics import FinancialAnalyzer
import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Any

class PredictionEngine:
    def __init__(self, analyzer: FinancialAnalyzer):
        self.analyzer = analyzer

    def generate_forecast(self, months_ahead: int = 3) -> Dict[str, Any]:
        """Genera una proyección pragmática para los próximos meses."""
        # 1. Obtener datos históricos saneados
        history = self.analyzer.get_monthly_breakdown()
        if history.empty: return {"error": "Historial insuficiente"}

        # 2. Calcular COMPONENTE FIJO (Suscripciones)
        subs = self.analyzer.detect_subscriptions()
        monthly_fixed_base = sum(s['avg_amount'] for s in subs)

        # 3. Calcular COMPONENTE MSI (Diferidos Activos)
        msi_burden = self.analyzer.get_active_msi_burden()
        
        # 4. Calcular COMPONENTE VARIABLE (Estadístico)
        # Usamos los últimos 4 meses para mayor relevancia reciente
        var_history = history['Variable'].tail(4)
        var_mean = var_history.mean()
        var_std = var_history.std() if len(var_history) > 1 else var_mean * 0.2

        # 5. Generar Proyección Mes a Mes
        forecasts = []
        last_date = pd.to_datetime(history['Periodo'].iloc[-1] + "-01")
        
        for i in range(1, months_ahead + 1):
            target_date = last_date + pd.DateOffset(months=i)
            
            # MSI: Solo sumar los que aún tengan meses restantes
            # (Simplificación: restamos i a months_left)
            active_msi = msi_burden[msi_burden['months_left'] >= i]['monthly_payment'].sum() if not msi_burden.empty else 0.0
            
            forecasts.append({
                "Mes": target_date.strftime("%Y-%m"),
                "Fijo (Conocido)": monthly_fixed_base,
                "Diferido (MSI)": active_msi,
                "Variable (Base)": var_mean,
                "Escenario Optimista": monthly_fixed_base + active_msi + (var_mean - var_std),
                "Escenario Base": monthly_fixed_base + active_msi + var_mean,
                "Escenario Conservador": monthly_fixed_base + active_msi + (var_mean + var_std),
            })

        return {
            "model_metadata": {
                "historical_avg_variable": var_mean,
                "fixed_subscriptions": monthly_fixed_base,
                "confidence_std": var_std
            },
            "projections": forecasts
        }
