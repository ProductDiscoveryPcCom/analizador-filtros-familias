"""
Módulo de carga y normalización de datos - v2.3
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
import warnings

# Suprimir warnings de pandas
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# Streamlit es opcional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


class FileType(Enum):
    """Tipos de archivo soportados"""
    CRAWL_SF_GSC = "crawl_gsc"
    KEYWORD_PLANNER = "keyword_planner"
    SEMRUSH = "semrush"
    ADOBE_URLS = "adobe_urls"
    CRAWL_MASTER = "crawl_master"
    ADOBE_FILTERS = "adobe_filters"
    CRAWL_HISTORICAL = "crawl_historical"
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
        if df is None or len(df) == 0:
            return FileType.UNKNOWN
            
        columns_lower = [str(c).lower() for c in df.columns]
        columns_str = ' '.join(columns_lower)
        filename_lower = filename.lower()
        
        # 1. Detectar por nombre de archivo primero (más específico)
        # SEMrush
        if 'semrush' in filename_lower or 'broad-match' in filename_lower:
            return FileType.SEMRUSH
        
        # Keyword Planner - más patrones
        if any(x in filename_lower for x in ['keywordplanner', 'keyword_planner', 'keyword-planner', 'kwr-', 'gkp', 'planner']):
            return FileType.KEYWORD_PLANNER
        
        # Crawl con GSC
        if any(x in filename_lower for x in ['topquery', 'top_query', 'top-query', 'gsc_']):
            return FileType.CRAWL_SF_GSC
        
        # Adobe Filters - más patrones
        if any(x in filename_lower for x in ['search_filter', 'searchfilter', 'filtro', 'filtros', 'filter']):
            return FileType.ADOBE_FILTERS
        
        # Adobe URLs - más flexible (no requiere 'adobe' en nombre)
        if any(x in filename_lower for x in ['entry_page', 'entrypage', 'categorias', 'trafico', 'traffic', 'urls_seo', 'seo_url']):
            return FileType.ADOBE_URLS
        
        # Crawl histórico
        if any(x in filename_lower for x in ['historico', 'historical', 'old_crawl']):
            return FileType.CRAWL_HISTORICAL
        
        # 2. Detectar crawl con extracción de seoFilterWrapper (MASTER)
        wrapper_cols = [c for c in df.columns if 'seofilterwrapper' in str(c).lower()]
        if wrapper_cols and 'Dirección' in df.columns:
            return FileType.CRAWL_MASTER
        
        # 3. Detectar crawl con GSC (columnas en español de Screaming Frog)
        if 'Dirección' in df.columns and 'Código de respuesta' in df.columns:
            gsc_cols = ['Clics', 'Impresiones', 'Posición']
            has_gsc = sum(1 for c in gsc_cols if c in df.columns) >= 2
            if has_gsc:
                return FileType.CRAWL_SF_GSC
            else:
                return FileType.CRAWL_HISTORICAL
        
        # 4. Detectar datos de GSC (export directo o TopQuery)
        if 'url' in columns_lower and 'top_query' in columns_lower:
            return FileType.CRAWL_SF_GSC
        
        # 5. Detectar SEMrush por columnas
        if 'Keyword' in df.columns and 'Volume' in df.columns:
            return FileType.SEMRUSH
        if 'keyword' in columns_lower and 'volume' in columns_lower:
            return FileType.SEMRUSH
        
        # 6. Detectar Keyword Planner (por columnas)
        kp_patterns = ['avg. monthly searches', 'competition', 'top of page bid', 
                       'búsquedas mensuales', 'competencia', 'puja']
        if any(p in columns_str for p in kp_patterns):
            return FileType.KEYWORD_PLANNER
        
        # 7. Detectar Adobe por patrones de datos
        if len(df) > 0:
            first_val = str(df.iloc[0, 0]).lower()
            
            # Verificar si parece filtro (contiene ':' como separador faceta:valor)
            looks_like_filter = ':' in first_val and 'http' not in first_val
            if looks_like_filter:
                return FileType.ADOBE_FILTERS
            
            # Verificar si la primera columna contiene URLs
            looks_like_url = any(x in first_val for x in ['http', 'www.', '.com', '.es', 'pccomponentes'])
            
            gsc_specific = ['top_query', 'clics', 'impresiones', 'posición']
            has_gsc_cols = any(gc in columns_lower for gc in gsc_specific)
            
            if looks_like_url and not has_gsc_cols:
                return FileType.ADOBE_URLS
        
        # 8. Detectar por estructura de columnas numéricas (Adobe típicamente tiene Visit/Orders/Revenue)
        numeric_indicators = ['visit', 'order', 'revenue', 'pedido', 'ingreso', 'sesion']
        if any(ind in columns_str for ind in numeric_indicators):
            # Si tiene URLs en primera columna, es Adobe URLs
            if len(df) > 0:
                first_val = str(df.iloc[0, 0]).lower()
                if 'http' in first_val or 'www' in first_val:
                    return FileType.ADOBE_URLS
                elif ':' in first_val:
                    return FileType.ADOBE_FILTERS
        
        return FileType.UNKNOWN


class DataLoader:
    """
    Cargador de datos unificado con auto-detección
    Soporta los 7 tipos de archivos del análisis SEO
    """
    
    ADOBE_SKIP_ROWS_OPTIONS = [0, 13, 14, 15]
    
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
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        last_error = ""
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    filepath, 
                    skiprows=skip_rows,
                    encoding=encoding, 
                    low_memory=False,
                    on_bad_lines='skip'
                )
                if len(df) > 0 and len(df.columns) > 0:
                    return df, ""
            except Exception as e:
                last_error = str(e)
                continue
        
        return None, f"No se pudo cargar: {last_error}"
    
    def _auto_detect_skip_rows(self, filepath: Path) -> int:
        """
        Auto-detecta si un archivo tiene cabeceras de Adobe Analytics
        sin depender del nombre del archivo.
        
        Los reportes de Adobe típicamente tienen:
        - Filas iniciales con metadatos (fechas, nombre del reporte)
        - Una línea vacía
        - La fila de cabeceras real con nombres de columnas
        """
        # Leer primeras 25 filas sin parsear
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                lines = [f.readline().strip() for _ in range(25)]
        except:
            try:
                with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
                    lines = [f.readline().strip() for _ in range(25)]
            except:
                return 0
        
        # Buscar patrones de fila de datos real (cabecera de tabla)
        data_header_patterns = ['url', 'page', 'filter', 'entry', 'search', 'keyword', 'dirección']
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Saltar líneas vacías
            if not line.strip():
                continue
            
            # Verificar si esta línea parece una cabecera de datos
            # (contiene palabras clave típicas de cabeceras y tiene separador ,)
            has_header_pattern = any(p in line_lower for p in data_header_patterns)
            has_separator = ',' in line or '\t' in line
            
            if has_header_pattern and has_separator:
                # Esta línea parece ser la cabecera, devolver su índice
                return i
        
        return 0
    
    def _detect_adobe_skip_rows(self, filepath: Path) -> int:
        """
        Detecta cuántas filas saltar en archivos Adobe.
        Primero intenta auto-detectar, luego usa valores conocidos.
        """
        # Primero intentar auto-detección inteligente
        auto_skip = self._auto_detect_skip_rows(filepath)
        if auto_skip > 0:
            # Verificar que la auto-detección es correcta
            df, _ = self._try_load_csv(filepath, skip_rows=auto_skip)
            if df is not None and len(df.columns) > 1:
                first_col = str(df.columns[0]).lower()
                if any(x in first_col for x in ['url', 'page', 'filter', 'entry', 'search']):
                    return auto_skip
        
        # Fallback: probar valores conocidos de Adobe Analytics
        for skip in self.ADOBE_SKIP_ROWS_OPTIONS:
            df, _ = self._try_load_csv(filepath, skip_rows=skip)
            if df is not None and len(df.columns) > 1:
                first_col = str(df.columns[0]).lower()
                if any(x in first_col for x in ['url', 'page', 'filter', 'entry', 'search']):
                    return skip
                if len(df) > 0:
                    first_val = str(df.iloc[0, 0]).lower()
                    if any(x in first_val for x in ['http', ':', 'www.']):
                        return skip
        
        # Si nada funciona, devolver 0 (sin skip)
        return 0
    
    def load_file(self, filepath: str, file_type: FileType = None, original_filename: str = None) -> LoadResult:
        """
        Carga un archivo con auto-detección de tipo
        
        Args:
            filepath: Ruta al archivo
            file_type: Tipo de archivo (opcional, se auto-detecta)
            original_filename: Nombre original del archivo (para detección por nombre)
        
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
        
        # Usar nombre original si se proporciona, si no usar el de la ruta
        filename = original_filename if original_filename else path.name
        load_warnings = []
        
        # Determinar skiprows para archivos con cabeceras especiales
        skip_rows = 0
        filename_lower = filename.lower()
        
        # Patrones para detectar archivos de Adobe por nombre
        adobe_name_patterns = [
            'adobe', 'sesiones', 'filtro', 'filtros', 'entry_page', 
            'search_filter', 'searchfilter', 'categorias', 'trafico',
            'traffic', 'urls_seo', 'seo_url', 'report'
        ]
        is_adobe_file = any(x in filename_lower for x in adobe_name_patterns)
        
        # Patrones para Keyword Planner
        kp_name_patterns = ['keywordplanner', 'keyword_planner', 'keyword-planner', 'kwr-', 'gkp', 'planner']
        is_kp_file = any(x in filename_lower for x in kp_name_patterns)
        
        # Si no detectamos por nombre, intentar detectar Adobe por contenido
        if not is_adobe_file and not is_kp_file:
            skip_rows = self._auto_detect_skip_rows(path)
            if skip_rows > 0:
                is_adobe_file = True
                load_warnings.append(f"Auto-detectadas {skip_rows} filas de cabecera")
        elif is_adobe_file:
            skip_rows = self._detect_adobe_skip_rows(path)
            if skip_rows > 0:
                load_warnings.append(f"Detectadas {skip_rows} filas de cabecera Adobe")
        elif is_kp_file:
            skip_rows = 2
            load_warnings.append("Detectadas 2 filas de cabecera Keyword Planner")
        
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
        try:
            df, process_warnings = self._process_by_type(df, file_type)
            load_warnings.extend(process_warnings)
        except Exception as e:
            return LoadResult(
                success=False,
                file_type=file_type,
                error=f"Error procesando archivo: {str(e)}"
            )
        
        return LoadResult(
            success=True,
            file_type=file_type,
            dataframe=df,
            row_count=len(df),
            columns=df.columns.tolist(),
            warnings=load_warnings,
            metadata={
                'filename': filename,
                'skip_rows': skip_rows
            }
        )
    
    def _process_by_type(self, df: pd.DataFrame, file_type: FileType) -> Tuple[pd.DataFrame, List[str]]:
        """
        Procesa y normaliza DataFrame según su tipo
        """
        processors = {
            FileType.CRAWL_MASTER: self._process_crawl_master,
            FileType.CRAWL_SF_GSC: self._process_crawl_gsc,
            FileType.CRAWL_HISTORICAL: self._process_crawl_historical,
            FileType.ADOBE_URLS: self._process_adobe_urls,
            FileType.ADOBE_FILTERS: self._process_adobe_filters,
            FileType.SEMRUSH: self._process_semrush,
            FileType.KEYWORD_PLANNER: self._process_keyword_planner,
        }
        
        processor = processors.get(file_type)
        if processor:
            return processor(df)
        return df, []
    
    def _process_crawl_master(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl maestro con extracción de seoFilterWrapper"""
        warnings_list = []
        
        # Calcular enlaces en seoFilterWrapper
        href_cols = [c for c in df.columns if 'seofilterwrapper_hrefs' in str(c).lower()]
        
        if href_cols:
            def count_wrapper_links(row):
                count = 0
                for col in href_cols:
                    val = row.get(col)
                    if pd.notna(val):
                        val_str = str(val).strip()
                        if val_str and (val_str.startswith('http') or val_str.startswith('/')):
                            count += 1
                return count
            
            df['wrapper_link_count'] = df.apply(count_wrapper_links, axis=1)
            df['has_wrapper'] = df['wrapper_link_count'] > 0
        else:
            warnings_list.append("No se encontraron columnas seoFilterWrapper_hrefs")
            df['wrapper_link_count'] = 0
            df['has_wrapper'] = False
        
        # Verificar columna exists
        exists_cols = [c for c in df.columns if 'seofilterwrapper_exists' in str(c).lower()]
        if exists_cols:
            df['wrapper_exists'] = df[exists_cols[0]].notna() & (df[exists_cols[0]].astype(str) != '')
        
        # Normalizar código de respuesta
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(
                df['Código de respuesta'], errors='coerce'
            ).fillna(0).astype(int)
        
        return df, warnings_list
    
    def _process_crawl_gsc(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl con datos de GSC integrados"""
        warnings_list = []
        
        numeric_cols = ['Clics', 'Impresiones', 'Posición', 'CTR']
        for col in numeric_cols:
            if col in df.columns:
                if col == 'CTR':
                    df[col] = df[col].astype(str).str.replace('%', '').str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(
                df['Código de respuesta'], errors='coerce'
            ).fillna(0).astype(int)
        
        # Añadir columnas de wrapper si no existen
        if 'wrapper_link_count' not in df.columns:
            df['wrapper_link_count'] = 0
            df['has_wrapper'] = False
        
        return df, warnings_list
    
    def _process_crawl_historical(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa crawl histórico"""
        warnings_list = []
        
        if 'Código de respuesta' in df.columns:
            df['Código de respuesta'] = pd.to_numeric(
                df['Código de respuesta'], errors='coerce'
            ).fillna(0).astype(int)
        
        href_cols = [c for c in df.columns if 'seofilterwrapper_hrefs' in str(c).lower()]
        if href_cols:
            df, _ = self._process_crawl_master(df)
        else:
            df['wrapper_link_count'] = 0
            df['has_wrapper'] = False
        
        return df, warnings_list
    
    def _process_adobe_urls(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa tráfico SEO por URL de Adobe Analytics"""
        warnings_list = []
        
        col_mapping = {}
        numeric_col_count = 0
        
        for i, col in enumerate(df.columns):
            col_str = str(col).lower()
            
            if any(x in col_str for x in ['url', 'page', 'entry']):
                col_mapping[col] = 'url'
            elif col_str.replace('.', '').replace(',', '').isdigit():
                if numeric_col_count == 0:
                    col_mapping[col] = 'visits_seo'
                elif numeric_col_count == 1:
                    col_mapping[col] = 'orders'
                elif numeric_col_count == 2:
                    col_mapping[col] = 'conversion_rate'
                elif numeric_col_count == 3:
                    col_mapping[col] = 'revenue'
                numeric_col_count += 1
            elif 'visit' in col_str or 'session' in col_str:
                col_mapping[col] = 'visits_seo'
            elif 'order' in col_str or 'pedido' in col_str:
                col_mapping[col] = 'orders'
            elif 'revenue' in col_str or 'ingreso' in col_str:
                col_mapping[col] = 'revenue'
            elif 'conversion' in col_str or 'rate' in col_str:
                col_mapping[col] = 'conversion_rate'
        
        if col_mapping:
            df = df.rename(columns=col_mapping)
            warnings_list.append(f"Columnas renombradas: {list(col_mapping.values())}")
        
        # Si no tiene 'url', verificar primera columna
        if 'url' not in df.columns and len(df) > 0:
            first_val = str(df.iloc[0, 0]).lower()
            if any(x in first_val for x in ['www.', 'http', '.com']):
                old_name = df.columns[0]
                df = df.rename(columns={old_name: 'url'})
        
        # Convertir métricas a numérico
        numeric_cols = ['visits_seo', 'orders', 'revenue', 'conversion_rate']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace('.', '', regex=False)
                df[col] = df[col].str.replace(',', '.', regex=False)
                df[col] = df[col].str.replace('%', '', regex=False).str.replace('€', '', regex=False).str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Normalizar URLs
        if 'url' in df.columns:
            df['url_clean'] = df['url'].astype(str).str.strip()
            df['url_full'] = df['url_clean'].apply(
                lambda x: 'https://' + x if x and not str(x).startswith('http') and x != 'nan' else x
            )
            df = df[df['url'].notna() & (df['url'] != '') & (df['url'].astype(str) != 'nan')]
        
        return df, warnings_list
    
    def _process_adobe_filters(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa demanda de filtros de Adobe Analytics"""
        warnings_list = []
        
        col_mapping = {}
        for i, col in enumerate(df.columns):
            col_str = str(col).lower()
            
            if any(x in col_str for x in ['filter', 'search', 'facet']):
                col_mapping[col] = 'filter_name'
            elif col_str.isdigit() or (i == 1 and col_str.replace('.', '').isdigit()):
                col_mapping[col] = 'visits_seo'
            elif 'visit' in col_str or 'session' in col_str:
                col_mapping[col] = 'visits_seo'
            elif 'order' in col_str:
                col_mapping[col] = 'orders'
            elif 'revenue' in col_str:
                col_mapping[col] = 'revenue'
        
        if col_mapping:
            df = df.rename(columns=col_mapping)
            warnings_list.append(f"Columnas renombradas: {list(col_mapping.values())}")
        
        # Si no tiene filter_name, verificar primera columna
        if 'filter_name' not in df.columns and len(df) > 0:
            first_val = str(df.iloc[0, 0])
            if ':' in first_val:
                old_name = df.columns[0]
                df = df.rename(columns={old_name: 'filter_name'})
                
                if len(df.columns) > 1 and 'visits_seo' not in df.columns:
                    second_col = df.columns[1]
                    if str(second_col).replace('.', '').isdigit():
                        df = df.rename(columns={second_col: 'visits_seo'})
        
        # Convertir visitas a numérico
        if 'visits_seo' in df.columns:
            df['visits_seo'] = df['visits_seo'].astype(str).str.replace('.', '', regex=False)
            df['visits_seo'] = df['visits_seo'].str.replace(',', '', regex=False).str.strip()
            df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
        
        # Parsear filter_name
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
            
            df = df[df['filter_name'].notna() & (df['filter_name'] != '') & (df['filter_name'].astype(str) != 'nan')]
        
        return df, warnings_list
    
    def _process_semrush(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa keywords de SEMrush"""
        warnings_list = []
        
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
        
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
        
        if 'kd' in df.columns:
            df['kd'] = pd.to_numeric(df['kd'], errors='coerce').fillna(0)
        
        if 'cpc' in df.columns:
            df['cpc'] = df['cpc'].astype(str).str.replace('$', '').str.replace(',', '.')
            df['cpc'] = pd.to_numeric(df['cpc'], errors='coerce').fillna(0)
        
        return df, warnings_list
    
    def _process_keyword_planner(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Procesa keywords de Google Keyword Planner"""
        warnings_list = []
        
        col_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower()
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
        
        if 'volume' in df.columns:
            def parse_volume(v):
                v_str = str(v).upper().strip()
                if '-' in v_str:
                    v_str = v_str.split('-')[-1].strip()
                v_str = v_str.replace('K', '000').replace('M', '000000').replace(',', '').replace('.', '')
                try:
                    return int(float(v_str))
                except:
                    return 0
            
            df['volume'] = df['volume'].apply(parse_volume)
        
        if 'competition' in df.columns:
            competition_map = {
                'low': 0.33, 'medium': 0.66, 'high': 1.0,
                'bajo': 0.33, 'medio': 0.66, 'alto': 1.0
            }
            df['competition_score'] = df['competition'].astype(str).str.lower().map(competition_map).fillna(0.5)
        
        return df, warnings_list
    
    def load_all_from_directory(self) -> Dict[str, LoadResult]:
        """Carga todos los archivos CSV de un directorio"""
        results = {}
        
        if not self.data_dir.exists():
            return results
        
        for filepath in self.data_dir.glob('*.csv'):
            result = self.load_file(str(filepath))
            results[filepath.name] = result
            
            if result.success:
                key = f"{result.file_type.value}"
                self.data[key] = result.dataframe
        
        self.load_results = results
        return results
    
    def get_crawl(self) -> Optional[pd.DataFrame]:
        """Obtiene el crawl principal (master > gsc > historical)"""
        for key in ['crawl_master', 'crawl_gsc', 'crawl_historical']:
            if key in self.data:
                return self.data[key]
        return None
    
    def get_adobe_urls(self) -> Optional[pd.DataFrame]:
        """Obtiene el DataFrame de tráfico por URL"""
        return self.data.get('adobe_urls')
    
    def get_adobe_filters(self) -> Optional[pd.DataFrame]:
        """Obtiene el DataFrame de demanda por filtros"""
        return self.data.get('adobe_filters')
    
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
        
        crawl = self.get_crawl()
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
        
        adobe_urls = self.get_adobe_urls()
        if adobe_urls is not None and 'visits_seo' in adobe_urls.columns:
            stats.total_traffic = int(adobe_urls['visits_seo'].sum())
        
        adobe_filters = self.get_adobe_filters()
        if adobe_filters is not None and 'visits_seo' in adobe_filters.columns:
            stats.total_demand = int(adobe_filters['visits_seo'].sum())
        
        self.stats = stats
        return stats
    
    def merge_crawl_with_traffic(self) -> Optional[pd.DataFrame]:
        """Combina crawl maestro con datos de tráfico de Adobe"""
        crawl = self.get_crawl()
        adobe = self.get_adobe_urls()
        
        if crawl is None:
            return None
        
        crawl = crawl.copy()
        
        if adobe is None:
            crawl['visits_seo'] = 0
            return crawl
        
        merged = crawl.merge(
            adobe[['url_full', 'visits_seo']],
            left_on='Dirección',
            right_on='url_full',
            how='left'
        )
        merged['visits_seo'] = merged['visits_seo'].fillna(0).astype(int)
        
        # Eliminar columna duplicada de forma segura
        if 'url_full' in merged.columns:
            merged = merged.drop(columns=['url_full'], errors='ignore')
        
        return merged


def validate_data_integrity(data: Dict[str, pd.DataFrame], expected_metrics: Dict = None) -> Dict[str, Any]:
    """
    Valida integridad de datos cargados
    """
    results = {
        'valid': True,
        'checks': {},
        'warnings': [],
        'stats': {}
    }
    
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


def render_file_upload_ui() -> Dict[str, LoadResult]:
    """Renderiza UI para subir y detectar tipos de archivos"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
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
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            result = loader.load_file(tmp_path)
            results[uploaded_file.name] = result
            
            if result.success:
                st.success(f"✅ **{uploaded_file.name}** → {result.file_type.value} ({result.row_count:,} filas)")
                if result.warnings:
                    for w in result.warnings:
                        st.caption(f"⚠️ {w}")
            else:
                st.error(f"❌ **{uploaded_file.name}**: {result.error}")
            
            os.unlink(tmp_path)
    
    return results
