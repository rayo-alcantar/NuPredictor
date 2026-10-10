from datetime import date

from sqlmodel import Session, create_engine
from sqlalchemy.pool import StaticPool

from src.analysis.metrics import FinancialAnalyzer
from src.core.database import Prediction, SQLModel, Statement, Transaction
from src.core.nu_extractor import NuExtractor
from src.prediction.engine import PredictionEngine


def memory_engine():
    db = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(db)
    return db


def test_new_nu_layout_extracts_installment_payment_and_cleans_merchant():
    text = """
    ¡Hola! Periodo: 10 SEP 2026 al 09 OCT 2026
    PAGO PARA NO GENERAR INTERESES = $6,154.74
    Adeudo del periodo anterior = $1,033.55
    Cargos regulares (no a meses) + $6,088.35
    Cargos y compras a meses (capital) + $498.43
    Pagos y abonos - $1,533.56
    Monto de intereses + $60.77
    IVA de intereses y comisiones + $7.20
    Límite de crédito $21,000.00
    Crédito disponible $11,490.07
    COMPRAS Y CARGOS DIFERIDOS A MESES CON INTERESES
    29 MAR 2026 Compra diferida - Str*Platzi -
    6/12 $5,990.00 $3,664.29 $498.43 6/12 19.90%$60.77 $7.20
    """
    parsed = NuExtractor(text).parse_msi()
    assert parsed[0]["merchant"] == "Compra diferida - Str*Platzi -"
    assert parsed[0]["installment"] == "6/12"
    assert parsed[0]["amount"] == 498.43
    assert parsed[0]["remaining_balance"] == 3664.29


def test_habits_report_groups_categories_and_recurring_merchants():
    db = memory_engine()
    with Session(db) as session:
        for index, month in enumerate((7, 8, 9), start=1):
            statement = Statement(
                filename=f"s{index}.pdf", file_hash=f"hash-{index}",
                period_start=date(2026, month, 1), period_end=date(2026, month, 9),
                total_balance=500.0, previous_balance=0.0, payments_made=0.0,
                purchases_made=500.0, interest_charged=0.0, iva_charged=0.0,
                credit_limit=21000.0, available_credit=20000.0, extraction_engine="test",
            )
            session.add(statement)
            session.commit()
            session.refresh(statement)
            session.add(Transaction(statement_id=statement.id, transaction_date=date(2026, month, 2), merchant="Openai", category="Sin Categoría", amount=399.0, type="ordinary"))
            session.add(Transaction(statement_id=statement.id, transaction_date=date(2026, month, 3), merchant="Uber Eats", category="Sin Categoría", amount=101.0, type="ordinary"))
        session.commit()

    report = FinancialAnalyzer(db).get_habits_report()
    assert report["observed_statements"] == 3
    assert report["ordinary_charge_total"] == 1500.0
    assert report["categories"][0]["category"] == "Suscripciones"
    assert report["recurring"][0]["merchant"] == "ChatGPT"
    assert report["recurring"][0]["monthly_amount"] == 399.0


def test_bias_ignores_legacy_outliers():
    db = memory_engine()
    with Session(db) as session:
        for period, base, actual in (("2026-07", 9800.0, 3400.0), ("2026-09", 9400.0, 1000.0), ("2026-10", 5700.0, 6150.0)):
            session.add(Prediction(target_period=period, base_amount=base, optimistic_amount=base, conservative_amount=base, actual_amount=actual, error_margin=0.0))
        session.commit()
    engine = PredictionEngine(FinancialAnalyzer(db))
    diagnostics = engine.get_bias_diagnostics()
    assert diagnostics["factor"] == 1.0
    assert diagnostics["excluded"] == 2
