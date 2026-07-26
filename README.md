# 🛡️ Agente Vigía — Agente Universal de Integridad de Datos

> *"La mayoría de los agentes IA analizan datos. Agente Vigía primero determina si esos datos merecen ser analizados."*

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red?logo=streamlit)](https://streamlit.io)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock%20Claude%203-orange?logo=amazonaws)](https://aws.amazon.com/bedrock/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)

**Hackathon:** IA Masivo Online AWS por Código Facilito 2026 — Reto 3: Agentes Especializados

---
<img width="2816" height="1584" alt="b2cb6563-778b-4ded-9ea8-1eef55ff038d" src="https://github.com/user-attachments/assets/1ad4734b-704c-485b-9ff5-0bfe15a03b5c" />

---
## ¿Qué es Agente Vigía?

Agente Vigía es un **agente inteligente de auditoría de datos** que analiza automáticamente cualquier fuente de datos empresarial sin requerir configuración manual. Descubre esquemas, detecta problemas de calidad, infiere relaciones entre tablas y genera insights ejecutivos con IA — todo desde una interfaz Streamlit interactiva.

A diferencia de los agentes IA tradicionales que razonan sobre toda la información disponible sin validar su integridad, Agente Vigía **audita la calidad de los datos antes de generar cualquier recomendación**, bloqueando registros corruptos y advirtiendo sobre datos comprometidos.

---

## Características Principales

| Capacidad | Descripción |
|---|---|
| **Descubrimiento automático** | Inspecciona tablas, columnas, tipos, PKs, FKs, índices y relaciones sin configuración |
| **Inferencia de relaciones** | Detecta relaciones no declaradas por convención de nombres y overlap de valores |
| **Clasificación semántica** | Identifica qué representa cada columna (email, monetario, fecha, categórico, etc.) con % de confianza |
| **Auditoría multi-capa** | Validación estructural, relacional, estadística y de completitud |
| **Data Quality Score** | Puntaje global y por tabla con explicación exacta del cálculo |
| **Detección de riesgos** | Identifica anomalías, outliers, integridad rota y datos comprometidos |
| **Insights con IA** | Genera reportes ejecutivos usando Amazon Bedrock, NVIDIA NIM u OpenAI |
| **Dashboard dinámico** | UI generativa que se adapta al esquema analizado |
| **Exportación** | Descarga reportes en Markdown y hallazgos en CSV |
| **Multi-fuente** | SQLite, CSV, Excel (PostgreSQL y MySQL preparados para futuro) |

---

## Pipeline de Análisis

```
┌──────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│  FUENTE DE DATOS │───▶|  SCHEMA INSPECTOR │────▶│  GENERIC AUDIT      │
│  SQLite/CSV/Excel│     │  • Introspección  │     │  • 11 reglas        │
│                  │     │  • Clasificación  │     │  • Score por tabla  │
│                  │     │  • Inferencia     │     │  • Hallazgos        │
└──────────────────┘     └───────────────────┘     └─────────┬───────────┘
                                                             │
                                                             ▼
┌─────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│   STREAMLIT     │◀────│   LLM LAYER      │◀────│  INSIGHT ENGINE     │
│   DASHBOARD     │     │  Bedrock/NVIDIA/  │     │  • Detección riesgos│
│   • 5 tabs      │     │  OpenAI/Mock      │     │  • Prompt dinámico  │
│   • Exportar    │     │  • Prompt adaptado│     │  • Risk register    │
└─────────────────┘     └───────────────────┘     └─────────────────────┘
```

---

## Fuentes de Datos Compatibles

| Fuente        | Estado           | Extensiones |
|---------------|------------------|-------------|
| **SQLite** | ✅ Disponible | `.db`, `.sqlite`, `.sqlite3` |
| **CSV** | ✅ Disponible | `.csv` (auto-detecta delimitador y encoding) |
| **Excel** | ✅ Disponible | `.xlsx`, `.xls` (múltiples hojas) |
| **PostgreSQL** | 🔜 Preparado | Formulario de conexión en UI |
| **MySQL** | 🔜 Preparado | Formulario de conexión en UI |
| **SQL Server** | 📋 Futuro | — |
| **APIs REST** | 📋 Futuro | — |

---

## Capacidades de Auditoría

### Reglas de Calidad (11 reglas pluggables)

| Regla | Categoría | Nivel | Qué detecta |
|---|---|---|---|
| `null_primary_key` | Structural | CRITICAL | PKs con valores NULL |
| `duplicate_primary_key` | Structural | CRITICAL | PKs duplicadas |
| `invalid_date` | Structural | ERROR | Fechas con formato inválido |
| `negative_value` | Structural | ERROR | Negativos en campos monetarios/cantidad |
| `empty_strings` | Completeness | WARNING | Alto % de strings vacíos |
| `null_required_field` | Completeness | ERROR/WARNING | NULLs en campos requeridos |
| `high_null_rate` | Completeness | WARNING | Columnas con >50% NULL |
| `orphaned_foreign_key` | Relational | ERROR | Valores huérfanos en FKs |
| `outlier_detection` | Statistical | WARNING | Outliers via método IQR |
| `constant_column` | Statistical | INFO | Columnas con un solo valor |
| `cardinality_anomaly` | Statistical | WARNING | Identificadores con duplicados |

### Clasificación Semántica

El inspector identifica automáticamente qué representa cada columna:

| Tipo Semántico | Ejemplo de Columna | Confianza Típica |
|---|---|---|
| `identifier` | `customer_id`, `order_id` | 85-95% |
| `monetary` | `salary`, `price`, `budget` | 80% |
| `email` | `email`, `correo` | 90-100% |
| `date`/`datetime` | `created_at`, `birth_date` | 85% |
| `categorical` | `status`, `type`, `category` | 75-80% |
| `boolean` | `is_active`, `has_paid` | 85% |
| `probability` | `confidence`, `sentiment` | 65-75% |
| `name` | `first_name`, `title` | 80-90% |
| `quantity` | `stock`, `count` | 75% |
| `measurement` | `temperature`, `weight` | 80% |

### Data Quality Score

El score inicia en **100 puntos** por tabla y se descuenta según hallazgos:

| Nivel + Categoría | Penalización |
|---|---|
| CRITICAL + Structural | -20 pts |
| CRITICAL + Relational/Consistency | -15 pts |
| CRITICAL + Completeness/Statistical | -10 pts |
| ERROR + Structural | -10 pts |
| ERROR + Relational/Consistency | -8 pts |
| ERROR + Completeness/Statistical | -5 pts |
| WARNING (cualquier categoría) | -2 a -3 pts |
| INFO | 0 pts |

El **score global** es un promedio ponderado por número de filas en cada tabla.

---

## Proveedores de IA

Sistema en cascada: intenta cada proveedor en orden y cae al siguiente si no hay credenciales.

| Prioridad | Proveedor | Modelo por defecto | Free Tier | Variable |
|---|---|---|---|---|
| 1 | 🟠 Amazon Bedrock | Claude 3 Haiku | ✅ Sí | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` |
| 2 | 🟢 NVIDIA NIM | DeepSeek-V4-Pro | ✅ Sí (1000 req/mes) | `NVIDIA_API_KEY` |
| 3 | 🔵 OpenAI API | gpt-4o-mini | ❌ No | `OPENAI_API_KEY` |
| 4 | ⚫ Mock local | Generador determinístico | ✅ Sin clave | *(ninguna)* |

El prompt se construye **dinámicamente** basándose en el esquema detectado, los hallazgos de auditoría y los riesgos identificados. Nunca asume dominio de negocio.

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | Python 3.11+ |
| Conectores | SQLite3, CSV, openpyxl (Excel) |
| Validación | Pydantic v2 |
| Inspección | Introspección de esquema + heurísticas |
| Auditoría | Motor de reglas pluggables |
| IA principal | Amazon Bedrock (Claude 3 Haiku) |
| IA alternativas | NVIDIA NIM (DeepSeek-V4-Pro), OpenAI |
| Frontend | Streamlit |
| Deploy | Streamlit Community Cloud (gratuito) |

---

## Instalación

### Prerrequisitos

- Python 3.11+
- (Opcional) Cuenta de AWS con acceso a Amazon Bedrock

### 1. Clonar el repositorio

```bash
git clone https://github.com/marcanogc/agente-vigia.git
cd agente-vigia
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. (Opcional) Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con las credenciales de tu proveedor de IA preferido:

```env
# Amazon Bedrock (recomendado)
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# O NVIDIA NIM (gratuito)
# NVIDIA_API_KEY=nvapi-...
# NVIDIA_MODEL_ID=deepseek-ai/deepseek-v4-pro
```

> **Sin API keys:** La aplicación funciona completamente sin credenciales usando el generador local de reportes.

### 4. Lanzar el dashboard

```bash
python run_demo.py
```

O directamente:

```bash
streamlit run vigia/dashboard/app.py
```

El dashboard estará disponible en `http://localhost:8501`.

---

## Uso Paso a Paso

### 1. Cargar datos

Al abrir el dashboard, selecciona tu fuente de datos:

- **Archivo:** Arrastra o selecciona un archivo SQLite, CSV o Excel
- **Demo:** Haz clic en "Cargar Demo" para ver las capacidades con datos de ejemplo
- **Base de datos remota:** (Futuro) Conecta directamente a PostgreSQL o MySQL

### 2. Análisis automático

Una vez cargados los datos, Agente Vigía ejecuta automáticamente:

1. **Descubrimiento de esquema** — Tablas, columnas, tipos, PKs, FKs
2. **Clasificación semántica** — Identifica qué representa cada columna
3. **Inferencia de relaciones** — Detecta FKs no declaradas
4. **Auditoría de calidad** — Evalúa 11 reglas sobre cada tabla
5. **Cálculo de score** — Data Quality Score global y por tabla
6. **Detección de riesgos** — Identifica anomalías y problemas críticos
7. **Generación de insights** — Reporte ejecutivo via IA

### 3. Explorar resultados

El dashboard presenta 5 tabs:

| Tab | Contenido |
|---|---|
| 📂 **Datos** | Explorador de datos crudos con estadísticas rápidas |
| 🗂️ **Esquema** | Tablas, columnas, tipos, relaciones declaradas e inferidas |
| 🔍 **Auditoría** | Hallazgos, score por tabla, filtros por nivel y categoría |
| 💡 **Insights** | Riesgos priorizados, reporte ejecutivo IA, exportación |
| 📋 **Resumen** | Vista consolidada con métricas clave |

### 4. Exportar

Desde el tab de Insights puedes descargar:
- **Reporte completo** en Markdown (`.md`)
- **Hallazgos** en CSV para análisis externo

---

## Ejemplos de Uso

### Auditar una base SQLite de producción

```python
from vigia.connectors import SQLiteConnector, ConnectionConfig, ConnectorType
from vigia.inspector import SchemaInspector
from vigia.audit.generic_engine import GenericAuditEngine
from vigia.insight.generic_engine import GenericInsightEngine

# Conectar
config = ConnectionConfig(connector_type=ConnectorType.SQLITE, file_path="mi_app.db")
connector = SQLiteConnector(config)
connector.connect()

# Inspeccionar
inspector = SchemaInspector(connector)
schema = inspector.inspect()
print(f"Tablas: {schema.total_tables}, Columnas: {schema.total_columns}")

# Auditar
audit = GenericAuditEngine(connector, schema)
report = audit.run_audit()
print(f"Score: {report.global_quality_score}/100, Hallazgos: {report.total_findings}")

# Insights
engine = GenericInsightEngine(connector, schema, report)
result = engine.run_analysis()
print(result.report_markdown)

connector.disconnect()
```

### Auditar un archivo CSV

```python
from vigia.connectors import CSVConnector, ConnectionConfig, ConnectorType
from vigia.inspector import SchemaInspector
from vigia.audit.generic_engine import GenericAuditEngine

config = ConnectionConfig(
    connector_type=ConnectorType.CSV,
    file_path="ventas_2024.csv",
    options={"encoding": "utf-8", "delimiter": ","}
)

with CSVConnector(config) as connector:
    schema = SchemaInspector(connector).inspect()
    report = GenericAuditEngine(connector, schema).run_audit()
    
    print(f"Score: {report.global_quality_score}/100")
    for finding in report.findings:
        print(f"  [{finding.level.value}] {finding.table}.{finding.column}: {finding.message}")
```

### Agregar una regla de auditoría personalizada

```python
from vigia.audit.rules import AuditRule, AuditCategory
from vigia.models.schema_models import AuditFinding, AuditLevel

class MyCustomRule(AuditRule):
    @property
    def name(self): return "my_custom_rule"
    
    @property
    def category(self): return AuditCategory.CONSISTENCY
    
    @property
    def description(self): return "Mi regla personalizada"
    
    def evaluate(self, connector, table_info, schema_metadata):
        findings = []
        # Tu lógica aquí
        return findings

# Usar con el motor
from vigia.audit.rules import DEFAULT_RULES
custom_rules = DEFAULT_RULES + [MyCustomRule()]
engine = GenericAuditEngine(connector, schema, rules=custom_rules)
```

---

## Configurar Amazon Bedrock

### Paso 1: Habilitar el modelo en la consola de AWS

1. Ir a [AWS Console → Amazon Bedrock → Model Access](https://console.aws.amazon.com/bedrock/home#/modelaccess)
2. Seleccionar **Anthropic → Claude 3 Haiku** y solicitar acceso (gratuito, aprobación inmediata)

### Paso 2: Crear usuario IAM con permisos mínimos

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
    }
  ]
}
```

### Paso 3: Configurar credenciales

En IAM → Usuario → Security Credentials → Create Access Key. Copia las credenciales en tu `.env`.

---

## Configurar NVIDIA NIM (Gratuito)

1. Ir a [build.nvidia.com](https://build.nvidia.com)
2. Crear cuenta (no requiere tarjeta de crédito)
3. Hacer clic en "Get API Key" → copiar clave `nvapi-...`
4. Agregar a `.env`:

```env
NVIDIA_API_KEY=nvapi-tu_clave_aqui
NVIDIA_MODEL_ID=deepseek-ai/deepseek-v4-pro
```

---

## Deploy en Streamlit Community Cloud

1. Sube el repositorio a GitHub (`.env` está en `.gitignore`).
2. Ve a [share.streamlit.io](https://share.streamlit.io) y conecta tu cuenta.
3. Selecciona el repositorio y como archivo principal: `vigia/dashboard/app.py`.
4. En **Settings → Secrets**, agrega tus credenciales.
5. Deploy.

---

## Arquitectura del Sistema

```
vigia/
├── connectors/             # Capa de conectores (patrón Strategy)
│   ├── base.py             #   ABC BaseConnector + dataclasses
│   ├── sqlite_connector.py #   Conector SQLite
│   └── csv_connector.py    #   Conector CSV/Excel
├── inspector/              # Introspección de esquemas
│   └── schema_inspector.py #   Descubrimiento + clasificación semántica + inferencia
├── audit/                  # Motor de auditoría
│   ├── generic_engine.py   #   Motor genérico con scoring
│   ├── rules.py            #   11 reglas pluggables (extensible)
│   └── engine.py           #   Motor legacy (demo)
├── insight/                # Generación de insights
│   ├── generic_engine.py   #   Motor genérico sin asumir dominio
│   ├── llm_dynamic.py      #   LLM con prompt dinámico
│   ├── engine.py           #   Motor legacy (demo)
│   └── llm.py              #   LLM legacy
├── dashboard/              # Frontend Streamlit
│   ├── app.py              #   Dashboard dinámico principal
│   ├── app_legacy.py       #   Dashboard legacy (demo)
│   └── pages/              #   Páginas modulares
│       ├── upload.py       #     Carga de datos
│       ├── data_view.py    #     Explorador de datos
│       ├── schema_view.py  #     Visualización de esquema
│       ├── audit_view.py   #     Resultados de auditoría
│       └── insights_view.py#     Insights y exportación
├── database/               # Base de datos demo
│   ├── connection.py       #   Conexión SQLite
│   ├── schema.sql          #   Esquema demo
│   └── seed.py             #   Datos de ejemplo (válidos + corruptos)
├── models/                 # Modelos de datos
│   ├── schema_models.py    #   Modelos del sistema universal
│   └── validation.py       #   Modelos Pydantic (demo)
└── __init__.py
```

### Principios de diseño

- **SOLID:** Cada componente tiene una responsabilidad única. Las reglas son extensibles sin modificar el motor.
- **Strategy Pattern:** Los conectores son intercambiables vía la interfaz `BaseConnector`.
- **Open/Closed:** Se agregan nuevas reglas y conectores sin tocar código existente.
- **Zero-config:** El sistema funciona sin configuración manual — descubre todo automáticamente.
- **Fail-safe:** Cuando no puede inferir algo, lo reporta como limitación en lugar de asumir.

---

## Tests

```bash
pytest tests/ -v
```

La suite cubre: validación de modelos Pydantic, motor de auditoría (estructural, relacional, semántica), motor de insights (sanitización, detección de riesgos, generación de reporte), seed de datos, conexión a base de datos y estructura de imports.

---

## Roadmap

- [ ] Conector PostgreSQL
- [ ] Conector MySQL
- [ ] Detección de correlaciones entre columnas
- [ ] Visualización de grafos de relaciones
- [ ] Historial de auditorías (tracking temporal)
- [ ] API REST para integración con pipelines
- [ ] Reglas de auditoría configurables desde la UI
- [ ] Soporte para archivos Parquet
- [ ] Conector para APIs REST

---

## Licencia

Este proyecto está licenciado bajo la **Apache License 2.0**.

```
Copyright (c) 2026 Gabriel Marcano
```

### Qué permite esta licencia:

| Permiso | |
|---|---|
| ✅ Uso comercial | Puedes usar el software en productos comerciales |
| ✅ Modificación | Puedes modificar el código fuente |
| ✅ Distribución | Puedes redistribuir el software |
| ✅ Uso privado | Puedes usar el software de forma privada |
| ✅ Sublicenciamiento | Puedes otorgar sublicencias |
| ✅ Grant de patentes | Los contribuyentes otorgan licencia de patentes |

### Condiciones:

| Condición | |
|---|---|
| 📋 Incluir licencia y copyright | Debes incluir una copia de la licencia en redistribuciones |
| 📋 Documentar cambios | Los archivos modificados deben indicar que fueron cambiados |
| 📋 Preservar atribución | Mantener notices de copyright y atribución |

### Limitaciones:

| Limitación | |
|---|---|
| ❌ Sin garantía | El software se proporciona "AS IS" |
| ❌ Sin responsabilidad | Los autores no son responsables por daños |
| ❌ Sin uso de marcas | No otorga permiso para usar nombres/marcas del autor |

Consulta el archivo [LICENSE](LICENSE) para el texto completo.

---

<p align="center">
  <strong>Agente Vigía v2.0.0</strong><br/>
  Hackathon IA Masivo Online AWS por Código Facilito 2026
</p>
