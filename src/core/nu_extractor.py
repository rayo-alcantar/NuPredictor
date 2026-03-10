import re
from datetime import datetime
from typing import Dict, List, Optional, Any

class NuExtractor:
    def __init__(self, text: str):
        self.text = text
        self.segments = self._segment_blocks()
        self.anomalies = []

    def _segment_blocks(self) -> Dict[str, str]:
        segments = {}
        resumen_match = re.search(r"(¡Hola.*?)(?=TRANSACCIONES DE)", self.text, re.S)
        segments['resumen'] = resumen_match.group(1) if resumen_match else ""
        trans_match = re.search(r"TRANSACCIONES DE.*?(?=SALDO A MESES|INFORMACIÓN DE COSTOS|$)", self.text, re.S)
        segments['transacciones'] = trans_match.group(0) if trans_match else ""
        msi_match = re.search(r"SALDO A MESES.*?(?=Nu México Financiera|$)", self.text, re.S)
        segments['msi'] = msi_match.group(0) if msi_match else ""
        return segments

    def parse_summary(self) -> Dict[str, Any]:
        summary = {}
        text = self.segments.get('resumen', "")
        period_match = re.search(r"Periodo:\s*(\d{1,2} [A-Z]{3} \d{4}) - (\d{1,2} [A-Z]{3} \d{4})", text)
        if period_match:
            summary['start_date'] = period_match.group(1); summary['end_date'] = period_match.group(2)
        summary['total_balance'] = self._extract_amount(r"Saldo total del periodo: \$([\d,.]+)")
        summary['previous_balance'] = self._extract_amount(r"Saldo inicial del periodo.*?\$([\d,.]+)")
        summary['payments'] = self._extract_amount(r"Pagos a tu tarjeta en el periodo - \$([\d,.]+)")
        summary['purchases'] = self._extract_amount(r"Compras \$([\d,.]+)")
        summary['returns'] = self._extract_amount(r"Abonos y devoluciones -? \$([\d,.]+)")
        summary['int_msi'] = self._extract_amount(r"Intereses de saldo a meses \$([\d,.]+)") or 0.0
        summary['int_rev'] = self._extract_amount(r"Intereses de saldo revolvente \$([\d,.]+)") or 0.0
        summary['int_disp'] = self._extract_amount(r"Intereses de disposiciones de saldo \$([\d,.]+)") or 0.0
        summary['interest_total'] = summary['int_msi'] + summary['int_rev'] + summary['int_disp']
        summary['iva'] = self._extract_amount(r"IVA \$([\d,.]+)")
        summary['msi_period_total'] = self._extract_amount(r"Saldo a meses con o sin intereses de este periodo \$([\d,.]+)")
        summary['credit_limit'] = self._extract_amount(r"Límite de crédito\s*\$([\d,.]+)")
        summary['available_credit'] = self._extract_amount(r"Límite disponible\s*\$([\d,.]+)")
        return summary

    def parse_transactions(self) -> List[Dict[str, Any]]:
        text = self.segments.get('transacciones', "")
        pattern = r"(\d{2} [A-Z]{3})\n(.*?)\s*\$(-?[\d,.]+)"
        matches = re.finditer(pattern, text, re.S)
        transactions = []
        for m in matches:
            date_str = m.group(1).strip(); merchant = m.group(2).replace("\n", " ").strip(); raw_amount = m.group(3).replace(",", "")
            if "¡Muchas gracias!" in merchant: continue
            t_type = "ordinary"
            if "Intereses de" in merchant: t_type = "interest"
            elif "Ajuste" in merchant or "Abono por" in merchant: t_type = "adjustment"
            elif "Disposición de" in merchant: t_type = "disposal"
            transactions.append({"date": date_str, "merchant": merchant, "amount": float(raw_amount), "type": t_type})
        return transactions

    def parse_msi(self) -> List[Dict[str, Any]]:
        text = self.segments.get('msi', "")
        pattern = r"(\d{2} [A-Z]{3})\s+(.*?)\s+\$([\d,.]+)\s+(\d+%)\s+(\d+/\d+)\s+\$([\d,.]+)\s+\$([\d,.]+)"
        matches = re.finditer(pattern, text)
        msi_items = []
        for m in matches:
            msi_items.append({"date": m.group(1), "merchant": m.group(2), "installment": m.group(5), "amount": float(m.group(6).replace(",", ""))})
        return msi_items

    def validate_accounting(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        prev = summary.get('previous_balance') or 0.0
        purch = summary.get('purchases') or 0.0
        msi_period = summary.get('msi_period_total') or 0.0
        iva = summary.get('iva') or 0.0
        payments = summary.get('payments') or 0.0
        returns = summary.get('returns') or 0.0
        interest_total = summary.get('interest_total') or 0.0
        target = summary.get('total_balance') or 0.0
        
        # Modo BASE: Nu parece agrupar intereses en 'Compras' para algunos casos
        balance_base = prev + purch + msi_period + iva - (payments + returns)
        diff_base = abs(balance_base - target)
        
        # Modo BASE + INTERESES: Nu reporta intereses por separado en otros casos
        balance_plus_int = balance_base + interest_total
        diff_plus_int = abs(balance_plus_int - target)
        
        mode = "unknown"
        final_diff = diff_base
        if diff_base < 1.0:
            mode = "base"
            final_diff = diff_base
        elif diff_plus_int < 1.0:
            mode = "base_plus_interest"
            final_diff = diff_plus_int
            
        return {
            "is_valid": mode != "unknown",
            "mode": mode,
            "calculated": round(balance_plus_int if mode == "base_plus_interest" else balance_base, 2),
            "target": target,
            "difference": round(final_diff, 2),
            "options": {
                "base_diff": round(diff_base, 2),
                "plus_int_diff": round(diff_plus_int, 2)
            },
            "breakdown": {"prev": prev, "purch": purch, "msi": msi_period, "int": interest_total, "iva": iva, "pay": payments, "ret": returns}
        }

    def _extract_amount(self, pattern: str) -> Optional[float]:
        match = re.search(pattern, self.text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError: return None
        return None
