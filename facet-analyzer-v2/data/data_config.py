"""
Módulo de configuración de datos - v2.3
Permite configurar períodos, mapear facetas y crear contexto para el chat
Genérico para cualquier categoría de productos
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import re

# Streamlit es opcional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


@dataclass
class DataSourceConfig:
    """Configuración de una fuente de datos"""
    name: str
    file_type: str
    filepath: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    description: str = ""
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    
    def period_str(self) -> str:
        """Retorna período como string legible"""
        if self.period_start and self.period_end:
            return f"{self.period_start.strftime('%d/%m/%Y')} - {self.period_end.strftime('%d/%m/%Y')}"
        return "No especificado"


@dataclass
class FacetMapping:
    """Mapeo de una faceta detectada"""
    facet_id: str
    facet_name: str
    pattern: str
    url_examples: List[str] = field(default_factory=list)
    url_count_200: int = 0
    url_count_404: int = 0
    adobe_filter_match: Optional[str] = None
    adobe_filter_prefix: Optional[str] = None
    user_verified: bool = False
    notes: str = ""
    category: str = ""
    is_custom: bool = False


@dataclass
class DatasetContext:
    """Contexto completo del dataset para el chat"""
    family_name: str
    base_url: str
    category_path: str = ""
    sources: List[DataSourceConfig] = field(default_factory=list)
    facet_mappings: List[FacetMapping] = field(default_factory=list)
    
    # Métricas calculadas
    total_urls: int = 0
    urls_200: int = 0
    urls_404: int = 0
    urls_301: int = 0
    total_traffic: int = 0
    total_demand: int = 0
    with_wrapper: int = 0
    without_wrapper: int = 0
    
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

## URL Base
{self.base_url}

## Fuentes de Datos
"""
        for source in self.sources:
            period = f" ({source.period_str()})" if source.period_start else ""
            context += f"- **{source.name}**: {source.row_count:,} registros{period}\n"
        
        context += f"""
## Métricas Generales
- URLs totales analizadas: {self.total_urls:,}
- URLs activas (200): {self.urls_200:,}
- URLs eliminadas (404): {self.urls_404:,}
- URLs redirigidas (301): {self.urls_301:,}
- Tráfico SEO total: {self.total_traffic:,} visitas
- Demanda total en filtros: {self.total_demand:,} sesiones

## Estado del seoFilterWrapper
- URLs con wrapper: {self.with_wrapper:,}
- URLs sin wrapper: {self.without_wrapper:,}
- Porcentaje con wrapper: {self.with_wrapper / max(self.urls_200, 1) * 100:.1f}%

## Facetas Configuradas ({len(self.facet_mappings)})
"""
        for fm in self.facet_mappings[:15]:
            status = "✓" if fm.user_verified else "?"
            context += f"- [{status}] **{fm.facet_name}**: {fm.url_count_200} URLs activas, {fm.url_count_404} eliminadas\n"
        
        if len(self.facet_mappings) > 15:
            context += f"- ... y {len(self.facet_mappings) - 15} facetas más\n"
        
        if self.authority_analysis_done:
            context += f"""
## Análisis de Autoridad (Completado)
{self.authority_summary[:1000] if self.authority_summary else 'Sin resumen disponible'}

### Top Fugas Detectadas
"""
            for i, leak in enumerate(self.top_leaks[:10], 1):
                context += f"{i}. {leak.get('url', 'N/A')}: {leak.get('traffic', 0):,} visitas ({leak.get('type', 'N/A')})\n"
        
        if self.facet_analysis_done:
            context += f"""
## Análisis de Facetas (Completado)
{self.facet_summary[:1000] if self.facet_summary else 'Sin resumen disponible'}

### Top Oportunidades
"""
            for i, opp in enumerate(self.top_opportunities[:10], 1):
                context += f"{i}. {opp.get('name', 'N/A')}: Score {opp.get('score', 0)}/100, {opp.get('urls_200', 0)} URLs, {opp.get('demand', 0):,} demanda\n"
        
        return context


def validate_regex_pattern(pattern: str) -> Tuple[bool, str]:
    """
    Valida que un patrón regex sea válido
    
    Returns:
        (es_valido, mensaje_error)
    """
    if not pattern or not pattern.strip():
        return False, "Patrón vacío"
    
    try:
        re.compile(pattern)
        return True, ""
    except re.error as e:
        return False, f"Regex inválido: {str(e)}"


class FacetDetector:
    """
    Detecta y agrupa facetas automáticamente desde URLs
    Genérico para cualquier categoría de productos
    """
    
    # Patrones genéricos corregidos
    GENERIC_PATTERNS = {
        'brand': {
            'category': 'marca',
            'patterns': [],
            'suggested_name': 'Marcas',
            'adobe_filter_prefix': 'marcas:',
            'dynamic': True,
        },
        
        # TAMAÑOS / DIMENSIONES
        'size_screen': {
            'category': 'tamaño',
            'patterns': [r'pulgadas', r'pequeno', r'grande', r'\d+-pulgadas', r'pantalla-\d+'],
            'suggested_name': 'Tamaño de Pantalla',
            'adobe_filter_prefix': 'pulgadas:',
        },
        'size_capacity': {
            'category': 'tamaño',
            'patterns': [r'litros', r'-l(?:/|$)', r'\d+-litros', r'capacidad'],
            'suggested_name': 'Capacidad',
            'adobe_filter_prefix': 'capacidad:',
        },
        'size_dimension': {
            'category': 'tamaño',
            'patterns': [r'\d+x\d+', r'-cm-', r'centimetros', r'metros'],
            'suggested_name': 'Dimensiones',
            'adobe_filter_prefix': 'dimensiones:',
        },
        
        # MEMORIA / ALMACENAMIENTO
        'memory_ram': {
            'category': 'memoria',
            'patterns': [r'\d+-?gb-?ram', r'memoria-ram', r'/ram-\d+'],
            'suggested_name': 'Memoria RAM',
            'adobe_filter_prefix': 'memoria ram:',
        },
        'storage': {
            'category': 'almacenamiento',
            'patterns': [r'\d+-?gb(?!-?ram)', r'\d+-?tb', r'almacenamiento', r'disco-duro', r'ssd-\d+'],
            'suggested_name': 'Almacenamiento',
            'adobe_filter_prefix': 'almacenamiento:',
        },
        
        # CONECTIVIDAD (patrones corregidos)
        'connectivity_5g': {
            'category': 'conectividad',
            'patterns': [r'/5g/', r'/5g$', r'-5g-', r'-5g$'],
            'suggested_name': 'Conectividad 5G',
            'adobe_filter_prefix': 'conectividad:',
        },
        'connectivity_wifi': {
            'category': 'conectividad',
            'patterns': [r'wifi-?\d*', r'wi-fi', r'wireless'],
            'suggested_name': 'WiFi',
            'adobe_filter_prefix': 'conectividad:',
        },
        'connectivity_bluetooth': {
            'category': 'conectividad',
            'patterns': [r'bluetooth', r'-bt-', r'-bt$'],
            'suggested_name': 'Bluetooth',
            'adobe_filter_prefix': 'conectividad:',
        },
        'connectivity_nfc': {
            'category': 'conectividad',
            'patterns': [r'/nfc/', r'/nfc$', r'-nfc-', r'-nfc$'],
            'suggested_name': 'NFC',
            'adobe_filter_prefix': 'conectividad:',
        },
        'dual_sim': {
            'category': 'conectividad',
            'patterns': [r'dual-?sim', r'doble-?sim'],
            'suggested_name': 'Dual SIM',
            'adobe_filter_prefix': None,
        },
        
        # ESTADO / CONDICIÓN
        'condition_new': {
            'category': 'estado',
            'patterns': [r'/nuevo/', r'/nuevo$', r'-nuevo-', r'-nuevos'],
            'suggested_name': 'Nuevo',
            'adobe_filter_prefix': 'estado del articulo:',
        },
        'condition_refurbished': {
            'category': 'estado',
            'patterns': [r'reacondicionado', r'refurbished', r'seminuevo', r'segunda-mano'],
            'suggested_name': 'Reacondicionado',
            'adobe_filter_prefix': 'estado del articulo:',
        },
        
        # PRECIO
        'price_range': {
            'category': 'precio',
            'patterns': [r'precio', r'barato', r'economico', r'gama-alta', r'gama-media', r'gama-baja'],
            'suggested_name': 'Rango de Precio',
            'adobe_filter_prefix': 'price:',
        },
        'price_offer': {
            'category': 'precio',
            'patterns': [r'oferta', r'descuento', r'promocion', r'outlet', r'liquidacion'],
            'suggested_name': 'Ofertas',
            'adobe_filter_prefix': None,
        },
        
        # VALORACIÓN
        'rating': {
            'category': 'valoracion',
            'patterns': [r'estrellas', r'valorado', r'rating', r'puntuacion'],
            'suggested_name': 'Valoración',
            'adobe_filter_prefix': 'valoracion:',
        },
        
        # COLORES
        'color': {
            'category': 'color',
            'patterns': [
                r'/negro/', r'/blanco/', r'/azul/', r'/rojo/', r'/verde/',
                r'/rosa/', r'/dorado/', r'/plata/', r'/gris/', r'/naranja/',
                r'-negro-', r'-blanco-', r'-azul-', r'-rojo-'
            ],
            'suggested_name': 'Color',
            'adobe_filter_prefix': 'color:',
        },
        
        # EFICIENCIA ENERGÉTICA
        'energy_class': {
            'category': 'eficiencia',
            'patterns': [r'clase-[a-g]', r'eficiencia-energetica', r'energy-star'],
            'suggested_name': 'Clase Energética',
            'adobe_filter_prefix': 'eficiencia energetica:',
        },
        
        # POTENCIA / RENDIMIENTO
        'power': {
            'category': 'potencia',
            'patterns': [r'\d+-?w(?:/|$)', r'vatios', r'watts', r'potencia-\d+'],
            'suggested_name': 'Potencia',
            'adobe_filter_prefix': 'potencia:',
        },
        'processor': {
            'category': 'rendimiento',
            'patterns': [
                r'intel', r'amd', r'ryzen', r'core-i\d', 
                r'snapdragon', r'mediatek', r'apple-m\d', r'exynos'
            ],
            'suggested_name': 'Procesador',
            'adobe_filter_prefix': 'procesador:',
        },
        
        # CARACTERÍSTICAS ESPECIALES
        'feature_waterproof': {
            'category': 'caracteristicas',
            'patterns': [r'resistente-agua', r'waterproof', r'sumergible', r'ip\d{2}'],
            'suggested_name': 'Resistente al Agua',
            'adobe_filter_prefix': None,
        },
        'feature_fast_charge': {
            'category': 'caracteristicas',
            'patterns': [r'carga-rapida', r'fast-?charge', r'quick-?charge'],
            'suggested_name': 'Carga Rápida',
            'adobe_filter_prefix': None,
        },
        
        # RUIDO
        'noise_level': {
            'category': 'ruido',
            'patterns': [r'\d+-?db', r'silencioso', r'bajo-ruido', r'decibelios'],
            'suggested_name': 'Nivel de Ruido',
            'adobe_filter_prefix': 'ruido:',
        },
        
        # TIPO / FORMATO
        'type_format': {
            'category': 'tipo',
            'patterns': [r'portatil', r'sobremesa', r'torre', r'compacto', r'mini', r'profesional'],
            'suggested_name': 'Tipo/Formato',
            'adobe_filter_prefix': 'tipo:',
        },
    }
    
    # Marcas conocidas por categoría
    KNOWN_BRANDS = {
        'tech': [
            'apple', 'samsung', 'xiaomi', 'huawei', 'oppo', 'realme', 'motorola',
            'google', 'honor', 'poco', 'nothing', 'oneplus', 'sony', 'lg', 'asus',
            'lenovo', 'hp', 'dell', 'acer', 'msi', 'razer', 'corsair', 'logitech'
        ],
        'appliances': [
            'bosch', 'siemens', 'balay', 'lg', 'samsung', 'whirlpool', 'electrolux',
            'aeg', 'miele', 'candy', 'beko', 'haier', 'hisense', 'teka', 'zanussi'
        ],
        'hvac': [
            'daikin', 'mitsubishi', 'fujitsu', 'lg', 'samsung', 'panasonic', 'hitachi',
            'carrier', 'toshiba', 'gree', 'haier', 'hisense'
        ],
        'tools': [
            'bosch', 'makita', 'dewalt', 'milwaukee', 'hikoki', 'metabo', 'black-decker',
            'stanley', 'ryobi', 'einhell', 'worx'
        ],
    }
    
    def __init__(self, crawl_df: pd.DataFrame, base_url: str = ""):
        """
        Inicializa el detector
        
        Args:
            crawl_df: DataFrame con columna 'Dirección' (URLs)
            base_url: URL base para extraer el path de categoría
        """
        self.crawl = crawl_df
        self.base_url = base_url
        self.urls = crawl_df['Dirección'].tolist() if 'Dirección' in crawl_df.columns else []
        self.detected_facets: List[FacetMapping] = []
        
        self.category_path = ""
        if base_url:
            try:
                from urllib.parse import urlparse
                self.category_path = urlparse(base_url).path.strip('/')
            except Exception:
                pass
    
    def _detect_brands(self) -> List[str]:
        """Detecta marcas presentes en las URLs"""
        all_brands = set()
        for brands in self.KNOWN_BRANDS.values():
            all_brands.update(brands)
        
        found_brands = []
        for brand in all_brands:
            pattern = f'/{brand}(/|$)'
            try:
                count = sum(1 for url in self.urls if re.search(pattern, url.lower()))
                if count > 5:
                    found_brands.append(brand)
            except Exception:
                continue
        
        return sorted(
            found_brands, 
            key=lambda b: sum(1 for u in self.urls if f'/{b}/' in u.lower()), 
            reverse=True
        )
    
    def detect_all(self) -> List[FacetMapping]:
        """Detecta todas las facetas en las URLs"""
        self.detected_facets = []
        
        # Detectar marcas dinámicamente
        found_brands = self._detect_brands()
        if found_brands:
            brand_patterns = [f'/{b}/' for b in found_brands[:30]]
            brand_pattern = '|'.join(brand_patterns)
            self._add_facet_if_found(
                facet_id='brand',
                facet_name='Marcas',
                pattern=brand_pattern,
                category='marca',
                adobe_filter_prefix='marcas:'
            )
        
        # Detectar facetas de patrones genéricos
        for facet_id, config in self.GENERIC_PATTERNS.items():
            if config.get('dynamic'):
                continue
            
            valid_patterns = []
            for p in config['patterns']:
                is_valid, _ = validate_regex_pattern(p)
                if is_valid:
                    valid_patterns.append(p)
            
            if valid_patterns:
                combined_pattern = '|'.join(valid_patterns)
                self._add_facet_if_found(
                    facet_id=facet_id,
                    facet_name=config['suggested_name'],
                    pattern=combined_pattern,
                    category=config['category'],
                    adobe_filter_prefix=config.get('adobe_filter_prefix')
                )
        
        return self.detected_facets
    
    def _add_facet_if_found(self, facet_id: str, facet_name: str, pattern: str,
                           category: str, adobe_filter_prefix: str = None):
        """Añade una faceta si se encuentran URLs que coinciden"""
        is_valid, error = validate_regex_pattern(pattern)
        if not is_valid:
            return
        
        try:
            if 'Código de respuesta' in self.crawl.columns:
                urls_200 = self.crawl[
                    (self.crawl['Código de respuesta'] == 200) &
                    (self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True))
                ]
                urls_404 = self.crawl[
                    (self.crawl['Código de respuesta'] == 404) &
                    (self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True))
                ]
            else:
                urls_200 = self.crawl[
                    self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True)
                ]
                urls_404 = pd.DataFrame()
            
            if len(urls_200) > 0 or len(urls_404) > 0:
                examples = urls_200['Dirección'].head(5).tolist() if len(urls_200) > 0 else urls_404['Dirección'].head(5).tolist()
                
                self.detected_facets.append(FacetMapping(
                    facet_id=facet_id,
                    facet_name=facet_name,
                    pattern=pattern,
                    url_examples=examples,
                    url_count_200=len(urls_200),
                    url_count_404=len(urls_404),
                    adobe_filter_match=adobe_filter_prefix,
                    user_verified=False,
                    category=category
                ))
        except Exception:
            pass
    
    def detect_unknown_patterns(self) -> List[Dict]:
        """Detecta patrones en URLs que no coinciden con facetas conocidas"""
        all_segments = {}
        
        for url in self.urls:
            path = url.lower()
            if self.category_path:
                path = path.split(self.category_path)[-1] if self.category_path in path else path
            
            parts = path.strip('/').split('/')
            for part in parts:
                segments = part.split('-')
                for seg in segments:
                    if len(seg) > 2 and seg.isalpha():
                        if seg not in all_segments:
                            all_segments[seg] = {'count': 0, 'urls': []}
                        all_segments[seg]['count'] += 1
                        if len(all_segments[seg]['urls']) < 3:
                            all_segments[seg]['urls'].append(url)
        
        known_patterns = []
        for config in self.GENERIC_PATTERNS.values():
            known_patterns.extend(config.get('patterns', []))
        for brands in self.KNOWN_BRANDS.values():
            known_patterns.extend(brands)
        
        unknown = []
        for segment, data in all_segments.items():
            if data['count'] > 10:
                is_known = False
                for p in known_patterns:
                    if p:
                        try:
                            if re.search(p, segment, re.IGNORECASE):
                                is_known = True
                                break
                        except Exception:
                            continue
                
                is_known = is_known or segment in [b for brands in self.KNOWN_BRANDS.values() for b in brands]
                
                if not is_known:
                    unknown.append({
                        'segment': segment,
                        'count': data['count'],
                        'example_urls': data['urls']
                    })
        
        return sorted(unknown, key=lambda x: x['count'], reverse=True)[:20]
    
    def add_custom_facet(self, name: str, pattern: str, category: str = 'custom') -> Optional[FacetMapping]:
        """Añade una faceta personalizada"""
        is_valid, error = validate_regex_pattern(pattern)
        if not is_valid:
            return None
        
        facet_id = f"custom_{name.lower().replace(' ', '_')}"
        
        try:
            if 'Código de respuesta' in self.crawl.columns:
                urls_200 = self.crawl[
                    (self.crawl['Código de respuesta'] == 200) &
                    (self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True))
                ]
                urls_404 = self.crawl[
                    (self.crawl['Código de respuesta'] == 404) &
                    (self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True))
                ]
            else:
                urls_200 = self.crawl[
                    self.crawl['Dirección'].str.contains(pattern, case=False, na=False, regex=True)
                ]
                urls_404 = pd.DataFrame()
        except Exception:
            urls_200 = pd.DataFrame()
            urls_404 = pd.DataFrame()
        
        facet = FacetMapping(
            facet_id=facet_id,
            facet_name=name,
            pattern=pattern,
            url_examples=urls_200['Dirección'].head(5).tolist() if len(urls_200) > 0 else [],
            url_count_200=len(urls_200),
            url_count_404=len(urls_404),
            user_verified=True,
            category=category,
            is_custom=True
        )
        
        self.detected_facets.append(facet)
        return facet


def render_data_period_config(data_sources: Dict[str, Any]) -> List[DataSourceConfig]:
    """Renderiza UI para configurar períodos de cada archivo"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
    st.subheader("📅 Configurar Períodos de Datos")
    
    st.info("""
    Indica el período que cubre cada archivo para contextualizar los análisis.
    """)
    
    configs = []
    
    for name, info in data_sources.items():
        with st.expander(f"📄 {name}", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input(
                    "Fecha inicio",
                    key=f"start_{name}",
                    format="DD/MM/YYYY"
                )
            
            with col2:
                end_date = st.date_input(
                    "Fecha fin",
                    key=f"end_{name}",
                    format="DD/MM/YYYY"
                )
            
            description = st.text_input(
                "Descripción",
                key=f"desc_{name}",
                placeholder="Ej: Tráfico SEO Q4 2025"
            )
            
            if isinstance(info, dict):
                st.caption(f"Tipo: `{info.get('file_type', 'desconocido')}` | Filas: {info.get('row_count', 'N/A'):,}")
            
            config = DataSourceConfig(
                name=name,
                file_type=info.get('file_type', 'unknown') if isinstance(info, dict) else 'unknown',
                filepath=name,
                period_start=datetime.combine(start_date, datetime.min.time()) if start_date else None,
                period_end=datetime.combine(end_date, datetime.max.time()) if end_date else None,
                description=description,
                row_count=info.get('row_count', 0) if isinstance(info, dict) else 0
            )
            configs.append(config)
    
    return configs


def render_facet_mapping_ui(detected_facets: List[FacetMapping],
                            unknown_patterns: List[Dict] = None) -> List[FacetMapping]:
    """Renderiza UI interactiva para mapear y verificar facetas"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
    st.subheader("🏷️ Configurar Facetas")
    
    verified_facets = []
    unknown_patterns = unknown_patterns or []
    
    # Agrupar facetas por categoría
    facets_by_category = {}
    for facet in detected_facets:
        cat = facet.category or 'otros'
        if cat not in facets_by_category:
            facets_by_category[cat] = []
        facets_by_category[cat].append(facet)
    
    tab1, tab2, tab3 = st.tabs([
        f"📋 Detectadas ({len(detected_facets)})",
        f"❓ Desconocidas ({len(unknown_patterns)})",
        "➕ Crear Nueva"
    ])
    
    with tab1:
        if not detected_facets:
            st.info("No se detectaron facetas. Asegúrate de que el crawl tenga URLs con patrones de filtros.")
        else:
            for category, facets in sorted(facets_by_category.items()):
                st.markdown(f"### {category.title()}")
                
                for facet in facets:
                    icon = "✅" if facet.user_verified else "🔍"
                    with st.expander(
                        f"{icon} {facet.facet_name} ({facet.url_count_200} URLs activas)",
                        expanded=False
                    ):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_name = st.text_input(
                                "Nombre",
                                value=facet.facet_name,
                                key=f"name_{facet.facet_id}"
                            )
                            
                            new_pattern = st.text_input(
                                "Patrón regex",
                                value=facet.pattern,
                                key=f"pattern_{facet.facet_id}",
                                help="Expresión regular para detectar URLs"
                            )
                            
                            # Validar patrón
                            is_valid, error = validate_regex_pattern(new_pattern)
                            if not is_valid:
                                st.error(f"⚠️ {error}")
                            
                            adobe_match = st.text_input(
                                "Prefijo Adobe Analytics",
                                value=facet.adobe_filter_match or "",
                                key=f"adobe_{facet.facet_id}",
                                placeholder="Ej: marcas:"
                            )
                        
                        with col2:
                            st.metric("URLs Activas", facet.url_count_200)
                            st.metric("URLs 404", facet.url_count_404)
                        
                        if facet.url_examples:
                            st.caption("**Ejemplos:**")
                            for url in facet.url_examples[:3]:
                                display_url = url.split('.com')[-1] if '.com' in url else url
                                st.code(display_url[:80], language=None)
                        
                        notes = st.text_area(
                            "Notas",
                            value=facet.notes,
                            key=f"notes_{facet.facet_id}",
                            height=60
                        )
                        
                        verified = st.checkbox(
                            "✅ Verificado",
                            value=facet.user_verified,
                            key=f"verified_{facet.facet_id}"
                        )
                        
                        if is_valid:
                            verified_facets.append(FacetMapping(
                                facet_id=facet.facet_id,
                                facet_name=new_name,
                                pattern=new_pattern,
                                url_examples=facet.url_examples,
                                url_count_200=facet.url_count_200,
                                url_count_404=facet.url_count_404,
                                adobe_filter_match=adobe_match if adobe_match else None,
                                user_verified=verified,
                                notes=notes,
                                category=facet.category,
                                is_custom=facet.is_custom
                            ))
    
    with tab2:
        if unknown_patterns:
            st.markdown("**Patrones encontrados que no coinciden con facetas conocidas:**")
            
            for pattern in unknown_patterns:
                with st.expander(f"❓ `{pattern['segment']}` ({pattern['count']} URLs)"):
                    for url in pattern['example_urls']:
                        display_url = url.split('.com')[-1] if '.com' in url else url
                        st.code(display_url[:80], language=None)
                    
                    if st.button(f"Crear faceta para '{pattern['segment']}'", key=f"create_{pattern['segment']}"):
                        st.session_state['new_facet_pattern'] = pattern['segment']
                        st.info("Ve a la pestaña 'Crear Nueva' para completar")
        else:
            st.success("✅ No hay patrones desconocidos significativos")
    
    with tab3:
        st.markdown("**Crear faceta personalizada:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input("Nombre de la faceta", key="new_facet_name")
            new_pattern = st.text_input(
                "Patrón regex",
                key="new_facet_pattern_input",
                value=st.session_state.get('new_facet_pattern', ''),
                help="Expresión regular. Ej: 'mi-filtro|otro-filtro'"
            )
            
            # Validar patrón nuevo
            if new_pattern:
                is_valid, error = validate_regex_pattern(new_pattern)
                if not is_valid:
                    st.error(f"⚠️ {error}")
        
        with col2:
            new_category = st.selectbox(
                "Categoría",
                options=[
                    'marca', 'tamaño', 'memoria', 'conectividad', 'estado',
                    'precio', 'color', 'caracteristicas', 'otros'
                ],
                key="new_facet_category"
            )
            new_adobe = st.text_input(
                "Prefijo Adobe (opcional)",
                key="new_facet_adobe",
                placeholder="Ej: mi-filtro:"
            )
        
        if st.button("➕ Crear Faceta", type="primary") and new_name and new_pattern:
            is_valid, error = validate_regex_pattern(new_pattern)
            if is_valid:
                new_facet = FacetMapping(
                    facet_id=f"custom_{new_name.lower().replace(' ', '_')}",
                    facet_name=new_name,
                    pattern=new_pattern,
                    url_examples=[],
                    url_count_200=0,
                    url_count_404=0,
                    adobe_filter_match=new_adobe if new_adobe else None,
                    user_verified=True,
                    category=new_category,
                    is_custom=True
                )
                verified_facets.append(new_facet)
                st.success(f"✅ Faceta '{new_name}' creada")
            else:
                st.error(f"No se puede crear: {error}")
    
    return verified_facets
