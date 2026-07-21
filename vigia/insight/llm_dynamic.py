"""
vigia.insight.llm_dynamic
------------------------------
Motor de generación de reportes con prompt dinámico.
Construye el prompt basándose en el contexto del esquema y los hallazgos
de auditoría, sin asumir ningún dominio de negocio específico.

Proveedores (en cascada):
  1. Amazon Bedrock (Claude 3 Haiku / Sonnet)
  2. NVIDIA NIM (DeepSeek-V4-Pro u otros)
  3. OpenAI / API compatible
  4. Generador local determinístico
"""

from __future__ import annotations

import json
import os
import requests
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada principal
# ─────────────────────────────────────────────────────────────────────────────


def generate_dynamic_report(context: dict[str, Any]) -> tuple[str, str]:
    """
    Genera el reporte ejecutivo dinámico de Agente Vigía.
    
    Args:
        context: Diccionario con toda la información del análisis
                 (generado por GenericInsightEngine._build_prompt_context).
    
    Returns:
        Tupla (report_markdown, provider_used).
    """
    prompt = _build_dynamic_prompt(context)
    system_prompt = _build_system_prompt()

    # 1. Intentar Amazon Bedrock
    result = _try_bedrock(system_prompt, prompt)
    if result:
        return result, "bedrock"

    # 2. Intentar NVIDIA NIM
    result = _try_nvidia(system_prompt, prompt)
    if result:
        return result, "nvidia"

    # 3. Intentar OpenAI
    result = _try_openai(system_prompt, prompt)
    if result:
        return result, "openai"

    # 4. Fallback local
    return _generate_deterministic_report(context), "mock"


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del prompt dinámico
# ─────────────────────────────────────────────────────────────────────────────


def _build_system_prompt() -> str:
    """System prompt genérico que no asume dominio."""
    return (
        "Eres Agente Vigía, un agente senior de inteligencia de datos empresariales. "
        "Tu rol es analizar resultados de auditoría de calidad de datos y generar reportes "
        "ejecutivos profesionales en español con formato Markdown.\n\n"
        "Reglas estrictas:\n"
        "1. NUNCA inventes información que no esté en los datos proporcionados.\n"
        "2. Si no puedes inferir algo con certeza, dilo explícitamente.\n"
        "3. Referencia siempre tablas y columnas específicas en tus observaciones.\n"
        "4. No asumas el dominio de negocio — basa tus insights solo en patrones de datos.\n"
        "5. Usa un tono ejecutivo, directo y profesional.\n"
        "6. Estructura el reporte con secciones claras usando headers Markdown.\n"
    )


def _build_dynamic_prompt(context: dict[str, Any]) -> str:
    """Construye el prompt completo adaptado al esquema analizado."""
    global_score = context.get("global_score", 100.0)
    total_tables = context.get("total_tables", 0)
    total_rows = context.get("total_rows", 0)
    total_findings = context.get("total_findings", 0)
    critical = context.get("critical_findings", 0)
    errors = context.get("error_findings", 0)
    warnings = context.get("warning_findings", 0)

    prompt_parts = []

    # Contexto del esquema
    prompt_parts.append("## CONTEXTO: Esquema Analizado\n")
    prompt_parts.append(context.get("schema_summary", "No disponible"))
    prompt_parts.append("")

    # Resumen de calidad
    prompt_parts.append("## CALIDAD DE DATOS\n")
    prompt_parts.append(f"**Score Global: {global_score:.1f}/100**")
    prompt_parts.append(f"- Tablas auditadas: {total_tables}")
    prompt_parts.append(f"- Filas totales: {total_rows:,}")
    prompt_parts.append(f"- Hallazgos totales: {total_findings} ({critical} CRITICAL, {errors} ERROR, {warnings} WARNING)")
    prompt_parts.append("")
    prompt_parts.append("Calidad por tabla:")
    prompt_parts.append(context.get("quality_summary", ""))
    prompt_parts.append("")

    # Hallazgos principales
    top_findings = context.get("top_findings", [])
    if top_findings:
        prompt_parts.append("## HALLAZGOS PRINCIPALES\n")
        for f in top_findings[:15]:
            prompt_parts.append(
                f"- [{f['level']}][{f['category']}] {f['table']}.{f.get('column', '*')}: {f['message']}"
            )
        prompt_parts.append("")

    # Riesgos
    risks = context.get("risks", [])
    if risks:
        prompt_parts.append("## RIESGOS DETECTADOS\n")
        for r in risks[:10]:
            prompt_parts.append(
                f"- [{r['priority']}] {r['risk_type']} en '{r['table']}'"
                f"{('.' + r['column']) if r.get('column') else ''}: {r['description']}"
            )
        prompt_parts.append("")

    # Limitaciones
    limitations = context.get("limitations", [])
    if limitations:
        prompt_parts.append("## LIMITACIONES DEL ANÁLISIS\n")
        for lim in limitations:
            prompt_parts.append(f"- {lim}")
        prompt_parts.append("")

    # Instrucciones para el reporte
    prompt_parts.append("## INSTRUCCIONES PARA EL REPORTE\n")
    prompt_parts.append("Genera un reporte ejecutivo completo en español con estas secciones:")
    prompt_parts.append("")
    prompt_parts.append("### 1. Resumen Ejecutivo")
    prompt_parts.append("Párrafo conciso del estado general de calidad de datos.")
    prompt_parts.append("")

    if global_score < 70:
        prompt_parts.append("### 2. Alerta de Integridad de Datos")
        prompt_parts.append("Advertencia sobre el riesgo de usar estos datos para decisiones.")
        prompt_parts.append("")

    prompt_parts.append("### 3. Hallazgos Clave")
    prompt_parts.append("Los problemas más importantes encontrados, referenciando tablas y columnas específicas.")
    prompt_parts.append("")
    prompt_parts.append("### 4. Riesgos y Anomalías")
    prompt_parts.append("Riesgos operacionales detectados con su prioridad.")
    prompt_parts.append("")
    prompt_parts.append("### 5. Recomendaciones Priorizadas")
    prompt_parts.append("Plan de acciones concretas ordenadas por impacto, referenciando entidades específicas.")
    prompt_parts.append("")

    if limitations:
        prompt_parts.append("### 6. Limitaciones")
        prompt_parts.append("Lo que el sistema no pudo determinar con certeza.")

    return "\n".join(prompt_parts)


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 1: Amazon Bedrock
# ─────────────────────────────────────────────────────────────────────────────


def _try_bedrock(system_prompt: str, user_prompt: str) -> str | None:
    """Invoca Amazon Bedrock (Claude 3)."""
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError
    except ImportError:
        return None

    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    has_explicit_creds = bool(
        access_key and secret_key and access_key != "your_access_key_id_here"
    )

    try:
        if has_explicit_creds:
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            client = boto3.client(service_name="bedrock-runtime", region_name=region)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
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

    except (NoCredentialsError, NoRegionError):
        pass
    except ClientError as e:
        print(f"[Agente Vigía] Bedrock ClientError: {e}")
    except Exception as e:
        print(f"[Agente Vigía] Bedrock error: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 2: NVIDIA NIM
# ─────────────────────────────────────────────────────────────────────────────


def _try_nvidia(system_prompt: str, user_prompt: str) -> str | None:
    """Invoca NVIDIA NIM API."""
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        return None

    model = os.environ.get("NVIDIA_MODEL_ID", "deepseek-ai/deepseek-v4-pro")

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 2000,
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
            print(f"[Agente Vigía] NVIDIA NIM Error (HTTP {response.status_code})")
    except Exception as e:
        print(f"[Agente Vigía] NVIDIA NIM exception: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Proveedor 3: OpenAI
# ─────────────────────────────────────────────────────────────────────────────


def _try_openai(system_prompt: str, user_prompt: str) -> str | None:
    """Invoca OpenAI o API compatible."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    api_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1/chat/completions")
    model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"[Agente Vigía] OpenAI Error (HTTP {response.status_code})")
    except Exception as e:
        print(f"[Agente Vigía] OpenAI exception: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Generador local determinístico
# ─────────────────────────────────────────────────────────────────────────────


def _generate_deterministic_report(context: dict[str, Any]) -> str:
    """
    Genera un reporte local sin LLM, basado en los datos del contexto.
    Funciona sin ninguna API key configurada.
    """
    global_score = context.get("global_score", 100.0)
    total_tables = context.get("total_tables", 0)
    total_rows = context.get("total_rows", 0)
    total_findings = context.get("total_findings", 0)
    critical = context.get("critical_findings", 0)
    errors = context.get("error_findings", 0)
    warnings = context.get("warning_findings", 0)
    risks = context.get("risks", [])
    table_scores = context.get("table_scores", [])
    top_findings = context.get("top_findings", [])
    limitations = context.get("limitations", [])

    report = []

    # Encabezado
    report.append("# Reporte de Integridad de Datos — Agente Vigía")
    report.append("")
    report.append(
        "> *Generado por el motor local de Agente Vigía. "
        "Para análisis potenciado por IA, configura Amazon Bedrock, NVIDIA NIM o OpenAI.*"
    )
    report.append("")

    # 1. Resumen Ejecutivo
    report.append("## 1. Resumen Ejecutivo")
    report.append("")

    # Determinar estado general
    if global_score >= 80:
        status_text = "Los datos presentan buena calidad general."
    elif global_score >= 50:
        status_text = "Los datos tienen problemas de calidad que requieren atención."
    else:
        status_text = "Los datos tienen calidad comprometida. Se requiere acción inmediata."

    report.append(
        f"Agente Vigía auditó **{total_tables} tablas** con un total de **{total_rows:,} registros**. "
        f"Se detectaron **{total_findings} hallazgos** de calidad "
        f"({critical} críticos, {errors} errores, {warnings} advertencias). "
        f"{status_text}"
    )
    report.append("")
    report.append(f"**Score Global de Confianza: {global_score:.1f}/100**")
    report.append("")

    # 2. Alerta de Integridad (solo si score bajo)
    if global_score < 70:
        report.append("## 2. Alerta de Integridad de Datos")
        report.append("")
        report.append(
            f"> **Score de Confianza: {global_score:.1f}/100 — "
            f"{'DATOS COMPROMETIDOS' if global_score < 50 else 'PRECAUCION'}**"
        )
        report.append(">")
        report.append(
            f"> Se detectaron {critical + errors} problemas graves. "
            "Tomar decisiones basadas en estos datos sin corrección previa "
            "representa un riesgo operacional significativo."
        )
        report.append("")

    # 3. Hallazgos Clave
    report.append("## 3. Hallazgos Clave")
    report.append("")

    if top_findings:
        # Agrupar por tabla
        tables_with_issues = {}
        for f in top_findings[:10]:
            table = f["table"]
            if table not in tables_with_issues:
                tables_with_issues[table] = []
            tables_with_issues[table].append(f)

        for table, findings in tables_with_issues.items():
            table_score_info = next((t for t in table_scores if t["table"] == table), None)
            score_str = f" (Score: {table_score_info['score']:.1f}/100)" if table_score_info else ""
            report.append(f"### Tabla: `{table}`{score_str}")
            report.append("")
            for f in findings:
                icon = "🚨" if f["level"] == "CRITICAL" else "❌" if f["level"] == "ERROR" else "⚠️"
                col_str = f"`.{f['column']}`" if f.get("column") else ""
                report.append(f"- {icon} **[{f['level']}]** {col_str} {f['message']}")
            report.append("")
    else:
        report.append("No se detectaron hallazgos significativos. Los datos están en buen estado.")
        report.append("")

    # 4. Riesgos y Anomalías
    report.append("## 4. Riesgos y Anomalías")
    report.append("")

    if risks:
        for i, risk in enumerate(risks[:8], 1):
            priority_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                risk["priority"], "⚪"
            )
            report.append(
                f"{i}. {priority_icon} **[{risk['priority']}] {risk['risk_type']}** "
                f"— `{risk['table']}`{('.' + risk['column']) if risk.get('column') else ''}"
            )
            report.append(f"   {risk['description']}")
            if risk.get("recommendation"):
                report.append(f"   *Recomendación: {risk['recommendation']}*")
            report.append("")
    else:
        report.append("No se detectaron riesgos operacionales significativos.")
        report.append("")

    # 5. Recomendaciones Priorizadas
    report.append("## 5. Recomendaciones Priorizadas")
    report.append("")

    recommendations = []

    # Generar recomendaciones basadas en los problemas encontrados
    if critical > 0:
        recommendations.append(
            "**Inmediato:** Corregir los hallazgos CRITICAL antes de usar los datos para cualquier análisis o decisión."
        )

    # Tablas con peor score
    bad_tables = [t for t in table_scores if t["score"] < 60]
    if bad_tables:
        bad_names = ", ".join(f"`{t['table']}`" for t in sorted(bad_tables, key=lambda x: x["score"])[:3])
        recommendations.append(
            f"**Alta prioridad:** Las tablas {bad_names} requieren limpieza de datos urgente."
        )

    # Recomendaciones de los riesgos
    for risk in risks[:3]:
        if risk.get("recommendation"):
            recommendations.append(f"**{risk['priority']}:** {risk['recommendation']}")

    if not recommendations:
        recommendations.append("Los datos están en buen estado. Mantener los procesos actuales de validación.")

    for i, rec in enumerate(recommendations, 1):
        report.append(f"{i}. {rec}")
    report.append("")

    # 6. Limitaciones
    if limitations:
        report.append("## 6. Limitaciones del Análisis")
        report.append("")
        for lim in limitations:
            report.append(f"- {lim}")
        report.append("")

    # Calidad por tabla
    report.append("---")
    report.append("")
    report.append("## Anexo: Score por Tabla")
    report.append("")
    report.append("| Tabla | Score | Filas | Hallazgos | Estado |")
    report.append("|-------|-------|-------|-----------|--------|")
    for t in sorted(table_scores, key=lambda x: x["score"]):
        status = "✅ OK" if t["score"] >= 80 else "⚠️ Precaución" if t["score"] >= 50 else "🚨 Crítico"
        report.append(f"| `{t['table']}` | {t['score']:.1f} | {t['rows']:,} | {t['findings']} | {status} |")
    report.append("")

    return "\n".join(report)
