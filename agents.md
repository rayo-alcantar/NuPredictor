# NuPredictor: Guía de Agentes y Arquitectura

You have access to Engram persistent memory via MCP tools (mem_save, mem_search, mem_session_summary, etc.).
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call mem_context to recover session state before continuing.

## 1. Objetivo del Sistema
Construir un motor local, robusto y auditable para el análisis de finanzas personales basado en estados de cuenta de Nu México, con capacidades de predicción multimodelo y validación contable estricta.

## 2. Arquitectura de Módulos (Contratos)
- **Ingestion (`src/core/discovery.py`):** Responsable de detectar PDFs, calcular hashes SHA-256 y gestionar la cola de procesamiento.
- **Extraction (`src/core/parser.py`):** Implementa el patrón de fallback (pypdf -> pdfplumber -> pymupdf). Debe devolver un objeto de texto normalizado.
- **Data Layer (`src/core/database.py`):** Utiliza SQLModel para gestionar la persistencia en SQLite. Define las 7 entidades principales (Statements, Transactions, Deferred, Recurring, Predictions, Aliases, Anomalies).
- **Accounting (`src/analysis/accounting.py`):** Valida la integridad del estado de cuenta mediante la ecuación contable.
- **Forecasting (`src/prediction/engine.py`):** Ejecuta modelos competitivos (Baseline, MA, ETS, Monte Carlo) y genera rangos de confianza.
- **UI/CLI (`src/ui/cli.py`):** Interfaz única para el usuario en español.

## 3. Reglas de Memoria y Estado
- El estado de procesamiento de cada PDF debe persistirse para evitar re-trabajo.
- Las decisiones de categorización manual del usuario deben guardarse en `MerchantAliases`.
- Cada ejecución de predicción debe quedar registrada para análisis de precisión posterior.

## 4. Convenciones de Nombres e Idioma
- **Código y Documentación Interna:** Inglés (clases, variables, métodos).
- **Interfaz de Usuario y Reportes:** Español (mensajes CLI, logs de éxito/error, archivos de salida).
- **Persistencia:** Nombres de tablas en plural (transactions, statements).

## 5. Validación Contable y Parser
- **Ecuación Contable Nu (Modo BASE):**
  `Saldo Actual = Saldo Anterior + Compras + MSI del Periodo + IVA - (Pagos + Devoluciones)`
  *Nota Técnica:* Esta ecuación ha demostrado ser 100% precisa ($0.00 de diferencia) para los 6 estados de cuenta analizados (Oct 2025 - Mar 2026). 
  - El sistema cuenta con un modo de respaldo llamado `base_plus_interest` para sumar intereses por separado, pero **no ha sido requerido** en ninguna de las muestras históricas actuales; todos los intereses detectados (incluyendo Feb/Mar 2026) parecen ya estar integrados en las partidas principales del resumen Nu.
- **Tipos de Cargos Identificados:**
  - `ordinary`: Compras normales.
  - `interest`: Intereses (revolventes, MSI o disposiciones).
  - `adjustment`: Abonos técnicos de Nu (compensación de planes fijos).
  - `disposal`: Disposiciones de efectivo.
  - `return`: Devoluciones comerciales.
- **Estado de Validación:**
  - Los 6 estados iniciales (Oct 2025 - Mar 2026) están validados al 100% con $0.00 de diferencia.
  - Cualquier PDF futuro con diferencia > $1.00 generará una anomalía para auditoría manual.

## 6. Límites de IA
- El parseo principal es **determinista (Regex)**.
- La IA (Gemini/OpenAI) se reserva exclusivamente para:
  1. Clasificación de comercios desconocidos (enviando solo el nombre del comercio).
  2. Generación de resúmenes ejecutivos narrativos.
- El sistema debe funcionar al 90% de su capacidad sin llaves de API externas.

## 6. Flujo Incremental Mensual
1. Escaneo de `estados-de-cuenta/`.
2. Identificación de archivos no procesados (vía hash).
3. Extracción de texto y validación de bloques.
4. Poblamiento de tablas y validación contable.
5. Actualización de modelos de predicción con el nuevo punto de datos.
