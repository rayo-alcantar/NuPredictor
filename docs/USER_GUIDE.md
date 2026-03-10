# Guía de Usuario: NuPredictor

NuPredictor es una herramienta local de análisis financiero diseñada para ayudarte a entender tus gastos de la tarjeta Nu México y predecir tus pagos futuros.

## 1. Requisitos
- Windows 10/11
- Miniconda o Anaconda instalado.
- Los estados de cuenta de Nu en formato PDF (descargados de la app).

## 2. Instalación
1. Clona o descarga este repositorio en tu máquina.
2. Abre una terminal (PowerShell o CMD) en la carpeta del proyecto.
3. Crea y activa el entorno virtual:
   ```bash
   conda create -n nu python=3.11 -y
   conda activate nu
   pip install -r requirements.txt
   ```

## 3. Estructura de Carpetas
- `estados-de-cuenta/`: Aquí debes colocar tus PDFs de Nu.
- `data/processed/`: Contiene la base de datos `nupredictor.db`.
- `data/exports/`: Aquí se guardarán los reportes CSV.
- `src/`: Código fuente del sistema.

## 4. Flujo de Uso Mensual (Recomendado)
El sistema está diseñado para ser muy simple de usar cada mes:

1. Descarga tu nuevo estado de cuenta de la app de Nu.
2. Colócalo en la carpeta `estados-de-cuenta/`.
3. Ejecuta el comando maestro:
   ```bash
   python main.py monthly-update
   ```
   Este comando hará tres cosas automáticamente:
   - Ingerirá el nuevo archivo.
   - Mostrará el resumen histórico actualizado.
   - Generará la predicción de pago para el próximo mes.

## 5. Comandos del CLI
Puedes usar `python main.py [comando]` para tareas específicas:

| Comando | Descripción |
| :--- | :--- |
| `init` | Inicializa la base de datos por primera vez. |
| `ingest` | Busca nuevos PDFs y los añade al historial. |
| `stats` | Muestra un resumen de los estados de cuenta guardados. |
| `forecast` | Genera predicciones de gasto para los próximos meses. |
| `export` | Genera archivos CSV en `data/exports/` para Excel. |
| `reset-db` | Borra toda la información y comienza de cero (pide confirmación). |
| `monthly-update` | Ejecuta el flujo completo mensual. |

## 6. Interpretación del Forecast
El comando `forecast` te mostrará tres escenarios:
- **Pago Base (Estimado):** Lo que probablemente pagarás basado en tus suscripciones y gasto promedio.
- **Escenario Conservador:** Un estimado que contempla picos de gasto (basado en meses de alta volatilidad).
- **Fijo + MSI:** El monto mínimo que ya tienes comprometido (suscripciones + meses sin intereses).
