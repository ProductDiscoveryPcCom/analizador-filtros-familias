"""
Sistema de Scoring Mejorado para Facetas
Permite configuración personalizada de ponderaciones
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import streamlit as st


@dataclass
class ScoringWeights:
    """Ponderaciones para el cálculo de score"""
    # Demanda (peso total: 40)
    demand_weight: float = 40.0
    demand_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'very_high': 100000,  # 100% del peso
        'high': 50000,        # 75% del peso
        'medium': 10000,      # 50% del peso
        'low': 1000,          # 25% del peso
    })
    
    # URLs activas (peso total: 30)
    urls_weight: float = 30.0
    urls_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'many': 100,          # 100% del peso
        'some': 10,           # 66% del peso
        'few': 1,             # 33% del peso
    })
    
    # Presencia en wrapper (peso total: 15)
    wrapper_weight: float = 15.0
    
    # Tráfico actual (peso total: 15)
    traffic_weight: float = 15.0
    traffic_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'high': 10000,        # 100% del peso
        'medium': 1000,       # 50% del peso
    })
    
    # Penalizaciones
    no_urls_penalty: float = 0.7  # Multiplicador si no hay URLs activas
    eliminated_bonus: float = 0.3  # Bonus para facetas eliminadas con alta demanda (indicar recrear)


@dataclass
class ScoreBreakdown:
    """Desglose detallado del score"""
    facet_name: str
    total_score: float
    
    # Componentes
    demand_score: float
    demand_reason: str
    
    urls_score: float
    urls_reason: str
    
    wrapper_score: float
    wrapper_reason: str
    
    traffic_score: float
    traffic_reason: str
    
    # Penalizaciones/Bonus aplicados
    adjustments: List[str]
    
    # Recomendación final
    action_type: str  # 'link' | 'recreate' | 'maintain' | 'ignore'
    recommendation: str
    confidence: str


class FacetScorer:
    """
    Calculador de scores para facetas con desglose detallado
    """
    
    def __init__(self, weights: ScoringWeights = None):
        self.weights = weights or ScoringWeights()
    
    def calculate_score(self,
                        facet_name: str,
                        urls_200: int,
                        urls_404: int,
                        demand_adobe: int,
                        demand_semrush: int,
                        traffic_seo: int,
                        in_wrapper: bool,
                        wrapper_links: int = 0) -> ScoreBreakdown:
        """
        Calcula el score de una faceta con desglose detallado
        
        Returns:
            ScoreBreakdown con todos los detalles
        """
        total_demand = demand_adobe + demand_semrush
        adjustments = []
        
        # 1. Score de Demanda (0-40)
        demand_score, demand_reason = self._calc_demand_score(total_demand)
        
        # 2. Score de URLs activas (0-30)
        urls_score, urls_reason = self._calc_urls_score(urls_200)
        
        # 3. Score de Wrapper (0-15)
        wrapper_score, wrapper_reason = self._calc_wrapper_score(in_wrapper, wrapper_links, urls_200)
        
        # 4. Score de Tráfico (0-15)
        traffic_score, traffic_reason = self._calc_traffic_score(traffic_seo)
        
        # Calcular total base
        total_base = demand_score + urls_score + wrapper_score + traffic_score
        
        # Aplicar ajustes
        total_adjusted = total_base
        
        # Penalización si no hay URLs activas
        if urls_200 == 0:
            penalty = 1 - self.weights.no_urls_penalty
            total_adjusted = total_base * self.weights.no_urls_penalty
            adjustments.append(f"Penalización -30% por no tener URLs activas")
            
            # Pero si hay alta demanda, indicar que podría recrearse
            if total_demand > self.weights.demand_thresholds['high']:
                bonus = total_adjusted * self.weights.eliminated_bonus
                total_adjusted += bonus
                adjustments.append(f"Bonus +{self.weights.eliminated_bonus*100:.0f}% por alta demanda (evaluar recrear)")
        
        # Determinar tipo de acción
        action_type, recommendation, confidence = self._determine_action(
            urls_200=urls_200,
            urls_404=urls_404,
            total_demand=total_demand,
            in_wrapper=in_wrapper,
            total_score=total_adjusted
        )
        
        return ScoreBreakdown(
            facet_name=facet_name,
            total_score=min(total_adjusted, 100),
            demand_score=demand_score,
            demand_reason=demand_reason,
            urls_score=urls_score,
            urls_reason=urls_reason,
            wrapper_score=wrapper_score,
            wrapper_reason=wrapper_reason,
            traffic_score=traffic_score,
            traffic_reason=traffic_reason,
            adjustments=adjustments,
            action_type=action_type,
            recommendation=recommendation,
            confidence=confidence
        )
    
    def _calc_demand_score(self, demand: int) -> Tuple[float, str]:
        """Calcula score de demanda"""
        w = self.weights
        t = w.demand_thresholds
        
        if demand >= t['very_high']:
            return w.demand_weight, f"Demanda muy alta ({demand:,})"
        elif demand >= t['high']:
            return w.demand_weight * 0.75, f"Demanda alta ({demand:,})"
        elif demand >= t['medium']:
            return w.demand_weight * 0.5, f"Demanda media ({demand:,})"
        elif demand >= t['low']:
            return w.demand_weight * 0.25, f"Demanda baja ({demand:,})"
        else:
            return 0, f"Demanda insuficiente ({demand:,})"
    
    def _calc_urls_score(self, urls_200: int) -> Tuple[float, str]:
        """Calcula score de URLs activas"""
        w = self.weights
        t = w.urls_thresholds
        
        if urls_200 >= t['many']:
            return w.urls_weight, f"Muchas URLs activas ({urls_200})"
        elif urls_200 >= t['some']:
            return w.urls_weight * 0.66, f"Algunas URLs activas ({urls_200})"
        elif urls_200 >= t['few']:
            return w.urls_weight * 0.33, f"Pocas URLs activas ({urls_200})"
        else:
            return 0, f"Sin URLs activas"
    
    def _calc_wrapper_score(self, in_wrapper: bool, wrapper_links: int, urls_200: int) -> Tuple[float, str]:
        """Calcula score de presencia en wrapper"""
        w = self.weights
        
        if urls_200 == 0:
            return 0, "N/A (sin URLs)"
        
        if not in_wrapper:
            return w.wrapper_weight, "No está en wrapper (oportunidad de añadir)"
        elif wrapper_links < 5:
            return w.wrapper_weight * 0.5, f"Presencia baja en wrapper ({wrapper_links} enlaces)"
        else:
            return 0, f"Ya tiene buena presencia ({wrapper_links} enlaces)"
    
    def _calc_traffic_score(self, traffic: int) -> Tuple[float, str]:
        """Calcula score de tráfico"""
        w = self.weights
        t = w.traffic_thresholds
        
        if traffic >= t['high']:
            return w.traffic_weight, f"Tráfico alto ({traffic:,})"
        elif traffic >= t['medium']:
            return w.traffic_weight * 0.5, f"Tráfico medio ({traffic:,})"
        else:
            return 0, f"Tráfico bajo ({traffic:,})"
    
    def _determine_action(self, urls_200: int, urls_404: int, 
                          total_demand: int, in_wrapper: bool,
                          total_score: float) -> Tuple[str, str, str]:
        """Determina la acción recomendada"""
        
        # Caso 1: URLs activas disponibles, no en wrapper
        if urls_200 > 0 and not in_wrapper:
            if total_score >= 60:
                return (
                    'link',
                    f"🔴 ALTA PRIORIDAD: Añadir {min(urls_200, 10)} enlaces a seoFilterWrapper",
                    'HIGH'
                )
            else:
                return (
                    'link',
                    f"🟡 MEDIA PRIORIDAD: Considerar añadir enlaces al wrapper",
                    'MEDIUM'
                )
        
        # Caso 2: URLs activas, ya en wrapper
        if urls_200 > 0 and in_wrapper:
            return (
                'maintain',
                "✅ Mantener: Ya está enlazada. Optimizar si es necesario.",
                'HIGH'
            )
        
        # Caso 3: Sin URLs activas pero con alta demanda
        if urls_200 == 0 and urls_404 > 0 and total_demand > 50000:
            return (
                'recreate',
                f"🟠 EVALUAR: {urls_404} URLs eliminadas con {total_demand:,} demanda. Considerar recrear.",
                'MEDIUM'
            )
        
        # Caso 4: Sin URLs y sin demanda significativa
        if urls_200 == 0 and total_demand < 10000:
            return (
                'ignore',
                "⚪ BAJA PRIORIDAD: Sin URLs activas y demanda insuficiente.",
                'HIGH'
            )
        
        # Caso por defecto
        return (
            'ignore',
            "Requiere análisis adicional",
            'LOW'
        )


def render_scoring_config_ui() -> ScoringWeights:
    """Renderiza UI para configurar ponderaciones de scoring"""
    
    st.subheader("⚖️ Configurar Ponderaciones de Score")
    
    with st.expander("Ajustar pesos del algoritmo de scoring"):
        st.info("""
        Ajusta los pesos según la importancia relativa de cada factor para tu negocio.
        Los pesos deben sumar 100.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            demand_weight = st.slider(
                "Peso: Demanda",
                min_value=0, max_value=60, value=40,
                help="Importancia del volumen de búsqueda y uso de filtros"
            )
            
            urls_weight = st.slider(
                "Peso: URLs Activas",
                min_value=0, max_value=50, value=30,
                help="Importancia de tener URLs disponibles para enlazar"
            )
        
        with col2:
            wrapper_weight = st.slider(
                "Peso: Presencia en Wrapper",
                min_value=0, max_value=30, value=15,
                help="Bonus por no estar ya enlazado"
            )
            
            traffic_weight = st.slider(
                "Peso: Tráfico Actual",
                min_value=0, max_value=30, value=15,
                help="Importancia del tráfico existente"
            )
        
        total_weight = demand_weight + urls_weight + wrapper_weight + traffic_weight
        
        if total_weight != 100:
            st.warning(f"⚠️ Los pesos suman {total_weight}, deberían sumar 100")
        else:
            st.success("✅ Pesos correctos (suman 100)")
        
        st.markdown("---")
        st.markdown("**Umbrales de demanda:**")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            very_high = st.number_input("Muy alta", value=100000, step=10000)
        with col2:
            high = st.number_input("Alta", value=50000, step=5000)
        with col3:
            medium = st.number_input("Media", value=10000, step=1000)
        with col4:
            low = st.number_input("Baja", value=1000, step=100)
        
        return ScoringWeights(
            demand_weight=demand_weight,
            urls_weight=urls_weight,
            wrapper_weight=wrapper_weight,
            traffic_weight=traffic_weight,
            demand_thresholds={
                'very_high': very_high,
                'high': high,
                'medium': medium,
                'low': low
            }
        )
    
    return ScoringWeights()  # Default


def render_score_breakdown_ui(breakdown: ScoreBreakdown):
    """Renderiza desglose visual del score"""
    
    with st.expander(f"📊 Desglose: {breakdown.facet_name} ({breakdown.total_score:.0f}/100)"):
        # Barra de progreso general
        st.progress(breakdown.total_score / 100)
        
        # Componentes
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Demanda**")
            st.progress(breakdown.demand_score / 40)
            st.caption(breakdown.demand_reason)
            
            st.markdown("**URLs Activas**")
            st.progress(breakdown.urls_score / 30)
            st.caption(breakdown.urls_reason)
        
        with col2:
            st.markdown("**Wrapper**")
            st.progress(breakdown.wrapper_score / 15 if breakdown.wrapper_score else 0)
            st.caption(breakdown.wrapper_reason)
            
            st.markdown("**Tráfico**")
            st.progress(breakdown.traffic_score / 15)
            st.caption(breakdown.traffic_reason)
        
        # Ajustes aplicados
        if breakdown.adjustments:
            st.markdown("**Ajustes aplicados:**")
            for adj in breakdown.adjustments:
                st.caption(f"• {adj}")
        
        # Recomendación
        st.markdown("---")
        st.markdown(f"**Recomendación:** {breakdown.recommendation}")
        
        confidence_color = {
            'HIGH': '🟢',
            'MEDIUM': '🟡', 
            'LOW': '🔴'
        }.get(breakdown.confidence, '⚪')
        st.caption(f"{confidence_color} Confianza: {breakdown.confidence}")
