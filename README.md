# NuPredictor 🚀

NuPredictor es una herramienta local diseñada para analizar tus estados de cuenta de la tarjeta Nu México, organizar tus gastos y predecir cuánto pagarás el próximo mes.

## ¿Para qué sirve?
- **Ingesta Automática:** Transforma tus PDFs de Nu en datos estructurados.
- **Limpieza de Gastos:** Normaliza nombres como "Uber *Eats" a "Uber Eats" automáticamente.
- **Predicción de Pagos:** Estima tu próximo pago separando gastos fijos, MSI y variables.
- **Privacidad Total:** Todo se procesa localmente en tu computadora.

## Instalación Rápida
1. Asegúrate de tener **Conda** instalado.
2. Clona este repositorio.
3. Crea el entorno virtual:
   ```bash
   conda create -n nu python=3.11 -y
   conda activate nu
   pip install -r requirements.txt
   ```

## Cómo usarlo cada mes
1. Descarga tu estado de cuenta PDF desde la app de Nu.
2. Colócalo en la carpeta `estados-de-cuenta/`.
3. Ejecuta el comando maestro:
   ```bash
   python main.py monthly-update
   ```

## Comandos Disponibles
- `python main.py doctor`: Revisa que el sistema esté bien configurado.
- `python main.py next-payment`: Resumen simple de tu próximo pago.
- `python main.py stats`: Ver historial de estados procesados.
- `python main.py export`: Genera archivos Excel (CSV) con tus gastos.
- `python main.py forecast`: Proyección detallada a futuro.

---
*Desarrollado con un enfoque pragmático para el control de finanzas personales.*
