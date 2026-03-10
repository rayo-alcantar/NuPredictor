import click
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
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
def next_payment():
    """Muestra una explicación simple de lo que pagarás el próximo mes."""
    analyzer = FinancialAnalyzer()
    engine_pred = PredictionEngine(analyzer)
    data = engine_pred.generate_forecast(months_ahead=1)
    
    if "error" in data:
        console.print(f"[red]{data['error']}[/red]"); return
    
    p = data['projections'][0]
    
    msg = f"""[bold white]Resumen de tu próximo pago estimado[/bold white]

Pagos fijos detectados: [green]${p['Fijo (Conocido)']:,.2f}[/green]
Cuotas a meses sin intereses activas: [green]${p['Diferido (MSI)']:,.2f}[/green]
Gasto variable promedio: [yellow]${p['Variable (Base)']:,.2f}[/yellow]

[bold cyan]Pago estimado para el próximo mes: ${p['Escenario Base']:,.2f}[/bold cyan]

[bold white]Explicación simple:[/bold white]

[bold]Pagos fijos[/bold]
Son cosas que pagas casi todos los meses (suscripciones o servicios).

[bold]Meses sin intereses[/bold]
Son compras que dividiste en varios meses y todavía estás pagando.

[bold]Gasto variable[/bold]
Es lo que normalmente gastas en compras del día a día.

[bold yellow]Escenario conservador (mes de gasto alto): ${p['Escenario Conservador']:,.2f}[/bold yellow]
"""
    console.print(Panel(msg, expand=False, title="Próximo Pago"))

@cli.command()
def doctor():
    """Diagnóstico rápido del sistema."""
    console.print("\n[bold]Sistema NuPredictor — Diagnóstico[/bold]\n")
    
    data_dir = "estados-de-cuenta"
    db_path = "data/processed/nupredictor.db"
    
    dir_ok = os.path.exists(data_dir)
    db_ok = os.path.exists(db_path)
    
    pdfs = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")] if dir_ok else []
    
    n_processed = 0
    if db_ok:
        try:
            with Session(engine) as session:
                n_processed = session.exec(select(func.count(Statement.id))).one()
        except Exception:
            db_ok = False
            
    console.print(f"Carpeta de estados de cuenta: {'[green]OK[/green]' if dir_ok else '[red]NO ENCONTRADA[/red]'}")
    console.print(f"Base de datos encontrada: {'[green]OK[/green]' if db_ok else '[red]ERROR / NO INICIALIZADA[/red]'}")
    console.print(f"Estados procesados: [cyan]{n_processed}[/cyan]")
    console.print(f"PDFs detectados en carpeta: [cyan]{len(pdfs)}[/cyan]")
    console.print(f"PDFs pendientes de ingerir: [yellow]{max(0, len(pdfs) - n_processed)}[/yellow]")
    
    if dir_ok and db_ok and len(pdfs) == n_processed:
        console.print("\n[bold green]Estado general: Todo parece funcionar correctamente.[/bold green]")
    elif not dir_ok:
        console.print("\n[bold red]Estado general: Requieres crear la carpeta 'estados-de-cuenta'.[/bold red]")
    elif not db_ok:
        console.print("\n[bold red]Estado general: Requieres inicializar la base con 'python main.py init'.[/bold red]")
    else:
        console.print("\n[bold yellow]Estado general: Hay archivos pendientes. Corre 'python main.py ingest'.[/bold yellow]")

@cli.command()
@click.pass_context
def monthly_update(ctx):
    """Flujo completo: Ingesta -> Stats -> Forecast."""
    console.print("[bold yellow]Iniciando flujo de actualización mensual...[/bold yellow]")
    ctx.invoke(ingest)
    console.print("\n")
    ctx.invoke(stats)
    console.print("\n")
    ctx.invoke(next_payment)

@cli.command()
def export():
    """Exporta los datos históricos y métricas a archivos CSV."""
    analyzer = FinancialAnalyzer()
    os.makedirs("data/exports", exist_ok=True)
    
    # 1. Resumen Mensual
    analyzer.get_monthly_breakdown().to_csv("data/exports/monthly_summary.csv", index=False)
    # 2. Top Comercios
    analyzer.get_top_merchants_clean(limit=50).to_csv("data/exports/top_merchants.csv", index=False)
    # 3. Suscripciones
    pd.DataFrame(analyzer.detect_subscriptions()).to_csv("data/exports/subscriptions_detected.csv", index=False)
    # 4. Transacciones Limpias (NUEVO)
    analyzer.get_all_transactions_clean().to_csv("data/exports/transactions_clean.csv", index=False)
    
    console.print("[green]Archivos exportados exitosamente en data/exports/[/green]")
    console.print("- monthly_summary.csv")
    console.print("- top_merchants.csv")
    console.print("- subscriptions_detected.csv")
    console.print("- transactions_clean.csv")

if __name__ == "__main__":
    cli()
