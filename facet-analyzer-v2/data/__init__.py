"""
Módulo de datos - Facet Architecture Analyzer v2.2
"""

from .loaders import (
    DataLoader,
    FileType,
    FileTypeDetector,
    LoadResult,
    DatasetStats,
    validate_data_integrity,
    render_file_upload_ui
)

from .family_library import (
    FamilyLibrary,
    FamilyMetadata,
    FamilyFile,
    get_default_library,
    quick_create_family
)

from .data_config import (
    DataSourceConfig,
    FacetMapping,
    DatasetContext,
    FacetDetector,
    render_data_period_config,
    render_facet_mapping_ui
)

__all__ = [
    # Loaders
    'DataLoader',
    'FileType',
    'FileTypeDetector', 
    'LoadResult',
    'DatasetStats',
    'validate_data_integrity',
    'render_file_upload_ui',
    
    # Family Library
    'FamilyLibrary',
    'FamilyMetadata',
    'FamilyFile',
    'get_default_library',
    'quick_create_family',
    
    # Data Config
    'DataSourceConfig',
    'FacetMapping',
    'DatasetContext',
    'FacetDetector',
    'render_data_period_config',
    'render_facet_mapping_ui',
]
