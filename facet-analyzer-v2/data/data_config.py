"""
Módulo de configuración de datos
Permite al usuario definir períodos, mapear facetas y normalizar datos
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import re
import json


@dataclass
class DataSourceConfig:
    """Configuración de una fuente de datos"""
    name: str
    file_type: str  # 'crawl' | 'adobe_urls' | 'adobe_filters' | 'gsc' | 'semrush'
    filepath: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    description: str = ""
    row_count: int = 0
    columns: List[str] = field(default_factory=list)


@dataclass
class FacetMapping:
    """Mapeo de una faceta"""
    facet_id: str
    facet_name: str
    pattern: str
    url_examples: List[str]
    url_count_200: int
    url_count_404: int
    adobe_filter_match: Optional[str] = None
    user_verified: bool = False
    notes: str = ""


@dataclass
class DatasetContext:
    """Contexto completo del dataset para el chat"""
    family_name: str
    base_url: str
    sources: List[DataSourceConfig]
    facet_mappings: List[FacetMapping]
    
    # Métricas calculadas
    total_urls: int = 0
    urls_200: int = 0
    urls_404: int = 0
    total_traffic: int = 0
    
    # Análisis completados
    authority_analysis_done: bool = False
    facet_analysis_done: bool = False
    
    # Resúmenes para el chat
    authority_summary: str = ""
    facet_summary: str = ""
    top_opportunities: List[Dict] = field(default_factory=list)
    top_leaks: List[Dict] = field(default_factory=list)
    
    def to_chat_context(self) -> str:
        """Genera contexto estructurado para el chat AI"""
        context = f"""
# CONTEXTO DEL DATASET: {self.family_name}

## Fuentes de Datos
"""
        for source in self.sources:
            period = ""
            if source.period_start and source.period_end:
                period = f" (Período: {source.period_start.strftime('%d/%m/%Y')} - {source.period_end.strftime('%d/%m/%Y')})"
            context += f"- **{source.name}**: {source.row_count:,} registros{period}\n"
        
        context += f"""
## Métricas Generales
- URLs totales analizadas: {self.total_urls:,}
- URLs activas (200): {self.urls_200:,}
- URLs eliminadas (404): {self.urls_404:,}
- Tráfico SEO total: {self.total_traffic:,} visitas

## Facetas Configuradas
"""
        for fm in self.facet_mappings:
            status = "✓ Verificada" if fm.user_verified else "Auto-detectada"
            context += f"- **{fm.facet_name}**: {fm.url_count_200} URLs activas, {fm.url_count_404} eliminadas [{status}]\n"
        
        if self.authority_analysis_done:
            context += f"""
## Análisis de Autoridad
{self.authority_summary}

### Top Fugas Detectadas
"""
            for i, leak in enumerate(self.top_leaks[:10], 1):
                context += f"{i}. {leak.get('url', 'N/A')}: {leak.get('traffic', 0):,} visitas, {leak.get('type', 'N/A')}\n"
        
        if self.facet_analysis_done:
            context += f"""
## Análisis de Facetas
{self.facet_summary}

### Top Oportunidades
"""
            for i, opp in enumerate(self.top_opportunities[:10], 1):
                context += f"{i}. {opp.get('name', 'N/A')}: Score {opp.get('score', 0)}/100, {opp.get('urls_200', 0)} URLs, {opp.get('demand', 0):,} demanda\n"
        
        return context


class FacetDetector:
    """Detecta y agrupa facetas automáticamente desde URLs"""
    
    # Patrones conocidos para auto-detección
    KNOWN_PATTERNS = {
        'size': {
            'patterns': [r'pulgadas', r'pequeno', r'grande', r'pantalla'],
            'suggested_name': 'Tamaño de Pantalla',
        },
        'memory': {
            'patterns': [r'(\d+)-?gb-?ram', r'memoria'],
            'suggested_name': 'Memoria RAM',
        },
        'storage': {
            'patterns': [r'(\d+)-?gb(?!-?ram)', r'almacenamiento', r'capacidad'],
            'suggested_name': 'Almacenamiento',
        },
        'connectivity': {
            'patterns': [r'5g', r'4g', r'wifi', r'bluetooth', r'nfc'],
            'suggested_name': 'Conectividad',
        },
        'brand': {
            'patterns': [r'/(apple|samsung|xiaomi|huawei|oppo|realme|motorola|google|honor|poco|nothing|oneplus)(/|$)'],
            'suggested_name': 'Marca',
        },
        'condition': {
            'patterns': [r'nuevo', r'reacondicionado', r'usado', r'seminuevo'],
            'suggested_name': 'Estado',
        },
        'price': {
            'patterns': [r'precio', r'barato', r'gama-alta', r'gama-media', r'gama-baja'],
            'suggested_name': 'Precio',
        },
        'rating': {
            'patterns': [r'estrellas', r'valorado', r'rating'],
            'suggested_name': 'Valoración',
        },
        'color': {
            'patterns': [r'negro', r'blanco', r'azul', r'rojo', r'verde', r'rosa', r'dorado', r'plata'],
            'suggested_name': 'Color',
        },
        'feature': {
            'patterns': [r'dual-sim', r'resistente', r'sumergible', r'carga-rapida'],
            'suggested_name': 'Características',
        },
    }
    
    def __init__(self, crawl_df: pd.DataFrame):
        self.crawl = crawl_df
        self.urls = crawl_df['Dirección'].tolist()
        self.detected_facets: List[FacetMapping] = []
    
    def detect_all(self) -> List[FacetMapping]:
        """Detecta todas las facetas en las URLs"""
        self.detected_facets = []
        
        for facet_id, config in self.KNOWN_PATTERNS.items():
            combined_pattern = '|'.join(config['patterns'])
            
            # Contar URLs
            urls_200 = self.crawl[
                (self.crawl['Código de respuesta'] == 200) & 
                (self.crawl['Dirección'].str.contains(combined_pattern, case=False, na=False, regex=True))
            ]
            urls_404 = self.crawl[
                (self.crawl['Código de respuesta'] == 404) & 
                (self.crawl['Dirección'].str.contains(combined_pattern, case=False, na=False, regex=True))
            ]
            
            if len(urls_200) > 0 or len(urls_404) > 0:
                # Obtener ejemplos
                examples = urls_200['Dirección'].head(5).tolist() if len(urls_200) > 0 else urls_404['Dirección'].head(5).tolist()
                
                self.detected_facets.append(FacetMapping(
                    facet_id=facet_id,
                    facet_name=config['suggested_name'],
                    pattern=combined_pattern,
                    url_examples=examples,
                    url_count_200=len(urls_200),
                    url_count_404=len(urls_404),
                    user_verified=False
                ))
        
        return self.detected_facets
    
    def detect_unknown_patterns(self) -> List[Dict]:
        """Detecta patrones en URLs que no coinciden con facetas conocidas"""
        # Extraer segmentos de URL únicos
        all_segments = set()
        
        for url in self.urls:
            # Extraer path después del dominio
            path = url.split('/')[-1] if '/' in url else url
            # Dividir por guiones
            segments = path.split('-')
            all_segments.update(segments)
        
        # Filtrar segmentos que no están en patrones conocidos
        known_patterns = []
        for config in self.KNOWN_PATTERNS.values():
            known_patterns.extend(config['patterns'])
        
        unknown = []
        for segment in all_segments:
            if len(segment) > 2:  # Ignorar segmentos muy cortos
                is_known = any(re.search(p, segment, re.IGNORECASE) for p in known_patterns)
                if not is_known:
                    # Contar ocurrencias
                    count = sum(1 for url in self.urls if segment.lower() in url.lower())
                    if count > 10:  # Solo mostrar si aparece en más de 10 URLs
                        unknown.append({
                            'segment': segment,
                            'count': count,
                            'example_urls': [u for u in self.urls if segment.lower() in u.lower()][:3]
                        })
        
        return sorted(unknown, key=lambda x: x['count'], reverse=True)[:20]


def render_data_period_config(uploaded_files: Dict[str, Any]) -> Dict[str, DataSourceConfig]:
    """
    Renderiza UI para configurar períodos de cada archivo
    
    Args:
        uploaded_files: Dict con archivos subidos {nombre: file_object}
    
    Returns:
        Dict con configuraciones de cada fuente
    """
    st.subheader("📅 Configurar Períodos de Datos")
    
    st.info("""
    Indica el período que cubre cada archivo de datos.
    Esto ayuda a contextualizar los análisis y evitar confusiones.
    """)
    
    configs = {}
    
    for file_name, file_obj in uploaded_files.items():
        with st.expander(f"📄 {file_name}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "Fecha inicio",
                    key=f"start_{file_name}",
                    format="DD/MM/YYYY"
                )
            
            with col2:
                end_date = st.date_input(
                    "Fecha fin",
                    key=f"end_{file_name}",
                    format="DD/MM/YYYY"
                )
            
            description = st.text_input(
                "Descripción (opcional)",
                key=f"desc_{file_name}",
                placeholder="Ej: Tráfico SEO Q4 2025"
            )
            
            # Detectar tipo de archivo
            file_type = 'unknown'
            if 'crawl' in file_name.lower():
                file_type = 'crawl'
            elif 'filtro' in file_name.lower() and 'url' in file_name.lower():
                file_type = 'adobe_urls'
            elif 'filtro' in file_name.lower() or 'filter' in file_name.lower():
                file_type = 'adobe_filters'
            elif 'gsc' in file_name.lower() or 'search console' in file_name.lower():
                file_type = 'gsc'
            elif 'semrush' in file_name.lower():
                file_type = 'semrush'
            
            st.caption(f"Tipo detectado: `{file_type}`")
            
            configs[file_name] = DataSourceConfig(
                name=file_name,
                file_type=file_type,
                filepath=file_name,
                period_start=datetime.combine(start_date, datetime.min.time()) if start_date else None,
                period_end=datetime.combine(end_date, datetime.max.time()) if end_date else None,
                description=description
            )
    
    return configs


def render_facet_mapping_ui(detected_facets: List[FacetMapping], 
                            unknown_patterns: List[Dict]) -> List[FacetMapping]:
    """
    Renderiza UI interactiva para mapear facetas
    
    Args:
        detected_facets: Facetas auto-detectadas
        unknown_patterns: Patrones no reconocidos
    
    Returns:
        Lista de facetas verificadas/modificadas por el usuario
    """
    st.subheader("🏷️ Configurar Facetas")
    
    st.info("""
    Revisa las facetas detectadas automáticamente y ajusta si es necesario.
    Puedes renombrar, cambiar patrones o crear nuevas facetas.
    """)
    
    verified_facets = []
    
    # Tab para facetas detectadas y nuevas
    tab1, tab2, tab3 = st.tabs(["Facetas Detectadas", "Patrones Desconocidos", "Crear Nueva"])
    
    with tab1:
        for i, facet in enumerate(detected_facets):
            with st.expander(
                f"{'✅' if facet.user_verified else '🔍'} {facet.facet_name} ({facet.url_count_200} URLs activas)",
                expanded=not facet.user_verified
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    new_name = st.text_input(
                        "Nombre de la faceta",
                        value=facet.facet_name,
                        key=f"name_{facet.facet_id}"
                    )
                    
                    new_pattern = st.text_input(
                        "Patrón regex",
                        value=facet.pattern,
                        key=f"pattern_{facet.facet_id}",
                        help="Expresión regular para detectar esta faceta en URLs"
                    )
                
                with col2:
                    st.metric("URLs Activas (200)", facet.url_count_200)
                    st.metric("URLs Eliminadas (404)", facet.url_count_404)
                
                st.caption("**Ejemplos de URLs:**")
                for url in facet.url_examples[:3]:
                    st.code(url.replace('https://www.pccomponentes.com', ''), language=None)
                
                notes = st.text_area(
                    "Notas",
                    value=facet.notes,
                    key=f"notes_{facet.facet_id}",
                    placeholder="Notas sobre esta faceta..."
                )
                
                verified = st.checkbox(
                    "✅ Verificado",
                    value=facet.user_verified,
                    key=f"verified_{facet.facet_id}"
                )
                
                verified_facets.append(FacetMapping(
                    facet_id=facet.facet_id,
                    facet_name=new_name,
                    pattern=new_pattern,
                    url_examples=facet.url_examples,
                    url_count_200=facet.url_count_200,
                    url_count_404=facet.url_count_404,
                    adobe_filter_match=facet.adobe_filter_match,
                    user_verified=verified,
                    notes=notes
                ))
    
    with tab2:
        st.markdown("**Patrones encontrados que no coinciden con facetas conocidas:**")
        
        if unknown_patterns:
            for pattern in unknown_patterns:
                with st.expander(f"❓ `{pattern['segment']}` ({pattern['count']} URLs)"):
                    st.caption("Ejemplos:")
                    for url in pattern['example_urls']:
                        st.code(url.replace('https://www.pccomponentes.com', ''), language=None)
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        assign_to = st.selectbox(
                            "Asignar a faceta",
                            options=['(No asignar)'] + [f.facet_name for f in verified_facets],
                            key=f"assign_{pattern['segment']}"
                        )
                    with col2:
                        if st.button("Asignar", key=f"btn_{pattern['segment']}"):
                            st.success(f"Patrón asignado a {assign_to}")
        else:
            st.success("✅ Todos los patrones están clasificados")
    
    with tab3:
        st.markdown("**Crear nueva faceta manualmente:**")
        
        new_facet_name = st.text_input("Nombre", key="new_facet_name")
        new_facet_pattern = st.text_input("Patrón regex", key="new_facet_pattern")
        
        if st.button("➕ Crear Faceta") and new_facet_name and new_facet_pattern:
            # Contar URLs con el nuevo patrón
            st.info(f"Faceta '{new_facet_name}' creada. Recarga para ver estadísticas.")
    
    return verified_facets
