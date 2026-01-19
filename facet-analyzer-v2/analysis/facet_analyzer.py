"""
Módulo de análisis de facetas - v2.2
Evalúa demanda vs estado actual de cada faceta
Genérico para cualquier categoría de productos
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
import re


@dataclass
class FacetStatus:
    """Estado de una faceta"""
    name: str
    pattern: str
    
    # URLs actuales
    urls_200: int
    urls_404: int
    
    # Tráfico
    traffic_seo: int
    traffic_historical: int
    
    # Demanda
    demand_adobe: int
    demand_keywords: int
    
    # seoFilterWrapper
    in_wrapper: bool
    wrapper_link_count: int
    
    # Evaluación
    status: str  # 'active' | 'partial' | 'eliminated' | 'missing'
    opportunity_score: float
    confidence: str
    recommendation: str
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'pattern': self.pattern,
            'urls_200': self.urls_200,
            'urls_404': self.urls_404,
            'traffic_seo': self.traffic_seo,
            'demand_adobe': self.demand_adobe,
            'demand_keywords': self.demand_keywords,
            'in_wrapper': self.in_wrapper,
            'status': self.status,
            'opportunity_score': self.opportunity_score,
            'confidence': self.confidence,
            'recommendation': self.recommendation,
        }


@dataclass
class FacetAnalysisResult:
    """Resultado del análisis de facetas"""
    facets: List[FacetStatus]
    opportunities: List[FacetStatus]
    alerts: List[str]
    summary: str


class FacetAnalyzer:
    """Analizador de facetas genérico"""
    
    def __init__(self, 
                 crawl_df: pd.DataFrame, 
                 adobe_urls_df: pd.DataFrame = None,
                 adobe_filters_df: pd.DataFrame = None, 
                 keywords_df: pd.DataFrame = None,
                 facet_mappings: List = None):
        """
        Args:
            crawl_df: Crawl con datos de seoFilterWrapper
            adobe_urls_df: Tráfico SEO por URL
            adobe_filters_df: Demanda por filtros
            keywords_df: Keywords de SEMrush/Keyword Planner
            facet_mappings: Lista de FacetMapping desde data_config
        """
        self.crawl = crawl_df.copy()
        self.adobe_urls = adobe_urls_df.copy() if adobe_urls_df is not None else pd.DataFrame()
        self.adobe_filters = adobe_filters_df.copy() if adobe_filters_df is not None else pd.DataFrame()
        self.keywords = keywords_df.copy() if keywords_df is not None else pd.DataFrame()
        self.facet_mappings = facet_mappings or []
        
        # Detectar columnas
        self.url_col = 'Dirección' if 'Dirección' in self.crawl.columns else 'url'
        self.status_col = 'Código de respuesta' if 'Código de respuesta' in self.crawl.columns else 'status_code'
        
        # Separar por código
        if self.status_col in self.crawl.columns:
            self.urls_200 = self.crawl[self.crawl[self.status_col] == 200]
            self.urls_404 = self.crawl[self.crawl[self.status_col] == 404]
        else:
            self.urls_200 = self.crawl
            self.urls_404 = pd.DataFrame()
    
    def _count_urls_by_pattern(self, pattern: str, status_code: int = None) -> int:
        """Cuenta URLs que coinciden con un patrón"""
        try:
            if status_code == 200:
                df = self.urls_200
            elif status_code == 404:
                df = self.urls_404
            else:
                df = self.crawl
            
            return len(df[df[self.url_col].str.contains(pattern, case=False, na=False, regex=True)])
        except Exception:
            return 0
    
    def _get_traffic_by_pattern(self, pattern: str) -> int:
        """Obtiene tráfico SEO de URLs que coinciden con patrón"""
        if len(self.adobe_urls) == 0:
            return 0
        
        url_col = 'url' if 'url' in self.adobe_urls.columns else 'url_full'
        traffic_col = 'visits_seo' if 'visits_seo' in self.adobe_urls.columns else 'visits'
        
        if url_col not in self.adobe_urls.columns or traffic_col not in self.adobe_urls.columns:
            return 0
        
        try:
            matching = self.adobe_urls[
                self.adobe_urls[url_col].str.contains(pattern, case=False, na=False, regex=True)
            ]
            return int(matching[traffic_col].sum())
        except Exception:
            return 0
    
    def _get_demand_adobe(self, filter_prefix: str) -> int:
        """Obtiene demanda de filtros de Adobe"""
        if len(self.adobe_filters) == 0 or not filter_prefix:
            return 0
        
        filter_col = 'filter_name' if 'filter_name' in self.adobe_filters.columns else self.adobe_filters.columns[0]
        traffic_col = 'visits_seo' if 'visits_seo' in self.adobe_filters.columns else 'visits'
        
        if traffic_col not in self.adobe_filters.columns:
            return 0
        
        try:
            matching = self.adobe_filters[
                self.adobe_filters[filter_col].str.contains(filter_prefix, case=False, na=False)
            ]
            return int(matching[traffic_col].sum())
        except Exception:
            return 0
    
    def _get_demand_keywords(self, keywords: List[str]) -> int:
        """Obtiene volumen de búsqueda de keywords"""
        if len(self.keywords) == 0:
            return 0
        
        kw_col = 'keyword' if 'keyword' in self.keywords.columns else 'Keyword'
        vol_col = 'volume' if 'volume' in self.keywords.columns else 'Volume'
        
        if kw_col not in self.keywords.columns or vol_col not in self.keywords.columns:
            return 0
        
        total = 0
        for kw in keywords:
            try:
                matching = self.keywords[
                    self.keywords[kw_col].str.contains(kw, case=False, na=False)
                ]
                total += matching[vol_col].sum()
            except Exception:
                pass
        
        return int(total)
    
    def _check_in_wrapper(self, pattern: str) -> tuple:
        """Verifica si la faceta está en seoFilterWrapper del nivel 0"""
        # Buscar página de nivel 0 o con menos profundidad
        depth_col = 'Nivel de profundidad' if 'Nivel de profundidad' in self.crawl.columns else None
        
        if depth_col:
            homepage = self.urls_200[self.urls_200[depth_col] == 0]
        else:
            homepage = self.urls_200.head(1)
        
        if len(homepage) == 0:
            return False, 0
        
        row = homepage.iloc[0]
        
        # Buscar columnas de hrefs
        href_cols = [c for c in self.crawl.columns if 'seofilterwrapper_hrefs' in c.lower()]
        
        count = 0
        for col in href_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                if re.search(pattern, str(val), re.IGNORECASE):
                    count += 1
        
        return count > 0, count
    
    def _calculate_opportunity_score(self, facet_data: dict) -> float:
        """Calcula puntuación de oportunidad (0-100)"""
        score = 0
        urls_200 = facet_data.get('urls_200', 0)
        
        # Sin URLs activas = oportunidad limitada
        if urls_200 == 0:
            demand = facet_data.get('demand_adobe', 0) + facet_data.get('demand_keywords', 0)
            if demand > 100000:
                return 30
            elif demand > 50000:
                return 20
            elif demand > 10000:
                return 10
            return 5
        
        # Demanda (hasta 40 puntos)
        demand = facet_data.get('demand_adobe', 0) + facet_data.get('demand_keywords', 0)
        if demand > 100000:
            score += 40
        elif demand > 50000:
            score += 30
        elif demand > 10000:
            score += 20
        elif demand > 1000:
            score += 10
        
        # URLs activas (hasta 30 puntos)
        if urls_200 > 100:
            score += 30
        elif urls_200 > 10:
            score += 20
        elif urls_200 > 0:
            score += 10
        
        # No está en wrapper (hasta 20 puntos bonus)
        if not facet_data.get('in_wrapper', True):
            score += 20
        
        # Tráfico existente (hasta 10 puntos)
        traffic = facet_data.get('traffic_seo', 0)
        if traffic > 10000:
            score += 10
        elif traffic > 1000:
            score += 5
        
        return min(score, 100)
    
    def _determine_status(self, urls_200: int, urls_404: int, in_wrapper: bool) -> str:
        """Determina el estado de una faceta"""
        if urls_200 > 0 and in_wrapper:
            return 'active'
        elif urls_200 > 0 and not in_wrapper:
            return 'partial'
        elif urls_200 == 0 and urls_404 > 0:
            return 'eliminated'
        return 'missing'
    
    def _determine_confidence(self, urls_200: int, demand: int, traffic: int) -> str:
        """Determina nivel de confianza"""
        sources = sum([
            urls_200 > 0,
            demand > 1000,
            traffic > 100
        ])
        
        if sources >= 3:
            return 'high'
        elif sources >= 2:
            return 'medium'
        return 'low'
    
    def analyze_facet(self, facet_mapping) -> FacetStatus:
        """Analiza una faceta específica"""
        name = facet_mapping.facet_name
        pattern = facet_mapping.pattern
        adobe_filter = facet_mapping.adobe_filter_match
        
        # Contar URLs
        urls_200 = self._count_urls_by_pattern(pattern, 200)
        urls_404 = self._count_urls_by_pattern(pattern, 404)
        
        # Tráfico
        traffic_seo = self._get_traffic_by_pattern(pattern)
        
        # Demanda
        demand_adobe = self._get_demand_adobe(adobe_filter) if adobe_filter else 0
        demand_keywords = self._get_demand_keywords([name.lower().replace('_', ' ')])
        
        # seoFilterWrapper
        in_wrapper, wrapper_count = self._check_in_wrapper(pattern)
        
        # Evaluaciones
        status = self._determine_status(urls_200, urls_404, in_wrapper)
        confidence = self._determine_confidence(urls_200, demand_adobe + demand_keywords, traffic_seo)
        
        facet_data = {
            'urls_200': urls_200,
            'urls_404': urls_404,
            'demand_adobe': demand_adobe,
            'demand_keywords': demand_keywords,
            'traffic_seo': traffic_seo,
            'in_wrapper': in_wrapper,
        }
        opportunity_score = self._calculate_opportunity_score(facet_data)
        
        # Generar recomendación
        if status == 'active':
            recommendation = "✅ Faceta activa y enlazada. Mantener y optimizar."
        elif status == 'partial':
            recommendation = f"🟡 URLs existen ({urls_200}) pero no en seoFilterWrapper. Añadir enlaces."
        elif status == 'eliminated':
            if demand_adobe > 10000:
                recommendation = f"🔴 URLs eliminadas con demanda alta ({demand_adobe:,}). Evaluar recrear."
            else:
                recommendation = "⚪ URLs eliminadas. Demanda insuficiente."
        else:
            recommendation = "❌ No hay URLs para esta faceta."
        
        return FacetStatus(
            name=name,
            pattern=pattern,
            urls_200=urls_200,
            urls_404=urls_404,
            traffic_seo=traffic_seo,
            traffic_historical=traffic_seo,
            demand_adobe=demand_adobe,
            demand_keywords=demand_keywords,
            in_wrapper=in_wrapper,
            wrapper_link_count=wrapper_count,
            status=status,
            opportunity_score=opportunity_score,
            confidence=confidence,
            recommendation=recommendation
        )
    
    def analyze_all_facets(self) -> FacetAnalysisResult:
        """Analiza todas las facetas configuradas"""
        facets = []
        opportunities = []
        alerts = []
        
        for mapping in self.facet_mappings:
            facet = self.analyze_facet(mapping)
            facets.append(facet)
            
            # Identificar oportunidades
            if facet.status == 'partial' and facet.opportunity_score > 50:
                opportunities.append(facet)
            
            # Generar alertas
            if facet.status == 'eliminated' and facet.demand_adobe > 10000:
                alerts.append(
                    f"⚠️ {facet.name}: {facet.urls_404:,} URLs eliminadas con {facet.demand_adobe:,} demanda"
                )
        
        # Ordenar por score
        opportunities = sorted(opportunities, key=lambda x: x.opportunity_score, reverse=True)
        
        summary = self._generate_summary(facets, opportunities, alerts)
        
        return FacetAnalysisResult(
            facets=facets,
            opportunities=opportunities,
            alerts=alerts,
            summary=summary
        )
    
    def _generate_summary(self, facets: List[FacetStatus], 
                          opportunities: List[FacetStatus],
                          alerts: List[str]) -> str:
        """Genera resumen del análisis"""
        active = sum(1 for f in facets if f.status == 'active')
        partial = sum(1 for f in facets if f.status == 'partial')
        eliminated = sum(1 for f in facets if f.status == 'eliminated')
        missing = sum(1 for f in facets if f.status == 'missing')
        
        summary = f"""
## Resumen de Facetas

### Estado Actual
- ✅ **Activas**: {active} facetas
- 🟡 **Parciales** (sin enlazar): {partial} facetas
- 🔴 **Eliminadas**: {eliminated} facetas
- ❌ **Sin URLs**: {missing} facetas

### Top Oportunidades
"""
        for i, opp in enumerate(opportunities[:5], 1):
            summary += f"{i}. **{opp.name}**: Score {opp.opportunity_score:.0f}/100 - {opp.urls_200} URLs, {opp.demand_adobe:,} demanda\n"
        
        if alerts:
            summary += "\n### ⚠️ Alertas\n"
            for alert in alerts:
                summary += f"- {alert}\n"
        
        return summary
