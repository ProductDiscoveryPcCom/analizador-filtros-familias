"""
Verificador HTTP de URLs - v2.2
Verifica el estado de URLs en lotes con manejo de rate limiting
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import requests
import time

# aiohttp es opcional (para verificación async)
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

# Streamlit es opcional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


@dataclass
class URLVerificationResult:
    """Resultado de verificación de una URL"""
    url: str
    status_code: int
    redirect_url: Optional[str] = None
    response_time_ms: float = 0
    error: Optional[str] = None
    verified_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'status_code': self.status_code,
            'redirect_url': self.redirect_url,
            'response_time_ms': self.response_time_ms,
            'error': self.error,
            'verified_at': self.verified_at,
        }


class HTTPVerifier:
    """Verificador HTTP con soporte para verificación en lotes"""
    
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (compatible; FacetAnalyzer/2.2; +https://pccomponentes.com)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    }
    
    def __init__(self, 
                 timeout: int = 10,
                 max_concurrent: int = 10,
                 delay_between_batches: float = 1.0):
        """
        Args:
            timeout: Timeout en segundos para cada request
            max_concurrent: Máximo de requests concurrentes
            delay_between_batches: Delay entre lotes en segundos
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.delay_between_batches = delay_between_batches
        self.results: List[URLVerificationResult] = []
    
    def verify_url_sync(self, url: str) -> URLVerificationResult:
        """Verifica una URL de forma síncrona"""
        start_time = time.time()
        
        try:
            response = requests.head(
                url,
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout,
                allow_redirects=False
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            redirect_url = None
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('Location', '')
            
            return URLVerificationResult(
                url=url,
                status_code=response.status_code,
                redirect_url=redirect_url,
                response_time_ms=round(elapsed_ms, 2),
                verified_at=datetime.now().isoformat()
            )
            
        except requests.exceptions.Timeout:
            return URLVerificationResult(
                url=url,
                status_code=0,
                error='Timeout',
                response_time_ms=(time.time() - start_time) * 1000,
                verified_at=datetime.now().isoformat()
            )
        except requests.exceptions.ConnectionError as e:
            return URLVerificationResult(
                url=url,
                status_code=0,
                error=f'Connection error: {str(e)[:50]}',
                verified_at=datetime.now().isoformat()
            )
        except Exception as e:
            return URLVerificationResult(
                url=url,
                status_code=0,
                error=str(e)[:100],
                verified_at=datetime.now().isoformat()
            )
    
    def verify_batch_sync(self, urls: List[str], progress_callback=None) -> List[URLVerificationResult]:
        """
        Verifica un lote de URLs de forma síncrona con threading
        
        Args:
            urls: Lista de URLs a verificar
            progress_callback: Función callback para reportar progreso
        """
        results = []
        total = len(urls)
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(self.verify_url_sync, url): url for url in urls}
            
            for i, future in enumerate(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = futures[future]
                    results.append(URLVerificationResult(
                        url=url,
                        status_code=0,
                        error=str(e)[:100],
                        verified_at=datetime.now().isoformat()
                    ))
                
                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(i + 1, total)
        
        self.results = results
        return results
    
    def get_summary(self) -> Dict:
        """Obtiene resumen de verificaciones"""
        if not self.results:
            return {}
        
        status_counts = {}
        errors = 0
        total_time = 0
        
        for r in self.results:
            if r.status_code == 0:
                errors += 1
            else:
                status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1
            total_time += r.response_time_ms
        
        return {
            'total': len(self.results),
            'status_200': status_counts.get(200, 0),
            'status_301': status_counts.get(301, 0),
            'status_302': status_counts.get(302, 0),
            'status_404': status_counts.get(404, 0),
            'status_500': status_counts.get(500, 0),
            'errors': errors,
            'avg_response_ms': total_time / max(len(self.results), 1),
            'status_counts': status_counts,
        }
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convierte resultados a DataFrame"""
        if not self.results:
            return pd.DataFrame()
        
        return pd.DataFrame([r.to_dict() for r in self.results])


def verify_urls_with_progress(urls: List[str], 
                              max_concurrent: int = 5,
                              timeout: int = 10) -> Tuple[pd.DataFrame, Dict]:
    """
    Verifica URLs mostrando progreso en Streamlit
    
    Args:
        urls: Lista de URLs a verificar
        max_concurrent: Conexiones simultáneas
        timeout: Timeout por URL
    
    Returns:
        (DataFrame con resultados, Diccionario con resumen)
    """
    verifier = HTTPVerifier(
        timeout=timeout,
        max_concurrent=max_concurrent
    )
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(current, total):
        progress_bar.progress(current / total)
        status_text.text(f"Verificando: {current}/{total} URLs")
    
    results = verifier.verify_batch_sync(urls, progress_callback=update_progress)
    
    progress_bar.progress(1.0)
    status_text.text(f"✅ Completado: {len(urls)} URLs verificadas")
    
    return verifier.to_dataframe(), verifier.get_summary()


def create_verification_summary(df: pd.DataFrame) -> str:
    """Crea resumen markdown de verificación"""
    if len(df) == 0:
        return "No hay datos de verificación."
    
    total = len(df)
    status_200 = len(df[df['status_code'] == 200])
    status_404 = len(df[df['status_code'] == 404])
    status_301 = len(df[df['status_code'] == 301])
    errors = len(df[df['status_code'] == 0])
    
    summary = f"""
## Resumen de Verificación HTTP

| Métrica | Valor |
|---------|-------|
| Total URLs | {total:,} |
| URLs activas (200) | {status_200:,} ({status_200/total*100:.1f}%) |
| URLs eliminadas (404) | {status_404:,} ({status_404/total*100:.1f}%) |
| Redirecciones (301) | {status_301:,} ({status_301/total*100:.1f}%) |
| Errores de conexión | {errors:,} ({errors/total*100:.1f}%) |
"""
    
    if status_404 > 0:
        summary += f"\n⚠️ **{status_404:,} URLs devuelven 404** - considerar redirección o eliminación de enlaces\n"
    
    if errors > 0:
        summary += f"\n⚠️ **{errors:,} URLs no respondieron** - verificar manualmente\n"
    
    return summary
