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
        resumen_match = re.search(r"(¡Hola.*?)(?=TRANSACCIONES DE|DESGLOSE DE MOVIMIENTOS)", self.text, re.S)
        segments['resumen'] = resumen_match.group(1) if resumen_match else ""
        trans_match = re.search(r"TRANSACCIONES DE.*?(?=SALDO A MESES|INFORMACIÓN DE COSTOS|$)", self.text, re.S)
        if not trans_match:
            trans_match = re.search(r"CARGOS, ABONOS Y COMPRAS REGULARES.*?(?=ATENCIÓN DE QUEJAS|$)", self.text, re.S)
        segments['transacciones'] = trans_match.group(0) if trans_match else ""
        msi_match = re.search(r"SALDO A MESES.*?(?=Nu México Financiera|$)", self.text, re.S)
        if not msi_match:
            msi_match = re.search(r"COMPRAS Y CARGOS DIFERIDOS A MESES.*?(?=CARGOS, ABONOS Y COMPRAS REGULARES|$)", self.text, re.S)
        segments['msi'] = msi_match.group(0) if msi_match else ""
        return segments

    def parse_summary(self) -> Dict[str, Any]:
        summary = {}
        text = self.segments.get('resumen', "")
        period_match = re.search(r"Periodo:\s*(\d{1,2} [A-Z]{3} \d{4}) - (\d{1,2} [A-Z]{3} \d{4})", text)
        if not period_match:
            period_match = re.search(r"Periodo:\s*(\d{1,2} [A-Z]{3} \d{4})\s+al\s+(\d{1,2} [A-Z]{3})\s+(\d{4})", text)
        if period_match:
            summary['start_date'] = period_match.group(1)
            summary['end_date'] = period_match.group(2) if len(period_match.groups()) == 2 else f"{period_match.group(2)} {period_match.group(3)}"
        summary['total_balance'] = self._extract_amount(r"Saldo total del periodo: \$([\d,.]+)")
        if summary['total_balance'] is None:
            summary['total_balance'] = self._extract_amount(r"PAGO PARA NO GENERAR INTERESES\d*\s*=\s*\$([\d,.]+)")
        summary['previous_balance'] = self._extract_amount(r"Saldo inicial del periodo.*?\$([\d,.]+)")
        if summary['previous_balance'] is None:
            summary['previous_balance'] = self._extract_amount(r"Adeudo del periodo anterior\s*=\s*\$([\d,.]+)")
        summary['payments'] = self._extract_amount(r"Pagos a tu tarjeta en el periodo - \$([\d,.]+)")
        if summary['payments'] is None:
            summary['payments'] = self._extract_amount(r"Pagos y abonos\s*-\s*\$([\d,.]+)")
        summary['purchases'] = self._extract_amount(r"Compras \$([\d,.]+)")
        if summary['purchases'] is None:
            summary['purchases'] = self._extract_amount(r"Cargos regulares \(no a meses\)\s*\+\s*\$([\d,.]+)")
        summary['returns'] = self._extract_amount(r"Abonos y devoluciones -? \$([\d,.]+)")
        if summary['returns'] is None:
            summary['returns'] = self._calculate_returns_from_transactions()
        summary['int_msi'] = self._extract_amount(r"Intereses de saldo a meses \$([\d,.]+)") or 0.0
        summary['int_rev'] = self._extract_amount(r"Intereses de saldo revolvente \$([\d,.]+)") or 0.0
        summary['int_disp'] = self._extract_amount(r"Intereses de disposiciones de saldo \$([\d,.]+)") or 0.0
        if not any([summary['int_msi'], summary['int_rev'], summary['int_disp']]):
            summary['int_msi'] = self._extract_amount(r"Monto de intereses\d*\s*\+\s*\$([\d,.]+)") or 0.0
        summary['interest_total'] = summary['int_msi'] + summary['int_rev'] + summary['int_disp']
        summary['iva'] = self._extract_amount(r"IVA \$([\d,.]+)")
        if summary['iva'] is None:
            summary['iva'] = self._extract_amount(r"IVA de intereses y comisiones\d*\s*\+\s*\$([\d,.]+)")
        summary['msi_period_total'] = self._extract_amount(r"Saldo a meses con o sin intereses de este periodo \$([\d,.]+)")
        if summary['msi_period_total'] is None:
            summary['msi_period_total'] = self._extract_amount(r"Cargos y compras a meses \(capital\)\d*\s*\+\s*\$([\d,.]+)")
        summary['credit_limit'] = self._extract_amount(r"Límite de crédito\s*\$([\d,.]+)")
        summary['available_credit'] = self._extract_amount(r"Límite disponible\s*\$([\d,.]+)")
        if summary['available_credit'] is None:
            summary['available_credit'] = self._extract_amount(r"Crédito disponible\s*\$([\d,.]+)")
        return summary

    def parse_transactions(self) -> List[Dict[str, Any]]:
        text = self.segments.get('transacciones', "")
        if "CARGOS, ABONOS Y COMPRAS REGULARES" in text:
            return self._parse_new_format_transactions(text)

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

    def _parse_new_format_transactions(self, text: str) -> List[Dict[str, Any]]:
        transactions = []
        pattern = r"(\d{2} [A-Z]{3}) \d{4}\s+\d{2} [A-Z]{3} \d{4}\s+(.*?)\s+\|\s+RFC:.*?([+-])\$([\d,.]+)"
        for m in re.finditer(pattern, text, re.S):
            date_str = m.group(1).strip()
            merchant = " ".join(m.group(2).replace("\n", " ").split())
            amount = float(m.group(4).replace(",", ""))
            if m.group(3) == "-":
                amount *= -1

            m_upper = merchant.upper()
            if "GRÁCIAS POR TU PAGO" in m_upper or "GRACIAS POR TU PAGO" in m_upper:
                t_type = "payment"
            elif m_upper.startswith("ABONO DE"):
                t_type = "return"
            elif "INTERESES" in m_upper or "IVA SOBRE INTERESES" in m_upper:
                t_type = "interest"
            elif "COMPRA DIFERIDA" in m_upper:
                t_type = "installment"
            elif "DISPOSICIÓN DE" in m_upper:
                t_type = "disposal"
            else:
                t_type = "ordinary"
            transactions.append({"date": date_str, "merchant": merchant, "amount": amount, "type": t_type})
        return transactions

    def parse_msi(self) -> List[Dict[str, Any]]:
        text = self.segments.get('msi', "")
        pattern = r"(\d{2} [A-Z]{3})\s+(.*?)\s+\$([\d,.]+)\s+(\d+%)\s+(\d+/\d+)\s+\$([\d,.]+)\s+\$([\d,.]+)"
        matches = re.finditer(pattern, text)
        msi_items = []
        for m in matches:
            msi_items.append({"date": m.group(1), "merchant": m.group(2), "installment": m.group(5), "amount": float(m.group(6).replace(",", ""))})
        if msi_items:
            return msi_items

        pattern = r"(\d{2} [A-Z]{3}) \d{4}\s+(.*?)\s+\$[\d,.]+\s+\$([\d,.]+)\s+\$([\d,.]+)\s+(\d+/\d+)\s+\d+\.\d+%"
        for m in re.finditer(pattern, text, re.S):
            merchant = " ".join(m.group(2).replace("\n", " ").split())
            msi_items.append({
                "date": m.group(1),
                "merchant": merchant,
                "installment": m.group(5),
                "amount": float(m.group(4).replace(",", "")),
                "remaining_balance": float(m.group(3).replace(",", ""))
            })
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

        # Newer Nu statements group refunds in "Pagos y abonos" while also
        # reporting regular charges net of those refunds.
        balance_plus_int_returns = balance_plus_int + returns
        diff_plus_int_returns = abs(balance_plus_int_returns - target)
        balance_plus_int_double_returns = balance_plus_int + (returns * 2)
        diff_plus_int_double_returns = abs(balance_plus_int_double_returns - target)
        
        mode = "unknown"
        final_diff = diff_base
        if diff_base < 1.0:
            mode = "base"
            final_diff = diff_base
        elif diff_plus_int < 1.0:
            mode = "base_plus_interest"
            final_diff = diff_plus_int
        elif diff_plus_int_returns < 1.0:
            mode = "base_plus_interest_returns_adjusted"
            final_diff = diff_plus_int_returns
        elif diff_plus_int_double_returns < 1.0:
            mode = "base_plus_interest_double_returns_adjusted"
            final_diff = diff_plus_int_double_returns

        return {
            "is_valid": mode != "unknown",
            "mode": mode,
            "calculated": round(balance_plus_int_double_returns if mode == "base_plus_interest_double_returns_adjusted" else balance_plus_int_returns if mode == "base_plus_interest_returns_adjusted" else balance_plus_int if mode == "base_plus_interest" else balance_base, 2),
            "target": target,
            "difference": round(final_diff, 2),
            "options": {
                "base_diff": round(diff_base, 2),
                "plus_int_diff": round(diff_plus_int, 2),
                "plus_int_returns_adjusted_diff": round(diff_plus_int_returns, 2),
                "plus_int_double_returns_adjusted_diff": round(diff_plus_int_double_returns, 2)
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

    def _calculate_returns_from_transactions(self) -> float:
        text = self.segments.get('transacciones', "")
        total = 0.0
        pattern = r"\d{2} [A-Z]{3} \d{4}\s+\d{2} [A-Z]{3} \d{4}\s+Abono de .*?\|\s+RFC:.*?-\$([\d,.]+)"
        for match in re.finditer(pattern, text, re.S):
            total += float(match.group(1).replace(",", ""))
        return total
