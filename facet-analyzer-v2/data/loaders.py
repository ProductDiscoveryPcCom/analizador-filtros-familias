"""
Módulo de carga y normalización de datos - v2.2
Soporte completo para los 7 tipos de archivos de datos

Archivos soportados:
1. Crawl SF + GSC - Crawl con datos de Google Search Console integrados
2. Google Keyword Planner - Volúmenes de búsqueda de Google Ads
3. SEMrush KMT - Keywords con volumen, KD e intent
4. Adobe URLs SEO - Tráfico SEO por URL (con revenue/orders)
5. Crawl SF + Extracción Custom - Dataset maestro con seoFilterWrapper
6. Adobe Search Filters - Demanda de facetas/filtros usados
7. Crawl URLs Adobe - URLs históricas con tráfico (detecta 404s)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from enum import Enum
import re

# Streamlit es opcional - solo se usa en render_file_upload_ui
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


class FileType(Enum):
    """Tipos de archivo soportados"""
    CRAWL_SF_GSC = "crawl_sf_gsc"           # #1
    KEYWORD_PLANNER = "keyword_planner"      # #2
    SEMRUSH = "semrush"                      # #3
    ADOBE_URLS = "adobe_urls"                # #4
    CRAWL_MASTER = "crawl_master"            # #5 - Dataset maestro
    ADOBE_FILTERS = "adobe_filters"          # #6
    CRAWL_HISTORICAL = "crawl_historical"    # #7
    UNKNOWN = "unknown"


@dataclass
class LoadResult:
    """Resultado de carga de un archivo"""
    success: bool
    file_type: FileType
    dataframe: Optional[pd.DataFrame] = None
    row_count: int = 0
    columns: List[str] = field(default_factory=list)
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class DatasetStats:
    """Estadísticas de un dataset cargado"""
    total_urls: int = 0
    urls_200: int = 0
    urls_404: int = 0
    urls_301: int = 0
    urls_other: int = 0
    with_wrapper: int = 0
    without_wrapper: int = 0
    total_traffic: int = 0
    total_demand: int = 0


class FileTypeDetector:
    """Detecta automáticamente el tipo de archivo basándose en columnas y contenido"""
    
    # Patrones de columnas para cada tipo
    COLUMN_PATTERNS = {
        FileType.CRAWL_MASTER: {
            'required': ['Dirección', 'Código de respuesta'],
            'optional': ['seoFilterWrapper_hrefs 1', 'seoFilterWrapper_exists 1', 'Indexabilidad'],
            'has_wrapper_extraction': True
        },
        FileType.CRAWL_SF_GSC: {
            'required': ['Dirección', 'Código de respuesta'],
            'optional': ['Clics', 'Impresiones', 'Posición', 'CTR'],
            'has_gsc_data': True
        },
        FileType.CRAWL_HISTORICAL: {
            'required': ['Dirección', 'Código de respuesta'],
            'optional': [],
            'from_url_list': True  # Crawl generado desde lista de URLs
        },
        FileType.ADOBE_URLS: {
            'required': [],  # Columnas varían
            'patterns': ['url', 'visits', 'sessions', 'page'],
            'has_traffic': True
        },
        FileType.ADOBE_FILTERS: {
            'required': [],
            'patterns': ['filter', 'search', 'facet'],
            'has_filter_names': True
        },
        FileType.SEMRUSH: {
            'required': ['Keyword'],
            'optional': ['Volume', 'Keyword Difficulty', 'Intent', 'CPC'],
        },
        FileType.KEYWORD_PLANNER: {
            'required': [],
            'patterns': ['keyword', 'avg. monthly searches', 'competition'],
        },
    }
    
    @classmethod
    def detect(cls, df: pd.DataFrame, filename: str = "") -> FileType:
        """
        Detecta el tipo de archivo
        
        Args:
            df: DataFrame cargado
            filename: Nombre del archivo (ayuda en la detección)
        
        Returns:
            FileType detectado
        """
        columns_lower = [c.lower() for c in df.columns]
        filename_lower = filename.lower()
        
        # 1. Detectar por nombre de archivo primero
        if 'semrush' in filename_lower or 'broad-match' in filename_lower:
            return FileType.SEMRUSH
        
        if 'keyword_planner' in filename_lower or 'keyword planner' in filename_lower:
            return FileType.KEYWORD_PLANNER
        
        if 'filtro' in filename_lower and 'filter' in filename_lower.replace('filtro', ''):
            return FileType.ADOBE_FILTERS
        
        if 'filtro' in filename_lower and ('url' in filename_lower or 'page' in filename_lower):
            return FileType.ADOBE_URLS
        
        # 2. Detectar crawl con extracción de seoFilterWrapper (MASTER)
        wrapper_cols = [c for c in df.columns if 'seofilterwrapper' in c.lower()]
        if wrapper_cols and 'Dirección' in df.columns:
            return FileType.CRAWL_MASTER
        
        # 3. Detectar crawl con GSC
        if 'Dirección' in df.columns and 'Código de respuesta' in df.columns:
            gsc_cols = ['Clics', 'Impresiones', 'Posición']
            has_gsc = sum(1 for c in gsc_cols if c in df.columns) >= 2
            if has_gsc:
                return FileType.CRAWL_SF_GSC
            else:
                return FileType.CRAWL_HISTORICAL
        
        # 4. Detectar SEMrush
        if 'Keyword' in df.columns and 'Volume' in df.columns:
            return FileType.SEMRUSH
        
        # 5. Detectar Keyword Planner
        kp_patterns = ['avg. monthly searches', 'competition', 'top of page bid']
        if any(p in ' '.join(columns_lower) for p in kp_patterns):
            return FileType.KEYWORD_PLANNER
        
        # 6. Detectar Adobe por patrones de columnas
        # Primero verificar si es Adobe URLs (tiene columnas de URL/Page)
        url_patterns = ['url', 'page', 'entry']
        has_url_col = any(any(p in c.lower() for p in url_patterns) for c in df.columns)
        
        filter_patterns = ['filter', 'facet', 'search filter']
        has_filter_col = any(any(p in c.lower() for p in filter_patterns) for c in df.columns)
        
        # Verificar si la primera columna contiene URLs (empieza con http o /)
        first_val = str(df.iloc[0, 0]).lower() if len(df) > 0 else ''
        looks_like_url = 'http' in first_val or first_val.startswith('/') or 'www.' in first_val
        
        # Verificar si parece filtro (contiene ':' como separador faceta:valor)
        looks_like_filter = ':' in first_val and not 'http' in first_val
        
        if has_url_col or looks_like_url:
            if not has_filter_col and not looks_like_filter:
                return FileType.ADOBE_URLS
        
        if has_filter_col or looks_like_filter:
            return FileType.ADOBE_FILTERS
        
        return FileType.UNKNOWN


class DataLoader:
    """
    Cargador de datos unificado con auto-detección
    Soporta los 7 tipos de archivos del análisis SEO
    """
    
    # Configuración de skiprows para archivos Adobe
    ADOBE_SKIP_ROWS_OPTIONS = [0, 13, 14, 15]  # Probar estas opciones
    
    def __init__(self, data_dir: str = None):
        """
        Inicializa el cargador
        
        Args:
            data_dir: Directorio de datos (default: /mnt/user-data/uploads)
        """
        self.data_dir = Path(data_dir) if data_dir else Path('/mnt/user-data/uploads')
        self.data: Dict[str, pd.DataFrame] = {}
        self.load_results: Dict[str, LoadResult] = {}
        self.stats: DatasetStats = DatasetStats()
    
    def _try_load_csv(self, filepath: Path, skip_rows: int = 0) -> Tuple[Optional[pd.DataFrame], str]:
        """
        Intenta cargar un CSV con diferentes encodings
        
        Returns:
            (DataFrame o None, mensaje de error)
        """
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    filepath, 
                    skiprows=skip_rows,
                    encoding=encoding, 
                    low_memory=False,
                    on_bad_lines='skip'
                )
                # Verificar que tiene datos
                if len(df) > 0 and len(df.columns) > 0:
                    return df, ""
            except Exception as e:
                continue
        
        return None, f"No se pudo cargar con ningún encoding"
    
    def _detect_adobe_skip_rows(self, filepath: Path) -> int:
        """
        Detecta cuántas filas saltar en archivos Adobe
        Adobe exporta con cabeceras de metadatos que varían
        """
        for skip in self.ADOBE_SKIP_ROWS_OPTIONS:
            df, _ = self._try_load_csv(filepath, skip_rows=skip)
            if df is not None:
                # Verificar que las columnas tienen sentido
                first_col = str(df.columns[0]).lower()
                # Si la primera columna parece una URL o un filtro, es correcto
                if any(x in first_col for x in ['url', 'page', 'filter', 'entry', 'search']):
                    return skip
                # Si la primera fila tiene datos que parecen URLs o filtros
                if len(df) > 0:
                    first_val = str(df.iloc[0, 0]).lower()
                    if 'http' in first_val or ':' in first_val or 'www.' in first_val:
                        return skip
        return 13  # Default para Adobe
    
    def load_file(self, filepath: str, file_type: FileType = None) -> LoadResult:
        """
        Carga un archivo con auto-detección de tipo
        
        Args:
            filepath: Ruta al archivo
            file_type: Tipo de archivo (opcional, se auto-detecta)
        
        Returns:
            LoadResult con el DataFrame y metadatos
        """
        path = Path(filepath)
        
        if not path.exists():
            return LoadResult(
                success=False,
                file_type=FileType.UNKNOWN,
                error=f"Archivo no encontrado: {filepath}"
            )
        
        filename = path.name
        warnings = []
        
        # Determinar skiprows para archivos Adobe
        skip_rows = 0
        if 'sesiones' in filename.lower() or 'filtro' in filename.lower():
            skip_rows = self._detect_adobe_skip_rows(path)
            if skip_rows > 0:
                warnings.append(f"Detectadas {skip_rows} filas de cabecera Adobe")
        
        # Cargar CSV
        df, error = self._try_load_csv(path, skip_rows=skip_rows)
        
        if df is None:
            return LoadResult(
                success=False,
                file_type=FileType.UNKNOWN,
                error=error
            )
        
        # Auto-detectar tipo si no se especificó
        if file_type is None:
            file_type = FileTypeDetector.detect(df, filename)
        
        # Procesar según tipo
        df, process_warnings = self._process_by_type(df, file_type)
        warnings.extend(process_warnings)
        
        return LoadResult(
            success=True,
            file_type=file_type,
            dataframe=df,
            row_count=len(df),
            columns=df.columns.tolist(),
            warnings=warnings,
            metadata={
                'filename': filename,
                'skip_rows': skip_rows
            }
        )
    
    def _process_by_type(self, df: pd.DataFrame, file_type: FileType) -> Tuple[pd.DataFrame, List[str]]:
        """
        Procesa y normaliza DataFrame según su tipo
        
        Returns:
            (DataFrame procesado, lista de warnings)
        """
        warnings = []
        
        if file_type == FileType.CRAWL_MASTER:
            df, w = self._process_crawl_master(df)
            warnings.extend(w)
            
        elif file_type == FileType.CRAWL_SF_GSC:
            df, w = self._process_crawl_gsc(df)
            warnings.extend(w)
            
        elif file_type == FileType.CRAWL_HISTORICAL:
            df, w = self._process_crawl_historical(df)
            warnings.extend(w)
            
        elif file_type == FileType.ADOBE_URLS:
            df, w = self._process_adobe_urls(df)
            warnings.extend(w)
            
        elif file_type == FileType.ADOBE_FILTERS:
            df, w = self._process_adobe_filters(df)
            warnings.extend(w)
            
        elif file_type == FileType.SEMRUSH:
            df, w = self._process_semrush(df)
            warnings.extend(w)
            
        elif file_type == FileType.KEYWORD_PLANNER:
            df, w = self._process_keyword_planner(df)
            warnings.extend(w)
        
        return df, warnings
    
    def _process_crawl_master(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl maestro con extracción de seoFilterWrapper"""
        warnings = []
        
        # Calcular enlaces en seoFilterWrapper
        href_cols = [c for c in df.columns if 'seofilterwrapper_hrefs' in c.lower()]
        
        if href_cols:
            def count_wrapper_links(row):
                count = 0
                for col in href_cols:
                    val = row.get(col)
                    if pd.notna(val) and str(val).strip():
                        # Verificar que es una URL válida
                        val_str = str(val).strip()
                        if val_str.startswith('http') or val_str.startswith('/'):
                            count += 1
                return count
            
            df['wrapper_link_count'] = df.apply(count_wrapper_links, axis=1)
            df['has_wrapper'] = df['wrapper_link_count'] > 0
        else:
            warnings.append("No se encontraron columnas seoFilterWrapper_hrefs")
            df['wrapper_link_count'] = 0
            df['has_wrapper'] = False
        
        # Verificar columna exists
        exists_cols = [c for c in df.columns if 'seofilterwrapper_exists' in c.lower()]
        if exists_cols:
            df['wrapper_exists'] = df[exists_cols[0]].notna() & (df[exists_cols[0]] != '')
        
        # Normalizar código de respuesta
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(df['Código de respuesta'], errors='coerce').fillna(0).astype(int)
        
        return df, warnings
    
    def _process_crawl_gsc(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl con datos de GSC integrados"""
        warnings = []
        
        # Convertir columnas numéricas de GSC
        numeric_cols = ['Clics', 'Impresiones', 'Posición', 'CTR']
        for col in numeric_cols:
            if col in df.columns:
                # Manejar porcentajes en CTR
                if col == 'CTR':
                    df[col] = df[col].astype(str).str.replace('%', '').str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Normalizar código de respuesta
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(df['Código de respuesta'], errors='coerce').fillna(0).astype(int)
        
        return df, warnings
    
    def _process_crawl_historical(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl histórico (desde lista de URLs con tráfico)"""
        warnings = []
        
        # Normalizar código de respuesta
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(df['Código de respuesta'], errors='coerce').fillna(0).astype(int)
        
        # Calcular wrapper si tiene las columnas
        href_cols = [c for c in df.columns if 'seofilterwrapper_hrefs' in c.lower()]
        if href_cols:
            df, _ = self._process_crawl_master(df)
        else:
            df['wrapper_link_count'] = 0
            df['has_wrapper'] = False
        
        return df, warnings
    
    def _process_adobe_urls(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa tráfico SEO por URL de Adobe Analytics"""
        warnings = []
        
        # Normalizar nombres de columnas
        col_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'url' in col_lower or 'page' in col_lower or 'entry' in col_lower:
                col_mapping[col] = 'url'
            elif 'visit' in col_lower or 'session' in col_lower:
                col_mapping[col] = 'visits_seo'
            elif 'order' in col_lower or 'pedido' in col_lower:
                col_mapping[col] = 'orders'
            elif 'revenue' in col_lower or 'ingreso' in col_lower:
                col_mapping[col] = 'revenue'
            elif 'conversion' in col_lower or 'rate' in col_lower:
                col_mapping[col] = 'conversion_rate'
        
        if col_mapping:
            df = df.rename(columns=col_mapping)
        
        # Si solo tiene 2 columnas sin nombres claros, asumir url, visits
        if len(df.columns) == 2 and 'url' not in df.columns:
            df.columns = ['url', 'visits_seo']
        
        # Convertir métricas a numérico
        numeric_cols = ['visits_seo', 'orders', 'revenue', 'conversion_rate']
        for col in numeric_cols:
            if col in df.columns:
                # Limpiar formato de números (comas, puntos, %)
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '').str.replace('€', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Normalizar URLs
        if 'url' in df.columns:
            df['url_clean'] = df['url'].astype(str).str.strip()
            df['url_full'] = df['url_clean'].apply(
                lambda x: 'https://' + x if x and not x.startswith('http') else x
            )
        
        # Eliminar filas sin URL válida
        if 'url' in df.columns:
            df = df[df['url'].notna() & (df['url'] != '') & (df['url'] != 'nan')]
        
        return df, warnings
    
    def _process_adobe_filters(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa demanda de filtros de Adobe Analytics"""
        warnings = []
        
        # Normalizar nombres de columnas
        col_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'filter' in col_lower or 'search' in col_lower or 'facet' in col_lower:
                col_mapping[col] = 'filter_name'
            elif 'visit' in col_lower or 'session' in col_lower:
                col_mapping[col] = 'visits_seo'
            elif 'order' in col_lower:
                col_mapping[col] = 'orders'
            elif 'revenue' in col_lower:
                col_mapping[col] = 'revenue'
        
        if col_mapping:
            df = df.rename(columns=col_mapping)
        
        # Si solo tiene 2 columnas, asumir filter_name, visits
        if len(df.columns) == 2 and 'filter_name' not in df.columns:
            df.columns = ['filter_name', 'visits_seo']
        
        # Convertir visitas a numérico
        if 'visits_seo' in df.columns:
            df['visits_seo'] = df['visits_seo'].astype(str).str.replace(',', '').str.strip()
            df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
        
        # Parsear filter_name para extraer faceta y valor
        if 'filter_name' in df.columns:
            def parse_filter(f):
                f_str = str(f)
                if ':' in f_str:
                    parts = f_str.split(':', 1)
                    return {'facet_type': parts[0].strip().lower(), 'facet_value': parts[1].strip()}
                return {'facet_type': 'unknown', 'facet_value': f_str}
            
            parsed = df['filter_name'].apply(parse_filter)
            df['facet_type'] = parsed.apply(lambda x: x['facet_type'])
            df['facet_value'] = parsed.apply(lambda x: x['facet_value'])
        
        # Eliminar filas vacías
        if 'filter_name' in df.columns:
            df = df[df['filter_name'].notna() & (df['filter_name'] != '') & (df['filter_name'] != 'nan')]
        
        return df, warnings
    
    def _process_semrush(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa keywords de SEMrush"""
        warnings = []
        
        # Normalizar nombres de columnas comunes
        col_mapping = {
            'Keyword': 'keyword',
            'Volume': 'volume',
            'Keyword Difficulty': 'kd',
            'CPC': 'cpc',
            'Intent': 'intent',
            'Trend': 'trend',
            'SERP Features': 'serp_features',
            'Results': 'results'
        }
        
        for old, new in col_mapping.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        
        # Convertir volumen a numérico
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
        
        # Convertir KD a numérico
        if 'kd' in df.columns:
            df['kd'] = pd.to_numeric(df['kd'], errors='coerce').fillna(0)
        
        # Convertir CPC a numérico
        if 'cpc' in df.columns:
            df['cpc'] = df['cpc'].astype(str).str.replace('$', '').str.replace(',', '.')
            df['cpc'] = pd.to_numeric(df['cpc'], errors='coerce').fillna(0)
        
        return df, warnings
    
    def _process_keyword_planner(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa keywords de Google Keyword Planner"""
        warnings = []
        
        # Normalizar nombres de columnas
        col_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'keyword' in col_lower and 'idea' not in col_lower:
                col_mapping[col] = 'keyword'
            elif 'avg' in col_lower and 'search' in col_lower:
                col_mapping[col] = 'volume'
            elif 'competition' in col_lower and 'index' not in col_lower:
                col_mapping[col] = 'competition'
            elif 'competition' in col_lower and 'index' in col_lower:
                col_mapping[col] = 'competition_index'
            elif 'top of page' in col_lower and 'low' in col_lower:
                col_mapping[col] = 'cpc_low'
            elif 'top of page' in col_lower and 'high' in col_lower:
                col_mapping[col] = 'cpc_high'
        
        if col_mapping:
            df = df.rename(columns=col_mapping)
        
        # Convertir volumen (puede venir como rango "1K - 10K")
        if 'volume' in df.columns:
            def parse_volume(v):
                v_str = str(v).upper().strip()
                if '-' in v_str:
                    # Tomar el valor alto del rango
                    v_str = v_str.split('-')[-1].strip()
                v_str = v_str.replace('K', '000').replace('M', '000000').replace(',', '').replace('.', '')
                try:
                    return int(float(v_str))
                except:
                    return 0
            
            df['volume'] = df['volume'].apply(parse_volume)
        
        # Normalizar competition a valores numéricos
        if 'competition' in df.columns:
            competition_map = {'low': 0.33, 'medium': 0.66, 'high': 1.0, 'bajo': 0.33, 'medio': 0.66, 'alto': 1.0}
            df['competition_score'] = df['competition'].astype(str).str.lower().map(competition_map).fillna(0.5)
        
        return df, warnings
    
    def load_all_from_directory(self) -> Dict[str, LoadResult]:
        """
        Carga todos los archivos CSV de un directorio
        
        Returns:
            Dict con resultados de carga por archivo
        """
        results = {}
        
        if not self.data_dir.exists():
            return results
        
        for filepath in self.data_dir.glob('*.csv'):
            result = self.load_file(str(filepath))
            results[filepath.name] = result
            
            if result.success:
                # Guardar en self.data con key basada en tipo
                key = f"{result.file_type.value}_{filepath.stem}"
                self.data[key] = result.dataframe
        
        self.load_results = results
        return results
    
    def get_master_crawl(self) -> Optional[pd.DataFrame]:
        """Obtiene el crawl maestro (con seoFilterWrapper)"""
        for key, df in self.data.items():
            if 'crawl_master' in key:
                return df
        return None
    
    def get_adobe_urls(self) -> Optional[pd.DataFrame]:
        """Obtiene el DataFrame de tráfico por URL"""
        for key, df in self.data.items():
            if 'adobe_urls' in key:
                return df
        return None
    
    def get_adobe_filters(self) -> Optional[pd.DataFrame]:
        """Obtiene el DataFrame de demanda por filtros"""
        for key, df in self.data.items():
            if 'adobe_filters' in key:
                return df
        return None
    
    def get_keywords(self) -> Optional[pd.DataFrame]:
        """Obtiene keywords combinados de SEMrush y Keyword Planner"""
        dfs = []
        
        for key, df in self.data.items():
            if 'semrush' in key and 'keyword' in df.columns:
                df_kw = df[['keyword', 'volume']].copy()
                df_kw['source'] = 'semrush'
                dfs.append(df_kw)
            elif 'keyword_planner' in key and 'keyword' in df.columns:
                df_kw = df[['keyword', 'volume']].copy()
                df_kw['source'] = 'keyword_planner'
                dfs.append(df_kw)
        
        if dfs:
            return pd.concat(dfs, ignore_index=True)
        return None
    
    def calculate_stats(self) -> DatasetStats:
        """Calcula estadísticas globales de los datos cargados"""
        stats = DatasetStats()
        
        # Estadísticas de crawl
        crawl = self.get_master_crawl()
        if crawl is not None and 'Código de respuesta' in crawl.columns:
            stats.total_urls = len(crawl)
            stats.urls_200 = len(crawl[crawl['Código de respuesta'] == 200])
            stats.urls_404 = len(crawl[crawl['Código de respuesta'] == 404])
            stats.urls_301 = len(crawl[crawl['Código de respuesta'] == 301])
            stats.urls_other = stats.total_urls - stats.urls_200 - stats.urls_404 - stats.urls_301
            
            if 'has_wrapper' in crawl.columns:
                crawl_200 = crawl[crawl['Código de respuesta'] == 200]
                stats.with_wrapper = len(crawl_200[crawl_200['has_wrapper'] == True])
                stats.without_wrapper = len(crawl_200[crawl_200['has_wrapper'] == False])
        
        # Tráfico total
        adobe_urls = self.get_adobe_urls()
        if adobe_urls is not None and 'visits_seo' in adobe_urls.columns:
            stats.total_traffic = int(adobe_urls['visits_seo'].sum())
        
        # Demanda total
        adobe_filters = self.get_adobe_filters()
        if adobe_filters is not None and 'visits_seo' in adobe_filters.columns:
            stats.total_demand = int(adobe_filters['visits_seo'].sum())
        
        self.stats = stats
        return stats
    
    def merge_crawl_with_traffic(self) -> Optional[pd.DataFrame]:
        """
        Combina crawl maestro con datos de tráfico de Adobe
        
        Returns:
            DataFrame combinado o None
        """
        crawl = self.get_master_crawl()
        adobe = self.get_adobe_urls()
        
        if crawl is None:
            return None
        
        if adobe is None:
            # Retornar crawl sin tráfico
            crawl['visits_seo'] = 0
            return crawl
        
        # Merge por URL
        merged = crawl.merge(
            adobe[['url_full', 'visits_seo']],
            left_on='Dirección',
            right_on='url_full',
            how='left'
        )
        merged['visits_seo'] = merged['visits_seo'].fillna(0).astype(int)
        
        # Limpiar columna duplicada
        if 'url_full' in merged.columns:
            merged = merged.drop(columns=['url_full'])
        
        return merged


def validate_data_integrity(data: Dict[str, pd.DataFrame], expected_metrics: Dict = None) -> Dict[str, Any]:
    """
    Valida integridad de datos cargados
    
    Args:
        data: Dict de DataFrames
        expected_metrics: Métricas esperadas (opcional)
    
    Returns:
        Dict con resultados de validación
    """
    results = {
        'valid': True,
        'checks': {},
        'warnings': [],
        'stats': {}
    }
    
    # Buscar crawl maestro
    crawl = None
    for key, df in data.items():
        if 'crawl' in key.lower() and 'Dirección' in df.columns:
            crawl = df
            break
    
    if crawl is not None:
        actual_total = len(crawl)
        actual_200 = len(crawl[crawl['Código de respuesta'] == 200]) if 'Código de respuesta' in crawl.columns else 0
        actual_404 = len(crawl[crawl['Código de respuesta'] == 404]) if 'Código de respuesta' in crawl.columns else 0
        
        results['stats'] = {
            'total_urls': actual_total,
            'urls_200': actual_200,
            'urls_404': actual_404
        }
        
        if expected_metrics:
            results['checks']['total_urls'] = {
                'expected': expected_metrics.get('total_urls_crawl'),
                'actual': actual_total,
                'match': actual_total == expected_metrics.get('total_urls_crawl', actual_total)
            }
    else:
        results['warnings'].append("No se encontró crawl con columna 'Dirección'")
        results['valid'] = False
    
    return results


# =============================================================================
# FUNCIONES DE UTILIDAD PARA STREAMLIT
# =============================================================================

def render_file_upload_ui() -> Dict[str, LoadResult]:
    """
    Renderiza UI para subir y detectar tipos de archivos
    
    Returns:
        Dict con archivos cargados
    """
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado. Instala con: pip install streamlit")
    
    st.subheader("📁 Subir Archivos de Datos")
    
    st.info("""
    **Archivos soportados:**
    1. **Crawl SF + GSC** - Crawl con datos de Google Search Console
    2. **Keyword Planner** - Volúmenes de Google Ads
    3. **SEMrush** - Keywords con volumen, KD, intent
    4. **Adobe URLs** - Tráfico SEO por URL
    5. **Crawl Maestro** - Con extracción de seoFilterWrapper
    6. **Adobe Filters** - Demanda por filtros/facetas
    7. **Crawl Histórico** - URLs con tráfico histórico
    """)
    
    uploaded_files = st.file_uploader(
        "Sube uno o más archivos CSV",
        type=['csv'],
        accept_multiple_files=True
    )
    
    results = {}
    
    if uploaded_files:
        loader = DataLoader()
        
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
            if result.success:
                st.success(f"✅ **{uploaded_file.name}** → {result.file_type.value} ({result.row_count:,} filas)")
                if result.warnings:
                    for w in result.warnings:
                        st.caption(f"⚠️ {w}")
            else:
                st.error(f"❌ **{uploaded_file.name}**: {result.error}")
            
            # Limpiar temporal
            import os
            os.unlink(tmp_path)
    
    return results
