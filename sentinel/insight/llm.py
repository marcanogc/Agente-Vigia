"""
sentinel/insight/llm.py
-----------------------
Motor de generación de reportes con soporte para:
  1. Amazon Bedrock (Claude 3 Haiku / Sonnet) — recomendado
  2. NVIDIA NIM API (DeepSeek-V4-Pro u otros) — alta capacidad analítica
  3. OpenAI / API compatible — alternativo
  4. Generador local determinístico — fallback sin dependencias externas
"""
import os
import json
import requests
from typing import List, Dict


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_insights_report(risks: List[Dict], quality_report: Dict) -> str:
    """
    Genera el reporte ejecutivo de Agente Vigía.
    Orden de prioridad: Bedrock → NVIDIA NIM → OpenAI → Mock local.
    """
    prompt = construct_prompt(risks, quality_report)

    # 1. Intentar Amazon Bedrock
    bedrock_result = _try_bedrock(prompt)
    if bedrock_result:
        return bedrock_result

    # 2. Intentar NVIDIA NIM (DeepSeek-V4-Pro u otro modelo configurado)
    nvidia_result = _try_nvidia(prompt)
    if nvidia_result:
        return nvidia_result

    # 3. Intentar OpenAI / API compatible
    openai_result = _try_openai(prompt)
    if openai_result:
        return openai_result

    # 4. Fallback local determinístico
    return generate_deterministic_mock(risks, quality_report)


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 1: Amazon Bedrock
# ─────────────────────────────────────────────────────────────────────────────

def _try_bedrock(prompt: str) -> str | None:
    """
    Invoca el modelo configurado en Amazon Bedrock usando boto3.
    Requiere: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION.
    El modelo predeterminado es Claude 3 Haiku (económico y rápido).
    """
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-3-haiku-20240307-v1:0"
    )

    # Verificar que boto3 esté disponible
    try:
        import boto3
        from botocore.exceptions import (
            ClientError,
            NoCredentialsError,
            NoRegionError,
        )
    except ImportError:
        return None  # boto3 no instalado

    # Verificar que haya credenciales configuradas
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    # Aceptamos credenciales explícitas O perfil de AWS configurado (~/.aws/credentials)
    has_explicit_creds = bool(access_key and secret_key and
                               access_key != "your_access_key_id_here")

    try:
        if has_explicit_creds:
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            # Usar perfil/rol de IAM configurado localmente o en la instancia
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region,
            )

        system_prompt = (
            "Eres Agente Vigía, un agente senior de inteligencia empresarial. "
            "Escribe reportes ejecutivos profesionales y concisos en español. "
            "Siempre referencia IDs específicos de registros validados en tus insights y recomendaciones. "
            "Usa formato Markdown con secciones claras."
        )

        # Formato para modelos Anthropic Claude en Bedrock (Messages API)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        })

        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")

    except NoCredentialsError:
        print("[Agente Vigía] Bedrock: No se encontraron credenciales de AWS. Usando fallback.")
    except NoRegionError:
        print("[Agente Vigía] Bedrock: No se especificó región de AWS. Usando fallback.")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"[Agente Vigía] Bedrock ClientError ({error_code}): {e}. Usando fallback.")
    except Exception as e:
        print(f"[Agente Vigía] Bedrock error inesperado: {e}. Usando fallback.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 2: NVIDIA NIM API (DeepSeek-V4-Pro, Llama, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def _try_nvidia(prompt: str) -> str | None:
    """
    Invoca modelos de NVIDIA NIM via su API compatible con OpenAI.
    Endpoint: https://integrate.api.nvidia.com/v1
    Requiere: NVIDIA_API_KEY
    Modelo por defecto: deepseek-ai/deepseek-v4-pro (1.6T params, MoE, 1M ctx)
    Obtén tu API key gratuita en: https://build.nvidia.com
    """
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        return None

    model = os.environ.get(
        "NVIDIA_MODEL_ID",
        "deepseek-ai/deepseek-v4-pro"
    )

    system_prompt = (
        "Eres Agente Vigía, un agente senior de inteligencia empresarial con capacidades "
        "avanzadas de análisis de datos. Escribe reportes ejecutivos profesionales y concisos "
        "en español. Siempre referencia IDs específicos de registros validados en tus insights "
        "y recomendaciones. Usa formato Markdown con secciones claras."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 1500,
            # Desactiva el modo "thinking" extendido para respuestas más rápidas
            "extra_body": {"chat_template_kwargs": {"thinking": False}},
        }
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(
                f"[Agente Vigía] NVIDIA NIM Error (HTTP {response.status_code}): "
                f"{response.text[:200]}. Usando fallback."
            )
    except Exception as e:
        print(f"[Agente Vigía] NVIDIA NIM exception: {e}. Usando fallback.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 3: OpenAI / API compatible
# ─────────────────────────────────────────────────────────────────────────────

def _try_openai(prompt: str) -> str | None:
    """Intenta generar el reporte usando una API compatible con OpenAI (Proveedor 3)."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    api_url = os.environ.get(
        "OPENAI_API_BASE",
        "https://api.openai.com/v1/chat/completions"
    )
    model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres Agente Vigía, un agente senior de inteligencia empresarial. "
                        "Escribe reportes ejecutivos en español con formato Markdown. "
                        "Referencia IDs específicos de registros validados."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"[Agente Vigía] OpenAI API Error (HTTP {response.status_code}). Usando fallback.")
    except Exception as e:
        print(f"[Agente Vigía] OpenAI exception: {e}. Usando fallback.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del prompt
# ─────────────────────────────────────────────────────────────────────────────

def construct_prompt(risks: List[Dict], quality_report: Dict) -> str:
    """Construye el prompt estructurado para el LLM."""
    return f"""Analiza los siguientes datos verificados y genera un reporte ejecutivo completo en español con formato Markdown.

**Puntuación de Calidad de Datos:** {quality_report.get('quality_score')}/100
**Resumen de Calidad:** {json.dumps(quality_report.get('summary'), ensure_ascii=False)}
**Problemas Detectados:** {json.dumps(quality_report.get('logs'), ensure_ascii=False)}

**Riesgos Operacionales Detectados:**
{json.dumps(risks, indent=2, ensure_ascii=False)}

**Instrucciones para el reporte:**
1. Estructura tu respuesta en cuatro secciones claras:
   - ## 1. Resumen Ejecutivo
   - ## 2. Alerta de Integridad de Datos (solo si el score < 70)
   - ## 3. Insights Clave de Negocio
   - ## 4. Plan de Acciones Recomendadas
2. En "Insights Clave", explica los bloqueos operacionales referenciando IDs específicos de proyectos/tareas/comunicaciones.
3. En "Acciones Recomendadas", incluye pasos accionables con responsables específicos o IDs de entidades.
4. Mantén un tono ejecutivo, directo y profesional.
5. Si el score de calidad es bajo, advierte sobre el riesgo de tomar decisiones con datos corruptos.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 3: Generador local determinístico (sin dependencias externas)
# ─────────────────────────────────────────────────────────────────────────────

def generate_deterministic_mock(risks: List[Dict], quality_report: Dict) -> str:
    """
    Generador de reporte local determinístico de alta calidad.
    Se activa cuando no hay credenciales de AWS ni OpenAI configuradas.
    """
    quality_score = quality_report.get("quality_score", 100.0)
    summary = quality_report.get("summary", {})
    failed_count = summary.get("failed_records", 0)
    total_records = summary.get("total_records", 0)

    stagnant_tasks = [r for r in risks if r["risk_type"] == "Stagnant Blocked Task"]
    sentiment_risks = [r for r in risks if r["risk_type"] == "Negative Communication Sentiment"]
    deadline_risks = [r for r in risks if r["risk_type"] == "Close Deadline Risk"]
    all_high = [r for r in risks if r.get("priority") == "HIGH"]

    report = [
        "# Reporte de Integridad Decisional — Agente Vigía",
        "",
        "> *Generado por el motor local de Agente Vigía. Para análisis potenciado por IA, configura Amazon Bedrock o una API OpenAI compatible.*",
        "",
    ]

    # 1. Resumen Ejecutivo
    report.append("## 1. Resumen Ejecutivo")
    report.append(
        f"Agente Vigía auditó **{total_records} registros** de los sistemas operacionales de la empresa. "
        f"Se detectaron **{failed_count} errores críticos estructurales** que fueron bloqueados antes del análisis. "
        f"El índice de confianza de datos es de **{quality_score:.1f}/100**. "
    )
    if len(all_high) > 0:
        report.append(
            f"Se identificaron **{len(all_high)} riesgos de prioridad ALTA** que requieren atención inmediata."
        )
    else:
        report.append("No se detectaron riesgos operacionales críticos en los datos validados.")
    report.append("")

    # 2. Alerta de Integridad
    if quality_score < 70.0:
        report.append("## 2. ⚠️ Alerta de Integridad de Datos")
        report.append(
            f"> **Score de Confianza: {quality_score:.1f}/100 — DATOS COMPROMETIDOS**\n"
            f"> Agente Vigía bloqueó **{failed_count} registros corruptos** antes del análisis. "
            f"Tomar decisiones sobre los datos sin procesar representa un riesgo operacional alto. "
            f"Se requiere corrección de datos de origen antes de la próxima auditoría."
        )
        report.append("")

    # 3. Key Insights
    report.append("## 3. Insights Clave de Negocio")
    insight_idx = 1

    if stagnant_tasks:
        t = stagnant_tasks[0]
        report.append(
            f"**Insight {insight_idx} — Bloqueador Operacional:** {t['description']} "
            f"Este bloqueo representa un riesgo directo para el proyecto **{t['project_id']}**."
        )
        insight_idx += 1

    if sentiment_risks:
        s = sentiment_risks[0]
        report.append(
            f"**Insight {insight_idx} — Brecha Contexto-Datos:** {s['description']} "
            f"Existe una contradicción entre los indicadores estructurados y la realidad operacional reportada."
        )
        insight_idx += 1

    if deadline_risks:
        d = deadline_risks[0]
        report.append(
            f"**Insight {insight_idx} — Riesgo de Deadline:** {d['description']}"
        )
        insight_idx += 1

    if insight_idx == 1:
        report.append(
            "Los datos validados no muestran riesgos operacionales críticos activos. "
            "Los proyectos en curso mantienen indicadores saludables."
        )
    report.append("")

    # 4. Plan de Acciones
    report.append("## 4. Plan de Acciones Recomendadas")
    action_idx = 1

    if stagnant_tasks:
        t = stagnant_tasks[0]
        report.append(
            f"{action_idx}. **Desbloquear tarea {t['evidence_reference']}** en proyecto **{t['project_id']}**: "
            f"Asignar un responsable para resolver el bloqueo de inmediato y actualizar el estado."
        )
        action_idx += 1

    if sentiment_risks:
        s = sentiment_risks[0]
        report.append(
            f"{action_idx}. **Investigar comunicación {s['evidence_reference']}** en proyecto **{s['project_id']}**: "
            f"Convocar reunión de emergencia con el equipo técnico para alinear el estado formal con la realidad reportada."
        )
        action_idx += 1

    if deadline_risks:
        d = deadline_risks[0]
        report.append(
            f"{action_idx}. **Revisión de deadline en proyecto {d['project_id']}**: "
            f"Evaluar con el equipo si el plazo es alcanzable o si se requiere una extensión formal."
        )
        action_idx += 1

    if failed_count > 0:
        report.append(
            f"{action_idx}. **Corregir errores de datos de origen**: "
            f"El equipo de Data/PMO debe rectificar los {failed_count} registros corruptos "
            f"(presupuestos negativos, fechas inválidas, IDs nulos) en los sistemas de origen para restaurar el Score de Confianza."
        )

    return "\n".join(report)
