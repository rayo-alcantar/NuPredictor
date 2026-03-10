import click
import os
from rich.console import Console
from rich.table import Table
from src.core.database import init_db, engine, Statement, Transaction, DeferredInstallment
from src.core.ingestor import Ingestor
from src.analysis.metrics import FinancialAnalyzer
from src.prediction.engine import PredictionEngine
from sqlmodel import Session, select, func
import pandas as pd

console = Console()

@click.group()
def cli():
    """NuPredictor: Sistema de análisis financiero local para Nu."""
    pass

@cli.command()
def init():
    """Inicializa la base de datos local."""
    console.print("[yellow]Inicializando base de datos...[/yellow]")
    init_db()
    console.print("[green]Base de datos inicializada correctamente.[/green]")

@cli.command()
@click.confirmation_option(prompt='¿Estás seguro de que deseas borrar toda la base de datos?')
def reset_db():
    """Borra y reinicializa la base de datos completa."""
    db_path = "data/processed/nupredictor.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        console.print(f"[red]Base de datos borrada: {db_path}[/red]")
    init_db()
    console.print("[green]Base de datos reinicializada.[/green]")

@cli.command()
@click.option('--dir', default='estados-de-cuenta', help='Directorio con PDFs.')
@click.pass_context
def ingest(ctx, dir):
    """Ingiere PDFs nuevos en la base de datos."""
    console.print(f"[blue]Escaneando directorio: {dir}[/blue]")
    ingestor = Ingestor()
    results = ingestor.process_all(dir)
    console.print(f"Ingestión finalizada: [green]{results['success']} éxitos[/green], [red]{results['failed']} fallidos[/red]")

@cli.command()
def stats():
    """Muestra estadísticas generales de la base de datos."""
    with Session(engine) as session:
        n_statements = session.exec(select(func.count(Statement.id))).one()
        n_transactions = session.exec(select(func.count(Transaction.id))).one()
        statements = session.exec(select(Statement).order_by(Statement.period_end.desc())).all()
        
        table = Table(title="Resumen Histórico de NuPredictor")
        table.add_column("Archivo", style="cyan"); table.add_column("Periodo Fin", style="magenta")
        table.add_column("Saldo Total", justify="right"); table.add_column("Val. Contable", justify="center")
        for s in statements:
            status = "✅" if s.is_valid_accounting else "❌"
            table.add_row(s.filename, s.period_end.strftime("%Y-%m-%d"), f"${s.total_balance:,.2f}", status)
        console.print(table)
        console.print(f"\nResumen: {n_statements} estados, {n_transactions} transacciones.")

@cli.command()
@click.option('--months', default=3, help='Número de meses a proyectar.')
def forecast(months):
    """Genera una predicción pragmática de pagos futuros."""
    analyzer = FinancialAnalyzer()
    engine_pred = PredictionEngine(analyzer)
    data = engine_pred.generate_forecast(months_ahead=months)
    
    if "error" in data:
        console.print(f"[red]{data['error']}[/red]"); return

    console.print(f"\n[bold blue]Proyección de Pagos Futuros (Próximos {months} meses)[/bold blue]")
    console.print(f"Gasto Fijo: [green]${data['model_metadata']['fixed_subscriptions']:,.2f}[/green] | Var. Promedio: [yellow]${data['model_metadata']['historical_avg_variable']:,.2f}[/yellow]\n")
    
    table = Table(header_style="bold cyan")
    table.add_column("Mes"); table.add_column("Fijo+MSI", justify="right")
    table.add_column("Var. Est.", justify="right"); table.add_column("Pago Base", justify="right", style="bold green")
    table.add_column("Esc. Conservador", justify="right", style="yellow")
    
    for p in data['projections']:
        fixed_msi = p['Fijo (Conocido)'] + p['Diferido (MSI)']
        table.add_row(p['Mes'], f"${fixed_msi:,.2f}", f"${p['Variable (Base)']:,.2f}", f"${p['Escenario Base']:,.2f}", f"${p['Escenario Conservador']:,.2f}")
    console.print(table)

@cli.command()
@click.pass_context
def monthly_update(ctx):
    """Flujo completo: Ingesta -> Stats -> Forecast."""
    console.print("[bold yellow]Iniciando flujo de actualización mensual...[/bold yellow]")
    ctx.invoke(ingest)
    console.print("\n")
    ctx.invoke(stats)
    console.print("\n")
    ctx.invoke(forecast, months=3)

@cli.command()
def export():
    """Exporta los datos históricos y métricas a archivos CSV."""
    analyzer = FinancialAnalyzer()
    os.makedirs("data/exports", exist_ok=True)
    
    # 1. Resumen Mensual
    summary = analyzer.get_monthly_breakdown()
    summary.to_csv("data/exports/monthly_summary.csv", index=False)
    
    # 2. Top Comercios
    tops = analyzer.get_top_merchants_clean(limit=50)
    tops.to_csv("data/exports/top_merchants.csv", index=False)
    
    # 3. Suscripciones
    subs = pd.DataFrame(analyzer.detect_subscriptions())
    subs.to_csv("data/exports/subscriptions_detected.csv", index=False)
    
    console.print("[green]Archivos exportados exitosamente en data/exports/[/green]")
    console.print("- monthly_summary.csv")
    console.print("- top_merchants.csv")
    console.print("- subscriptions_detected.csv")

if __name__ == "__main__":
    cli()
