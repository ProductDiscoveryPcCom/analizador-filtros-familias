"""
Configuración central de la herramienta Facet Architecture Analyzer v2
Todos los patrones y constantes verificados en auditoría crítica
"""

# =============================================================================
# PATRONES DE BÚSQUEDA - VERIFICADOS Y CONSISTENTES
# =============================================================================

FACET_PATTERNS = {
    'PULGADAS': {
        'pattern': r'pulgadas|pequeno',
        'description': 'Filtros de tamaño de pantalla',
        'adobe_filter': 'pulgadas:',
    },
    '5G': {
        'pattern': r'5g',
        'description': 'Conectividad 5G (incluye modelos)',
        'adobe_filter': 'conectividad:',
    },
    'RAM': {
        'pattern': r'gb-ram',
        'description': 'Memoria RAM',
        'adobe_filter': 'memoria ram:',
    },
    'ALMACENAMIENTO': {
        'pattern': r'\d+-gb(?!-ram)',
        'description': 'Capacidad de almacenamiento',
        'adobe_filter': 'almacenamiento:',
    },
    'DUAL_SIM': {
        'pattern': r'dual-sim',
        'description': 'Dual SIM',
        'adobe_filter': None,
    },
    'NFC': {
        'pattern': r'/nfc',
        'description': 'Tecnología NFC',
        'adobe_filter': None,
    },
    'REACONDICIONADO': {
        'pattern': r'reacondicionado',
        'description': 'Estado reacondicionado',
        'adobe_filter': 'estado del articulo:',
    },
    'MARCA': {
        'pattern': r'apple|samsung|xiaomi|google|oppo|realme|motorola|honor|poco|nothing|huawei',
        'description': 'Marcas principales',
        'adobe_filter': 'marcas:',
    },
}

# =============================================================================
# CONFIGURACIÓN DE MODELOS AI - VALIDACIÓN DUAL
# =============================================================================

AI_MODELS = {
    'claude-sonnet-4': {
        'id': 'claude-sonnet-4-20250514',
        'provider': 'anthropic',
        'cost_input': 3.0,   # $ por 1M tokens
        'cost_output': 15.0,
        'strengths': ['código', 'análisis de datos', 'razonamiento'],
    },
    'claude-opus-4': {
        'id': 'claude-opus-4-20250514',
        'provider': 'anthropic',
        'cost_input': 15.0,
        'cost_output': 75.0,
        'strengths': ['razonamiento complejo', 'decisiones críticas'],
    },
    'gpt-4o': {
        'id': 'gpt-4o',
        'provider': 'openai',
        'cost_input': 2.5,
        'cost_output': 10.0,
        'strengths': ['validación', 'detección de inconsistencias'],
    },
    'gpt-4-turbo': {
        'id': 'gpt-4-turbo',
        'provider': 'openai',
        'cost_input': 10.0,
        'cost_output': 30.0,
        'strengths': ['precisión numérica', 'validación crítica'],
    },
}

AI_CONFIGS = {
    'economic': {
        'name': 'Economic',
        'description': 'Para análisis exploratorio y validación rápida',
        'cost_estimate': '$2-3/sesión',
        'models': {
            'query_generation': 'claude-sonnet-4',
            'primary_analysis': 'claude-sonnet-4',
            'validation': 'gpt-4o',
            'chat': 'claude-sonnet-4',
            'chat_validation': 'gpt-4o',
            'recommendations': 'claude-sonnet-4',
            'recommendations_validation': 'gpt-4o',
            'arbiter': 'gpt-4-turbo',  # Para resolver conflictos
        },
    },
    'hybrid': {
        'name': 'Hybrid',
        'description': 'Balance calidad/coste - RECOMENDADO',
        'cost_estimate': '$5-8/sesión',
        'models': {
            'query_generation': 'claude-sonnet-4',
            'primary_analysis': 'claude-sonnet-4',
            'validation': 'gpt-4-turbo',
            'chat': 'claude-sonnet-4',
            'chat_validation': 'gpt-4o',
            'recommendations': 'claude-opus-4',
            'recommendations_validation': 'gpt-4-turbo',
            'arbiter': 'claude-opus-4',
        },
    },
    'premium': {
        'name': 'Premium',
        'description': 'Máxima precisión para decisiones críticas',
        'cost_estimate': '$15-25/sesión',
        'models': {
            'query_generation': 'claude-opus-4',
            'primary_analysis': 'claude-opus-4',
            'validation': 'gpt-4-turbo',
            'chat': 'claude-opus-4',
            'chat_validation': 'gpt-4-turbo',
            'recommendations': 'claude-opus-4',
            'recommendations_validation': 'gpt-4-turbo',
            'arbiter': 'claude-sonnet-4',  # Tercer modelo como árbitro
        },
    },
}

# =============================================================================
# UMBRALES Y CONFIGURACIÓN DE ANÁLISIS
# =============================================================================

ANALYSIS_THRESHOLDS = {
    # Fuga de autoridad
    'min_traffic_for_leak': 100,      # Mínimo tráfico para considerar "fuga"
    'high_traffic_threshold': 1000,   # Umbral de tráfico alto
    
    # Dilución de autoridad
    'max_links_optimal': 10,          # Máximo enlaces recomendado
    'min_traffic_for_dilution': 500,  # Tráfico mínimo para no considerar dilución
    
    # Niveles de confianza
    'high_confidence_sources': 3,     # Mínimo fuentes para alta confianza
    'medium_confidence_sources': 2,
    
    # Consenso AI
    'numeric_tolerance': 0.01,        # 1% tolerancia para comparar números
    'min_consensus_confidence': 0.8,  # 80% mínimo para consenso
}

# =============================================================================
# ARCHIVOS DE DATOS ESPERADOS
# =============================================================================

DATA_FILES = {
    'crawl_adobe': {
        'filename': 'internos_html_smartphone_urls_adobe - internos_html_smartphone_urls_adobe.csv',
        'description': 'Crawl de URLs de Adobe Analytics',
        'required_columns': ['Dirección', 'Código de respuesta', 'Indexabilidad'],
    },
    'crawl_sf_original': {
        'filename': 'smartphone_crawl_internal_html_all.csv',
        'description': 'Crawl original de Screaming Frog',
        'required_columns': ['Dirección', 'Código de respuesta', 'Clics'],
    },
    'adobe_urls': {
        'filename': 'Sesiones_por_filtro_-_SEO__5__-_Page_Clean_URL__1_.csv',
        'description': 'Tráfico SEO por URL (Adobe 2025)',
        'skip_rows': 13,
        'columns': ['url', 'visits_seo'],
    },
    'adobe_filters': {
        'filename': 'Sesiones_por_filtro_-_SEO__3__-_Search_Filters.csv',
        'description': 'Demanda por filtros (Adobe 2025)',
        'skip_rows': 13,
        'columns': ['filter_name', 'visits_seo'],
    },
    'gsc': {
        'filename': 'PCCOM_Top_Query_ES_Untitled_page_Tabla_smartphone.csv',
        'description': 'Google Search Console - Top queries',
        'required_columns': ['Top queries', 'Clics', 'Impresiones'],
    },
    'semrush': {
        'filename': 'smartphone_broad-match_es_2026-01-13.csv',
        'description': 'Keywords SEMrush',
        'required_columns': ['Keyword', 'Volume'],
    },
}

# =============================================================================
# CONSTANTES VERIFICADAS EN AUDITORÍA
# =============================================================================

VERIFIED_METRICS = {
    'total_urls_crawl': 26330,
    'urls_200': 8170,
    'urls_404': 17482,
    'urls_301': 678,
    'pages_with_wrapper': 5642,
    'pages_without_wrapper': 2528,
    'traffic_not_distributed': 67312,
    'pages_high_traffic_no_wrapper': 62,
    'dilution_pages': 37,
    'pulgadas_historical_traffic': 39030,
}
