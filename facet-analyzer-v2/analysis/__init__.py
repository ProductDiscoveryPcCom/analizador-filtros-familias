"""
Módulo de análisis - Facet Architecture Analyzer v2.3
"""

from .authority_analyzer import (
    AuthorityAnalyzer,
    AuthorityLeak,
    AuthorityAnalysisResult,
    get_wrapper_distribution
)

from .facet_analyzer import (
    FacetAnalyzer,
    FacetStatus,
    FacetAnalysisResult
)

from .scoring import (
    FacetScorer,
    FacetScore,
    ScoringWeights,
    calculate_indexation_score,
    generate_scoring_report
)

__all__ = [
    # Authority
    'AuthorityAnalyzer',
    'AuthorityLeak',
    'AuthorityAnalysisResult',
    'get_wrapper_distribution',
    
    # Facet
    'FacetAnalyzer',
    'FacetStatus',
    'FacetAnalysisResult',
    
    # Scoring
    'FacetScorer',
    'FacetScore',
    'ScoringWeights',
    'calculate_indexation_score',
    'generate_scoring_report',
]
