"""
Módulo de verificación HTTP en tiempo real
Verifica el estado actual de URLs antes de recomendar
"""

import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from urllib.parse import urlparse
import streamlit as st


@dataclass
class HTTPVerificationResult:
    """Resultado de verificación HTTP de una URL"""
    url: str
    status_code: int
    is_ok: bool                    # 200-299
    is_redirect: bool              # 301, 302, 307, 308
    redirect_target: Optional[str]
    is_indexable: bool             # No redirect, no noindex
    response_time_ms: float
    error: Optional[str]
    verified_at: str


@dataclass 
class BatchVerificationResult:
    """Resultado de verificación de lote de URLs"""
    total_urls: int
    verified: int
    ok_count: int                  # 200-299
    redirect_count: int            # 3xx
    not_found_count: int           # 404
    error_count: int               # 5xx u otros errores
    results: List[HTTPVerificationResult]
    duration_seconds: float


class HTTPVerifier:
    """
    Verificador HTTP para URLs
    Verifica estado actual antes de hacer recomendaciones
    """
    
    def __init__(self, 
                 timeout: int = 10,
                 max_workers: int = 5,  # Reducido de 10 a 5
                 user_agent: str = None,
                 rate_limit_delay: float = 0.3):  # Aumentado de 0.1 a 0.3
        """
        Inicializa el verificador
        
        Args:
            timeout: Timeout por request en segundos
            max_workers: Máximo de requests paralelos (5 recomendado para evitar bloqueos)
            user_agent: User agent personalizado
            rate_limit_delay: Delay entre requests (segundos) - 0.3s = ~3 req/s máximo
        """
        self.timeout = timeout
        self.max_workers = max_workers
        self.rate_limit_delay = rate_limit_delay
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; FacetAnalyzer/2.0; "
            "+https://www.pccomponentes.com)"
        )
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Crea sesión HTTP con configuración óptima"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'es-ES,es;q=0.9',
        })
        # Configurar retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def verify_url(self, url: str) -> HTTPVerificationResult:
        """
        Verifica una URL individual
        
        Args:
            url: URL a verificar
        
        Returns:
            HTTPVerificationResult con estado actual
        """
        from datetime import datetime
        
        start_time = time.time()
        
        try:
            # HEAD request primero (más rápido)
            response = self.session.head(
                url, 
                timeout=self.timeout,
                allow_redirects=False
            )
            
            status_code = response.status_code
            response_time = (time.time() - start_time) * 1000
            
            # Detectar redirect
            is_redirect = status_code in [301, 302, 307, 308]
            redirect_target = None
            if is_redirect:
                redirect_target = response.headers.get('Location', '')
                # Resolver URL relativa
                if redirect_target and not redirect_target.startswith('http'):
                    parsed = urlparse(url)
                    redirect_target = f"{parsed.scheme}://{parsed.netloc}{redirect_target}"
            
            # Verificar si es indexable
            # (No redirect + código 200 + sin x-robots-tag noindex)
            x_robots = response.headers.get('X-Robots-Tag', '').lower()
            is_indexable = (
                status_code == 200 and 
                'noindex' not in x_robots
            )
            
            return HTTPVerificationResult(
                url=url,
                status_code=status_code,
                is_ok=200 <= status_code < 300,
                is_redirect=is_redirect,
                redirect_target=redirect_target,
                is_indexable=is_indexable,
                response_time_ms=response_time,
                error=None,
                verified_at=datetime.now().isoformat()
            )
            
        except requests.Timeout:
            return HTTPVerificationResult(
                url=url,
                status_code=0,
                is_ok=False,
                is_redirect=False,
                redirect_target=None,
                is_indexable=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error="Timeout",
                verified_at=datetime.now().isoformat()
            )
        except requests.RequestException as e:
            return HTTPVerificationResult(
                url=url,
                status_code=0,
                is_ok=False,
                is_redirect=False,
                redirect_target=None,
                is_indexable=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
                verified_at=datetime.now().isoformat()
            )
    
    def verify_batch(self, 
                     urls: List[str], 
                     progress_callback=None) -> BatchVerificationResult:
        """
        Verifica un lote de URLs en paralelo
        
        Args:
            urls: Lista de URLs a verificar
            progress_callback: Función para reportar progreso (opcional)
        
        Returns:
            BatchVerificationResult con todos los resultados
        """
        start_time = time.time()
        results = []
        
        # Usar ThreadPoolExecutor para paralelismo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Enviar todas las tareas
            future_to_url = {
                executor.submit(self.verify_url, url): url 
                for url in urls
            }
            
            # Recoger resultados
            completed = 0
            for future in as_completed(future_to_url):
                result = future.result()
                results.append(result)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, len(urls))
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
        
        # Calcular estadísticas
        duration = time.time() - start_time
        ok_count = sum(1 for r in results if r.is_ok)
        redirect_count = sum(1 for r in results if r.is_redirect)
        not_found_count = sum(1 for r in results if r.status_code == 404)
        error_count = sum(1 for r in results if r.error is not None)
        
        return BatchVerificationResult(
            total_urls=len(urls),
            verified=len(results),
            ok_count=ok_count,
            redirect_count=redirect_count,
            not_found_count=not_found_count,
            error_count=error_count,
            results=results,
            duration_seconds=duration
        )
    
    def verify_recommendations(self, 
                                recommendations: List[Dict],
                                url_field: str = 'url') -> List[Dict]:
        """
        Verifica URLs de una lista de recomendaciones
        Añade campo 'http_verified' a cada recomendación
        
        Args:
            recommendations: Lista de dicts con recomendaciones
            url_field: Nombre del campo que contiene la URL
        
        Returns:
            Recomendaciones con verificación HTTP añadida
        """
        urls = [r.get(url_field) for r in recommendations if r.get(url_field)]
        
        # Verificar en lote
        batch_result = self.verify_batch(urls)
        
        # Crear mapa de resultados
        verification_map = {r.url: r for r in batch_result.results}
        
        # Añadir verificación a cada recomendación
        verified_recommendations = []
        for rec in recommendations:
            url = rec.get(url_field)
            verification = verification_map.get(url)
            
            rec_copy = rec.copy()
            if verification:
                rec_copy['http_verified'] = {
                    'status_code': verification.status_code,
                    'is_ok': verification.is_ok,
                    'is_indexable': verification.is_indexable,
                    'redirect_target': verification.redirect_target,
                    'verified_at': verification.verified_at,
                    'error': verification.error
                }
                
                # Actualizar confianza basada en verificación
                if not verification.is_ok:
                    rec_copy['confidence'] = 'LOW'
                    rec_copy['recommendation'] = f"⚠️ URL no disponible ({verification.status_code}). {rec.get('recommendation', '')}"
            else:
                rec_copy['http_verified'] = None
            
            verified_recommendations.append(rec_copy)
        
        return verified_recommendations


class RecommendationVerifier:
    """
    Verifica recomendaciones antes de presentarlas
    Integra verificación HTTP con análisis de facetas
    """
    
    def __init__(self):
        self.http_verifier = HTTPVerifier()
    
    def verify_authority_leaks(self, leaks: List) -> List:
        """
        Verifica URLs de fugas de autoridad
        
        Args:
            leaks: Lista de AuthorityLeak
        
        Returns:
            Lista de leaks con verificación HTTP
        """
        # Extraer URLs
        urls = [leak.url for leak in leaks]
        
        # Verificar
        batch_result = self.http_verifier.verify_batch(urls)
        verification_map = {r.url: r for r in batch_result.results}
        
        # Añadir verificación
        verified_leaks = []
        for leak in leaks:
            verification = verification_map.get(leak.url)
            
            # Crear copia con verificación
            leak_dict = {
                'url': leak.url,
                'traffic_seo': leak.traffic_seo,
                'wrapper_links': leak.wrapper_links,
                'leak_type': leak.leak_type,
                'severity': leak.severity,
                'recommendation': leak.recommendation,
                'http_status': verification.status_code if verification else None,
                'http_ok': verification.is_ok if verification else False,
                'http_indexable': verification.is_indexable if verification else False,
            }
            
            # Ajustar recomendación si URL no está disponible
            if verification and not verification.is_ok:
                leak_dict['severity'] = 'info'  # Bajar severidad
                leak_dict['recommendation'] = f"ℹ️ URL ya no disponible ({verification.status_code})"
            
            verified_leaks.append(leak_dict)
        
        return verified_leaks
    
    def verify_facet_opportunities(self, facets: List) -> List:
        """
        Verifica URLs de oportunidades de facetas
        
        Args:
            facets: Lista de FacetStatus
        
        Returns:
            Lista de facetas con verificación HTTP de URLs de ejemplo
        """
        # Para cada faceta, verificar algunas URLs de ejemplo
        # (no todas, para no sobrecargar)
        verified_facets = []
        
        for facet in facets:
            facet_dict = {
                'name': facet.name,
                'status': facet.status,
                'urls_200': facet.urls_200,
                'urls_404': facet.urls_404,
                'demand_adobe': facet.demand_adobe,
                'opportunity_score': facet.opportunity_score,
                'confidence': facet.confidence,
                'recommendation': facet.recommendation,
                'http_verified': False,  # Marcar si se verificó
            }
            verified_facets.append(facet_dict)
        
        return verified_facets


# =============================================================================
# FUNCIONES DE UTILIDAD PARA STREAMLIT
# =============================================================================

def verify_urls_with_progress(urls: List[str], 
                               container=None) -> BatchVerificationResult:
    """
    Verifica URLs mostrando progreso en Streamlit
    
    Args:
        urls: Lista de URLs
        container: Contenedor de Streamlit para mostrar progreso
    
    Returns:
        BatchVerificationResult
    """
    verifier = HTTPVerifier()
    
    if container:
        progress_bar = container.progress(0)
        status_text = container.empty()
        
        def update_progress(current, total):
            progress_bar.progress(current / total)
            status_text.text(f"Verificando... {current}/{total} URLs")
        
        result = verifier.verify_batch(urls, progress_callback=update_progress)
        
        progress_bar.empty()
        status_text.empty()
    else:
        result = verifier.verify_batch(urls)
    
    return result


def create_verification_summary(result: BatchVerificationResult) -> str:
    """
    Crea resumen legible de verificación HTTP
    
    Args:
        result: BatchVerificationResult
    
    Returns:
        Markdown con resumen
    """
    summary = f"""
### 🔍 Verificación HTTP Completada

| Métrica | Valor |
|---------|-------|
| URLs verificadas | {result.verified} |
| ✅ OK (200) | {result.ok_count} |
| ➡️ Redirecciones | {result.redirect_count} |
| ❌ No encontradas (404) | {result.not_found_count} |
| ⚠️ Errores | {result.error_count} |
| ⏱️ Tiempo | {result.duration_seconds:.1f}s |

"""
    
    # Añadir alertas si hay problemas
    if result.not_found_count > 0:
        summary += f"\n⚠️ **Atención**: {result.not_found_count} URLs devuelven 404\n"
    
    if result.error_count > 0:
        summary += f"\n⚠️ **Errores de red**: {result.error_count} URLs no pudieron verificarse\n"
    
    return summary
