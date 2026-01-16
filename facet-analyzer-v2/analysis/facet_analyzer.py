"""
Módulo de análisis de facetas
Evalúa demanda vs estado actual de cada faceta
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
    traffic_seo: int          # Tráfico actual de URLs 200
    traffic_historical: int    # Tráfico histórico (incluye 404s)
    
    # Demanda
    demand_adobe: int         # Visitas de filtros en Adobe
    demand_semrush: int       # Volumen de búsqueda SEMrush
    
    # seoFilterWrapper
    in_wrapper: bool
    wrapper_link_count: int
    
    # Evaluación
    status: str               # 'active' | 'partial' | 'eliminated' | 'missing'
    opportunity_score: float  # 0-100
    confidence: str           # 'high' | 'medium' | 'low'
    recommendation: str


@dataclass
class FacetAnalysisResult:
    """Resultado del análisis de facetas"""
    facets: List[FacetStatus]
    opportunities: List[FacetStatus]
    alerts: List[str]
    summary: str


class FacetAnalyzer:
    """Analizador de facetas con evaluación de oportunidades"""
    
    FACET_PATTERNS = {
        'PULGADAS': {
            'pattern': r'pulgadas|pequeno',
            'adobe_filter': 'pulgadas:',
            'description': 'Tamaño de pantalla',
        },
        'RAM': {
            'pattern': r'gb-ram',
            'adobe_filter': 'memoria ram:',
            'description': 'Memoria RAM',
        },
        'ALMACENAMIENTO': {
            'pattern': r'(\d+)-gb(?!-ram)',
            'adobe_filter': 'almacenamiento:',
            'description': 'Almacenamiento interno',
        },
        '5G': {
            'pattern': r'5g',
            'adobe_filter': 'conectividad:',
            'description': 'Conectividad 5G',
        },
        'DUAL_SIM': {
            'pattern': r'dual-sim',
            'adobe_filter': None,
            'description': 'Dual SIM',
        },
        'NFC': {
            'pattern': r'/nfc',
            'adobe_filter': None,
            'description': 'NFC',
        },
        'REACONDICIONADO': {
            'pattern': r'reacondicionado',
            'adobe_filter': 'estado del articulo:',
            'description': 'Reacondicionado',
        },
        'MARCA': {
            'pattern': r'/(apple|samsung|xiaomi|google|oppo|realme|motorola|honor|poco|nothing|huawei)(/|$)',
            'adobe_filter': 'marcas:',
            'description': 'Marcas',
        },
        'PRECIO': {
            'pattern': r'precio|barato|gama',
            'adobe_filter': 'price:',
            'description': 'Rango de precio',
        },
    }
    
    def __init__(self, crawl_df: pd.DataFrame, adobe_urls_df: pd.DataFrame, 
                 adobe_filters_df: pd.DataFrame, semrush_df: pd.DataFrame = None):
        self.crawl = crawl_df
        self.adobe_urls = adobe_urls_df
        self.adobe_filters = adobe_filters_df
        self.semrush = semrush_df
        
        # Separar por código
        self.urls_200 = crawl_df[crawl_df['Código de respuesta'] == 200]
        self.urls_404 = crawl_df[crawl_df['Código de respuesta'] == 404]
        
        # Preparar merge de tráfico
        self._prepare_traffic_data()
    
    def _prepare_traffic_data(self):
        """Prepara datos de tráfico para análisis"""
        # Normalizar URLs de Adobe
        if 'url_full' not in self.adobe_urls.columns:
            self.adobe_urls['url_full'] = self.adobe_urls['url'].apply(
                lambda x: 'https://' + str(x) if not str(x).startswith('http') else str(x)
            )
    
    def _count_urls_by_pattern(self, pattern: str, status_code: int = None) -> int:
        """Cuenta URLs que coinciden con un patrón"""
        df = self.crawl
        if status_code:
            df = df[df['Código de respuesta'] == status_code]
        return len(df[df['Dirección'].str.contains(pattern, case=False, na=False, regex=True)])
    
    def _get_traffic_by_pattern(self, pattern: str) -> int:
        """Obtiene tráfico SEO de URLs que coinciden con patrón"""
        matching_urls = self.adobe_urls[
            self.adobe_urls['url'].str.contains(pattern, case=False, na=False, regex=True)
        ]
        return int(matching_urls['visits_seo'].sum())
    
    def _get_demand_adobe(self, filter_prefix: str) -> int:
        """Obtiene demanda de filtros de Adobe"""
        if filter_prefix is None:
            return 0
        matching = self.adobe_filters[
            self.adobe_filters['filter_name'].str.contains(filter_prefix, case=False, na=False)
        ]
        return int(matching['visits_seo'].sum())
    
    def _get_demand_semrush(self, keywords: List[str]) -> int:
        """Obtiene volumen de búsqueda de SEMrush"""
        if self.semrush is None:
            return 0
        
        total = 0
        for kw in keywords:
            matching = self.semrush[
                self.semrush['Keyword'].str.contains(kw, case=False, na=False)
            ]
            total += matching['Volume'].sum()
        return int(total)
    
    def _check_in_wrapper(self, pattern: str) -> tuple:
        """Verifica si la faceta está en seoFilterWrapper del nivel 0"""
        homepage = self.urls_200[self.urls_200['Nivel de profundidad'] == 0]
        
        if len(homepage) == 0:
            return False, 0
        
        row = homepage.iloc[0]
        href_cols = [f'seoFilterWrapper_hrefs {i}' for i in range(1, 84)]
        
        count = 0
        for col in href_cols:
            if col in self.crawl.columns:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    if re.search(pattern, str(val), re.IGNORECASE):
                        count += 1
        
        return count > 0, count
    
    def _calculate_opportunity_score(self, facet: dict) -> float:
        """Calcula puntuación de oportunidad (0-100)"""
        score = 0
        urls_200 = facet.get('urls_200', 0)
        
        # Si no hay URLs activas, la oportunidad es limitada
        # Solo se puede "recrear" páginas, no enlazar existentes
        if urls_200 == 0:
            # Solo dar puntos por demanda alta (podría justificar recrear)
            demand = facet.get('demand_adobe', 0) + facet.get('demand_semrush', 0)
            if demand > 100000:
                return 30  # Alta demanda justifica evaluar recreación
            elif demand > 50000:
                return 20
            elif demand > 10000:
                return 10
            else:
                return 5  # Demanda baja + sin URLs = oportunidad mínima
        
        # Demanda (hasta 40 puntos)
        demand = facet.get('demand_adobe', 0) + facet.get('demand_semrush', 0)
        if demand > 100000:
            score += 40
        elif demand > 50000:
            score += 30
        elif demand > 10000:
            score += 20
        elif demand > 1000:
            score += 10
        
        # URLs activas disponibles (hasta 30 puntos)
        if urls_200 > 100:
            score += 30
        elif urls_200 > 10:
            score += 20
        elif urls_200 > 0:
            score += 10
        
        # No está en wrapper (hasta 20 puntos bonus)
        if not facet.get('in_wrapper', True):
            score += 20
        
        # Tráfico existente (hasta 10 puntos)
        traffic = facet.get('traffic_seo', 0)
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
            return 'partial'  # URLs existen pero no están enlazadas
        elif urls_200 == 0 and urls_404 > 0:
            return 'eliminated'  # URLs fueron eliminadas
        else:
            return 'missing'  # No hay URLs
    
    def _determine_confidence(self, urls_200: int, demand: int, traffic: int) -> str:
        """Determina nivel de confianza de la recomendación"""
        sources = 0
        if urls_200 > 0:
            sources += 1
        if demand > 1000:
            sources += 1
        if traffic > 100:
            sources += 1
        
        if sources >= 3:
            return 'high'
        elif sources >= 2:
            return 'medium'
        else:
            return 'low'
    
    def analyze_facet(self, name: str, config: dict) -> FacetStatus:
        """Analiza una faceta específica"""
        pattern = config['pattern']
        adobe_filter = config.get('adobe_filter')
        
        # Contar URLs
        urls_200 = self._count_urls_by_pattern(pattern, 200)
        urls_404 = self._count_urls_by_pattern(pattern, 404)
        
        # Tráfico
        traffic_seo = self._get_traffic_by_pattern(pattern)
        
        # Demanda
        demand_adobe = self._get_demand_adobe(adobe_filter)
        demand_semrush = self._get_demand_semrush([name.lower().replace('_', ' ')])
        
        # seoFilterWrapper
        in_wrapper, wrapper_count = self._check_in_wrapper(pattern)
        
        # Evaluaciones
        status = self._determine_status(urls_200, urls_404, in_wrapper)
        confidence = self._determine_confidence(urls_200, demand_adobe + demand_semrush, traffic_seo)
        
        facet_data = {
            'urls_200': urls_200,
            'urls_404': urls_404,
            'demand_adobe': demand_adobe,
            'demand_semrush': demand_semrush,
            'traffic_seo': traffic_seo,
            'in_wrapper': in_wrapper,
        }
        opportunity_score = self._calculate_opportunity_score(facet_data)
        
        # Generar recomendación
        if status == 'active':
            recommendation = "✅ Faceta activa y enlazada. Mantener y optimizar."
        elif status == 'partial':
            recommendation = f"🟡 URLs existen ({urls_200}) pero no están en seoFilterWrapper. Añadir enlaces."
        elif status == 'eliminated':
            if demand_adobe > 10000:
                recommendation = f"🔴 URLs eliminadas con demanda alta ({demand_adobe:,}). Evaluar recrear."
            else:
                recommendation = f"⚪ URLs eliminadas. Demanda insuficiente para recrear."
        else:
            recommendation = "❌ No hay URLs para esta faceta."
        
        return FacetStatus(
            name=name,
            pattern=pattern,
            urls_200=urls_200,
            urls_404=urls_404,
            traffic_seo=traffic_seo,
            traffic_historical=traffic_seo,  # Simplificado
            demand_adobe=demand_adobe,
            demand_semrush=demand_semrush,
            in_wrapper=in_wrapper,
            wrapper_link_count=wrapper_count,
            status=status,
            opportunity_score=opportunity_score,
            confidence=confidence,
            recommendation=recommendation
        )
    
    def analyze_all_facets(self) -> FacetAnalysisResult:
        """Analiza todas las facetas definidas"""
        facets = []
        opportunities = []
        alerts = []
        
        for name, config in self.FACET_PATTERNS.items():
            facet = self.analyze_facet(name, config)
            facets.append(facet)
            
            # Identificar oportunidades
            if facet.status == 'partial' and facet.opportunity_score > 50:
                opportunities.append(facet)
            
            # Generar alertas
            if facet.status == 'eliminated' and facet.demand_adobe > 10000:
                alerts.append(
                    f"⚠️ {name}: {facet.urls_404:,} URLs eliminadas con {facet.demand_adobe:,} demanda"
                )
        
        # Ordenar oportunidades por score
        opportunities = sorted(opportunities, key=lambda x: x.opportunity_score, reverse=True)
        
        # Generar resumen
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
- 🟡 **Parciales** (URLs sin enlazar): {partial} facetas
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
