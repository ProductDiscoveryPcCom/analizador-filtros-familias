"""
Sistema de Scoring para Facetas - v2.2
Permite configurar pesos y calcular puntuaciones
Genérico para cualquier categoría de productos
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
# Streamlit es opcional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


@dataclass
class ScoringWeights:
    """Pesos configurables para el scoring"""
    demand_semrush: float = 0.15      # Volumen de búsqueda SEMrush
    demand_kp: float = 0.15           # Volumen Google Keyword Planner
    traffic_gsc: float = 0.15         # Clics de GSC
    traffic_adobe: float = 0.10       # Visitas Adobe Analytics
    demand_filters: float = 0.20      # Uso de filtros en site
    commercial_intent: float = 0.10   # Intención comercial (SEMrush)
    longtail_coverage: float = 0.05   # Cobertura de long-tail
    revenue_potential: float = 0.10   # Potencial de revenue (Adobe)
    
    def __post_init__(self):
        """Valida que los pesos sumen 1"""
        total = (self.demand_semrush + self.demand_kp + self.traffic_gsc + 
                 self.traffic_adobe + self.demand_filters + self.commercial_intent +
                 self.longtail_coverage + self.revenue_potential)
        if abs(total - 1.0) > 0.01:
            # Normalizar
            factor = 1.0 / total
            self.demand_semrush *= factor
            self.demand_kp *= factor
            self.traffic_gsc *= factor
            self.traffic_adobe *= factor
            self.demand_filters *= factor
            self.commercial_intent *= factor
            self.longtail_coverage *= factor
            self.revenue_potential *= factor
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'demand_semrush': self.demand_semrush,
            'demand_kp': self.demand_kp,
            'traffic_gsc': self.traffic_gsc,
            'traffic_adobe': self.traffic_adobe,
            'demand_filters': self.demand_filters,
            'commercial_intent': self.commercial_intent,
            'longtail_coverage': self.longtail_coverage,
            'revenue_potential': self.revenue_potential,
        }


@dataclass
class ScoreBreakdown:
    """Desglose del score de una faceta"""
    facet_name: str
    total_score: float
    components: Dict[str, float] = field(default_factory=dict)
    raw_values: Dict[str, float] = field(default_factory=dict)
    confidence: str = 'low'
    data_sources_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'facet_name': self.facet_name,
            'total_score': self.total_score,
            'components': self.components,
            'raw_values': self.raw_values,
            'confidence': self.confidence,
            'data_sources_count': self.data_sources_count,
        }


class FacetScorer:
    """Calcula scores de facetas basándose en múltiples fuentes"""
    
    # Umbrales para normalización (se pueden ajustar por categoría)
    DEFAULT_THRESHOLDS = {
        'demand_very_high': 100000,
        'demand_high': 50000,
        'demand_medium': 10000,
        'demand_low': 1000,
        'traffic_very_high': 50000,
        'traffic_high': 10000,
        'traffic_medium': 1000,
        'traffic_low': 100,
    }
    
    def __init__(self, 
                 weights: ScoringWeights = None,
                 thresholds: Dict[str, int] = None):
        """
        Args:
            weights: Pesos para cada componente
            thresholds: Umbrales para normalización
        """
        self.weights = weights or ScoringWeights()
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
    
    def _normalize_demand(self, value: float) -> float:
        """Normaliza un valor de demanda a 0-100"""
        if value >= self.thresholds['demand_very_high']:
            return 100
        elif value >= self.thresholds['demand_high']:
            return 70 + 30 * (value - self.thresholds['demand_high']) / (self.thresholds['demand_very_high'] - self.thresholds['demand_high'])
        elif value >= self.thresholds['demand_medium']:
            return 40 + 30 * (value - self.thresholds['demand_medium']) / (self.thresholds['demand_high'] - self.thresholds['demand_medium'])
        elif value >= self.thresholds['demand_low']:
            return 10 + 30 * (value - self.thresholds['demand_low']) / (self.thresholds['demand_medium'] - self.thresholds['demand_low'])
        else:
            return 10 * value / max(self.thresholds['demand_low'], 1)
    
    def _normalize_traffic(self, value: float) -> float:
        """Normaliza un valor de tráfico a 0-100"""
        if value >= self.thresholds['traffic_very_high']:
            return 100
        elif value >= self.thresholds['traffic_high']:
            return 70 + 30 * (value - self.thresholds['traffic_high']) / (self.thresholds['traffic_very_high'] - self.thresholds['traffic_high'])
        elif value >= self.thresholds['traffic_medium']:
            return 40 + 30 * (value - self.thresholds['traffic_medium']) / (self.thresholds['traffic_high'] - self.thresholds['traffic_medium'])
        elif value >= self.thresholds['traffic_low']:
            return 10 + 30 * (value - self.thresholds['traffic_low']) / (self.thresholds['traffic_medium'] - self.thresholds['traffic_low'])
        else:
            return 10 * value / max(self.thresholds['traffic_low'], 1)
    
    def _normalize_intent(self, intent: str) -> float:
        """Normaliza intención comercial a 0-100"""
        intent_scores = {
            'transactional': 100,
            'commercial': 80,
            'informational': 40,
            'navigational': 60,
        }
        if isinstance(intent, str):
            intent_lower = intent.lower().strip()
            # Manejar intents combinados como "C, I"
            if ',' in intent_lower:
                intents = [i.strip() for i in intent_lower.split(',')]
                scores = []
                for i in intents:
                    if i.startswith('c'):
                        scores.append(80)
                    elif i.startswith('t'):
                        scores.append(100)
                    elif i.startswith('i'):
                        scores.append(40)
                    elif i.startswith('n'):
                        scores.append(60)
                return max(scores) if scores else 50
            
            for key, score in intent_scores.items():
                if intent_lower.startswith(key[0]):
                    return score
        return 50  # Default
    
    def score_facet(self, 
                    facet_name: str,
                    demand_semrush: float = 0,
                    demand_kp: float = 0,
                    traffic_gsc: float = 0,
                    traffic_adobe: float = 0,
                    demand_filters: float = 0,
                    intent: str = '',
                    longtail_count: int = 0,
                    revenue: float = 0) -> ScoreBreakdown:
        """
        Calcula el score de una faceta
        
        Args:
            facet_name: Nombre de la faceta
            demand_semrush: Volumen de búsqueda SEMrush
            demand_kp: Volumen Google Keyword Planner
            traffic_gsc: Clics GSC
            traffic_adobe: Visitas Adobe
            demand_filters: Uso de filtros en site
            intent: Intención comercial (string)
            longtail_count: Número de keywords long-tail
            revenue: Revenue potencial
        
        Returns:
            ScoreBreakdown con el desglose del score
        """
        components = {}
        raw_values = {
            'demand_semrush': demand_semrush,
            'demand_kp': demand_kp,
            'traffic_gsc': traffic_gsc,
            'traffic_adobe': traffic_adobe,
            'demand_filters': demand_filters,
            'intent': intent,
            'longtail_count': longtail_count,
            'revenue': revenue,
        }
        
        # Calcular cada componente normalizado
        components['demand_semrush'] = self._normalize_demand(demand_semrush) * self.weights.demand_semrush
        components['demand_kp'] = self._normalize_demand(demand_kp) * self.weights.demand_kp
        components['traffic_gsc'] = self._normalize_traffic(traffic_gsc) * self.weights.traffic_gsc
        components['traffic_adobe'] = self._normalize_traffic(traffic_adobe) * self.weights.traffic_adobe
        components['demand_filters'] = self._normalize_demand(demand_filters) * self.weights.demand_filters
        components['commercial_intent'] = self._normalize_intent(intent) * self.weights.commercial_intent
        
        # Long-tail (normalizar a max 100 keywords)
        longtail_score = min(longtail_count / 100, 1) * 100
        components['longtail_coverage'] = longtail_score * self.weights.longtail_coverage
        
        # Revenue (normalizar a max 100K)
        revenue_score = min(revenue / 100000, 1) * 100
        components['revenue_potential'] = revenue_score * self.weights.revenue_potential
        
        # Total
        total_score = sum(components.values())
        
        # Confianza basada en fuentes con datos
        data_sources = sum([
            1 if demand_semrush > 0 else 0,
            1 if demand_kp > 0 else 0,
            1 if traffic_gsc > 0 else 0,
            1 if traffic_adobe > 0 else 0,
            1 if demand_filters > 0 else 0,
        ])
        
        if data_sources >= 4:
            confidence = 'high'
        elif data_sources >= 2:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return ScoreBreakdown(
            facet_name=facet_name,
            total_score=round(total_score, 2),
            components={k: round(v, 2) for k, v in components.items()},
            raw_values=raw_values,
            confidence=confidence,
            data_sources_count=data_sources
        )
    
    def score_from_dataframes(self,
                              facet_pattern: str,
                              facet_name: str,
                              semrush_df: pd.DataFrame = None,
                              kp_df: pd.DataFrame = None,
                              gsc_df: pd.DataFrame = None,
                              adobe_urls_df: pd.DataFrame = None,
                              adobe_filters_df: pd.DataFrame = None) -> ScoreBreakdown:
        """
        Calcula score extrayendo datos de DataFrames
        
        Args:
            facet_pattern: Patrón regex para identificar la faceta
            facet_name: Nombre de la faceta
            semrush_df: DataFrame de SEMrush
            kp_df: DataFrame de Keyword Planner
            gsc_df: DataFrame de GSC
            adobe_urls_df: DataFrame de Adobe URLs
            adobe_filters_df: DataFrame de Adobe Filters
        """
        demand_semrush = 0
        demand_kp = 0
        traffic_gsc = 0
        traffic_adobe = 0
        demand_filters = 0
        intent = ''
        longtail_count = 0
        revenue = 0
        
        # SEMrush
        if semrush_df is not None and len(semrush_df) > 0:
            kw_col = 'keyword' if 'keyword' in semrush_df.columns else 'Keyword'
            vol_col = 'volume' if 'volume' in semrush_df.columns else 'Volume'
            intent_col = 'intent' if 'intent' in semrush_df.columns else 'Intent'
            
            if kw_col in semrush_df.columns and vol_col in semrush_df.columns:
                matching = semrush_df[
                    semrush_df[kw_col].str.contains(facet_pattern, case=False, na=False, regex=True)
                ]
                demand_semrush = matching[vol_col].sum() if len(matching) > 0 else 0
                longtail_count = len(matching)
                
                if intent_col in matching.columns and len(matching) > 0:
                    intent = matching[intent_col].mode().iloc[0] if len(matching[intent_col].mode()) > 0 else ''
        
        # Keyword Planner
        if kp_df is not None and len(kp_df) > 0:
            kw_col = 'keyword' if 'keyword' in kp_df.columns else kp_df.columns[0]
            vol_col = 'volume' if 'volume' in kp_df.columns else 'avg_monthly_searches'
            
            if kw_col in kp_df.columns:
                matching = kp_df[
                    kp_df[kw_col].str.contains(facet_pattern, case=False, na=False, regex=True)
                ]
                if vol_col in kp_df.columns:
                    demand_kp = matching[vol_col].sum() if len(matching) > 0 else 0
        
        # GSC
        if gsc_df is not None and len(gsc_df) > 0:
            url_col = 'Dirección' if 'Dirección' in gsc_df.columns else 'url'
            clicks_col = 'Clics' if 'Clics' in gsc_df.columns else 'clicks'
            
            if url_col in gsc_df.columns and clicks_col in gsc_df.columns:
                matching = gsc_df[
                    gsc_df[url_col].str.contains(facet_pattern, case=False, na=False, regex=True)
                ]
                traffic_gsc = matching[clicks_col].sum() if len(matching) > 0 else 0
        
        # Adobe URLs
        if adobe_urls_df is not None and len(adobe_urls_df) > 0:
            url_col = 'url' if 'url' in adobe_urls_df.columns else 'url_full'
            visits_col = 'visits_seo' if 'visits_seo' in adobe_urls_df.columns else 'visits'
            revenue_col = 'revenue' if 'revenue' in adobe_urls_df.columns else None
            
            if url_col in adobe_urls_df.columns and visits_col in adobe_urls_df.columns:
                matching = adobe_urls_df[
                    adobe_urls_df[url_col].str.contains(facet_pattern, case=False, na=False, regex=True)
                ]
                traffic_adobe = matching[visits_col].sum() if len(matching) > 0 else 0
                
                if revenue_col and revenue_col in matching.columns:
                    revenue = matching[revenue_col].sum() if len(matching) > 0 else 0
        
        # Adobe Filters
        if adobe_filters_df is not None and len(adobe_filters_df) > 0:
            filter_col = 'filter_name' if 'filter_name' in adobe_filters_df.columns else adobe_filters_df.columns[0]
            visits_col = 'visits_seo' if 'visits_seo' in adobe_filters_df.columns else 'visits'
            
            if filter_col in adobe_filters_df.columns and visits_col in adobe_filters_df.columns:
                matching = adobe_filters_df[
                    adobe_filters_df[filter_col].str.contains(facet_pattern, case=False, na=False, regex=True)
                ]
                demand_filters = matching[visits_col].sum() if len(matching) > 0 else 0
        
        return self.score_facet(
            facet_name=facet_name,
            demand_semrush=demand_semrush,
            demand_kp=demand_kp,
            traffic_gsc=traffic_gsc,
            traffic_adobe=traffic_adobe,
            demand_filters=demand_filters,
            intent=intent,
            longtail_count=longtail_count,
            revenue=revenue
        )


def render_scoring_config_ui() -> ScoringWeights:
    """Renderiza UI para configurar pesos de scoring"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
    st.subheader("⚖️ Configurar Pesos de Scoring")
    
    st.info("""
    Ajusta los pesos según la importancia de cada métrica para tu negocio.
    Los pesos se normalizarán automáticamente para sumar 100%.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Demanda Externa**")
        demand_semrush = st.slider("SEMrush (volumen)", 0, 100, 15, key="w_semrush")
        demand_kp = st.slider("Keyword Planner", 0, 100, 15, key="w_kp")
        
        st.markdown("**🔍 Rendimiento SEO**")
        traffic_gsc = st.slider("GSC (clics)", 0, 100, 15, key="w_gsc")
        traffic_adobe = st.slider("Adobe (visitas)", 0, 100, 10, key="w_adobe")
    
    with col2:
        st.markdown("**📈 Demanda Interna**")
        demand_filters = st.slider("Uso de filtros", 0, 100, 20, key="w_filters")
        
        st.markdown("**💰 Comercial**")
        commercial = st.slider("Intención comercial", 0, 100, 10, key="w_intent")
        revenue = st.slider("Revenue potencial", 0, 100, 10, key="w_revenue")
        
        st.markdown("**📝 Cobertura**")
        longtail = st.slider("Long-tail", 0, 100, 5, key="w_longtail")
    
    # Mostrar total
    total = demand_semrush + demand_kp + traffic_gsc + traffic_adobe + demand_filters + commercial + longtail + revenue
    
    if total != 100:
        st.warning(f"Total actual: {total}% - Se normalizará a 100%")
    else:
        st.success("✅ Total: 100%")
    
    weights = ScoringWeights(
        demand_semrush=demand_semrush / 100,
        demand_kp=demand_kp / 100,
        traffic_gsc=traffic_gsc / 100,
        traffic_adobe=traffic_adobe / 100,
        demand_filters=demand_filters / 100,
        commercial_intent=commercial / 100,
        longtail_coverage=longtail / 100,
        revenue_potential=revenue / 100
    )
    
    return weights


def render_score_breakdown_ui(breakdown: ScoreBreakdown):
    """Renderiza visualización del desglose de score"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
    st.markdown(f"### {breakdown.facet_name}")
    
    # Score total con color
    score = breakdown.total_score
    if score >= 70:
        color = "green"
    elif score >= 40:
        color = "orange"
    else:
        color = "red"
    
    st.markdown(f"**Score Total:** :{color}[{score:.1f}/100]")
    st.caption(f"Confianza: {breakdown.confidence} ({breakdown.data_sources_count} fuentes)")
    
    # Desglose
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Componentes:**")
        for name, value in breakdown.components.items():
            pct = value / max(score, 0.01) * 100 if score > 0 else 0
            st.progress(min(value / 20, 1.0), text=f"{name}: {value:.1f}")
    
    with col2:
        st.markdown("**Valores brutos:**")
        for name, value in breakdown.raw_values.items():
            if isinstance(value, (int, float)) and value > 0:
                st.caption(f"{name}: {value:,.0f}")
            elif isinstance(value, str) and value:
                st.caption(f"{name}: {value}")
