"""
Facet Architecture Analyzer v2.1
Herramienta de análisis SEO para arquitectura de facetas en e-commerce
Con validación dual, chat contextual y persistencia en Drive
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# =============================================================================
# AUTENTICACIÓN - DEBE IR ANTES DE CUALQUIER OTRA COSA
# =============================================================================

from auth.authenticator import EmailAuthenticator, render_user_menu, ALLOWED_DOMAIN

# Verificar autenticación ANTES de configurar la página
auth = EmailAuthenticator()

if not auth.is_authenticated():
    # Página de login
    st.set_page_config(
        page_title="Login - Facet Analyzer",
        page_icon="🔐",
        layout="centered"
    )
    
    # Estilos
    st.markdown("""
    <style>
        .login-box {
            max-width: 400px;
            margin: 50px auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Acceso")
        st.markdown("**Facet Architecture Analyzer v2.1**")
        st.markdown("---")
    
    # Verificar SMTP
    if not auth.is_smtp_configured():
        st.error("""
        ⚠️ **Sistema de email no configurado**
        
        Configura en Streamlit Secrets:
        ```
        SMTP_HOST = "smtp.gmail.com"
        SMTP_PORT = 587
        SMTP_USERNAME = "tu-email@gmail.com"
        SMTP_PASSWORD = "tu-app-password"
        SMTP_FROM_EMAIL = "tu-email@gmail.com"
        ```
        """)
        st.stop()
    
    # Estado del login
    if 'login_step' not in st.session_state:
        st.session_state.login_step = 'email'
    if 'login_email' not in st.session_state:
        st.session_state.login_email = ''
    
    # Paso 1: Email
    if st.session_state.login_step == 'email':
        with st.form("email_form"):
            st.markdown(f"Introduce tu email **@{ALLOWED_DOMAIN}**")
            
            email = st.text_input(
                "Email corporativo",
                placeholder=f"nombre@{ALLOWED_DOMAIN}"
            )
            
            submitted = st.form_submit_button("📧 Enviar código", use_container_width=True)
            
            if submitted and email:
                success, message = auth.send_verification_code(email)
                if success:
                    st.session_state.login_email = email.strip().lower()
                    st.session_state.login_step = 'code'
                    st.rerun()
                else:
                    st.error(message)
    
    # Paso 2: Código
    elif st.session_state.login_step == 'code':
        st.success(f"📧 Código enviado a **{st.session_state.login_email}**")
        
        with st.form("code_form"):
            code = st.text_input(
                "Código de 6 dígitos",
                max_chars=6,
                placeholder="000000"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                verify = st.form_submit_button("✅ Verificar", use_container_width=True)
            with col2:
                back = st.form_submit_button("← Volver", use_container_width=True)
            
            if verify and code:
                success, message = auth.verify_code(st.session_state.login_email, code)
                if success:
                    st.success("✅ ¡Bienvenido!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
            
            if back:
                st.session_state.login_step = 'email'
                st.rerun()
        
        if st.button("🔄 Reenviar código"):
            success, msg = auth.send_verification_code(st.session_state.login_email)
            if success:
                st.success("Código reenviado")
            else:
                st.error(msg)
    
    st.markdown("---")
    st.caption(f"Solo emails @{ALLOWED_DOMAIN}")
    st.stop()

# =============================================================================
# USUARIO AUTENTICADO - CONFIGURACIÓN DE PÁGINA PRINCIPAL
# =============================================================================

# Configuración de página
st.set_page_config(
    page_title="Facet Analyzer v2.1",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# IMPORTS DE MÓDULOS PROPIOS
# =============================================================================

from config.settings import AI_CONFIGS, FACET_PATTERNS, VERIFIED_METRICS
from data.loaders import DataLoader, validate_data_integrity
from data.family_library import FamilyLibrary
from data.data_config import (
    DataSourceConfig, FacetMapping, DatasetContext,
    FacetDetector, render_facet_mapping_ui
)
from data.drive_storage import HybridLibraryStorage, render_drive_config_ui
from analysis.authority_analyzer import AuthorityAnalyzer
from analysis.facet_analyzer import FacetAnalyzer
from analysis.scoring import FacetScorer, ScoringWeights, render_scoring_config_ui, render_score_breakdown_ui
from analysis.http_verifier import HTTPVerifier, create_verification_summary
from ai.api_clients import check_api_configuration, DualAIClient
from ai.dual_validator import DualValidator, QueryGenerator
from chat.contextual_chat import ContextualChat, render_contextual_chat_ui
from export.report_generator import export_authority_leaks, export_facet_analysis, generate_implementation_report

# =============================================================================
# INICIALIZACIÓN DE SESSION STATE
# =============================================================================

if 'data' not in st.session_state:
    st.session_state.data = {}
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'current_family' not in st.session_state:
    st.session_state.current_family = None
if 'ai_mode' not in st.session_state:
    st.session_state.ai_mode = 'hybrid'
if 'source_configs' not in st.session_state:
    st.session_state.source_configs = []
if 'detected_facets' not in st.session_state:
    st.session_state.detected_facets = []
if 'verified_facets' not in st.session_state:
    st.session_state.verified_facets = []
if 'dataset_context' not in st.session_state:
    st.session_state.dataset_context = None
if 'authority_result' not in st.session_state:
    st.session_state.authority_result = None
if 'facet_result' not in st.session_state:
    st.session_state.facet_result = None
if 'scoring_weights' not in st.session_state:
    st.session_state.scoring_weights = ScoringWeights()

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.image("https://www.pccomponentes.com/favicon.ico", width=50)
    st.title("Facet Analyzer v2.1")
    
    # Mostrar usuario y opción de logout
    st.markdown(f"👤 **{auth.get_current_user()}**")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        auth.logout()
        st.rerun()
    
    st.markdown("---")
    
    # ==========================================================================
    # CONFIGURACIÓN DE API KEYS
    # ==========================================================================
    st.subheader("🔑 API Keys")
    
    with st.expander("Configurar APIs", expanded=False):
        st.caption("Las keys se guardan solo en esta sesión")
        
        # Verificar si hay secretos de Streamlit
        has_streamlit_secrets = False
        try:
            if hasattr(st, 'secrets'):
                if 'ANTHROPIC_API_KEY' in st.secrets:
                    has_streamlit_secrets = True
                    st.success("✅ Keys detectadas en Streamlit Secrets")
        except Exception:
            pass
        
        if not has_streamlit_secrets:
            anthropic_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=st.session_state.get('anthropic_key', ''),
                placeholder="sk-ant-api03-...",
                help="Obtener en console.anthropic.com"
            )
            if anthropic_key:
                st.session_state.anthropic_key = anthropic_key
                os.environ['ANTHROPIC_API_KEY'] = anthropic_key
            
            openai_key = st.text_input(
                "OpenAI API Key",
                type="password",
                value=st.session_state.get('openai_key', ''),
                placeholder="sk-...",
                help="Obtener en platform.openai.com"
            )
            if openai_key:
                st.session_state.openai_key = openai_key
                os.environ['OPENAI_API_KEY'] = openai_key
        
        # Mostrar estado
        api_status = check_api_configuration()
        
        col1, col2 = st.columns(2)
        with col1:
            if api_status['anthropic']['configured']:
                st.success("✅ Claude")
            else:
                st.error("❌ Claude")
        with col2:
            if api_status['openai']['configured']:
                st.success("✅ GPT")
            else:
                st.error("❌ GPT")
        
        if api_status['anthropic']['configured'] and api_status['openai']['configured']:
            st.success("🔒 Validación dual activa")
        else:
            st.warning("⚠️ Validación dual no disponible")
    
    st.markdown("---")
    
    # ==========================================================================
    # MODO AI
    # ==========================================================================
    st.subheader("⚙️ Modo AI")
    
    ai_mode = st.selectbox(
        "Modo de Procesamiento",
        options=['economic', 'hybrid', 'premium'],
        index=1,
        format_func=lambda x: AI_CONFIGS[x]['name']
    )
    st.session_state.ai_mode = ai_mode
    
    config = AI_CONFIGS[ai_mode]
    st.caption(config['description'])
    st.caption(f"💰 Coste estimado: {config['cost_estimate']}")
    
    st.markdown("---")
    
    # ==========================================================================
    # CARGAR DATOS
    # ==========================================================================
    st.subheader("📁 Datos")
    
    # Inicializar biblioteca híbrida (local + Drive)
    library = HybridLibraryStorage()
    families = library.list_families()
    
    data_source = st.radio(
        "Fuente de datos",
        options=['📚 Biblioteca', '📤 Subir archivos'],
        horizontal=True
    )
    
    if data_source == '📚 Biblioteca':
        # Mostrar estado de Drive
        if library.is_drive_enabled():
            st.caption("☁️ Google Drive conectado")
            if st.button("🔄 Sincronizar Drive", use_container_width=True):
                synced = library.sync_from_drive()
                st.success(f"✅ {synced} familias sincronizadas")
                st.rerun()
        
        if families:
            family_options = {f['id']: f"📂 {f.get('name', f['id'])}" for f in families}
            selected_family = st.selectbox(
                "Seleccionar familia",
                options=list(family_options.keys()),
                format_func=lambda x: family_options[x]
            )
            
            if selected_family:
                family_meta = next((f for f in families if f['id'] == selected_family), None)
                if family_meta:
                    st.caption(f"📅 Fuente: {family_meta.get('source', 'local')}")
                    
                    if st.button("🔄 Cargar Familia", type="primary", use_container_width=True):
                        with st.spinner(f"Cargando..."):
                            local_lib = FamilyLibrary()
                            st.session_state.data = local_lib.load_family_data(selected_family)
                            st.session_state.current_family = family_meta
                            st.session_state.data_loaded = True
                            
                            # Resetear análisis previos
                            st.session_state.authority_result = None
                            st.session_state.facet_result = None
                            st.session_state.dataset_context = None
                            st.session_state.detected_facets = []
                            st.session_state.verified_facets = []
                        
                        st.success(f"✅ Cargada")
                        st.rerun()
        else:
            st.info("No hay familias guardadas")
        
        # Crear nueva familia
        with st.expander("➕ Nueva familia"):
            new_family_name = st.text_input("Nombre", placeholder="Ej: Smartphones")
            new_family_url = st.text_input("URL base", placeholder="https://...")
            new_crawl = st.file_uploader("Crawl (CSV)", type=['csv'], key='new_crawl')
            new_adobe_urls = st.file_uploader("Adobe URLs", type=['csv'], key='new_adobe')
            new_adobe_filters = st.file_uploader("Adobe Filters", type=['csv'], key='new_filters')
            
            if st.button("💾 Crear") and new_family_name and new_crawl:
                import tempfile
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                    tmp.write(new_crawl.getvalue())
                    crawl_path = tmp.name
                
                adobe_urls_path = None
                if new_adobe_urls:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                        tmp.write(new_adobe_urls.getvalue())
                        adobe_urls_path = tmp.name
                
                adobe_filters_path = None
                if new_adobe_filters:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                        tmp.write(new_adobe_filters.getvalue())
                        adobe_filters_path = tmp.name
                
                with st.spinner("Creando..."):
                    local_lib = FamilyLibrary()
                    new_meta = local_lib.create_family(
                        name=new_family_name,
                        description=f"Familia: {new_family_name}",
                        base_url=new_family_url or "",
                        crawl_file=crawl_path,
                        adobe_urls_file=adobe_urls_path,
                        adobe_filters_file=adobe_filters_path
                    )
                    
                    if library.is_drive_enabled():
                        library.sync_to_drive(new_meta.id)
                
                st.success(f"✅ Creada")
                st.rerun()
    
    else:  # Subir archivos
        data_dir = st.text_input(
            "Directorio",
            value="/mnt/user-data/uploads"
        )
        
        if st.button("🔄 Cargar", type="primary", use_container_width=True):
            with st.spinner("Cargando..."):
                loader = DataLoader(data_dir)
                st.session_state.data = loader.load_all()
                st.session_state.data_loaded = True
                st.session_state.current_family = None
                st.session_state.authority_result = None
                st.session_state.facet_result = None
                st.session_state.dataset_context = None
            
            st.success(f"✅ {len(st.session_state.data)} datasets")
            st.rerun()
    
    # Mostrar datasets cargados
    if st.session_state.data_loaded:
        st.markdown("---")
        st.caption("**Cargados:**")
        for name, df in st.session_state.data.items():
            st.caption(f"• {name}: {len(df):,}")

# =============================================================================
# CONTENIDO PRINCIPAL
# =============================================================================

# Verificar API status para uso global
api_status = check_api_configuration()

# Verificar si hay datos cargados
if not st.session_state.data_loaded:
    st.title("🔍 Facet Architecture Analyzer v2.1")
    
    st.info("""
    ### Bienvenido
    
    Esta herramienta analiza la arquitectura de facetas de tu e-commerce para:
    
    1. **Detectar fugas de autoridad** - Páginas con tráfico que no distribuyen PageRank
    2. **Identificar oportunidades** - Facetas con demanda que no están enlazadas
    3. **Optimizar seoFilterWrapper** - Recomendaciones basadas en datos
    
    ### Para comenzar:
    
    1. **Configura las API Keys** (sidebar) para validación dual
    2. **Carga una familia** de la biblioteca o sube archivos
    3. **Configura los datos** (períodos y facetas)
    4. **Ejecuta los análisis**
    5. **Usa el chat** para explorar los resultados
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("APIs", "✅" if api_status['anthropic']['configured'] and api_status['openai']['configured'] else "❌")
    with col2:
        st.metric("Drive", "✅" if library.is_drive_enabled() else "❌")
    with col3:
        st.metric("Familias", len(families))
    
    st.stop()

# =============================================================================
# TABS PRINCIPALES
# =============================================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "⚙️ Configurar",
    "📊 Dashboard",
    "🔴 Autoridad", 
    "📋 Facetas",
    "💬 Chat",
    "📚 Biblioteca",
    "📥 Exportar"
])

# =============================================================================
# TAB 1: CONFIGURAR DATOS
# =============================================================================

with tab1:
    st.header("⚙️ Configurar Datos")
    
    st.info("Configura períodos de datos y verifica las facetas detectadas antes de analizar.")
    
    # PASO 1: PERÍODOS
    st.subheader("📅 Paso 1: Períodos de Datos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Crawl:**")
        crawl_start = st.date_input("Inicio", key="crawl_start", format="DD/MM/YYYY")
        crawl_end = st.date_input("Fin", key="crawl_end", format="DD/MM/YYYY")
    
    with col2:
        st.markdown("**Adobe Analytics:**")
        adobe_start = st.date_input("Inicio", key="adobe_start", format="DD/MM/YYYY")
        adobe_end = st.date_input("Fin", key="adobe_end", format="DD/MM/YYYY")
    
    st.session_state.source_configs = [
        DataSourceConfig(
            name="Crawl", file_type="crawl", filepath="crawl.csv",
            period_start=datetime.combine(crawl_start, datetime.min.time()) if crawl_start else None,
            period_end=datetime.combine(crawl_end, datetime.max.time()) if crawl_end else None,
            row_count=len(st.session_state.data.get('crawl_adobe', pd.DataFrame()))
        ),
        DataSourceConfig(
            name="Adobe", file_type="adobe_urls", filepath="adobe.csv",
            period_start=datetime.combine(adobe_start, datetime.min.time()) if adobe_start else None,
            period_end=datetime.combine(adobe_end, datetime.max.time()) if adobe_end else None,
            row_count=len(st.session_state.data.get('adobe_urls', pd.DataFrame()))
        )
    ]
    
    st.markdown("---")
    
    # PASO 2: FACETAS
    st.subheader("🏷️ Paso 2: Configurar Facetas")
    
    if 'crawl_adobe' in st.session_state.data:
        crawl_df = st.session_state.data['crawl_adobe']
        
        if st.button("🔍 Detectar Facetas", type="primary"):
            with st.spinner("Analizando URLs..."):
                detector = FacetDetector(crawl_df)
                detected = detector.detect_all()
                unknown = detector.detect_unknown_patterns()
                
                st.session_state.detected_facets = detected
                st.session_state.unknown_patterns = unknown
            
            st.success(f"✅ {len(detected)} facetas, {len(unknown)} patrones desconocidos")
        
        if st.session_state.detected_facets:
            verified = render_facet_mapping_ui(
                st.session_state.detected_facets,
                st.session_state.get('unknown_patterns', [])
            )
            st.session_state.verified_facets = verified
            
            verified_count = sum(1 for f in verified if f.user_verified)
            st.caption(f"✅ {verified_count}/{len(verified)} verificadas")
    else:
        st.warning("Carga datos primero")
    
    st.markdown("---")
    
    # PASO 3: SCORING
    st.subheader("⚖️ Paso 3: Ponderaciones")
    
    weights = render_scoring_config_ui()
    st.session_state.scoring_weights = weights

# =============================================================================
# TAB 2: DASHBOARD
# =============================================================================

with tab2:
    st.header("📊 Dashboard")
    
    if 'crawl_adobe' not in st.session_state.data:
        st.warning("Carga datos primero")
        st.stop()
    
    crawl = st.session_state.data['crawl_adobe']
    
    total_urls = len(crawl)
    urls_200 = len(crawl[crawl['Código de respuesta'] == 200])
    urls_404 = len(crawl[crawl['Código de respuesta'] == 404])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("URLs Totales", f"{total_urls:,}")
    with col2:
        st.metric("Activas (200)", f"{urls_200:,}", f"{urls_200/total_urls*100:.1f}%")
    with col3:
        st.metric("Eliminadas (404)", f"{urls_404:,}")
    with col4:
        if 'wrapper_link_count' in crawl.columns:
            with_wrapper = len(crawl[(crawl['Código de respuesta'] == 200) & (crawl['wrapper_link_count'] > 0)])
            st.metric("Con Wrapper", f"{with_wrapper:,}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Status Codes")
        status_counts = crawl['Código de respuesta'].value_counts()
        fig = px.pie(values=status_counts.values, names=status_counts.index)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Enlaces en Wrapper")
        if 'wrapper_link_count' in crawl.columns:
            crawl_200 = crawl[crawl['Código de respuesta'] == 200]
            fig = px.histogram(crawl_200, x='wrapper_link_count', nbins=20)
            st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# TAB 3: AUTORIDAD
# =============================================================================

with tab3:
    st.header("🔴 Análisis de Fuga de Autoridad")
    
    if 'crawl_adobe' not in st.session_state.data:
        st.warning("Carga datos primero")
        st.stop()
    
    if st.button("🔍 Analizar Autoridad", type="primary"):
        with st.spinner("Analizando..."):
            crawl = st.session_state.data['crawl_adobe']
            adobe_urls = st.session_state.data.get('adobe_urls', pd.DataFrame())
            
            analyzer = AuthorityAnalyzer(crawl, adobe_urls)
            result = analyzer.get_full_analysis()
            st.session_state.authority_result = result
        
        st.success("✅ Completado")
    
    if st.session_state.authority_result:
        result = st.session_state.authority_result
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tipo 1 (Sin distribución)", len([l for l in result.top_leaks if l.leak_type == 'no_distribution']))
        with col2:
            st.metric("Tipo 2 (Dilución)", len([l for l in result.top_leaks if l.leak_type == 'dilution']))
        with col3:
            st.metric("Tráfico Afectado", f"{sum(l.traffic_seo for l in result.top_leaks):,}")
        
        st.markdown("---")
        st.subheader("Top Fugas")
        
        leak_data = []
        for leak in result.top_leaks[:20]:
            path = leak.url.replace('https://www.pccomponentes.com/smartphone-moviles', '') or '/'
            leak_data.append({
                'URL': path,
                'Tráfico': f"{leak.traffic_seo:,}",
                'Enlaces': leak.wrapper_links,
                'Tipo': leak.leak_type,
                'Severidad': leak.severity
            })
        
        st.dataframe(pd.DataFrame(leak_data), use_container_width=True)
        
        with st.expander("📄 Resumen Completo"):
            st.markdown(result.summary)

# =============================================================================
# TAB 4: FACETAS
# =============================================================================

with tab4:
    st.header("📋 Análisis de Facetas")
    
    if 'crawl_adobe' not in st.session_state.data:
        st.warning("Carga datos primero")
        st.stop()
    
    facets_to_analyze = st.session_state.verified_facets if st.session_state.verified_facets else []
    
    if not facets_to_analyze:
        st.warning("Ve a 'Configurar' y detecta facetas primero")
        st.stop()
    
    if st.button("🔍 Analizar Facetas", type="primary"):
        with st.spinner("Analizando..."):
            crawl = st.session_state.data['crawl_adobe']
            adobe_urls = st.session_state.data.get('adobe_urls', pd.DataFrame())
            adobe_filters = st.session_state.data.get('adobe_filters', pd.DataFrame())
            
            scorer = FacetScorer(st.session_state.scoring_weights)
            
            results = []
            for facet in facets_to_analyze:
                urls_200 = len(crawl[(crawl['Código de respuesta'] == 200) & 
                                     (crawl['Dirección'].str.contains(facet.pattern, case=False, na=False, regex=True))])
                urls_404 = len(crawl[(crawl['Código de respuesta'] == 404) & 
                                     (crawl['Dirección'].str.contains(facet.pattern, case=False, na=False, regex=True))])
                
                demand_adobe = 0
                if len(adobe_filters) > 0 and facet.adobe_filter_match:
                    mask = adobe_filters['filter_name'].str.contains(facet.adobe_filter_match, case=False, na=False)
                    demand_adobe = int(adobe_filters[mask]['visits_seo'].sum())
                
                traffic = 0
                if len(adobe_urls) > 0:
                    mask = adobe_urls['url_full'].str.contains(facet.pattern, case=False, na=False, regex=True)
                    traffic = int(adobe_urls[mask]['visits_seo'].sum())
                
                breakdown = scorer.calculate_score(
                    facet_name=facet.facet_name,
                    urls_200=urls_200, urls_404=urls_404,
                    demand_adobe=demand_adobe, demand_semrush=0,
                    traffic_seo=traffic, in_wrapper=urls_200 > 0
                )
                
                results.append({
                    'facet': facet, 'breakdown': breakdown,
                    'urls_200': urls_200, 'urls_404': urls_404,
                    'demand': demand_adobe, 'traffic': traffic
                })
            
            results.sort(key=lambda x: x['breakdown'].total_score, reverse=True)
            st.session_state.facet_results = results
        
        st.success("✅ Completado")
    
    if 'facet_results' in st.session_state:
        results = st.session_state.facet_results
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔴 Alta", len([r for r in results if r['breakdown'].total_score >= 60]))
        with col2:
            st.metric("🟡 Media", len([r for r in results if 30 <= r['breakdown'].total_score < 60]))
        with col3:
            st.metric("⚪ Baja", len([r for r in results if r['breakdown'].total_score < 30]))
        
        st.markdown("---")
        
        facet_data = [{
            'Faceta': r['breakdown'].facet_name,
            'Score': f"{r['breakdown'].total_score:.0f}",
            'URLs 200': r['urls_200'],
            'URLs 404': r['urls_404'],
            'Demanda': f"{r['demand']:,}",
            'Acción': r['breakdown'].action_type
        } for r in results]
        
        st.dataframe(pd.DataFrame(facet_data), use_container_width=True)
        
        st.markdown("---")
        st.subheader("Desglose")
        for r in results[:5]:
            render_score_breakdown_ui(r['breakdown'])

# =============================================================================
# TAB 5: CHAT
# =============================================================================

with tab5:
    st.header("💬 Chat sobre tus Datos")
    
    # Construir contexto
    if st.session_state.dataset_context is None and st.session_state.data_loaded:
        crawl = st.session_state.data.get('crawl_adobe', pd.DataFrame())
        adobe_urls = st.session_state.data.get('adobe_urls', pd.DataFrame())
        
        context = DatasetContext(
            family_name=st.session_state.current_family.get('name', 'Dataset') if st.session_state.current_family else 'Dataset',
            base_url="https://www.pccomponentes.com",
            sources=st.session_state.source_configs,
            facet_mappings=st.session_state.verified_facets,
            total_urls=len(crawl),
            urls_200=len(crawl[crawl['Código de respuesta'] == 200]) if len(crawl) > 0 else 0,
            urls_404=len(crawl[crawl['Código de respuesta'] == 404]) if len(crawl) > 0 else 0,
            total_traffic=int(adobe_urls['visits_seo'].sum()) if len(adobe_urls) > 0 else 0,
            authority_analysis_done=st.session_state.authority_result is not None,
            facet_analysis_done='facet_results' in st.session_state
        )
        
        if st.session_state.authority_result:
            context.authority_summary = st.session_state.authority_result.summary
            context.top_leaks = [
                {'url': l.url, 'traffic': l.traffic_seo, 'type': l.leak_type}
                for l in st.session_state.authority_result.top_leaks[:10]
            ]
        
        if 'facet_results' in st.session_state:
            context.top_opportunities = [
                {'name': r['breakdown'].facet_name, 'score': r['breakdown'].total_score,
                 'urls_200': r['urls_200'], 'demand': r['demand']}
                for r in st.session_state.facet_results[:10]
            ]
        
        st.session_state.dataset_context = context
    
    from chat.contextual_chat import render_contextual_chat_ui
    render_contextual_chat_ui(st.session_state.dataset_context)

# =============================================================================
# TAB 6: BIBLIOTECA
# =============================================================================

with tab6:
    st.header("📚 Biblioteca")
    
    render_drive_config_ui()
    
    st.markdown("---")
    st.subheader("Familias")
    
    all_families = library.list_families()
    
    if all_families:
        for family in all_families:
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                icon = "☁️" if family.get('source') == 'drive' else "💾"
                st.markdown(f"**{icon} {family.get('name', family['id'])}**")
            with col2:
                if family.get('source') != 'drive' and library.is_drive_enabled():
                    if st.button("☁️", key=f"sync_{family['id']}"):
                        library.sync_to_drive(family['id'])
                        st.success("✓")
            with col3:
                if st.button("🗑️", key=f"del_{family['id']}"):
                    FamilyLibrary().delete_family(family['id'])
                    st.rerun()
    else:
        st.info("No hay familias")

# =============================================================================
# TAB 7: EXPORTAR
# =============================================================================

with tab7:
    st.header("📥 Exportar")
    
    if not st.session_state.authority_result and 'facet_results' not in st.session_state:
        st.warning("Ejecuta análisis primero")
        st.stop()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.authority_result:
            csv = export_authority_leaks(st.session_state.authority_result)
            st.download_button("📥 Fugas (CSV)", csv, "authority_leaks.csv", "text/csv")
    
    with col2:
        if 'facet_results' in st.session_state:
            data = [{
                'faceta': r['breakdown'].facet_name,
                'score': r['breakdown'].total_score,
                'urls_200': r['urls_200'],
                'demanda': r['demand'],
                'accion': r['breakdown'].action_type
            } for r in st.session_state.facet_results]
            csv = pd.DataFrame(data).to_csv(index=False)
            st.download_button("📥 Facetas (CSV)", csv, "facets.csv", "text/csv")
    
    if st.button("📄 Generar Reporte"):
        report = generate_implementation_report(
            st.session_state.authority_result,
            st.session_state.get('facet_results', [])
        )
        st.download_button("📥 Reporte (MD)", report, "report.md", "text/markdown")
        with st.expander("Vista previa"):
            st.markdown(report)
