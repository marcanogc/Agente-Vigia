# 🛡️ Agente Vigía — Agente Autónomo de Integridad Decisional

> *"La mayoría de los agentes IA analizan datos. Agente Vigía primero determina si esos datos merecen ser analizados."*

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red?logo=streamlit)](https://streamlit.io)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock%20Claude%203-orange?logo=amazonaws)](https://aws.amazon.com/bedrock/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Hackathon:** IA Masivo Online AWS por Código Facilito 2026 — Reto 3: Agentes Especializados

---

## El Problema

Las organizaciones sufren una **Brecha Contexto-Datos**: los sistemas estructurados (ERP, Jira)
reportan un estado saludable del proyecto, mientras las comunicaciones no estructuradas (Slack, Teams,
Email) revelan bloqueos ocultos y riesgos críticos.

Los agentes de IA tradicionales razonan sobre **toda** la información disponible sin validar su
integridad, generando insights basados en datos corruptos o contradictorios.

**Agente Vigía resuelve esto** auditando la calidad e integridad de los datos *antes* de generar
cualquier recomendación.

---

## ¿Qué hace Agente Vigía?

```
Datos crudos → Auditoría → Solo datos validados → Detección de riesgos → IA (Bedrock) → Insights
```

1. **Ingesta datos** de proyectos, tareas y comunicaciones (simulando ERP/Jira/Slack).
2. **Audita cada registro** contra reglas estructurales, relacionales y semánticas con Pydantic.
3. **Bloquea los registros corruptos** antes del análisis (presupuestos negativos, fechas inválidas,
   IDs nulos, tareas huérfanas).
4. **Detecta riesgos operacionales** en los datos validados: tareas bloqueadas estancadas,
   sentimiento negativo en comunicaciones, deadlines en riesgo.
5. **Genera un reporte ejecutivo** usando Amazon Bedrock (Claude 3 Haiku/Sonnet) con insights
   trazables a IDs específicos de registros.
6. **Muestra todo** en un dashboard Streamlit interactivo con 4 tabs.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMAS DE ORIGEN                           │
│         ERP / Jira / Slack  →  SQLite (datos crudos)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUDIT ENGINE                                 │
│  ✦ Validación estructural (Pydantic)                           │
│  ✦ Validación relacional (integridad referencial)              │
│  ✦ Validación semántica (brechas contexto-datos)               │
│  → Output: quality_score + audit_logs                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Solo datos validados
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INSIGHT ENGINE                                │
│  ✦ Detección de tareas bloqueadas y estancadas                 │
│  ✦ Análisis de sentimiento en comunicaciones                   │
│  ✦ Riesgo de deadlines próximos                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM LAYER (en cascada)                       │
│  1. 🟠 Amazon Bedrock — Claude 3 Haiku/Sonnet  (principal)     │
│  2. 🟢 OpenAI / API compatible               (alternativo)     │
│  3. ⚫ Generador local determinístico         (sin API key)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               AGENTE VIGÍA — STREAMLIT DASHBOARD               │
│  Tab 1: Datos Crudos  │  Tab 2: Auditoría                      │
│  Tab 3: Insights      │  Tab 4: Acciones                        │
└─────────────────────────────────────────────────────────────────┘
```

### Servicios AWS utilizados

| Servicio | Uso |
|---|---|
| **Amazon Bedrock** | Motor LLM principal — Claude 3 Haiku para generación de reportes ejecutivos |
| **Streamlit Community Cloud** | Hosting gratuito del dashboard web |

---

## Proveedores de IA soportados

Agente Vigía usa un sistema en cascada: intenta cada proveedor en orden y cae al siguiente si no hay credenciales.

| Prioridad | Proveedor | Modelo por defecto | Free Tier | Variable |
|---|---|---|---|---|
| 1 | 🟠 Amazon Bedrock | Claude 3 Haiku | ✅ Sí | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` |
| 2 | 🟢 NVIDIA NIM | DeepSeek-V4-Pro | ✅ Sí (1000 req/mes) | `NVIDIA_API_KEY` |
| 3 | 🔵 OpenAI API | gpt-4o-mini | ❌ No | `OPENAI_API_KEY` |
| 4 | ⚫ Mock local | Generador determinístico | ✅ Sin clave | *(ninguna)* |

### ¿Por qué DeepSeek-V4-Pro en NVIDIA NIM?

- **1.6 billones de parámetros** con arquitectura MoE (49B activos por inferencia)
- Contexto de **1 millón de tokens** — ideal para análisis de grandes volúmenes de datos
- Arquitectura híbrida CSA+HCA que reduce FLOPs en un 73% vs. modelos densos equivalentes
- Disponible gratis en [build.nvidia.com](https://build.nvidia.com) — no requiere tarjeta de crédito

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | Python 3.11+ |
| Base de datos | SQLite |
| Validación | Pydantic v2 |
| IA principal | Amazon Bedrock (Claude 3 Haiku) |
| IA alternativa | OpenAI API compatible |
| Frontend | Streamlit |
| Deploy | Streamlit Community Cloud (gratuito) |

---

## Instalación Local

### Prerrequisitos

- Python 3.11+
- Cuenta de AWS con acceso a Amazon Bedrock habilitado (Free Tier disponible)

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

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

> **Sin AWS:** La aplicación funciona sin credenciales usando el generador local de reportes.

### 4. Inicializar la base de datos y lanzar el dashboard

```bash
python run_demo.py
```

O directamente:

```bash
streamlit run sentinel/dashboard/app.py
```

El dashboard estará disponible en `http://localhost:8501`.

---

## Configurar Amazon Bedrock

### Paso 1: Habilitar el modelo en la consola de AWS

1. Ir a [AWS Console → Amazon Bedrock → Model Access](https://console.aws.amazon.com/bedrock/home#/modelaccess)
2. Seleccionar **Anthropic → Claude 3 Haiku** y solicitar acceso (gratuito, aprobación inmediata)

### Paso 2: Crear usuario IAM con permisos mínimos

Política IAM recomendada:

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

### Paso 3: Obtener credenciales

En IAM → Usuario → Security Credentials → Create Access Key.
Copia el Access Key ID y Secret Access Key en tu `.env`.

---

## Configurar NVIDIA NIM (DeepSeek-V4-Pro)

Alternativa gratuita de alta capacidad analítica. No requiere tarjeta de crédito.

### Paso 1: Obtener API Key

1. Ir a [build.nvidia.com](https://build.nvidia.com)
2. Crear cuenta o iniciar sesión
3. En cualquier página de modelo, hacer clic en **"Get API Key"**
4. Copiar la clave (empieza con `nvapi-...`)

### Paso 2: Configurar en `.env`

```env
NVIDIA_API_KEY=nvapi-tu_clave_aqui
NVIDIA_MODEL_ID=deepseek-ai/deepseek-v4-pro
```

### Modelos disponibles recomendados

| Modelo | Parámetros | Contexto | Ideal para |
|---|---|---|---|
| `deepseek-ai/deepseek-v4-pro` | 1.6T (MoE, 49B activos) | 1M tokens | Análisis profundo de datos |
| `deepseek-ai/deepseek-v4-flash` | 284B (MoE, 13B activos) | 1M tokens | Velocidad + eficiencia |
| `meta/llama-3.3-70b-instruct` | 70B | 128K tokens | Uso general |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | 253B | 128K tokens | Razonamiento avanzado |

> **Nota:** Si tanto Bedrock como NVIDIA están configurados, Bedrock tiene prioridad.
> Para usar NVIDIA primero, omite las variables `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`.

---

## Deploy en Streamlit Community Cloud (Gratis)

1. Sube el repositorio a GitHub (asegúrate de que `.env` está en `.gitignore`).
2. Ve a [share.streamlit.io](https://share.streamlit.io) y conecta tu cuenta de GitHub.
3. Selecciona el repositorio y como archivo principal: `sentinel/dashboard/app.py`.
4. En **Settings → Secrets**, agrega el proveedor que prefieras:

```toml
# Opción A — Amazon Bedrock
AWS_ACCESS_KEY_ID = "tu_access_key"
AWS_SECRET_ACCESS_KEY = "tu_secret_key"
AWS_DEFAULT_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Opción B — NVIDIA NIM
# NVIDIA_API_KEY = "nvapi-..."
# NVIDIA_MODEL_ID = "deepseek-ai/deepseek-v4-pro"
```

5. Deploy. Tu app estará en `https://tu-usuario-agente-vigia.streamlit.app`.

---

## Estructura del Proyecto

```
sentinel/
├── audit/
│   └── engine.py          # Motor de auditoría (structural/relational/semantic)
├── dashboard/
│   └── app.py             # Dashboard Streamlit
├── database/
│   ├── connection.py      # Conexión SQLite
│   ├── schema.sql         # Esquema de BD
│   └── seed.py            # Datos de demo (válidos + corruptos)
├── insight/
│   ├── engine.py          # Detección de riesgos operacionales
│   └── llm.py             # Capa LLM: Bedrock → OpenAI → Mock
├── models/
│   └── validation.py      # Modelos Pydantic
└── __init__.py

tests/                     # Suite de pruebas pytest
.env.example               # Plantilla de variables de entorno
.streamlit/
│   ├── config.toml        # Tema y configuración de Streamlit
│   └── secrets.toml.example
requirements.txt
run_demo.py                # Script de inicio rápido
```

---

## Tests

```bash
pytest tests/ -v
```

---

## Demo

🔗 **Demo en vivo:** [agente-vigia-demo.streamlit.app](https://agente-vigia-nzwktli8ysnpbqr6s9xhkz.streamlit.app/) *(reemplaza con tu URL)*

📹 **Video de presentación:** *(enlace al video del hackathon)*

---

## Reglas de Auditoría

| Tipo | Regla | Penalización |
|---|---|---|
| Structural | Presupuesto negativo | -15 pts |
| Structural | Fecha inválida | -15 pts |
| Structural | ID nulo/faltante | -15 pts |
| Relational | Tarea huérfana (proyecto inexistente) | -10 pts |
| Relational | Comunicación sin proyecto | -5 pts |
| Semantic | Proyecto COMPLETED con tareas incompletas | -5 pts |
| Semantic | Proyecto ACTIVE con comunicaciones muy negativas | -5 pts |
| Semantic | Tarea BLOCKED estancada +30 días | -5 pts |

---

## Licencia

MIT © 2026 — Desarrollado para el Hackathon IA Masivo Online AWS por Código Facilito.

---

*🛡️ Agente Vigía — Porque las mejores decisiones se toman sobre datos en los que puedes confiar.*
