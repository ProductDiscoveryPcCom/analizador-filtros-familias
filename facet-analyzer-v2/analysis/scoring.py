"""
Sistema de puntuación de facetas - v2.3
Genérico y configurable para cualquier categoría de productos
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ScoringWeights:
    """Pesos configurables para el scoring"""
    demand_weight: float = 0.35
    performance_weight: float = 0.25
    coverage_weight: float = 0.20
    opportunity_weight: float = 0.20
    
    def validate(self) -> bool:
        """Valida que los pesos sumen 1.0"""
        total = (self.demand_weight + self.performance_weight + 
                 self.coverage_weight + self.opportunity_weight)
        return abs(total - 1.0) < 0.01
    
    def normalize(self):
        """Normaliza los pesos para que sumen 1.0"""
        total = (self.demand_weight + self.performance_weight + 
                 self.coverage_weight + self.opportunity_weight)
        if total > 0:
            self.demand_weight /= total
            self.performance_weight /= total
            self.coverage_weight /= total
            self.opportunity_weight /= total


@dataclass
class FacetScore:
    """Puntuación detallada de una faceta"""
    facet_name: str
    
    # Scores parciales (0-100)
    demand_score: float = 0.0
    performance_score: float = 0.0
    coverage_score: float = 0.0
    opportunity_score: float = 0.0
    
    # Score final
    total_score: float = 0.0
    
    # Datos de soporte
    demand_value: int = 0
    traffic_value: int = 0
    urls_200: int = 0
    urls_404: int = 0
    in_wrapper: bool = False
    
    # Clasificación
    tier: str = ""  # 'S', 'A', 'B', 'C', 'D'
    recommendation: str = ""
    confidence: str = "medium"
    
    def to_dict(self) -> Dict:
        return {
            'facet_name': self.facet_name,
            'demand_score': round(self.demand_score, 1),
            'performance_score': round(self.performance_score, 1),
            'coverage_score': round(self.coverage_score, 1),
            'opportunity_score': round(self.opportunity_score, 1),
            'total_score': round(self.total_score, 1),
            'demand_value': self.demand_value,
            'traffic_value': self.traffic_value,
            'urls_200': self.urls_200,
            'urls_404': self.urls_404,
            'in_wrapper': self.in_wrapper,
            'tier': self.tier,
            'recommendation': self.recommendation,
            'confidence': self.confidence,
        }


class FacetScorer:
    """
    Sistema de puntuación de facetas genérico
    """
    
    # Umbrales por defecto
    DEFAULT_THRESHOLDS = {
        'demand_very_high': 100000,
        'demand_high': 50000,
        'demand_medium': 10000,
        'demand_low': 1000,
        'traffic_very_high': 50000,
        'traffic_high': 10000,
        'traffic_medium': 1000,
        'traffic_low': 100,
        'urls_many': 100,
        'urls_some': 10,
        'urls_few': 1,
    }
    
    # Tiers de clasificación
    TIERS = {
        90: 'S',
        75: 'A',
        50: 'B',
        25: 'C',
        0: 'D',
    }
    
    def __init__(self, 
                 weights: ScoringWeights = None,
                 thresholds: Dict = None):
        """
        Args:
            weights: Pesos para el scoring
            thresholds: Umbrales personalizados
        """
        self.weights = weights or ScoringWeights()
        self.weights.normalize()
        
        self.thresholds = {**self.DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)
    
    def _score_demand(self, demand: int) -> float:
        """Calcula score de demanda (0-100)"""
        if demand >= self.thresholds['demand_very_high']:
            return 100
        elif demand >= self.thresholds['demand_high']:
            return 80
        elif demand >= self.thresholds['demand_medium']:
            return 60
        elif demand >= self.thresholds['demand_low']:
            return 40
        elif demand > 0:
            return 20
        return 0
    
    def _score_performance(self, traffic: int, urls_200: int) -> float:
        """Calcula score de rendimiento (0-100)"""
        # Score por tráfico (70%)
        if traffic >= self.thresholds['traffic_very_high']:
            traffic_score = 100
        elif traffic >= self.thresholds['traffic_high']:
            traffic_score = 80
        elif traffic >= self.thresholds['traffic_medium']:
            traffic_score = 60
        elif traffic >= self.thresholds['traffic_low']:
            traffic_score = 40
        elif traffic > 0:
            traffic_score = 20
        else:
            traffic_score = 0
        
        # Score por URLs activas (30%)
        if urls_200 >= self.thresholds['urls_many']:
            urls_score = 100
        elif urls_200 >= self.thresholds['urls_some']:
            urls_score = 70
        elif urls_200 >= self.thresholds['urls_few']:
            urls_score = 40
        else:
            urls_score = 0
        
        return traffic_score * 0.7 + urls_score * 0.3
    
    def _score_coverage(self, urls_200: int, urls_404: int, in_wrapper: bool) -> float:
        """Calcula score de cobertura (0-100)"""
        total_urls = urls_200 + urls_404
        
        if total_urls == 0:
            return 0
        
        # Ratio de URLs activas (50%)
        active_ratio = urls_200 / total_urls
        ratio_score = active_ratio * 100
        
        # Bonus por estar en wrapper (30%)
        wrapper_score = 100 if in_wrapper else 0
        
        # Penalización por URLs 404 (20%)
        if urls_404 == 0:
            penalty_score = 100
        elif urls_404 < 10:
            penalty_score = 80
        elif urls_404 < 50:
            penalty_score = 50
        else:
            penalty_score = 20
        
        return ratio_score * 0.5 + wrapper_score * 0.3 + penalty_score * 0.2
    
    def _score_opportunity(self, demand: int, traffic: int, in_wrapper: bool, urls_200: int) -> float:
        """Calcula score de oportunidad (0-100)"""
        # Alta demanda + bajo tráfico = alta oportunidad
        if demand == 0:
            return 0
        
        # Potencial sin explotar
        if traffic == 0 and demand > self.thresholds['demand_medium']:
            base_score = 90
        elif traffic < demand * 0.1:  # Menos del 10% capturado
            base_score = 80
        elif traffic < demand * 0.3:
            base_score = 60
        elif traffic < demand * 0.5:
            base_score = 40
        else:
            base_score = 20
        
        # Bonus si no está en wrapper (oportunidad de añadir)
        if not in_wrapper and urls_200 > 0:
            base_score = min(100, base_score + 20)
        
        return base_score
    
    def _get_tier(self, score: float) -> str:
        """Determina el tier basado en el score"""
        for threshold, tier in sorted(self.TIERS.items(), reverse=True):
            if score >= threshold:
                return tier
        return 'D'
    
    def _generate_recommendation(self, score: FacetScore) -> str:
        """Genera recomendación basada en el análisis"""
        if score.tier == 'S':
            if score.in_wrapper:
                return "⭐ Faceta estrella. Mantener posición prominente en seoFilterWrapper."
            else:
                return "🚀 Alta prioridad: Añadir inmediatamente a seoFilterWrapper."
        
        elif score.tier == 'A':
            if score.in_wrapper:
                return "✅ Buen rendimiento. Optimizar contenido de páginas de filtro."
            else:
                return "📈 Añadir a seoFilterWrapper para capturar demanda existente."
        
        elif score.tier == 'B':
            if score.urls_200 > 0:
                return "🔍 Monitorear rendimiento. Evaluar inclusión si mejora demanda."
            else:
                return "⚠️ Hay demanda pero sin URLs. Evaluar crear páginas de filtro."
        
        elif score.tier == 'C':
            if score.urls_404 > score.urls_200:
                return "🔴 Muchas URLs eliminadas. Evaluar si recuperar o redireccionar."
            else:
                return "📊 Baja prioridad. Monitorear tendencias de demanda."
        
        else:  # D
            return "⏸️ Sin acción requerida. Demanda insuficiente."
    
    def _determine_confidence(self, demand: int, traffic: int, urls_200: int) -> str:
        """Determina nivel de confianza del análisis"""
        sources = 0
        
        if demand > self.thresholds['demand_low']:
            sources += 1
        if traffic > self.thresholds['traffic_low']:
            sources += 1
        if urls_200 > 0:
            sources += 1
        
        if sources >= 3:
            return 'high'
        elif sources >= 2:
            return 'medium'
        return 'low'
    
    def score_facet(self, 
                    facet_name: str,
                    demand: int = 0,
                    traffic: int = 0,
                    urls_200: int = 0,
                    urls_404: int = 0,
                    in_wrapper: bool = False) -> FacetScore:
        """
        Calcula puntuación completa de una faceta
        """
        # Scores parciales
        demand_score = self._score_demand(demand)
        performance_score = self._score_performance(traffic, urls_200)
        coverage_score = self._score_coverage(urls_200, urls_404, in_wrapper)
        opportunity_score = self._score_opportunity(demand, traffic, in_wrapper, urls_200)
        
        # Score total ponderado
        total_score = (
            demand_score * self.weights.demand_weight +
            performance_score * self.weights.performance_weight +
            coverage_score * self.weights.coverage_weight +
            opportunity_score * self.weights.opportunity_weight
        )
        
        # Crear objeto de score
        score = FacetScore(
            facet_name=facet_name,
            demand_score=demand_score,
            performance_score=performance_score,
            coverage_score=coverage_score,
            opportunity_score=opportunity_score,
            total_score=total_score,
            demand_value=demand,
            traffic_value=traffic,
            urls_200=urls_200,
            urls_404=urls_404,
            in_wrapper=in_wrapper,
            tier=self._get_tier(total_score),
            confidence=self._determine_confidence(demand, traffic, urls_200),
        )
        
        score.recommendation = self._generate_recommendation(score)
        
        return score
    
    def score_multiple(self, facets_data: List[Dict]) -> List[FacetScore]:
        """
        Calcula scores para múltiples facetas
        
        Args:
            facets_data: Lista de dicts con keys:
                - facet_name, demand, traffic, urls_200, urls_404, in_wrapper
        """
        scores = []
        for data in facets_data:
            score = self.score_facet(
                facet_name=data.get('facet_name', 'Unknown'),
                demand=data.get('demand', 0),
                traffic=data.get('traffic', 0),
                urls_200=data.get('urls_200', 0),
                urls_404=data.get('urls_404', 0),
                in_wrapper=data.get('in_wrapper', False),
            )
            scores.append(score)
        
        return sorted(scores, key=lambda x: x.total_score, reverse=True)
    
    def to_dataframe(self, scores: List[FacetScore]) -> pd.DataFrame:
        """Convierte lista de scores a DataFrame"""
        data = [s.to_dict() for s in scores]
        return pd.DataFrame(data)
    
    def get_tier_summary(self, scores: List[FacetScore]) -> Dict[str, int]:
        """Resumen de facetas por tier"""
        summary = {'S': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for score in scores:
            if score.tier in summary:
                summary[score.tier] += 1
        return summary
    
    def get_priority_actions(self, scores: List[FacetScore], top_n: int = 10) -> List[Dict]:
        """Obtiene las acciones prioritarias"""
        actions = []
        
        # Priorizar: alto score + no en wrapper + URLs disponibles
        priority_scores = sorted(
            [s for s in scores if not s.in_wrapper and s.urls_200 > 0],
            key=lambda x: x.total_score,
            reverse=True
        )
        
        for score in priority_scores[:top_n]:
            actions.append({
                'facet': score.facet_name,
                'action': 'ADD_TO_WRAPPER',
                'priority': score.tier,
                'score': score.total_score,
                'potential_traffic': score.demand_value,
                'urls_available': score.urls_200,
            })
        
        return actions


def calculate_indexation_score(
    gsc_clicks: int = 0,
    gsc_impressions: int = 0,
    gsc_position: float = 0,
    adobe_traffic: int = 0,
    demand_volume: int = 0,
    urls_count: int = 0
) -> Tuple[float, str, str]:
    """
    Calcula score de indexación para una faceta/URL
    
    Returns:
        (score, decision, explanation)
    """
    score = 0
    factors = []
    
    # GSC Clicks (40 puntos max)
    if gsc_clicks >= 1000:
        score += 40
        factors.append(f"Clicks altos ({gsc_clicks:,})")
    elif gsc_clicks >= 500:
        score += 30
        factors.append(f"Clicks medios ({gsc_clicks:,})")
    elif gsc_clicks >= 100:
        score += 20
        factors.append(f"Clicks bajos ({gsc_clicks:,})")
    elif gsc_clicks > 0:
        score += 10
        factors.append(f"Algunos clicks ({gsc_clicks:,})")
    
    # GSC Position (20 puntos max)
    if 0 < gsc_position <= 10:
        score += 20
        factors.append(f"Posición top 10 ({gsc_position:.1f})")
    elif gsc_position <= 20:
        score += 15
        factors.append(f"Posición top 20 ({gsc_position:.1f})")
    elif gsc_position <= 50:
        score += 10
        factors.append(f"Posición media ({gsc_position:.1f})")
    
    # Adobe Traffic (20 puntos max)
    if adobe_traffic >= 5000:
        score += 20
        factors.append(f"Tráfico alto ({adobe_traffic:,})")
    elif adobe_traffic >= 1000:
        score += 15
        factors.append(f"Tráfico medio ({adobe_traffic:,})")
    elif adobe_traffic >= 100:
        score += 10
        factors.append(f"Tráfico bajo ({adobe_traffic:,})")
    
    # Demand Volume (20 puntos max)
    if demand_volume >= 50000:
        score += 20
        factors.append(f"Demanda muy alta ({demand_volume:,})")
    elif demand_volume >= 10000:
        score += 15
        factors.append(f"Demanda alta ({demand_volume:,})")
    elif demand_volume >= 1000:
        score += 10
        factors.append(f"Demanda media ({demand_volume:,})")
    
    # Decisión
    if score >= 70:
        decision = "INDEX"
        explanation = f"Alta prioridad de indexación. Factores: {', '.join(factors)}"
    elif score >= 40:
        decision = "EVALUATE"
        explanation = f"Evaluar caso por caso. Factores: {', '.join(factors)}"
    else:
        decision = "NOINDEX"
        explanation = f"Baja prioridad. Factores: {', '.join(factors) if factors else 'Sin datos significativos'}"
    
    return score, decision, explanation


def generate_scoring_report(scores: List[FacetScore], family_name: str = "") -> str:
    """Genera reporte de scoring en markdown"""
    scorer = FacetScorer()
    tier_summary = scorer.get_tier_summary(scores)
    
    report = f"""
# Reporte de Scoring de Facetas
{'## ' + family_name if family_name else ''}

## Resumen por Tier

| Tier | Cantidad | Descripción |
|------|----------|-------------|
| S | {tier_summary['S']} | Facetas estrella - Máxima prioridad |
| A | {tier_summary['A']} | Alto rendimiento - Mantener |
| B | {tier_summary['B']} | Rendimiento medio - Optimizar |
| C | {tier_summary['C']} | Bajo rendimiento - Evaluar |
| D | {tier_summary['D']} | Sin prioridad - Monitorear |

## Top 10 Facetas por Score

| Faceta | Score | Tier | Demanda | Tráfico | URLs | En Wrapper |
|--------|-------|------|---------|---------|------|------------|
"""
    
    for score in sorted(scores, key=lambda x: x.total_score, reverse=True)[:10]:
        wrapper_icon = "✅" if score.in_wrapper else "❌"
        report += f"| {score.facet_name} | {score.total_score:.0f} | {score.tier} | {score.demand_value:,} | {score.traffic_value:,} | {score.urls_200} | {wrapper_icon} |\n"
    
    report += """
## Acciones Prioritarias

"""
    priority_actions = scorer.get_priority_actions(scores, 5)
    for i, action in enumerate(priority_actions, 1):
        report += f"{i}. **{action['facet']}** (Tier {action['priority']}): Añadir a seoFilterWrapper - {action['urls_available']} URLs disponibles, potencial {action['potential_traffic']:,} búsquedas\n"
    
    return report
