# Arquitectura Técnica: NuPredictor

NuPredictor es un sistema modular diseñado para la integridad contable y la interpretabilidad financiera.

## 1. Motor de Extracción (Parser)
El sistema utiliza una estrategia de **fallback multinivel**:
1. **pypdf:** Extractor principal. Se prefiere porque mantiene la estructura secuencial de líneas necesaria para las expresiones regulares de Nu.
2. **pdfplumber/pymupdf:** Utilizados como respaldo si el texto extraído no contiene palabras clave críticas.

El proceso sigue este flujo: `Extracción -> Normalización -> Segmentación por Bloques -> Parseo Regex`.

## 2. Reconciliación Contable
Para asegurar que los datos son correctos, el sistema valida cada PDF con la ecuación:
`Saldo Actual = Saldo Anterior + Compras + MSI del Periodo + IVA - (Pagos + Devoluciones)`

El sistema detecta automáticamente si el MSI del periodo está reportado como un "extra" o integrado en las compras basándose en el desbalance observado.

## 3. Modelo de Datos (SQLite + SQLModel)
- `statements`: Metadatos y totales del estado de cuenta.
- `transactions`: Movimientos individuales clasificados (`ordinary`, `interest`, `adjustment`, `disposal`).
- `deferred_installments`: Seguimiento de planes a meses activos.
- `merchant_aliases`: Capa de normalización de nombres (ej. "Uber *Eats" -> "Uber Eats").

## 4. Modelo de Predicción
El forecast utiliza un enfoque **híbrido**:
- **Parte Determinista:** Suma literal de suscripciones detectadas y cuotas de MSI vigentes.
- **Parte Probabilística:** Media móvil de los últimos 4 meses de gasto variable discrecional.
- **Escenarios:** Se calcula la desviación estándar del gasto variable para generar un rango de confianza (Escenario Base vs Conservador).

## 5. Detección de Suscripciones
Un comercio se clasifica como suscripción si:
1. Aparece en al menos el 75% de los estados de cuenta procesados.
2. El monto es relativamente estable (se usa el promedio histórico para la predicción).
