"""
Facet Architecture Analyzer v2.3
Aplicación principal de Streamlit
Herramienta genérica para análisis de arquitectura de facetas SEO
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import tempfile
import os

# Configuración de página (debe ser lo primero)
st.set_page_config(
    page_title="Facet Architecture Analyzer v2.3",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Imports de módulos propios
from data.loaders import DataLoader, FileType, LoadResult, validate_data_integrity
from data.family_library import FamilyLibrary, FamilyMetadata, get_default_library
from data.data_config import (
    FacetDetector, FacetMapping, DatasetContext,
    render_facet_mapping_ui, validate_regex_pattern
)
from data.drive_storage import HybridLibraryStorage, render_drive_config_ui

from analysis.authority_analyzer import AuthorityAnalyzer, get_wrapper_distribution
from analysis.facet_analyzer import FacetAnalyzer
from analysis.scoring import FacetScorer, generate_scoring_report

from config.settings import (
    AI_CONFIGS, ANALYSIS_THRESHOLDS, DATA_KEYS, CRAWL_KEYS_PRIORITY
)

# =============================================================================
# CONSTANTES Y CONFIGURACIÓN
# =============================================================================

VERSION = "2.3"

# Claves de datos unificadas (desde settings.py)
UNIFIED_DATA_KEYS = DATA_KEYS

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def init_session_state():
    """Inicializa el estado de sesión"""
    defaults = {
        'loaded_data': {},
        'current_family': None,
        'family_metadata': None,
        'facet_mappings': [],
        'analysis_results': {},
        'dataset_context': None,
        'data_loaded': False,
        'active_tab': 'home',
        'last_error': None,
        'last_warning': None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_error(message: str):
    """Muestra un error y lo guarda en session_state"""
    st.error(f"❌ {message}")
    st.session_state['last_error'] = message


def show_warning(message: str):
    """Muestra un warning y lo guarda en session_state"""
    st.warning(f"⚠️ {message}")
    st.session_state['last_warning'] = message


def show_success(message: str):
    """Muestra un mensaje de éxito"""
    st.success(f"✅ {message}")


def get_crawl_data() -> Optional[pd.DataFrame]:
    """
    Obtiene el crawl principal usando claves unificadas
    Prioridad: crawl_master > crawl_gsc > crawl_historical
    """
    data = st.session_state.get('loaded_data', {})
    
    for key in CRAWL_KEYS_PRIORITY:
        if key in data and data[key] is not None:
            return data[key]
    
    return None


def get_data_by_key(key: str) -> Optional[pd.DataFrame]:
    """Obtiene datos por clave unificada"""
    return st.session_state.get('loaded_data', {}).get(key)


# =============================================================================
# CARGA DE DATOS
# =============================================================================

def process_uploaded_files(uploaded_files: List) -> Dict[str, LoadResult]:
    """Procesa archivos subidos y retorna resultados"""
    results = {}
    loader = DataLoader()
    
    for uploaded_file in uploaded_files:
        try:
            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            # Cargar y detectar tipo - pasar nombre original para detección
            result = loader.load_file(tmp_path, original_filename=uploaded_file.name)
            results[uploaded_file.name] = result
            
            # Limpiar temporal
            os.unlink(tmp_path)
            
        except Exception as e:
            results[uploaded_file.name] = LoadResult(
                success=False,
                file_type=FileType.UNKNOWN,
                error=str(e)
            )
    
    return results


def process_loaded_data(results: Dict[str, LoadResult]) -> bool:
    """
    Procesa resultados de carga y actualiza session_state
    Retorna True si se cargó al menos un archivo exitosamente
    """
    loaded_count = 0
    error_count = 0
    warnings = []
    
    for filename, result in results.items():
        if result.success and result.dataframe is not None:
            # Usar clave unificada basada en el tipo de archivo
            key = result.file_type.value
            st.session_state['loaded_data'][key] = result.dataframe
            loaded_count += 1
            
            # Mostrar info
            st.success(f"✅ **{filename}** → `{key}` ({result.row_count:,} filas)")
            
            # Mostrar warnings del archivo
            if result.warnings:
                for w in result.warnings:
                    st.caption(f"  ⚠️ {w}")
                    warnings.append(f"{filename}: {w}")
        else:
            error_count += 1
            error_msg = result.error if result.error else "Error desconocido"
            st.error(f"❌ **{filename}**: {error_msg}")
    
    # Feedback consolidado
    if loaded_count == 0 and error_count > 0:
        show_error("No se pudo cargar ningún archivo. Verifica el formato de los CSVs.")
        return False
    elif loaded_count > 0:
        st.session_state['data_loaded'] = True
        
        # Validar integridad de datos
        validation = validate_data_integrity(st.session_state['loaded_data'])
        if not validation['valid']:
            for w in validation.get('warnings', []):
                show_warning(w)
        
        return True
    else:
        show_warning("No se subieron archivos para procesar.")
        return False


def load_family_data(family_id: str) -> bool:
    """Carga datos de una familia guardada"""
    try:
        library = get_default_library()
        
        if not library.family_exists(family_id):
            show_error(f"Familia '{family_id}' no encontrada")
            return False
        
        # Cargar datos con claves unificadas
        data = library.load_family_data(family_id)
        
        if not data:
            show_error("La familia no contiene datos")
            return False
        
        # Actualizar session_state
        st.session_state['loaded_data'] = data
        st.session_state['current_family'] = family_id
        st.session_state['family_metadata'] = library.get_family(family_id)
        st.session_state['data_loaded'] = True
        
        show_success(f"Familia '{family_id}' cargada con {len(data)} datasets")
        return True
        
    except Exception as e:
        show_error(f"Error cargando familia: {str(e)}")
        return False


# =============================================================================
# COMPONENTES DE UI
# =============================================================================

def render_sidebar():
    """Renderiza la barra lateral"""
    with st.sidebar:
        st.image("https://raw.githubusercontent.com/streamlit/streamlit/develop/lib/streamlit/static/logo.svg", width=50)
        st.title("Facet Analyzer")
        st.caption(f"v{VERSION}")
        
        st.divider()
        
        # Estado de datos
        if st.session_state.get('data_loaded'):
            data = st.session_state.get('loaded_data', {})
            
            st.success("📊 Datos cargados")
            
            # Mostrar datasets disponibles
            for key in CRAWL_KEYS_PRIORITY + ['adobe_urls', 'adobe_filters', 'semrush', 'keyword_planner']:
                if key in data:
                    df = data[key]
                    st.caption(f"✓ {key}: {len(df):,} filas")
            
            # Info de familia actual
            if st.session_state.get('current_family'):
                st.info(f"📁 Familia: {st.session_state['current_family']}")
        else:
            st.warning("⚠️ Sin datos cargados")
        
        st.divider()
        
        # Navegación
        st.subheader("📑 Navegación")
        
        tabs = {
            'home': '🏠 Inicio',
            'load': '📁 Cargar Datos',
            'config': '⚙️ Configurar Facetas',
            'authority': '🔗 Análisis Autoridad',
            'facets': '🏷️ Análisis Facetas',
            'strategy': '📊 Estrategia',
            'export': '📤 Exportar',
        }
        
        for key, label in tabs.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state['active_tab'] = key
                st.rerun()
        
        st.divider()
        
        # Acciones rápidas
        if st.session_state.get('data_loaded'):
            st.subheader("⚡ Acciones")
            
            if st.button("🔄 Recargar datos", use_container_width=True):
                st.session_state['loaded_data'] = {}
                st.session_state['data_loaded'] = False
                st.rerun()


def render_home_tab():
    """Renderiza la pestaña de inicio"""
    st.title("🔍 Facet Architecture Analyzer")
    st.caption(f"v{VERSION} - Herramienta de análisis SEO para arquitectura de facetas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 ¿Qué hace esta herramienta?
        
        Analiza la arquitectura de enlaces internos en páginas de filtros/facetas de e-commerce:
        
        1. **Fuga de Autoridad**: Detecta páginas que no distribuyen PageRank
        2. **Análisis de Facetas**: Evalúa demanda vs estado actual
        3. **Scoring**: Prioriza facetas por potencial SEO
        4. **Estrategia**: Genera recomendaciones de enlazado interno
        """)
    
    with col2:
        st.markdown("""
        ### 📁 Archivos Soportados
        
        | Tipo | Descripción |
        |------|-------------|
        | Crawl Master | Screaming Frog + extracción seoFilterWrapper |
        | Crawl GSC | Screaming Frog + datos de Search Console |
        | Adobe URLs | Tráfico SEO por URL |
        | Adobe Filters | Demanda por filtros |
        | SEMrush | Keywords con volumen |
        | Keyword Planner | Volúmenes de Google Ads |
        """)
    
    st.divider()
    
    # Estado actual
    if st.session_state.get('data_loaded'):
        st.success("✅ Datos cargados - Navega a las pestañas de análisis")
        
        crawl = get_crawl_data()
        if crawl is not None:
            col1, col2, col3, col4 = st.columns(4)
            
            status_col = 'Código de respuesta' if 'Código de respuesta' in crawl.columns else None
            
            with col1:
                st.metric("URLs Totales", f"{len(crawl):,}")
            
            with col2:
                if status_col:
                    urls_200 = len(crawl[crawl[status_col] == 200])
                    st.metric("URLs 200", f"{urls_200:,}")
            
            with col3:
                if status_col:
                    urls_404 = len(crawl[crawl[status_col] == 404])
                    st.metric("URLs 404", f"{urls_404:,}")
            
            with col4:
                if 'has_wrapper' in crawl.columns and status_col:
                    crawl_200 = crawl[crawl[status_col] == 200]
                    with_wrapper = len(crawl_200[crawl_200['has_wrapper'] == True])
                    st.metric("Con Wrapper", f"{with_wrapper:,}")
    else:
        st.info("👈 Ve a **Cargar Datos** para comenzar")


def render_load_tab():
    """Renderiza la pestaña de carga de datos"""
    st.title("📁 Cargar Datos")
    
    tab1, tab2, tab3 = st.tabs(["📤 Subir Archivos", "📚 Biblioteca", "☁️ Google Drive"])
    
    with tab1:
        st.subheader("Subir archivos CSV")
        
        st.info("""
        **Archivos recomendados:**
        - **Obligatorio**: Crawl Master (Screaming Frog con extracción de seoFilterWrapper)
        - **Recomendado**: Adobe URLs (tráfico SEO), Adobe Filters (demanda filtros)
        - **Opcional**: SEMrush, Keyword Planner, Crawl GSC
        """)
        
        uploaded_files = st.file_uploader(
            "Selecciona uno o más archivos CSV",
            type=['csv'],
            accept_multiple_files=True,
            key="file_uploader"
        )
        
        if uploaded_files:
            if st.button("🚀 Procesar Archivos", type="primary"):
                with st.spinner("Procesando archivos..."):
                    results = process_uploaded_files(uploaded_files)
                    success = process_loaded_data(results)
                    
                    if success:
                        st.balloons()
    
    with tab2:
        st.subheader("📚 Biblioteca de Familias")
        
        library = get_default_library()
        families = library.list_families()
        
        if families:
            for family in families:
                with st.expander(f"📁 {family['name']}", expanded=False):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.caption(f"URLs: {family.get('total_urls', 'N/A'):,}")
                        st.caption(f"Tráfico: {family.get('total_traffic', 'N/A'):,}")
                        
                        badges = []
                        if family.get('has_crawl_master'):
                            badges.append("Crawl ✓")
                        if family.get('has_adobe_urls'):
                            badges.append("Adobe ✓")
                        if family.get('has_semrush'):
                            badges.append("SEMrush ✓")
                        
                        if badges:
                            st.caption(" | ".join(badges))
                    
                    with col2:
                        if st.button("📥 Cargar", key=f"load_{family['id']}"):
                            if load_family_data(family['id']):
                                st.rerun()
        else:
            st.info("No hay familias guardadas. Sube archivos y guárdalos como familia.")
        
        st.divider()
        
        # Crear nueva familia
        st.subheader("➕ Crear Nueva Familia")
        
        with st.form("new_family_form"):
            name = st.text_input("Nombre de la familia", placeholder="Ej: Smartphones")
            description = st.text_area("Descripción", placeholder="Descripción de la categoría")
            base_url = st.text_input("URL Base", placeholder="https://www.example.com/smartphones")
            
            submitted = st.form_submit_button("💾 Guardar como Familia")
            
            if submitted and name and st.session_state.get('data_loaded'):
                try:
                    # Guardar datos actuales como familia
                    data = st.session_state.get('loaded_data', {})
                    
                    # Crear familia con los archivos disponibles
                    metadata = library.create_family(
                        name=name,
                        description=description,
                        base_url=base_url
                    )
                    
                    # Añadir archivos disponibles
                    for key, df in data.items():
                        try:
                            # Guardar temporalmente y añadir
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w') as tmp:
                                df.to_csv(tmp.name, index=False)
                                
                                file_type = FileType(key) if key in [ft.value for ft in FileType] else FileType.UNKNOWN
                                library.add_file_to_family(metadata.id, tmp.name, file_type)
                                
                                os.unlink(tmp.name)
                        except Exception as e:
                            st.warning(f"No se pudo añadir {key}: {e}")
                    
                    st.session_state['current_family'] = metadata.id
                    st.session_state['family_metadata'] = metadata
                    show_success(f"Familia '{name}' creada exitosamente")
                    st.rerun()
                    
                except Exception as e:
                    show_error(f"Error creando familia: {e}")
    
    with tab3:
        render_drive_config_ui()


def render_config_tab():
    """Renderiza la pestaña de configuración de facetas"""
    st.title("⚙️ Configurar Facetas")
    
    if not st.session_state.get('data_loaded'):
        st.warning("⚠️ Primero debes cargar datos")
        return
    
    crawl = get_crawl_data()
    
    if crawl is None:
        st.error("No hay crawl disponible para detectar facetas")
        return
    
    # URL base
    family_meta = st.session_state.get('family_metadata')
    default_base_url = family_meta.base_url if family_meta and hasattr(family_meta, 'base_url') else ""
    
    base_url = st.text_input(
        "URL Base de la Categoría",
        value=default_base_url,
        placeholder="https://www.example.com/categoria"
    )
    
    st.divider()
    
    # Detectar facetas
    if st.button("🔍 Detectar Facetas Automáticamente", type="primary"):
        with st.spinner("Analizando URLs..."):
            detector = FacetDetector(crawl, base_url)
            detected = detector.detect_all()
            unknown = detector.detect_unknown_patterns()
            
            st.session_state['facet_mappings'] = detected
            st.session_state['unknown_patterns'] = unknown
            
            show_success(f"Detectadas {len(detected)} facetas")
    
    # Mostrar facetas detectadas
    if st.session_state.get('facet_mappings'):
        verified = render_facet_mapping_ui(
            st.session_state['facet_mappings'],
            st.session_state.get('unknown_patterns', [])
        )
        
        if st.button("💾 Guardar Configuración"):
            st.session_state['facet_mappings'] = verified
            show_success(f"Guardadas {len(verified)} facetas")


def render_authority_tab():
    """Renderiza la pestaña de análisis de autoridad"""
    st.title("🔗 Análisis de Autoridad")
    
    if not st.session_state.get('data_loaded'):
        st.warning("⚠️ Primero debes cargar datos")
        return
    
    crawl = get_crawl_data()
    adobe_urls = get_data_by_key('adobe_urls')
    
    if crawl is None:
        st.error("No hay crawl disponible para el análisis")
        return
    
    # Ejecutar análisis
    if st.button("▶️ Ejecutar Análisis de Autoridad", type="primary"):
        with st.spinner("Analizando fuga de autoridad..."):
            analyzer = AuthorityAnalyzer(crawl, adobe_urls)
            result = analyzer.get_full_analysis()
            
            st.session_state['analysis_results']['authority'] = result
            show_success("Análisis completado")
    
    # Mostrar resultados
    if 'authority' in st.session_state.get('analysis_results', {}):
        result = st.session_state['analysis_results']['authority']
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Fugas Detectadas", result.total_leaks)
        
        with col2:
            st.metric("Tráfico Afectado", f"{result.total_traffic_affected:,}")
        
        with col3:
            st.metric("URLs 404", result.dead_ends_count)
        
        with col4:
            st.metric("Tráfico Perdido", f"{result.dead_ends_traffic:,}")
        
        st.divider()
        
        # Resumen
        st.markdown(result.summary)
        
        # Tabla de fugas
        if result.top_leaks:
            st.subheader("📋 Top Fugas de Autoridad")
            
            leaks_df = pd.DataFrame([l.to_dict() for l in result.top_leaks])
            st.dataframe(
                leaks_df,
                use_container_width=True,
                hide_index=True
            )
        
        # Distribución de wrapper
        st.subheader("📊 Distribución de Enlaces en seoFilterWrapper")
        distribution = get_wrapper_distribution(crawl)
        st.bar_chart(distribution.set_index('range')['count'])


def render_facets_tab():
    """Renderiza la pestaña de análisis de facetas"""
    st.title("🏷️ Análisis de Facetas")
    
    if not st.session_state.get('data_loaded'):
        st.warning("⚠️ Primero debes cargar datos")
        return
    
    if not st.session_state.get('facet_mappings'):
        st.warning("⚠️ Primero debes configurar las facetas")
        return
    
    crawl = get_crawl_data()
    adobe_urls = get_data_by_key('adobe_urls')
    adobe_filters = get_data_by_key('adobe_filters')
    # Obtener keywords (semrush tiene prioridad si tiene datos, sino keyword_planner)
    keywords = get_data_by_key('semrush')
    if keywords is None or len(keywords) == 0:
        kp = get_data_by_key('keyword_planner')
        if kp is not None and len(kp) > 0:
            keywords = kp
    
    if crawl is None:
        st.error("No hay crawl disponible")
        return
    
    # URL base
    family_meta = st.session_state.get('family_metadata')
    base_url = family_meta.base_url if family_meta and hasattr(family_meta, 'base_url') else ""
    
    # Ejecutar análisis
    if st.button("▶️ Ejecutar Análisis de Facetas", type="primary"):
        with st.spinner("Analizando facetas..."):
            analyzer = FacetAnalyzer(
                crawl_df=crawl,
                adobe_urls_df=adobe_urls,
                adobe_filters_df=adobe_filters,
                keywords_df=keywords,
                facet_mappings=st.session_state['facet_mappings'],
                base_url=base_url
            )
            
            result = analyzer.analyze_all_facets()
            st.session_state['analysis_results']['facets'] = result
            show_success("Análisis completado")
    
    # Mostrar resultados
    if 'facets' in st.session_state.get('analysis_results', {}):
        result = st.session_state['analysis_results']['facets']
        
        # Resumen
        st.markdown(result.summary)
        
        # Alertas
        if result.alerts:
            st.subheader("⚠️ Alertas")
            for alert in result.alerts:
                st.warning(alert)
        
        # Tabla de facetas
        if result.facets:
            st.subheader("📋 Estado de Facetas")
            
            facets_df = pd.DataFrame([f.to_dict() for f in result.facets])
            
            # Ordenar por opportunity_score
            facets_df = facets_df.sort_values('opportunity_score', ascending=False)
            
            st.dataframe(
                facets_df,
                use_container_width=True,
                hide_index=True
            )
        
        # Oportunidades
        if result.opportunities:
            st.subheader("🚀 Oportunidades Detectadas")
            
            for opp in result.opportunities[:10]:
                with st.expander(f"**{opp.name}** - Score: {opp.opportunity_score:.0f}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("URLs Activas", opp.urls_200)
                        st.metric("Demanda Adobe", f"{opp.demand_adobe:,}")
                    
                    with col2:
                        st.metric("Tráfico SEO", f"{opp.traffic_seo:,}")
                        st.metric("En Wrapper", "✅" if opp.in_wrapper else "❌")
                    
                    st.info(opp.recommendation)


def render_strategy_tab():
    """Renderiza la pestaña de estrategia"""
    st.title("📊 Estrategia de Enlazado")
    
    if not st.session_state.get('data_loaded'):
        st.warning("⚠️ Primero debes cargar datos")
        return
    
    # Verificar que hay análisis de facetas
    if 'facets' not in st.session_state.get('analysis_results', {}):
        st.warning("⚠️ Primero ejecuta el análisis de facetas")
        return
    
    facet_result = st.session_state['analysis_results']['facets']
    
    st.subheader("⚙️ Configurar Scoring")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        demand_weight = st.slider("Peso Demanda", 0.0, 1.0, 0.35, 0.05)
    
    with col2:
        performance_weight = st.slider("Peso Rendimiento", 0.0, 1.0, 0.25, 0.05)
    
    with col3:
        coverage_weight = st.slider("Peso Cobertura", 0.0, 1.0, 0.20, 0.05)
    
    with col4:
        opportunity_weight = st.slider("Peso Oportunidad", 0.0, 1.0, 0.20, 0.05)
    
    # Normalizar
    total = demand_weight + performance_weight + coverage_weight + opportunity_weight
    if abs(total - 1.0) > 0.01:
        st.warning(f"⚠️ Los pesos suman {total:.2f}, se normalizarán a 1.0")
    
    if st.button("📈 Generar Scoring", type="primary"):
        with st.spinner("Calculando scores..."):
            from analysis.scoring import ScoringWeights
            
            weights = ScoringWeights(
                demand_weight=demand_weight / total,
                performance_weight=performance_weight / total,
                coverage_weight=coverage_weight / total,
                opportunity_weight=opportunity_weight / total
            )
            
            scorer = FacetScorer(weights=weights)
            
            # Preparar datos para scoring
            facets_data = []
            for facet in facet_result.facets:
                facets_data.append({
                    'facet_name': facet.name,
                    'demand': facet.demand_adobe + facet.demand_keywords,
                    'traffic': facet.traffic_seo,
                    'urls_200': facet.urls_200,
                    'urls_404': facet.urls_404,
                    'in_wrapper': facet.in_wrapper,
                })
            
            scores = scorer.score_multiple(facets_data)
            st.session_state['analysis_results']['scores'] = scores
            
            show_success("Scoring completado")
    
    # Mostrar resultados
    if 'scores' in st.session_state.get('analysis_results', {}):
        scores = st.session_state['analysis_results']['scores']
        
        # Resumen por tier
        st.subheader("📊 Distribución por Tier")
        
        scorer = FacetScorer()
        tier_summary = scorer.get_tier_summary(scores)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Tier S", tier_summary['S'], help="Facetas estrella")
        with col2:
            st.metric("Tier A", tier_summary['A'], help="Alto rendimiento")
        with col3:
            st.metric("Tier B", tier_summary['B'], help="Rendimiento medio")
        with col4:
            st.metric("Tier C", tier_summary['C'], help="Bajo rendimiento")
        with col5:
            st.metric("Tier D", tier_summary['D'], help="Sin prioridad")
        
        st.divider()
        
        # Tabla completa
        st.subheader("📋 Scoring Completo")
        
        scores_df = scorer.to_dataframe(scores)
        st.dataframe(
            scores_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Acciones prioritarias
        st.subheader("⚡ Acciones Prioritarias")
        
        actions = scorer.get_priority_actions(scores, 10)
        
        for i, action in enumerate(actions, 1):
            st.markdown(
                f"**{i}. {action['facet']}** (Tier {action['priority']}) - "
                f"Score: {action['score']:.0f} | "
                f"URLs: {action['urls_available']} | "
                f"Potencial: {action['potential_traffic']:,}"
            )


def render_export_tab():
    """Renderiza la pestaña de exportación"""
    st.title("📤 Exportar Resultados")
    
    if not st.session_state.get('data_loaded'):
        st.warning("⚠️ No hay datos para exportar")
        return
    
    results = st.session_state.get('analysis_results', {})
    
    if not results:
        st.warning("⚠️ No hay análisis para exportar. Ejecuta primero los análisis.")
        return
    
    st.subheader("📊 Exportar Análisis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Exportar scores
        if 'scores' in results:
            st.markdown("### 📈 Scoring de Facetas")
            
            scorer = FacetScorer()
            scores_df = scorer.to_dataframe(results['scores'])
            
            csv = scores_df.to_csv(index=False)
            st.download_button(
                "📥 Descargar CSV",
                csv,
                "facet_scores.csv",
                "text/csv",
                key="download_scores"
            )
            
            # Reporte markdown
            family_name = st.session_state.get('family_metadata', {})
            family_name = family_name.name if hasattr(family_name, 'name') else ""
            
            report = generate_scoring_report(results['scores'], family_name)
            st.download_button(
                "📥 Descargar Reporte (MD)",
                report,
                "scoring_report.md",
                "text/markdown",
                key="download_report"
            )
    
    with col2:
        # Exportar autoridad
        if 'authority' in results:
            st.markdown("### 🔗 Análisis de Autoridad")
            
            leaks_df = pd.DataFrame([l.to_dict() for l in results['authority'].top_leaks])
            
            if len(leaks_df) > 0:
                csv = leaks_df.to_csv(index=False)
                st.download_button(
                    "📥 Descargar Fugas (CSV)",
                    csv,
                    "authority_leaks.csv",
                    "text/csv",
                    key="download_leaks"
                )
    
    st.divider()
    
    # Exportar familia completa
    if st.session_state.get('current_family'):
        st.subheader("📦 Exportar Familia Completa")
        
        if st.button("📥 Exportar como ZIP"):
            try:
                library = get_default_library()
                family_id = st.session_state['current_family']
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = f"{tmpdir}/{family_id}.zip"
                    library.export_family(family_id, zip_path)
                    
                    with open(zip_path, 'rb') as f:
                        st.download_button(
                            "📥 Descargar ZIP",
                            f.read(),
                            f"{family_id}.zip",
                            "application/zip"
                        )
            except Exception as e:
                show_error(f"Error exportando: {e}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Función principal"""
    init_session_state()
    render_sidebar()
    
    # Renderizar tab activo
    active_tab = st.session_state.get('active_tab', 'home')
    
    tabs = {
        'home': render_home_tab,
        'load': render_load_tab,
        'config': render_config_tab,
        'authority': render_authority_tab,
        'facets': render_facets_tab,
        'strategy': render_strategy_tab,
        'export': render_export_tab,
    }
    
    render_func = tabs.get(active_tab, render_home_tab)
    render_func()


if __name__ == "__main__":
    main()
