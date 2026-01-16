"""
Módulo de análisis de autoridad
Detecta fuga y dilución de PageRank
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class AuthorityLeak:
    """Representa una fuga de autoridad detectada"""
    url: str
    traffic_seo: int
    wrapper_links: int
    leak_type: str  # 'no_distribution' | 'dilution' | 'dead_end'
    severity: str   # 'high' | 'medium' | 'low'
    recommendation: str


@dataclass
class AuthorityAnalysisResult:
    """Resultado del análisis de autoridad"""
    total_leaks: int
    total_traffic_affected: int
    leaks_by_type: Dict[str, int]
    top_leaks: List[AuthorityLeak]
    summary: str


class AuthorityAnalyzer:
    """Analizador de fuga y dilución de autoridad"""
    
    def __init__(self, crawl_df: pd.DataFrame, adobe_urls_df: pd.DataFrame):
        self.crawl = crawl_df
        self.adobe_urls = adobe_urls_df
        self.merged = self._merge_data()
        
    def _merge_data(self) -> pd.DataFrame:
        """Combina crawl con tráfico"""
        merged = self.crawl.merge(
            self.adobe_urls[['url_full', 'visits_seo']],
            left_on='Dirección',
            right_on='url_full',
            how='left'
        )
        merged['visits_seo'] = merged['visits_seo'].fillna(0)
        return merged
    
    def analyze_no_distribution(self, min_traffic: int = 100) -> List[AuthorityLeak]:
        """
        FUGA TIPO 1: Páginas con tráfico pero sin seoFilterWrapper
        Estas páginas reciben autoridad pero no la distribuyen
        """
        urls_200 = self.merged[self.merged['Código de respuesta'] == 200]
        
        no_dist = urls_200[
            (urls_200['wrapper_link_count'] == 0) & 
            (urls_200['visits_seo'] >= min_traffic)
        ].copy()
        
        leaks = []
        for _, row in no_dist.iterrows():
            traffic = int(row['visits_seo'])
            severity = 'high' if traffic > 5000 else ('medium' if traffic > 1000 else 'low')
            
            leaks.append(AuthorityLeak(
                url=row['Dirección'],
                traffic_seo=traffic,
                wrapper_links=0,
                leak_type='no_distribution',
                severity=severity,
                recommendation=f"Añadir seoFilterWrapper con enlaces a facetas relevantes"
            ))
        
        return sorted(leaks, key=lambda x: x.traffic_seo, reverse=True)
    
    def analyze_dilution(self, max_links: int = 10, min_traffic: int = 500) -> List[AuthorityLeak]:
        """
        FUGA TIPO 2: Páginas con muchos enlaces pero poco tráfico
        Diluyen la poca autoridad que tienen entre muchos destinos
        """
        urls_200 = self.merged[self.merged['Código de respuesta'] == 200]
        
        dilution = urls_200[
            (urls_200['wrapper_link_count'] >= max_links) & 
            (urls_200['visits_seo'] < min_traffic)
        ].copy()
        
        leaks = []
        for _, row in dilution.iterrows():
            links = int(row['wrapper_link_count'])
            traffic = int(row['visits_seo'])
            
            # Ratio de dilución: más enlaces + menos tráfico = peor
            ratio = links / max(traffic, 1)
            severity = 'high' if ratio > 0.5 else ('medium' if ratio > 0.1 else 'low')
            
            leaks.append(AuthorityLeak(
                url=row['Dirección'],
                traffic_seo=traffic,
                wrapper_links=links,
                leak_type='dilution',
                severity=severity,
                recommendation=f"Reducir de {links} a máximo {max_links} enlaces priorizando alto rendimiento"
            ))
        
        return sorted(leaks, key=lambda x: x.wrapper_links, reverse=True)
    
    def analyze_dead_ends(self) -> Tuple[int, int, Dict[str, int]]:
        """
        FUGA TIPO 3: URLs 404 (dead ends)
        Estas URLs no pueden pasar autoridad porque no existen
        """
        urls_404 = self.crawl[self.crawl['Código de respuesta'] == 404]
        
        # Cruzar con Adobe para ver tráfico histórico
        urls_404_with_traffic = urls_404.merge(
            self.adobe_urls[['url_full', 'visits_seo']],
            left_on='Dirección',
            right_on='url_full',
            how='inner'
        )
        
        total_404 = len(urls_404)
        total_traffic_lost = int(urls_404_with_traffic['visits_seo'].sum())
        
        # Clasificar por tipo de faceta
        facet_counts = {}
        patterns = {
            'PULGADAS': r'pulgadas|pequeno',
            '5G': r'5g',
            'RAM': r'gb-ram',
            'DUAL_SIM': r'dual-sim',
            'NFC': r'/nfc',
            'REACONDICIONADO': r'reacondicionado',
        }
        
        for facet, pattern in patterns.items():
            count = len(urls_404[urls_404['Dirección'].str.contains(pattern, case=False, na=False)])
            if count > 0:
                facet_counts[facet] = count
        
        return total_404, total_traffic_lost, facet_counts
    
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
        
        # Resumen
        summary = f"""
## Análisis de Autoridad del Hub

### Fuga Tipo 1: Autoridad No Distribuida
- **{len(no_dist_leaks)}** páginas con tráfico pero sin seoFilterWrapper
- **{no_dist_traffic:,}** visitas SEO totales afectadas
- Estas páginas reciben PageRank pero no lo distribuyen a través del seoFilterWrapper

### Fuga Tipo 2: Dilución de Autoridad
- **{len(dilution_leaks)}** páginas con ratio enlaces/tráfico alto
- Tienen muchos enlaces salientes pero poco tráfico propio
- El PageRank se diluye entre demasiados destinos

### Fuga Tipo 3: Dead Ends (URLs 404)
- **{dead_ends_count:,}** URLs devuelven 404
- **{dead_ends_traffic:,}** visitas históricas a URLs eliminadas
- Facetas más afectadas: {', '.join(f'{k}: {v:,}' for k, v in sorted(dead_ends_facets.items(), key=lambda x: x[1], reverse=True)[:5])}

### Recomendación Principal
Priorizar páginas con alto tráfico y sin seoFilterWrapper:
1. `/mas-relevantes` - Máxima prioridad
2. Páginas `/nuevo/*` y `/reacondicionado/*`
3. Reducir enlaces en páginas con dilución extrema
"""
        
        return AuthorityAnalysisResult(
            total_leaks=len(no_dist_leaks) + len(dilution_leaks),
            total_traffic_affected=no_dist_traffic + dead_ends_traffic,
            leaks_by_type={
                'no_distribution': len(no_dist_leaks),
                'dilution': len(dilution_leaks),
                'dead_ends': dead_ends_count,
            },
            top_leaks=top_leaks,
            summary=summary
        )


def get_wrapper_distribution(crawl_df: pd.DataFrame) -> pd.DataFrame:
    """Calcula distribución de enlaces en seoFilterWrapper"""
    urls_200 = crawl_df[crawl_df['Código de respuesta'] == 200]
    
    bins = [0, 1, 2, 3, 5, 10, 20, 50, 100]
    labels = ['0', '1', '2', '3-4', '5-9', '10-19', '20-49', '50+']
    
    distribution = pd.cut(
        urls_200['wrapper_link_count'], 
        bins=bins, 
        labels=labels, 
        right=False
    ).value_counts().sort_index()
    
    return distribution.to_frame('count').reset_index()
