"""
Módulo de análisis de autoridad - v2.2
Detecta fuga y dilución de PageRank
Genérico para cualquier categoría
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import re


@dataclass
class AuthorityLeak:
    """Representa una fuga de autoridad detectada"""
    url: str
    traffic_seo: int
    wrapper_links: int
    leak_type: str  # 'no_distribution' | 'dilution' | 'dead_end'
    severity: str   # 'high' | 'medium' | 'low'
    recommendation: str
    
    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'traffic_seo': self.traffic_seo,
            'wrapper_links': self.wrapper_links,
            'leak_type': self.leak_type,
            'severity': self.severity,
            'recommendation': self.recommendation,
        }


@dataclass
class AuthorityAnalysisResult:
    """Resultado del análisis de autoridad"""
    total_leaks: int
    total_traffic_affected: int
    leaks_by_type: Dict[str, int]
    top_leaks: List[AuthorityLeak]
    dead_ends_count: int
    dead_ends_traffic: int
    dead_ends_by_facet: Dict[str, int]
    summary: str


class AuthorityAnalyzer:
    """Analizador de fuga y dilución de autoridad"""
    
    def __init__(self, crawl_df: pd.DataFrame, adobe_urls_df: pd.DataFrame = None):
        """
        Args:
            crawl_df: Crawl con wrapper_link_count calculado
            adobe_urls_df: Tráfico SEO por URL (opcional)
        """
        self.crawl = crawl_df.copy()
        self.adobe_urls = adobe_urls_df.copy() if adobe_urls_df is not None else pd.DataFrame()
        
        # Asegurar que wrapper_link_count existe
        if 'wrapper_link_count' not in self.crawl.columns:
            self.crawl['wrapper_link_count'] = 0
        
        self.merged = self._merge_data()
    
    def _merge_data(self) -> pd.DataFrame:
        """Combina crawl con tráfico"""
        if len(self.adobe_urls) == 0 or 'url_full' not in self.adobe_urls.columns:
            self.crawl['visits_seo'] = 0
            return self.crawl
        
        # Intentar varios nombres de columna URL
        url_col = 'Dirección' if 'Dirección' in self.crawl.columns else 'url'
        
        merged = self.crawl.merge(
            self.adobe_urls[['url_full', 'visits_seo']],
            left_on=url_col,
            right_on='url_full',
            how='left'
        )
        merged['visits_seo'] = merged['visits_seo'].fillna(0).astype(int)
        
        # Limpiar columna duplicada
        if 'url_full' in merged.columns:
            merged = merged.drop(columns=['url_full'])
        
        return merged
    
    def analyze_no_distribution(self, min_traffic: int = 100) -> List[AuthorityLeak]:
        """
        FUGA TIPO 1: Páginas con tráfico pero sin seoFilterWrapper
        """
        url_col = 'Dirección' if 'Dirección' in self.merged.columns else 'url'
        status_col = 'Código de respuesta' if 'Código de respuesta' in self.merged.columns else 'status_code'
        
        # Filtrar URLs 200
        if status_col in self.merged.columns:
            urls_200 = self.merged[self.merged[status_col] == 200].copy()
        else:
            urls_200 = self.merged.copy()
        
        # Páginas sin distribución
        no_dist = urls_200[
            (urls_200['wrapper_link_count'] == 0) & 
            (urls_200['visits_seo'] >= min_traffic)
        ]
        
        leaks = []
        for _, row in no_dist.iterrows():
            traffic = int(row['visits_seo'])
            severity = 'high' if traffic > 5000 else ('medium' if traffic > 1000 else 'low')
            
            leaks.append(AuthorityLeak(
                url=row[url_col],
                traffic_seo=traffic,
                wrapper_links=0,
                leak_type='no_distribution',
                severity=severity,
                recommendation="Añadir seoFilterWrapper con enlaces a facetas relevantes"
            ))
        
        return sorted(leaks, key=lambda x: x.traffic_seo, reverse=True)
    
    def analyze_dilution(self, max_links: int = 10, min_traffic: int = 500) -> List[AuthorityLeak]:
        """
        FUGA TIPO 2: Páginas con muchos enlaces pero poco tráfico
        """
        url_col = 'Dirección' if 'Dirección' in self.merged.columns else 'url'
        status_col = 'Código de respuesta' if 'Código de respuesta' in self.merged.columns else 'status_code'
        
        if status_col in self.merged.columns:
            urls_200 = self.merged[self.merged[status_col] == 200].copy()
        else:
            urls_200 = self.merged.copy()
        
        dilution = urls_200[
            (urls_200['wrapper_link_count'] >= max_links) & 
            (urls_200['visits_seo'] < min_traffic)
        ]
        
        leaks = []
        for _, row in dilution.iterrows():
            links = int(row['wrapper_link_count'])
            traffic = int(row['visits_seo'])
            ratio = links / max(traffic, 1)
            severity = 'high' if ratio > 0.5 else ('medium' if ratio > 0.1 else 'low')
            
            leaks.append(AuthorityLeak(
                url=row[url_col],
                traffic_seo=traffic,
                wrapper_links=links,
                leak_type='dilution',
                severity=severity,
                recommendation=f"Reducir de {links} a máximo {max_links} enlaces"
            ))
        
        return sorted(leaks, key=lambda x: x.wrapper_links, reverse=True)
    
    def analyze_dead_ends(self) -> Tuple[int, int, Dict[str, int]]:
        """
        FUGA TIPO 3: URLs 404 (dead ends)
        """
        url_col = 'Dirección' if 'Dirección' in self.crawl.columns else 'url'
        status_col = 'Código de respuesta' if 'Código de respuesta' in self.crawl.columns else 'status_code'
        
        if status_col not in self.crawl.columns:
            return 0, 0, {}
        
        urls_404 = self.crawl[self.crawl[status_col] == 404]
        
        # Cruzar con Adobe
        total_traffic_lost = 0
        if len(self.adobe_urls) > 0 and 'url_full' in self.adobe_urls.columns:
            urls_404_with_traffic = urls_404.merge(
                self.adobe_urls[['url_full', 'visits_seo']],
                left_on=url_col,
                right_on='url_full',
                how='inner'
            )
            total_traffic_lost = int(urls_404_with_traffic['visits_seo'].sum())
        
        # Clasificar por patrones comunes
        facet_counts = {}
        patterns = {
            'TAMAÑO': r'pulgadas|litros|cm',
            'CONECTIVIDAD': r'5g|wifi|nfc',
            'MEMORIA': r'gb-ram',
            'ALMACENAMIENTO': r'gb(?!-ram)|tb',
            'ESTADO': r'reacondicionado|nuevo',
        }
        
        for facet, pattern in patterns.items():
            count = len(urls_404[urls_404[url_col].str.contains(pattern, case=False, na=False, regex=True)])
            if count > 0:
                facet_counts[facet] = count
        
        return len(urls_404), total_traffic_lost, facet_counts
    
    def get_full_analysis(self) -> AuthorityAnalysisResult:
        """Ejecuta análisis completo de autoridad"""
        
        # Tipo 1: No distribución
        no_dist_leaks = self.analyze_no_distribution()
        no_dist_traffic = sum(l.traffic_seo for l in no_dist_leaks)
        
        # Tipo 2: Dilución
        dilution_leaks = self.analyze_dilution()
        
        # Tipo 3: Dead ends
        dead_ends_count, dead_ends_traffic, dead_ends_facets = self.analyze_dead_ends()
        
        # Combinar top leaks
        all_leaks = no_dist_leaks + dilution_leaks
        top_leaks = sorted(all_leaks, key=lambda x: x.traffic_seo, reverse=True)[:20]
        
        # Generar resumen
        summary = f"""
## Análisis de Autoridad

### Fuga Tipo 1: Autoridad No Distribuida
- **{len(no_dist_leaks)}** páginas con tráfico pero sin seoFilterWrapper
- **{no_dist_traffic:,}** visitas SEO totales afectadas

### Fuga Tipo 2: Dilución de Autoridad
- **{len(dilution_leaks)}** páginas con ratio enlaces/tráfico alto

### Fuga Tipo 3: Dead Ends (URLs 404)
- **{dead_ends_count:,}** URLs devuelven 404
- **{dead_ends_traffic:,}** visitas históricas perdidas
"""
        if dead_ends_facets:
            summary += f"- Facetas más afectadas: {', '.join(f'{k}: {v:,}' for k, v in sorted(dead_ends_facets.items(), key=lambda x: x[1], reverse=True)[:5])}\n"
        
        return AuthorityAnalysisResult(
            total_leaks=len(no_dist_leaks) + len(dilution_leaks),
            total_traffic_affected=no_dist_traffic + dead_ends_traffic,
            leaks_by_type={
                'no_distribution': len(no_dist_leaks),
                'dilution': len(dilution_leaks),
                'dead_ends': dead_ends_count,
            },
            top_leaks=top_leaks,
            dead_ends_count=dead_ends_count,
            dead_ends_traffic=dead_ends_traffic,
            dead_ends_by_facet=dead_ends_facets,
            summary=summary
        )


def get_wrapper_distribution(crawl_df: pd.DataFrame) -> pd.DataFrame:
    """Calcula distribución de enlaces en seoFilterWrapper"""
    status_col = 'Código de respuesta' if 'Código de respuesta' in crawl_df.columns else 'status_code'
    
    if status_col in crawl_df.columns:
        urls_200 = crawl_df[crawl_df[status_col] == 200]
    else:
        urls_200 = crawl_df
    
    if 'wrapper_link_count' not in urls_200.columns:
        return pd.DataFrame({'range': ['N/A'], 'count': [len(urls_200)]})
    
    bins = [0, 1, 2, 3, 5, 10, 20, 50, 100, 1000]
    labels = ['0', '1', '2', '3-4', '5-9', '10-19', '20-49', '50-99', '100+']
    
    distribution = pd.cut(
        urls_200['wrapper_link_count'].clip(upper=999), 
        bins=bins, 
        labels=labels, 
        right=False
    ).value_counts().sort_index()
    
    return distribution.to_frame('count').reset_index().rename(columns={'index': 'range'})
