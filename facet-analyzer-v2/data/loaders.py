"""
Módulo de carga y normalización de datos
Maneja todos los archivos CSV con validación
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import streamlit as st


class DataLoader:
    """Cargador de datos con caché y validación"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path('/mnt/user-data/uploads')
        self.data: Dict[str, pd.DataFrame] = {}
        self.load_status: Dict[str, bool] = {}
        
    @st.cache_data(ttl=3600)
    def load_crawl_adobe(_self, filepath: str = None) -> pd.DataFrame:
        """Carga el crawl de URLs de Adobe"""
        if filepath is None:
            filepath = _self.data_dir / 'internos_html_smartphone_urls_adobe - internos_html_smartphone_urls_adobe.csv'
        
        df = pd.read_csv(filepath, low_memory=False)
        
        # Calcular enlaces en seoFilterWrapper
        href_cols = [f'seoFilterWrapper_hrefs {i}' for i in range(1, 84)]
        
        def count_wrapper_links(row):
            count = 0
            for col in href_cols:
                if col in df.columns:
                    val = row.get(col)
                    if pd.notna(val) and str(val).strip() and str(val).startswith('http'):
                        count += 1
            return count
        
        df['wrapper_link_count'] = df.apply(count_wrapper_links, axis=1)
        df['has_wrapper'] = df['wrapper_link_count'] > 0
        
        return df
    
    @st.cache_data(ttl=3600)
    def load_crawl_sf_original(_self, filepath: str = None) -> pd.DataFrame:
        """Carga el crawl original de Screaming Frog"""
        if filepath is None:
            filepath = _self.data_dir / 'smartphone_crawl_internal_html_all.csv'
        
        df = pd.read_csv(filepath, encoding='utf-8-sig', low_memory=False)
        
        # Convertir columnas numéricas
        numeric_cols = ['Clics', 'Impresiones', 'Posición']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    
    @st.cache_data(ttl=3600)
    def load_adobe_urls(_self, filepath: str = None) -> pd.DataFrame:
        """Carga tráfico SEO por URL de Adobe"""
        if filepath is None:
            filepath = _self.data_dir / 'Sesiones_por_filtro_-_SEO__5__-_Page_Clean_URL__1_.csv'
        
        df = pd.read_csv(filepath, skiprows=13, encoding='utf-8-sig')
        df.columns = ['url', 'visits_seo']
        df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
        
        # Normalizar URLs
        df['url_full'] = df['url'].apply(
            lambda x: 'https://' + str(x) if not str(x).startswith('http') else str(x)
        )
        
        return df
    
    @st.cache_data(ttl=3600)
    def load_adobe_filters(_self, filepath: str = None) -> pd.DataFrame:
        """Carga demanda por filtros de Adobe"""
        if filepath is None:
            filepath = _self.data_dir / 'Sesiones_por_filtro_-_SEO__3__-_Search_Filters.csv'
        
        df = pd.read_csv(filepath, skiprows=13, encoding='utf-8-sig')
        df.columns = ['filter_name', 'visits_seo']
        df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
        
        return df
    
    @st.cache_data(ttl=3600)
    def load_gsc(_self, filepath: str = None) -> pd.DataFrame:
        """Carga datos de Google Search Console"""
        if filepath is None:
            filepath = _self.data_dir / 'PCCOM_Top_Query_ES_Untitled_page_Tabla_smartphone.csv'
        
        df = pd.read_csv(filepath)
        
        # Convertir columnas numéricas
        numeric_cols = ['Clics', 'Impresiones']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    
    @st.cache_data(ttl=3600)
    def load_semrush(_self, filepath: str = None) -> pd.DataFrame:
        """Carga keywords de SEMrush"""
        if filepath is None:
            filepath = _self.data_dir / 'smartphone_broad-match_es_2026-01-13.csv'
        
        df = pd.read_csv(filepath)
        return df
    
    def load_all(self) -> Dict[str, pd.DataFrame]:
        """Carga todos los datasets disponibles"""
        loaders = {
            'crawl_adobe': self.load_crawl_adobe,
            'crawl_sf': self.load_crawl_sf_original,
            'adobe_urls': self.load_adobe_urls,
            'adobe_filters': self.load_adobe_filters,
            'gsc': self.load_gsc,
            'semrush': self.load_semrush,
        }
        
        for name, loader in loaders.items():
            try:
                self.data[name] = loader()
                self.load_status[name] = True
            except Exception as e:
                self.load_status[name] = False
                st.warning(f"No se pudo cargar {name}: {e}")
        
        return self.data
    
    def get_merged_data(self) -> pd.DataFrame:
        """Combina crawl con tráfico de Adobe"""
        if 'crawl_adobe' not in self.data or 'adobe_urls' not in self.data:
            raise ValueError("Faltan datos necesarios para merge")
        
        crawl = self.data['crawl_adobe']
        adobe = self.data['adobe_urls']
        
        merged = crawl.merge(
            adobe[['url_full', 'visits_seo']],
            left_on='Dirección',
            right_on='url_full',
            how='left'
        )
        merged['visits_seo'] = merged['visits_seo'].fillna(0)
        
        return merged
    
    def get_urls_by_status(self) -> Dict[str, set]:
        """Retorna sets de URLs por código de respuesta"""
        if 'crawl_adobe' not in self.data:
            raise ValueError("Crawl no cargado")
        
        df = self.data['crawl_adobe']
        
        return {
            '200': set(df[df['Código de respuesta'] == 200]['Dirección']),
            '404': set(df[df['Código de respuesta'] == 404]['Dirección']),
            '301': set(df[df['Código de respuesta'] == 301]['Dirección']),
        }


def validate_data_integrity(data: Dict[str, pd.DataFrame], expected_metrics: Dict = None) -> Dict[str, any]:
    """
    Valida integridad de datos
    
    Args:
        data: DataFrames cargados
        expected_metrics: Métricas esperadas (opcional). 
                          Si no se proporciona, solo calcula estadísticas sin validar.
    
    Returns:
        Dict con resultados de validación o estadísticas
    """
    results = {}
    
    if 'crawl_adobe' in data:
        df = data['crawl_adobe']
        
        actual_total = len(df)
        actual_200 = len(df[df['Código de respuesta'] == 200])
        actual_404 = len(df[df['Código de respuesta'] == 404])
        
        # Si hay métricas esperadas, validar
        if expected_metrics:
            results['total_urls'] = {
                'expected': expected_metrics.get('total_urls_crawl'),
                'actual': actual_total,
                'match': actual_total == expected_metrics.get('total_urls_crawl')
            }
            results['urls_200'] = {
                'expected': expected_metrics.get('urls_200'),
                'actual': actual_200,
                'match': actual_200 == expected_metrics.get('urls_200')
            }
            results['urls_404'] = {
                'expected': expected_metrics.get('urls_404'),
                'actual': actual_404,
                'match': actual_404 == expected_metrics.get('urls_404')
            }
        else:
            # Solo mostrar estadísticas sin validar
            results['total_urls'] = {
                'expected': None,
                'actual': actual_total,
                'match': True  # Sin expectativa, siempre "válido"
            }
            results['urls_200'] = {
                'expected': None,
                'actual': actual_200,
                'match': True
            }
            results['urls_404'] = {
                'expected': None,
                'actual': actual_404,
                'match': True
            }
    
    return results
