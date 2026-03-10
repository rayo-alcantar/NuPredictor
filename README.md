# NuPredictor 🚀 💜

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](https://opensource.org/licenses/MIT)
[![Nu Brand](https://img.shields.io/badge/Nu-México-8A05BE.svg)](https://nu.com.mx/)

**NuPredictor** es una herramienta de código abierto diseñada para ayudarte a tomar el control total de tus finanzas con la tarjeta Nu México. Analiza tus estados de cuenta en PDF, normaliza tus datos y predice tus próximos pagos de forma inteligente y 100% privada. 💸

---

## ✨ Características Principales

- **📥 Ingesta Inteligente:** Transforma tus estados de cuenta PDF en datos estructurados automáticamente.
- **🧹 Normalización de Comercios:** Limpia nombres complejos (ej. `UBER *EATS HELP.UBER.C` -> `Uber Eats`).
- **📈 Análisis Histórico:** Visualiza la evolución de tus gastos, pagos y utilización de crédito.
- **🔮 Forecast Pragmático:** Predice tu próximo pago separando cargos fijos, MSI y gastos variables.
- **🔒 Privacidad Local:** Tus datos nunca salen de tu máquina. Sin nube, sin rastreo externo.

---

## 🛠️ Instalación

Elige el método que mejor se adapte a tu equipo:

### Opción A: Con Miniconda / Anaconda (Recomendado) 🐍
```bash
git clone https://github.com/rayo-alcantar/NuPredictor.git
cd NuPredictor
conda create -n nu python=3.11 -y
conda activate nu
pip install -r requirements.txt
```

### Opción B: Con Python venv (Estándar) 📦
```bash
git clone https://github.com/rayo-alcantar/NuPredictor.git
cd NuPredictor
python -m venv .venv
# Activar en Windows:
.venv\Scripts\activate
# Activar en Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

### Opción C: Instalación Directa (Global) 🌍
*Asegúrate de tener Python 3.11 o superior instalado.*
```bash
git clone https://github.com/rayo-alcantar/NuPredictor.git
cd NuPredictor
pip install -r requirements.txt
```

---

## 📅 Flujo de Uso Mensual

Usar NuPredictor es tan simple como el corazón morado:

1. **Descarga** tu estado de cuenta PDF desde la app de Nu.
2. **Colócalo** en la carpeta `estados-de-cuenta/`.
3. **Ejecuta el comando maestro:**
   ```bash
   python main.py monthly-update
   ```

---

## 🕹️ Referencia de Comandos CLI

| Comando | Descripción |
| :--- | :--- |
| `init` | Inicializa la base de datos por primera vez. |
| `doctor` | 🩺 Diagnóstico del sistema y verificación de archivos. |
| `monthly-update` | 🔄 Flujo completo: Ingesta + Estadísticas + Predicción. |
| `next-payment` | 💳 Explicación simple de lo que pagarás el próximo mes. |
| `stats` | 📈 Resumen histórico de estados procesados. |
| `export` | 📤 Genera archivos CSV listos para Excel. |
| `forecast` | 🔭 Proyección detallada a futuro. |
| `reset-db` | ⚠️ Borra todo y reinicia el sistema (pide confirmación). |

---

## 📖 Cómo Funciona (Arquitectura)

1. **Extracción:** Utiliza un motor de fallback (`pypdf` como primario) para extraer texto manteniendo la estructura de Nu.
2. **Reconciliación:** Valida que la suma de transacciones, intereses, IVA y pagos coincida exactamente con el saldo final.
3. **Persistencia:** Guarda todo en una base de datos local `SQLite` usando `SQLModel`.
4. **Predicción:** Combina tus costos fijos detectados con una media móvil de tus gastos variables para darte un rango de pago estimado.

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Si tienes ideas para mejorar el parser o nuevos modelos de predicción:
1. Haz un **Fork** del proyecto.
2. Crea una rama para tu característica (`git checkout -b feature/MejoraIncreible`).
3. Haz **commit** de tus cambios (`git commit -m 'Añadida mejora increíble'`).
4. Haz **Push** a la rama (`git push origin feature/MejoraIncreible`).
5. Abre un **Pull Request**.

---

## 🛡️ Privacidad y Seguridad

NuPredictor **no es un producto oficial de Nu**. No estamos afiliados ni respaldados por Nu México. 

**Seguridad de Datos:** El archivo `.gitignore` está configurado para que nunca subas accidentalmente tus estados de cuenta reales (`.pdf`) o tu base de datos (`.db`) a repositorios públicos. **Mantén tu información personal a salvo.**

---
*Hecho con 💜 para la comunidad financiera. ¡Que viva el corazón morado!*
