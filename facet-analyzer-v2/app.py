"""
Facet Architecture Analyzer v2.2
Aplicación principal Streamlit
Genérica para cualquier categoría de e-commerce
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import json
from datetime import datetime

# Añadir el directorio al path
sys.path.insert(0, str(Path(__file__).parent))

# Imports locales
from data.loaders import DataLoader, FileType, LoadResult, render_file_upload_ui
from data.family_library import FamilyLibrary, FamilyMetadata, get_default_library
from data.data_config import (
    DatasetContext, FacetDetector, FacetMapping,
    render_data_period_config, render_facet_mapping_ui
)
from data.drive_storage import render_drive_config_ui, HybridLibraryStorage

from analysis.authority_analyzer import AuthorityAnalyzer, get_wrapper_distribution
from analysis.facet_analyzer import FacetAnalyzer, FacetAnalysisResult
from analysis.scoring import FacetScorer, ScoringWeights, render_scoring_config_ui, render_score_breakdown_ui

from config.settings import AI_CONFIGS, ANALYSIS_THRESHOLDS


# =============================================================================
# CONFIGURACIÓN DE LA APP
# =============================================================================

st.set_page_config(
    page_title="Facet Architecture Analyzer",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# ESTADO DE SESIÓN
# =============================================================================

def init_session_state():
    """Inicializa el estado de la sesión"""
    defaults = {
        'authenticated': True,
        'current_family': None,
        'loaded_data': {},
        'load_results': {},
        'facet_mappings': [],
        'analysis_results': {},
        'context': None,
        'scoring_weights': None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    """Renderiza el sidebar con navegación y configuración"""
    with st.sidebar:
        st.title("🏗️ Facet Analyzer")
        st.caption("v2.2 - Genérico")
        
        st.divider()
        
        # Navegación
        st.subheader("📍 Navegación")
        page = st.radio(
            "Selecciona sección:",
            options=[
                "📁 Cargar Datos",
                "🔍 Análisis de Autoridad",
                "📊 Análisis de Facetas",
                "⚙️ Estrategia",
                "💬 Chat AI",
                "📤 Exportar",
                "⚙️ Configuración"
            ],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Estado actual
        if st.session_state.get('current_family'):
            family = st.session_state['current_family']
            st.success(f"📂 {family.get('name', 'Sin nombre')}")
            
            # Métricas rápidas
            if st.session_state.get('loaded_data'):
                data = st.session_state['loaded_data']
                if 'crawl_master' in data or 'crawl_adobe' in data:
                    crawl_key = 'crawl_master' if 'crawl_master' in data else 'crawl_adobe'
                    crawl = data[crawl_key]
                    st.metric("URLs cargadas", f"{len(crawl):,}")
        else:
            st.info("Sin familia cargada")
        
        st.divider()
        
        # Enlaces útiles
        st.caption("📚 Recursos")
        st.markdown("[Documentación](https://docs.claude.com)")
        
        return page


# =============================================================================
# PÁGINA: CARGAR DATOS
# =============================================================================

def render_data_loading_page():
    """Página de carga de datos"""
    st.header("📁 Cargar Datos")
    
    tab1, tab2, tab3 = st.tabs(["📤 Subir Archivos", "📚 Biblioteca", "☁️ Google Drive"])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_library_tab()
    
    with tab3:
        render_drive_config_ui()


def render_upload_tab():
    """Tab de subida de archivos"""
    st.subheader("Subir archivos de datos")
    
    st.info("""
    **Archivos soportados (7 tipos):**
    1. 🔴 **Crawl SF + GSC** - Crawl con datos de Google Search Console (obligatorio)
    2. ⚪ **Keyword Planner** - Volúmenes de Google Ads (opcional)
    3. ⚪ **SEMrush** - Keywords con volumen, KD, intent (opcional)
    4. 🟡 **Adobe URLs SEO** - Tráfico por URL con revenue (recomendado)
    5. 🔴 **Crawl SF + Extracción** - Con seoFilterWrapper (crítico)
    6. 🔴 **Adobe Filters** - Demanda de facetas usadas (crítico)
    7. 🔴 **Crawl Histórico** - URLs con tráfico histórico (crítico)
    """)
    
    uploaded_files = st.file_uploader(
        "Sube uno o más archivos CSV",
        type=['csv'],
        accept_multiple_files=True,
        key="data_uploader"
    )
    
    if uploaded_files:
        loader = DataLoader()
        results = {}
        
        for uploaded_file in uploaded_files:
            # Guardar temporalmente
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            # Cargar y detectar tipo
            result = loader.load_file(tmp_path)
            results[uploaded_file.name] = result
            
            # Mostrar resultado
            col1, col2 = st.columns([3, 1])
            with col1:
                if result.success:
                    st.success(f"✅ **{uploaded_file.name}**")
                    st.caption(f"Tipo: `{result.file_type.value}` | Filas: {result.row_count:,}")
                else:
                    st.error(f"❌ **{uploaded_file.name}**: {result.error}")
            
            with col2:
                if result.success:
                    # Permitir cambiar tipo manualmente
                    new_type = st.selectbox(
                        "Tipo",
                        options=[ft.value for ft in FileType if ft != FileType.UNKNOWN],
                        index=[ft.value for ft in FileType if ft != FileType.UNKNOWN].index(result.file_type.value) if result.file_type != FileType.UNKNOWN else 0,
                        key=f"type_{uploaded_file.name}",
                        label_visibility="collapsed"
                    )
            
            # Limpiar temporal
            import os
            os.unlink(tmp_path)
            
            # Guardar en session state
            if result.success:
                key = f"{result.file_type.value}"
                st.session_state['loaded_data'][key] = result.dataframe
                st.session_state['load_results'][uploaded_file.name] = result
        
        # Botón para procesar
        if st.button("🚀 Procesar Datos", type="primary"):
            with st.spinner("Procesando..."):
                process_loaded_data()
            st.success("✅ Datos procesados correctamente")
            st.rerun()


def render_library_tab():
    """Tab de biblioteca de familias"""
    st.subheader("Biblioteca de Familias")
    
    library = get_default_library()
    families = library.list_families()
    
    if not families:
        st.info("No hay familias guardadas. Sube archivos y crea una nueva familia.")
        
        # Formulario para crear familia
        with st.expander("➕ Crear nueva familia"):
            name = st.text_input("Nombre de la familia", placeholder="Ej: Smartphones")
            base_url = st.text_input("URL base", placeholder="https://www.pccomponentes.com/smartphone-moviles")
            description = st.text_area("Descripción", placeholder="Descripción de la categoría...")
            
            if st.button("Crear familia") and name and base_url:
                metadata = library.create_family(
                    name=name,
                    description=description,
                    base_url=base_url
                )
                st.success(f"✅ Familia '{name}' creada con ID: {metadata.id}")
                st.rerun()
    else:
        # Mostrar familias existentes
        for family in families:
            with st.expander(f"📁 {family['name']}", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.caption(f"ID: `{family['id']}`")
                    st.caption(f"URL: {family.get('base_url', 'N/A')}")
                    st.caption(f"Actualizado: {family.get('updated_at', 'N/A')[:10]}")
                
                with col2:
                    st.metric("URLs", f"{family.get('total_urls', 0):,}")
                    st.metric("Tráfico", f"{family.get('total_traffic', 0):,}")
                
                with col3:
                    if st.button("Cargar", key=f"load_{family['id']}"):
                        load_family(family['id'])
                        st.rerun()
                    
                    if st.button("🗑️", key=f"delete_{family['id']}"):
                        library.delete_family(family['id'])
                        st.success("Familia eliminada")
                        st.rerun()


def load_family(family_id: str):
    """Carga una familia de la biblioteca"""
    library = get_default_library()
    
    try:
        data = library.load_family_data(family_id)
        metadata = library.get_family(family_id)
        
        st.session_state['loaded_data'] = data
        st.session_state['current_family'] = metadata.to_dict() if metadata else {'id': family_id, 'name': family_id}
        
        st.success(f"✅ Familia '{family_id}' cargada")
    except Exception as e:
        st.error(f"Error cargando familia: {e}")


def process_loaded_data():
    """Procesa los datos cargados y crea contexto"""
    data = st.session_state.get('loaded_data', {})
    
    if not data:
        return
    
    # Buscar crawl maestro
    crawl = None
    for key in ['crawl_master', 'crawl_adobe', 'crawl_gsc']:
        if key in data:
            crawl = data[key]
            break
    
    if crawl is None:
        st.warning("No se encontró crawl maestro")
        return
    
    # Detectar facetas
    base_url = st.session_state.get('current_family', {}).get('base_url', '')
    detector = FacetDetector(crawl, base_url)
    facet_mappings = detector.detect_all()
    
    st.session_state['facet_mappings'] = facet_mappings
    
    # Crear contexto
    context = DatasetContext(
        family_name=st.session_state.get('current_family', {}).get('name', 'Sin nombre'),
        base_url=base_url,
        total_urls=len(crawl),
        facet_mappings=facet_mappings
    )
    
    # Calcular métricas
    if 'Código de respuesta' in crawl.columns:
        context.urls_200 = len(crawl[crawl['Código de respuesta'] == 200])
        context.urls_404 = len(crawl[crawl['Código de respuesta'] == 404])
        context.urls_301 = len(crawl[crawl['Código de respuesta'] == 301])
    
    if 'has_wrapper' in crawl.columns:
        crawl_200 = crawl[crawl['Código de respuesta'] == 200] if 'Código de respuesta' in crawl.columns else crawl
        context.with_wrapper = len(crawl_200[crawl_200['has_wrapper'] == True])
        context.without_wrapper = len(crawl_200[crawl_200['has_wrapper'] == False])
    
    # Tráfico
    adobe_urls = data.get('adobe_urls')
    if adobe_urls is not None and 'visits_seo' in adobe_urls.columns:
        context.total_traffic = int(adobe_urls['visits_seo'].sum())
    
    st.session_state['context'] = context


# =============================================================================
# PÁGINA: ANÁLISIS DE AUTORIDAD
# =============================================================================

def render_authority_analysis_page():
    """Página de análisis de autoridad"""
    st.header("🔍 Análisis de Autoridad")
    
    data = st.session_state.get('loaded_data', {})
    
    if not data:
        st.warning("⚠️ Primero carga los datos en la sección 'Cargar Datos'")
        return
    
    # Buscar crawl
    crawl = None
    for key in ['crawl_master', 'crawl_adobe', 'crawl_gsc']:
        if key in data:
            crawl = data[key]
            break
    
    if crawl is None:
        st.error("No se encontró crawl maestro")
        return
    
    # Adobe URLs
    adobe_urls = data.get('adobe_urls')
    
    # Ejecutar análisis
    analyzer = AuthorityAnalyzer(crawl, adobe_urls)
    
    tab1, tab2, tab3 = st.tabs(["📊 Resumen", "🔴 Fugas Detectadas", "📈 Distribución"])
    
    with tab1:
        render_authority_summary(analyzer)
    
    with tab2:
        render_authority_leaks(analyzer)
    
    with tab3:
        render_wrapper_distribution(crawl)


def render_authority_summary(analyzer: AuthorityAnalyzer):
    """Renderiza resumen del análisis de autoridad"""
    result = analyzer.get_full_analysis()
    
    # Guardar en session state
    st.session_state['analysis_results']['authority'] = result
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Fugas",
            f"{result.total_leaks:,}",
            help="URLs con problemas de distribución de autoridad"
        )
    
    with col2:
        st.metric(
            "Tráfico Afectado",
            f"{result.total_traffic_affected:,}",
            help="Visitas SEO en páginas con fugas"
        )
    
    with col3:
        st.metric(
            "Dead Ends (404)",
            f"{result.dead_ends_count:,}",
            help="URLs que devuelven 404"
        )
    
    with col4:
        st.metric(
            "Tráfico Perdido",
            f"{result.dead_ends_traffic:,}",
            help="Tráfico histórico en URLs 404"
        )
    
    st.divider()
    
    # Resumen markdown
    st.markdown(result.summary)


def render_authority_leaks(analyzer: AuthorityAnalyzer):
    """Renderiza tabla de fugas detectadas"""
    result = analyzer.get_full_analysis()
    
    if not result.top_leaks:
        st.info("No se detectaron fugas significativas")
        return
    
    # Convertir a DataFrame
    leaks_data = [leak.to_dict() for leak in result.top_leaks]
    df = pd.DataFrame(leaks_data)
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        leak_type = st.selectbox(
            "Tipo de fuga",
            options=['Todos', 'no_distribution', 'dilution'],
            key="leak_type_filter"
        )
    
    with col2:
        severity = st.selectbox(
            "Severidad",
            options=['Todos', 'high', 'medium', 'low'],
            key="severity_filter"
        )
    
    # Aplicar filtros
    if leak_type != 'Todos':
        df = df[df['leak_type'] == leak_type]
    if severity != 'Todos':
        df = df[df['severity'] == severity]
    
    # Mostrar tabla
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            'url': st.column_config.TextColumn('URL', width='large'),
            'traffic_seo': st.column_config.NumberColumn('Tráfico SEO', format="%d"),
            'wrapper_links': st.column_config.NumberColumn('Enlaces Wrapper'),
            'leak_type': st.column_config.TextColumn('Tipo'),
            'severity': st.column_config.TextColumn('Severidad'),
            'recommendation': st.column_config.TextColumn('Recomendación', width='large'),
        }
    )
    
    # Exportar
    if st.button("📥 Exportar CSV"):
        csv = df.to_csv(index=False)
        st.download_button(
            "Descargar",
            csv,
            "authority_leaks.csv",
            "text/csv"
        )


def render_wrapper_distribution(crawl: pd.DataFrame):
    """Renderiza distribución de enlaces en seoFilterWrapper"""
    distribution = get_wrapper_distribution(crawl)
    
    st.subheader("Distribución de enlaces en seoFilterWrapper")
    
    # Gráfico de barras
    st.bar_chart(distribution.set_index('range')['count'])
    
    # Tabla
    st.dataframe(distribution, use_container_width=True)


# =============================================================================
# PÁGINA: ANÁLISIS DE FACETAS
# =============================================================================

def render_facet_analysis_page():
    """Página de análisis de facetas"""
    st.header("📊 Análisis de Facetas")
    
    data = st.session_state.get('loaded_data', {})
    facet_mappings = st.session_state.get('facet_mappings', [])
    
    if not data:
        st.warning("⚠️ Primero carga los datos")
        return
    
    tab1, tab2, tab3 = st.tabs(["🏷️ Configurar Facetas", "📊 Análisis", "⚖️ Scoring"])
    
    with tab1:
        render_facet_config_tab(data, facet_mappings)
    
    with tab2:
        render_facet_analysis_tab(data, facet_mappings)
    
    with tab3:
        render_scoring_tab(data, facet_mappings)


def render_facet_config_tab(data: Dict, facet_mappings: List):
    """Tab de configuración de facetas"""
    # Detectar patrones desconocidos
    crawl = None
    for key in ['crawl_master', 'crawl_adobe', 'crawl_gsc']:
        if key in data:
            crawl = data[key]
            break
    
    if crawl is None:
        st.error("No hay crawl cargado")
        return
    
    detector = FacetDetector(crawl)
    unknown = detector.detect_unknown_patterns()
    
    # UI de mapeo
    verified = render_facet_mapping_ui(facet_mappings, unknown)
    
    if st.button("💾 Guardar configuración"):
        st.session_state['facet_mappings'] = verified
        st.success(f"✅ {len(verified)} facetas guardadas")


def render_facet_analysis_tab(data: Dict, facet_mappings: List):
    """Tab de análisis de facetas"""
    if not facet_mappings:
        st.warning("Primero configura las facetas en la pestaña anterior")
        return
    
    # Buscar datos
    crawl = None
    for key in ['crawl_master', 'crawl_adobe', 'crawl_gsc']:
        if key in data:
            crawl = data[key]
            break
    
    adobe_urls = data.get('adobe_urls')
    adobe_filters = data.get('adobe_filters')
    keywords = data.get('semrush') or data.get('keyword_planner')
    
    # Ejecutar análisis
    analyzer = FacetAnalyzer(
        crawl,
        adobe_urls_df=adobe_urls,
        adobe_filters_df=adobe_filters,
        keywords_df=keywords,
        facet_mappings=facet_mappings
    )
    
    result = analyzer.analyze_all_facets()
    
    # Guardar
    st.session_state['analysis_results']['facets'] = result
    
    # Mostrar resumen
    st.markdown(result.summary)
    
    st.divider()
    
    # Tabla de facetas
    if result.facets:
        facets_data = [f.to_dict() for f in result.facets]
        df = pd.DataFrame(facets_data)
        
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                'name': st.column_config.TextColumn('Faceta'),
                'urls_200': st.column_config.NumberColumn('URLs Activas'),
                'urls_404': st.column_config.NumberColumn('URLs 404'),
                'traffic_seo': st.column_config.NumberColumn('Tráfico'),
                'demand_adobe': st.column_config.NumberColumn('Demanda'),
                'status': st.column_config.TextColumn('Estado'),
                'opportunity_score': st.column_config.ProgressColumn('Score', min_value=0, max_value=100),
            }
        )


def render_scoring_tab(data: Dict, facet_mappings: List):
    """Tab de scoring"""
    col1, col2 = st.columns([1, 2])
    
    with col1:
        weights = render_scoring_config_ui()
        st.session_state['scoring_weights'] = weights
    
    with col2:
        if not facet_mappings:
            st.info("Configura facetas para ver scores")
            return
        
        st.subheader("📊 Scores por Faceta")
        
        # Calcular scores
        scorer = FacetScorer(weights=weights)
        
        # Obtener DataFrames
        semrush = data.get('semrush')
        kp = data.get('keyword_planner')
        gsc = None
        for key in ['crawl_master', 'crawl_adobe', 'crawl_gsc']:
            if key in data:
                gsc = data[key]
                break
        adobe_urls = data.get('adobe_urls')
        adobe_filters = data.get('adobe_filters')
        
        scores = []
        for mapping in facet_mappings[:20]:  # Limitar a 20
            breakdown = scorer.score_from_dataframes(
                facet_pattern=mapping.pattern,
                facet_name=mapping.facet_name,
                semrush_df=semrush,
                kp_df=kp,
                gsc_df=gsc,
                adobe_urls_df=adobe_urls,
                adobe_filters_df=adobe_filters
            )
            scores.append(breakdown)
        
        # Ordenar por score
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        # Mostrar top 10
        for breakdown in scores[:10]:
            with st.expander(f"{breakdown.facet_name} - Score: {breakdown.total_score:.1f}"):
                render_score_breakdown_ui(breakdown)


# =============================================================================
# PÁGINA: ESTRATEGIA
# =============================================================================

def render_strategy_page():
    """Página de estrategia"""
    st.header("⚙️ Estrategia de Arquitectura")
    
    analysis = st.session_state.get('analysis_results', {})
    
    if not analysis:
        st.warning("Ejecuta primero los análisis de autoridad y facetas")
        return
    
    authority = analysis.get('authority')
    facets = analysis.get('facets')
    
    tab1, tab2, tab3 = st.tabs(["📋 Recomendaciones", "🔗 seoFilterWrapper", "📈 Priorización"])
    
    with tab1:
        render_recommendations(authority, facets)
    
    with tab2:
        render_wrapper_recommendations(authority, facets)
    
    with tab3:
        render_prioritization(authority, facets)


def render_recommendations(authority, facets):
    """Renderiza recomendaciones generales"""
    st.subheader("Recomendaciones Generales")
    
    recommendations = []
    
    if authority:
        if authority.dead_ends_count > 1000:
            recommendations.append({
                'priority': 'ALTA',
                'category': 'Dead Ends',
                'issue': f"{authority.dead_ends_count:,} URLs devuelven 404",
                'action': "Implementar redirecciones 301 o eliminar enlaces internos",
                'impact': f"{authority.dead_ends_traffic:,} visitas históricas perdidas"
            })
        
        no_dist = authority.leaks_by_type.get('no_distribution', 0)
        if no_dist > 100:
            recommendations.append({
                'priority': 'ALTA',
                'category': 'Distribución',
                'issue': f"{no_dist:,} páginas con tráfico sin seoFilterWrapper",
                'action': "Añadir seoFilterWrapper con enlaces a facetas relevantes",
                'impact': f"Mejorar distribución de PageRank"
            })
    
    if facets:
        partial = sum(1 for f in facets.facets if f.status == 'partial')
        if partial > 0:
            recommendations.append({
                'priority': 'MEDIA',
                'category': 'Facetas',
                'issue': f"{partial} facetas con URLs pero sin enlazar",
                'action': "Añadir enlaces en seoFilterWrapper del nivel superior",
                'impact': "Mejorar descubrimiento de facetas"
            })
    
    if recommendations:
        df = pd.DataFrame(recommendations)
        st.dataframe(df, use_container_width=True)
    else:
        st.success("✅ No se detectaron problemas críticos")


def render_wrapper_recommendations(authority, facets):
    """Renderiza recomendaciones para seoFilterWrapper"""
    st.subheader("Configuración de seoFilterWrapper")
    
    st.info("""
    **Principios de distribución:**
    - L0 (categoría principal): 20-30 enlaces máximo
    - L1 (marcas/filtros principales): 10-15 enlaces
    - L2 (combinaciones): 5-10 enlaces
    - L3+: Considerar no incluir wrapper
    """)
    
    # Tabla de configuración recomendada
    config = [
        {'Nivel': 'L0', 'Tipo enlace': 'Marcas top', 'Cantidad': '15-18', 'Criterio': 'Revenue + Tráfico'},
        {'Nivel': 'L0', 'Tipo enlace': 'Atributos clave', 'Cantidad': '5-8', 'Criterio': 'Demanda + Intent'},
        {'Nivel': 'L0', 'Tipo enlace': 'Ofertas', 'Cantidad': '1-2', 'Criterio': 'Conversión'},
        {'Nivel': 'L1', 'Tipo enlace': 'Modelos top', 'Cantidad': '5-10', 'Criterio': 'Clics GSC'},
        {'Nivel': 'L1', 'Tipo enlace': 'Combinaciones', 'Cantidad': '3-5', 'Criterio': 'Demanda filtros'},
        {'Nivel': 'L2', 'Tipo enlace': 'Relacionados', 'Cantidad': '3-5', 'Criterio': 'Relevancia'},
    ]
    
    st.dataframe(pd.DataFrame(config), use_container_width=True)


def render_prioritization(authority, facets):
    """Renderiza matriz de priorización"""
    st.subheader("Matriz de Priorización")
    
    if not facets:
        st.warning("Ejecuta el análisis de facetas primero")
        return
    
    # Crear matriz
    data = []
    for f in facets.facets:
        data.append({
            'Faceta': f.name,
            'Score': f.opportunity_score,
            'Demanda': f.demand_adobe + f.demand_keywords,
            'URLs': f.urls_200,
            'Estado': f.status,
            'Prioridad': 'ALTA' if f.opportunity_score > 70 else ('MEDIA' if f.opportunity_score > 40 else 'BAJA')
        })
    
    df = pd.DataFrame(data)
    df = df.sort_values('Score', ascending=False)
    
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            'Score': st.column_config.ProgressColumn('Score', min_value=0, max_value=100),
            'Demanda': st.column_config.NumberColumn(format="%d"),
        }
    )


# =============================================================================
# PÁGINA: CHAT AI
# =============================================================================

def render_chat_page():
    """Página de chat con AI"""
    st.header("💬 Chat AI")
    
    st.info("""
    **Chat contextual con AI**
    
    El chat tiene acceso al contexto de tu análisis para responder preguntas específicas.
    
    *Nota: Requiere configurar API keys de Anthropic/OpenAI en la sección Configuración.*
    """)
    
    # Mostrar contexto actual
    context = st.session_state.get('context')
    if context:
        with st.expander("📋 Contexto actual"):
            st.code(context.to_chat_context()[:2000] + "...", language='markdown')
    
    # Chat simple (placeholder)
    st.text_area("Escribe tu pregunta:", height=100, key="chat_input")
    
    if st.button("Enviar"):
        st.info("💡 Funcionalidad de chat en desarrollo. Integración con Claude/GPT próximamente.")


# =============================================================================
# PÁGINA: EXPORTAR
# =============================================================================

def render_export_page():
    """Página de exportación"""
    st.header("📤 Exportar Resultados")
    
    analysis = st.session_state.get('analysis_results', {})
    
    if not analysis:
        st.warning("No hay resultados para exportar. Ejecuta los análisis primero.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Exportar Datos")
        
        # Autoridad
        if 'authority' in analysis:
            if st.button("📥 Fugas de Autoridad (CSV)"):
                result = analysis['authority']
                df = pd.DataFrame([l.to_dict() for l in result.top_leaks])
                csv = df.to_csv(index=False)
                st.download_button("Descargar", csv, "authority_leaks.csv", "text/csv")
        
        # Facetas
        if 'facets' in analysis:
            if st.button("📥 Análisis de Facetas (CSV)"):
                result = analysis['facets']
                df = pd.DataFrame([f.to_dict() for f in result.facets])
                csv = df.to_csv(index=False)
                st.download_button("Descargar", csv, "facet_analysis.csv", "text/csv")
    
    with col2:
        st.subheader("📄 Exportar Reporte")
        
        if st.button("📥 Reporte Completo (Markdown)"):
            report = generate_full_report()
            st.download_button("Descargar", report, "facet_analysis_report.md", "text/markdown")


def generate_full_report() -> str:
    """Genera reporte completo en Markdown"""
    analysis = st.session_state.get('analysis_results', {})
    context = st.session_state.get('context')
    
    report = f"""# Facet Architecture Analyzer - Reporte

**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

"""
    
    if context:
        report += f"""## Contexto

- **Familia:** {context.family_name}
- **URL Base:** {context.base_url}
- **Total URLs:** {context.total_urls:,}
- **URLs Activas (200):** {context.urls_200:,}
- **URLs 404:** {context.urls_404:,}
- **Con seoFilterWrapper:** {context.with_wrapper:,}
- **Sin seoFilterWrapper:** {context.without_wrapper:,}

"""
    
    if 'authority' in analysis:
        result = analysis['authority']
        report += result.summary
    
    if 'facets' in analysis:
        result = analysis['facets']
        report += result.summary
    
    return report


# =============================================================================
# PÁGINA: CONFIGURACIÓN
# =============================================================================

def render_config_page():
    """Página de configuración"""
    st.header("⚙️ Configuración")
    
    tab1, tab2, tab3 = st.tabs(["🔑 API Keys", "📊 Umbrales", "ℹ️ Info"])
    
    with tab1:
        st.subheader("Configuración de API Keys")
        
        anthropic_key = st.text_input("Anthropic API Key", type="password", key="anthropic_key")
        openai_key = st.text_input("OpenAI API Key", type="password", key="openai_key")
        
        if st.button("Guardar"):
            if anthropic_key:
                st.session_state['anthropic_api_key'] = anthropic_key
            if openai_key:
                st.session_state['openai_api_key'] = openai_key
            st.success("✅ Claves guardadas en sesión")
    
    with tab2:
        st.subheader("Umbrales de Análisis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.number_input("Min tráfico para fuga", value=100, key="th_min_traffic")
            st.number_input("Max enlaces óptimos", value=10, key="th_max_links")
        
        with col2:
            st.number_input("Demanda alta", value=50000, key="th_demand_high")
            st.number_input("Demanda muy alta", value=100000, key="th_demand_very_high")
    
    with tab3:
        st.subheader("Información del Sistema")
        
        st.markdown(f"""
        **Facet Architecture Analyzer v2.2**
        
        - Desarrollado para PCComponentes
        - Genérico para cualquier categoría de e-commerce
        - Soporta 7 tipos de archivos de datos
        
        **Archivos soportados:**
        1. Crawl SF + GSC
        2. Google Keyword Planner
        3. SEMrush KMT
        4. Adobe Analytics URLs
        5. Crawl SF + Extracción Custom
        6. Adobe Search Filters
        7. Crawl Histórico
        """)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Función principal"""
    init_session_state()
    
    # Renderizar sidebar y obtener página
    page = render_sidebar()
    
    # Renderizar página correspondiente
    if page == "📁 Cargar Datos":
        render_data_loading_page()
    elif page == "🔍 Análisis de Autoridad":
        render_authority_analysis_page()
    elif page == "📊 Análisis de Facetas":
        render_facet_analysis_page()
    elif page == "⚙️ Estrategia":
        render_strategy_page()
    elif page == "💬 Chat AI":
        render_chat_page()
    elif page == "📤 Exportar":
        render_export_page()
    elif page == "⚙️ Configuración":
        render_config_page()


if __name__ == "__main__":
    main()
