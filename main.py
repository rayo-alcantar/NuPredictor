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
    
    if results['success'] > 0:
        analyzer = FinancialAnalyzer()
        engine_pred = PredictionEngine(analyzer)
        val_count = engine_pred.validate_past_predictions()
        if val_count > 0:
            console.print(f"[bold cyan]🤖 Aprendizaje de Modelo:[/bold cyan] Se validaron {val_count} predicciones con los nuevos datos.")

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
@click.argument('raw_name', required=False)
@click.argument('clean_name', required=False)
@click.argument('category', required=False)
def alias(raw_name, clean_name, category):
    """
    Limpia los nombres de comercios (Modo interactivo si no hay argumentos).
    """
    analyzer = FinancialAnalyzer()
    
    # Modo Interactivo
    if not raw_name:
        console.print("[bold cyan]Modo de Limpieza de Comercios[/bold cyan]")
        unaliased = analyzer.get_unaliased_merchants(limit=5)
        
        if not unaliased:
            console.print("¡Genial! Todos tus comercios frecuentes ya tienen un nombre limpio.")
            return

        console.print(f"He encontrado {len(unaliased)} comercios frecuentes con nombres difíciles. Vamos a limpiarlos:\n")
        for raw in unaliased:
            if click.confirm(f"¿Quieres renombrar '{raw}'?"):
                clean = click.prompt(f"  Nombre legible (ej. Uber Eats)", default=raw)
                cat = click.prompt(f"  Categoría (ej. Comida, Transporte, Compras)", default="Otros")
                analyzer.upsert_alias(raw, clean, cat)
                console.print(f"  [green]✓ Guardado![/green]\n")
        return

    # Modo Directo
    if not (clean_name and category):
        console.print("[red]Error: Si usas argumentos, debes pasar los tres: RAW_NAME CLEAN_NAME CATEGORY[/red]")
        return
        
    analyzer.upsert_alias(raw_name, clean_name, category)
    console.print(f"[green]Alias guardado:[/green] {raw_name} -> [bold]{clean_name}[/bold] ({category})")

@cli.command()
@click.option('--meses', default=None, type=int, help='¿Cuántos meses al futuro quieres ver?')
def forecast(meses):
    """Predice cuánto pagarás en los próximos meses."""
    analyzer = FinancialAnalyzer()
    engine_pred = PredictionEngine(analyzer)
    
    # 1. Preguntar meses si no se dieron por parámetro
    if meses is None:
        meses = click.prompt("¿A cuántos meses quieres ver tu predicción?", type=int, default=3)

    # 2. Preguntar por gastos extra
    adjustments = {}
    if click.confirm("\n¿Tienes planeado algún gasto fuerte extraordinario próximamente?"):
        monto = click.prompt("  ¿De cuánto es el gasto?", type=float)
        offset = click.prompt(f"  ¿En qué mes será? (1-{meses})", type=click.IntRange(1, meses), default=1)
        adjustments[offset] = monto

    data = engine_pred.generate_forecast(months_ahead=meses, adjustments=adjustments)
    
    if "error" in data:
        console.print(f"\n[bold red]Ups![/bold red] {data['error']}"); return

    console.print(f"\n[bold magenta]🔮 Tu Futuro Financiero (Próximos {meses} meses)[/bold magenta]")
    console.print(f"Basado en tus últimos gastos y MSI activos:\n")
    
    table = Table(header_style="bold cyan", box=None)
    table.add_column("Mes", style="dim"); table.add_column("Fijos + MSI", justify="right")
    table.add_column("Variable Est.", justify="right"); table.add_column("Extra", justify="right", style="magenta")
    table.add_column("Total Estimado", justify="right", style="bold green")
    
    for p in data['projections']:
        fixed_msi = p['Fijo (Conocido)'] + p['Diferido (MSI)']
        extra_val = p.get('Ajuste Manual', 0.0)
        table.add_row(
            p['Mes'], 
            f"${fixed_msi:,.2f}", 
            f"${p['Variable (Est.)']:,.2f}", 
            f"${extra_val:,.2f}" if extra_val > 0 else "-",
            f"${p['Escenario Base']:,.2f}"
        )
    console.print(table)
    
    console.print(f"\n[bold yellow]💡 Nota de NuPredictor:[/bold yellow]")
    console.print(f"Tu gasto variable estimado es de [cyan]${data['model_metadata']['historical_avg_variable']:,.2f}[/cyan] mensuales.")
    if meses > 0:
        console.print(f"Para {p['Mes']}, el escenario conservador es de [yellow]${p['Escenario Conservador']:,.2f}[/yellow].\n")

@cli.command()
def tutorial():
    """Guía rápida para nuevos usuarios."""
    steps = [
        ("1. Ingesta", "Coloca tus PDFs de Nu en la carpeta 'estados-de-cuenta'."),
        ("2. Actualización", "Ejecuta 'python main.py monthly-update' para leer los archivos."),
        ("3. Limpieza", "Usa 'python main.py alias' para que los nombres feos del banco se vean bien."),
        ("4. Predicción", "Usa 'python main.py next-payment' para saber cuánto pagarás el próximo mes.")
    ]
    
    console.print(Panel("[bold purple]¡Bienvenido a NuPredictor! 💜[/bold purple]\n\nSigue estos pasos para dominar tus finanzas:", expand=False))
    for i, (title, desc) in enumerate(steps):
        console.print(f"[bold cyan]{title}[/bold cyan]: {desc}")

@cli.command()
def next_payment():
    """Muestra una explicación simple de lo que pagarás el próximo mes."""
    analyzer = FinancialAnalyzer()
    engine_pred = PredictionEngine(analyzer)
    data = engine_pred.generate_forecast(months_ahead=1)
    
    if "error" in data:
        console.print(f"[red]{data['error']}[/red]"); return
    
    p = data['projections'][0]
    
    msg = f"""[bold white]Resumen de tu próximo pago estimado ({p['Mes']})[/bold white]

Pagos fijos detectados: [green]${p['Fijo (Conocido)']:,.2f}[/green]
Cuotas a meses sin intereses activas: [green]${p['Diferido (MSI)']:,.2f}[/green]
Gasto variable (WMA 4 meses): [yellow]${p['Variable (Est.)']:,.2f}[/yellow]

[bold cyan]Pago estimado: ${p['Escenario Base']:,.2f}[/bold cyan]

[bold white]Escenarios:[/bold white]
- Optimista (Gasto bajo): [green]${p['Escenario Optimista']:,.2f}[/green]
- Conservador (Gasto alto): [yellow]${p['Escenario Conservador']:,.2f}[/yellow]

[italic]Nota: El cálculo usa un promedio ponderado dando más importancia a tus meses de gasto más recientes.[/italic]
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

@cli.command()
def model_metrics():
    """Muestra el desempeño y sesgo del modelo de predicción."""
    from src.core.database import Prediction
    analyzer = FinancialAnalyzer()
    engine_pred = PredictionEngine(analyzer)
    
    with Session(engine) as session:
        preds = session.exec(select(Prediction).order_by(Prediction.target_period.desc())).all()
    
    bias = engine_pred.get_bias_correction_factor()
    
    console.print("\n[bold]Desempeño del Modelo de Predicción[/bold]\n")
    console.print(f"Factor de corrección de sesgo actual: [magenta]{bias:.4f}[/magenta] (Multiplicador aplicado a nuevas predicciones)\n")
    
    if not preds:
        console.print("No hay predicciones registradas todavía.")
        return
        
    table = Table(title="Historial de Predicciones")
    table.add_column("Periodo", style="cyan")
    table.add_column("Predicho (Base)", justify="right")
    table.add_column("Real", justify="right")
    table.add_column("Error %", justify="right")
    
    for p in preds:
        real_str = f"${p.actual_amount:,.2f}" if p.actual_amount is not None else "[dim]Pendiente[/dim]"
        err_str = f"{p.error_margin * 100:+.2f}%" if p.error_margin is not None else "-"
        
        if p.error_margin is not None:
            err_style = "green" if p.error_margin >= 0 else "red"
            err_str = f"[{err_style}]{err_str}[/{err_style}]"
            
        table.add_row(
            p.target_period,
            f"${p.base_amount:,.2f}",
            real_str,
            err_str
        )
        
    console.print(table)

if __name__ == "__main__":
    cli()
