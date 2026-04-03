from datetime import date, datetime
from typing import Optional, List, Dict
from sqlmodel import Field, SQLModel, Relationship, create_engine, Session

# Utilidad para meses en español
SPANISH_MONTHS = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
}

def parse_spanish_date(date_str: str) -> Optional[date]:
    try:
        parts = date_str.strip().split()
        if len(parts) != 3: return None
        day = int(parts[0]); month = SPANISH_MONTHS.get(parts[1].upper()); year = int(parts[2])
        return date(year, month, day) if month else None
    except Exception: return None

class Statement(SQLModel, table=True):
    __tablename__ = "statements"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    file_hash: str = Field(unique=True)
    period_start: date; period_end: date
    total_balance: float; previous_balance: float; payments_made: float; purchases_made: float
    msi_period_total: float = Field(default=0.0)
    returns_total: float = Field(default=0.0)
    interest_charged: float; iva_charged: float
    credit_limit: float; available_credit: float
    extraction_engine: str
    reconciliation_mode: str = Field(default="unknown")
    is_valid_accounting: bool = False
    accounting_diff: float = 0.0
    processed_at: datetime = Field(default_factory=datetime.now)
    
    transactions: List["Transaction"] = Relationship(back_populates="statement")
    deferred_installments: List["DeferredInstallment"] = Relationship(back_populates="statement")

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id")
    transaction_date: date; merchant: str = Field(index=True); category: str = Field(index=True)
    amount: float; type: str = Field(default="ordinary")
    statement: Statement = Relationship(back_populates="transactions")

class DeferredInstallment(SQLModel, table=True):
    __tablename__ = "deferred_installments"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id")
    merchant: str; current_installment: int; total_installments: int; installment_amount: float; remaining_balance: float
    statement: Statement = Relationship(back_populates="deferred_installments")

class MerchantAlias(SQLModel, table=True): # RESTAURADA
    __tablename__ = "merchant_aliases"
    id: Optional[int] = Field(default=None, primary_key=True)
    raw_name: str = Field(unique=True)
    clean_name: str
    category: str

class Anomaly(SQLModel, table=True):
    __tablename__ = "anomalies"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: Optional[int] = Field(default=None, foreign_key="statements.id")
    anomaly_type: str; description: str; detected_at: datetime = Field(default_factory=datetime.now)

class Prediction(SQLModel, table=True):
    __tablename__ = "predictions"
    id: Optional[int] = Field(default=None, primary_key=True)
    target_period: str = Field(index=True)
    generated_at: datetime = Field(default_factory=datetime.now)
    base_amount: float
    optimistic_amount: float
    conservative_amount: float
    actual_amount: Optional[float] = Field(default=None)
    error_margin: Optional[float] = Field(default=None)

sqlite_url = "sqlite:///data/processed/nupredictor.db"
engine = create_engine(sqlite_url, echo=False)
def init_db(): SQLModel.metadata.create_all(engine)
