"""
Configuración central de la herramienta Facet Architecture Analyzer v2.3
Configuración genérica para cualquier categoría de productos
"""

# =============================================================================
# CONFIGURACIÓN DE MODELOS AI - VALIDACIÓN DUAL
# =============================================================================

AI_MODELS = {
    'claude-sonnet-4': {
        'id': 'claude-sonnet-4-20250514',
        'provider': 'anthropic',
        'cost_input': 3.0,
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
        'name': '💰 Economic',
        'description': 'Para análisis exploratorio y validación rápida',
        'cost_estimate': '$2-3/sesión',
        'models': {
            'query_generation': 'claude-sonnet-4',
            'primary_analysis': 'claude-sonnet-4',
            'validation': 'gpt-4o',
            'chat': 'claude-sonnet-4',
            'chat_validation': 'gpt-4o',
        },
    },
    'hybrid': {
        'name': '⚖️ Hybrid (Recomendado)',
        'description': 'Balance calidad/coste',
        'cost_estimate': '$5-8/sesión',
        'models': {
            'query_generation': 'claude-sonnet-4',
            'primary_analysis': 'claude-sonnet-4',
            'validation': 'gpt-4-turbo',
            'chat': 'claude-sonnet-4',
            'chat_validation': 'gpt-4o',
            'recommendations': 'claude-opus-4',
        },
    },
    'premium': {
        'name': '🏆 Premium',
        'description': 'Máxima precisión para decisiones críticas',
        'cost_estimate': '$15-25/sesión',
        'models': {
            'query_generation': 'claude-opus-4',
            'primary_analysis': 'claude-opus-4',
            'validation': 'gpt-4-turbo',
            'chat': 'claude-opus-4',
            'chat_validation': 'gpt-4-turbo',
        },
    },
}

# =============================================================================
# PATRONES DE FACETAS (referencia, los específicos están en data_config.py)
# =============================================================================

FACET_PATTERNS = {
    'SIZE': {
        'pattern': r'pulgadas|litros|cm|metros',
        'description': 'Tamaño/Dimensiones',
    },
    'MEMORY': {
        'pattern': r'gb-ram|memoria',
        'description': 'Memoria RAM',
    },
    'STORAGE': {
        'pattern': r'\d+-gb(?!-ram)|\d+-tb',
        'description': 'Almacenamiento',
    },
    'CONNECTIVITY': {
        'pattern': r'5g|wifi|bluetooth|nfc',
        'description': 'Conectividad',
    },
    'CONDITION': {
        'pattern': r'nuevo|reacondicionado|seminuevo',
        'description': 'Estado del producto',
    },
    'BRAND': {
        'pattern': r'',
        'description': 'Marcas',
    },
}

# =============================================================================
# UMBRALES DE ANÁLISIS
# =============================================================================

ANALYSIS_THRESHOLDS = {
    # Fuga de autoridad
    'min_traffic_for_leak': 100,
    'high_traffic_threshold': 1000,
    
    # Dilución
    'max_links_optimal': 10,
    'min_traffic_for_dilution': 500,
    
    # Confianza
    'high_confidence_sources': 3,
    'medium_confidence_sources': 2,
    
    # Consenso AI
    'numeric_tolerance': 0.01,
    'min_consensus_confidence': 0.8,
    
    # Scoring de facetas
    'demand_very_high': 100000,
    'demand_high': 50000,
    'demand_medium': 10000,
    'demand_low': 1000,
}

# =============================================================================
# CLAVES DE DATOS UNIFICADAS
# =============================================================================

DATA_KEYS = {
    'crawl_master': 'crawl_master',
    'crawl_gsc': 'crawl_gsc',
    'crawl_historical': 'crawl_historical',
    'adobe_urls': 'adobe_urls',
    'adobe_filters': 'adobe_filters',
    'semrush': 'semrush',
    'keyword_planner': 'keyword_planner',
}

# Lista de claves de crawl en orden de prioridad
CRAWL_KEYS_PRIORITY = ['crawl_master', 'crawl_gsc', 'crawl_historical']

# =============================================================================
# MÉTRICAS VERIFICADAS (se actualizan por familia)
# =============================================================================

VERIFIED_METRICS = {
    'total_urls_crawl': None,
    'urls_200': None,
    'urls_404': None,
    'pages_with_wrapper': None,
    'pages_without_wrapper': None,
}
