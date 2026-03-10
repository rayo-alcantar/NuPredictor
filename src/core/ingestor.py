from sqlmodel import Session, select
from datetime import date
from src.core.database import Statement, Transaction, DeferredInstallment, Anomaly, engine, parse_spanish_date
from src.core.discovery import get_unprocessed_files
from src.core.parser_engines import PDFParserEngines
from src.core.nu_extractor import NuExtractor
import os

class Ingestor:
    def __init__(self, db_engine=engine):
        self.engine = db_engine
        self.parser_mgr = PDFParserEngines()

    def process_all(self, directory: str):
        files = get_unprocessed_files(directory)
        results = {"success": 0, "failed": 0}
        for file_path, file_hash in files:
            try:
                self._process_single_file(file_path, file_hash)
                results["success"] += 1
            except Exception as e:
                print(f"Error procesando {file_path}: {e}"); results["failed"] += 1
        return results

    def _process_single_file(self, file_path: str, file_hash: str):
        text, engine_name = self.parser_mgr.get_best_text(file_path)
        extractor = NuExtractor(text)
        summary = extractor.parse_summary(); trans_list = extractor.parse_transactions(); msi_list = extractor.parse_msi()
        validation = extractor.validate_accounting(summary)
        
        with Session(self.engine) as session:
            db_stmt = Statement(
                filename=os.path.basename(file_path), file_hash=file_hash,
                period_start=parse_spanish_date(summary.get('start_date', "")) or date(1900,1,1),
                period_end=parse_spanish_date(summary.get('end_date', "")) or date(1900,1,1),
                total_balance=summary.get('total_balance', 0.0), previous_balance=summary.get('previous_balance', 0.0),
                payments_made=summary.get('payments', 0.0), purchases_made=summary.get('purchases', 0.0),
                msi_period_total=validation.get('msi_period', 0.0), returns_total=summary.get('returns', 0.0),
                interest_charged=summary.get('interest_total', 0.0), iva_charged=summary.get('iva', 0.0),
                credit_limit=summary.get('credit_limit', 0.0), available_credit=summary.get('available_credit', 0.0),
                extraction_engine=engine_name, 
                reconciliation_mode=validation['mode'], # NUEVO
                is_valid_accounting=validation['is_valid'], accounting_diff=validation['difference']
            )
            session.add(db_stmt); session.commit(); session.refresh(db_stmt)

            if not validation['is_valid']:
                session.add(Anomaly(statement_id=db_stmt.id, anomaly_type="accounting_imbalance", 
                                   description=f"Dif: ${validation['difference']} | Opciones: {validation['options']}"))

            for t in trans_list:
                t_date = parse_spanish_date(f"{t['date']} {db_stmt.period_end.year}")
                session.add(Transaction(statement_id=db_stmt.id, transaction_date=t_date or db_stmt.period_end,
                                       merchant=t['merchant'], category="Sin Categoría", amount=t['amount'], type=t['type']))
            for m in msi_list:
                p_parts = m['installment'].split('/')
                session.add(DeferredInstallment(statement_id=db_stmt.id, merchant=m['merchant'], current_installment=int(p_parts[0]),
                                               total_installments=int(p_parts[1]), installment_amount=m['amount'], remaining_balance=0.0))
            session.commit()
