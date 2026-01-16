"""
Módulo de exportación de resultados
Genera reportes y archivos CSV para implementación
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import io


def export_authority_leaks(authority_result) -> str:
    """
    Exporta fugas de autoridad a CSV string
    
    Args:
        authority_result: AuthorityAnalysisResult con top_leaks
    
    Returns:
        CSV como string
    """
    if not authority_result or not authority_result.top_leaks:
        return "url,trafico,enlaces,tipo,severidad,recomendacion\n"
    
    data = []
    for leak in authority_result.top_leaks:
        data.append({
            'url': leak.url,
            'trafico_seo': leak.traffic_seo,
            'enlaces_wrapper': leak.wrapper_links,
            'tipo_fuga': leak.leak_type,
            'severidad': leak.severity,
            'recomendacion': leak.recommendation,
        })
    
    df = pd.DataFrame(data)
    return df.to_csv(index=False, encoding='utf-8-sig')


def export_facet_analysis(facet_results: List[Dict]) -> str:
    """
    Exporta análisis de facetas a CSV string
    
    Args:
        facet_results: Lista de dicts con 'breakdown' (ScoreBreakdown) y métricas
    
    Returns:
        CSV como string
    """
    if not facet_results:
        return "faceta,score,urls_200,urls_404,demanda,trafico,accion,recomendacion,confianza\n"
    
    data = []
    for r in facet_results:
        breakdown = r.get('breakdown')
        if breakdown:
            data.append({
                'faceta': breakdown.facet_name,
                'score': breakdown.total_score,
                'urls_200': r.get('urls_200', 0),
                'urls_404': r.get('urls_404', 0),
                'demanda': r.get('demand', 0),
                'trafico': r.get('traffic', 0),
                'accion': breakdown.action_type,
                'recomendacion': breakdown.recommendation,
                'confianza': breakdown.confidence
            })
    
    df = pd.DataFrame(data)
    return df.to_csv(index=False, encoding='utf-8-sig')


def generate_implementation_report(
    authority_result,
    facet_results: List[Dict] = None
) -> str:
    """
    Genera reporte de implementación en Markdown
    
    Args:
        authority_result: Resultado del análisis de autoridad
        facet_results: Lista de resultados de facetas (nuevo formato con breakdown)
    
    Returns:
        Reporte en Markdown
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    report = f"""# Reporte de Implementación - seoFilterWrapper

**Generado:** {timestamp}

---

## Resumen Ejecutivo

Este reporte contiene las recomendaciones priorizadas para optimizar la arquitectura
de enlaces internos del hub de productos.

---

## 1. Fugas de Autoridad

"""
    
    if authority_result and authority_result.top_leaks:
        total_leaks = len(authority_result.top_leaks)
        total_traffic = sum(l.traffic_seo for l in authority_result.top_leaks)
        
        report += f"""### Métricas Clave

| Métrica | Valor |
|---------|-------|
| Total fugas detectadas | {total_leaks} |
| Tráfico afectado | {total_traffic:,} visitas |

### Top 10 Prioridades

| URL | Tráfico | Tipo | Severidad |
|-----|---------|------|-----------|
"""
        for leak in authority_result.top_leaks[:10]:
            path = leak.url.replace('https://www.pccomponentes.com/smartphone-moviles', '') or '/'
            report += f"| `{path}` | {leak.traffic_seo:,} | {leak.leak_type} | {leak.severity} |\n"
        
        report += "\n### Acciones Recomendadas\n\n"
        for i, leak in enumerate(authority_result.top_leaks[:5], 1):
            report += f"{i}. **{leak.url.split('/')[-1] or 'homepage'}**: {leak.recommendation}\n"
    else:
        report += "*Análisis de autoridad no ejecutado*\n"
    
    report += """
---

## 2. Oportunidades de Facetas

"""
    
    if facet_results:
        high_priority = [r for r in facet_results if r['breakdown'].total_score >= 60]
        medium_priority = [r for r in facet_results if 30 <= r['breakdown'].total_score < 60]
        low_priority = [r for r in facet_results if r['breakdown'].total_score < 30]
        
        report += f"""### Métricas Clave

| Prioridad | Cantidad |
|-----------|----------|
| 🔴 Alta (Score ≥60) | {len(high_priority)} |
| 🟡 Media (Score 30-59) | {len(medium_priority)} |
| ⚪ Baja (Score <30) | {len(low_priority)} |

### Alta Prioridad

| Faceta | Score | URLs Activas | Demanda | Acción |
|--------|-------|--------------|---------|--------|
"""
        for r in high_priority:
            b = r['breakdown']
            report += f"| {b.facet_name} | {b.total_score:.0f}/100 | {r['urls_200']} | {r['demand']:,} | {b.action_type} |\n"
        
        if medium_priority:
            report += """
### Media Prioridad

| Faceta | Score | URLs Activas | Demanda | Acción |
|--------|-------|--------------|---------|--------|
"""
            for r in medium_priority:
                b = r['breakdown']
                report += f"| {b.facet_name} | {b.total_score:.0f}/100 | {r['urls_200']} | {r['demand']:,} | {b.action_type} |\n"
        
        # Detalles de recomendaciones
        report += "\n### Detalles de Recomendaciones\n\n"
        for r in facet_results[:5]:
            b = r['breakdown']
            report += f"**{b.facet_name}** (Score: {b.total_score:.0f})\n"
            report += f"- {b.recommendation}\n"
            report += f"- Confianza: {b.confidence}\n\n"
    else:
        report += "*Análisis de facetas no ejecutado*\n"
    
    report += """
---

## 3. Plan de Implementación

### Fase 1 - Inmediato (Semana 1-2)
- Implementar seoFilterWrapper en páginas de alta prioridad sin distribución
- Foco en URLs con tráfico >1000 visitas

### Fase 2 - Corto Plazo (Semana 3-4)
- Añadir enlaces a facetas de alta demanda no representadas en wrapper
- Revisar facetas con URLs eliminadas pero alta demanda (evaluar recrear)

### Fase 3 - Optimización (Mes 2)
- Revisar y optimizar distribución de enlaces existentes
- Eliminar enlaces a URLs con bajo rendimiento

---

## 4. Notas de Implementación

1. **Validación**: Todas las recomendaciones están basadas en datos reales verificados
2. **HTTP Check**: Verificar estado HTTP 200 antes de implementar cambios
3. **Deploy**: Cambios en seoFilterWrapper requieren deploy de frontend
4. **Monitoreo**: Revisar GSC 2-4 semanas post-implementación
5. **Iteración**: Re-ejecutar análisis mensualmente

---

## 5. Criterios de Scoring

El score de oportunidad (0-100) se calcula considerando:

| Factor | Peso |
|--------|------|
| Demanda (Adobe/SEMrush) | 40% |
| URLs activas disponibles | 30% |
| Ausencia en wrapper | 15% |
| Tráfico actual | 15% |

**Penalizaciones**: 
- URLs sin páginas activas: -30% al score final
- Bonus si hay alta demanda en URLs eliminadas (indica potencial de recrear)

---

*Generado automáticamente por Facet Architecture Analyzer v2.1*
"""
    
    return report


def export_wrapper_changes(changes: List[Dict]) -> str:
    """
    Exporta cambios propuestos para seoFilterWrapper a CSV
    
    Args:
        changes: Lista de cambios propuestos
    
    Returns:
        CSV como string
    """
    if not changes:
        return "accion,url_destino,anchor_text,prioridad,justificacion\n"
    
    data = []
    for change in changes:
        data.append({
            'accion': change.get('action', 'add'),
            'url_destino': change.get('target_url', ''),
            'anchor_text': change.get('anchor_text', ''),
            'prioridad': change.get('priority', 'medium'),
            'justificacion': change.get('justification', ''),
        })
    
    df = pd.DataFrame(data)
    return df.to_csv(index=False, encoding='utf-8-sig')
