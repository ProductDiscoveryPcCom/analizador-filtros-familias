"""
Gestor de Biblioteca de Familias de Productos - v2.3
Almacena y gestiona datos de diferentes categorías para reutilización
Con soporte para los 7 tipos de archivos de datos
"""

import os
import json
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import hashlib

from .loaders import DataLoader, FileType, LoadResult


@dataclass
class FamilyFile:
    """Información de un archivo en la familia"""
    original_name: str
    stored_name: str
    file_type: str
    row_count: int
    columns: List[str]
    added_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FamilyMetadata:
    """Metadatos de una familia de productos"""
    id: str
    name: str
    slug: str
    description: str
    created_at: str
    updated_at: str
    base_url: str
    category_path: str = ""
    
    # Estadísticas
    total_urls: int = 0
    urls_200: int = 0
    urls_404: int = 0
    urls_301: int = 0
    with_wrapper: int = 0
    without_wrapper: int = 0
    total_traffic: int = 0
    total_demand: int = 0
    
    # Archivos incluidos
    files: Dict[str, FamilyFile] = field(default_factory=dict)
    
    # Flags de disponibilidad
    has_crawl_master: bool = False
    has_crawl_gsc: bool = False
    has_adobe_urls: bool = False
    has_adobe_filters: bool = False
    has_semrush: bool = False
    has_keyword_planner: bool = False
    has_crawl_historical: bool = False
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario para serialización"""
        data = asdict(self)
        if self.files:
            data['files'] = {
                k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
                for k, v in self.files.items()
            }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FamilyMetadata':
        """Crea instancia desde diccionario"""
        if 'files' in data and data['files']:
            files = {}
            for k, v in data['files'].items():
                if isinstance(v, dict):
                    files[k] = FamilyFile(**v)
                else:
                    files[k] = v
            data['files'] = files
        return cls(**data)


class FamilyLibrary:
    """
    Biblioteca de familias de productos
    Gestiona almacenamiento y carga de datos por categoría
    """
    
    # Mapeo de tipos de archivo a nombres de almacenamiento (claves unificadas)
    FILE_STORAGE_NAMES = {
        FileType.CRAWL_MASTER: 'crawl_master.csv',
        FileType.CRAWL_SF_GSC: 'crawl_gsc.csv',
        FileType.CRAWL_HISTORICAL: 'crawl_historical.csv',
        FileType.ADOBE_URLS: 'adobe_urls.csv',
        FileType.ADOBE_FILTERS: 'adobe_filters.csv',
        FileType.SEMRUSH: 'semrush.csv',
        FileType.KEYWORD_PLANNER: 'keyword_planner.csv',
    }
    
    # Claves de datos unificadas
    DATA_KEYS = {
        FileType.CRAWL_MASTER: 'crawl_master',
        FileType.CRAWL_SF_GSC: 'crawl_gsc',
        FileType.CRAWL_HISTORICAL: 'crawl_historical',
        FileType.ADOBE_URLS: 'adobe_urls',
        FileType.ADOBE_FILTERS: 'adobe_filters',
        FileType.SEMRUSH: 'semrush',
        FileType.KEYWORD_PLANNER: 'keyword_planner',
    }
    
    def __init__(self, library_path: str = None):
        """
        Inicializa la biblioteca
        
        Args:
            library_path: Ruta base de la biblioteca. Por defecto usa ./library/
        """
        self.library_path = Path(library_path) if library_path else Path('./library')
        self.library_path.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.library_path / 'index.json'
        self.families: Dict[str, FamilyMetadata] = {}
        
        self._load_index()
    
    def _load_index(self):
        """Carga el índice de familias"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for family_id, family_data in data.get('families', {}).items():
                        try:
                            self.families[family_id] = FamilyMetadata.from_dict(family_data)
                        except Exception as e:
                            print(f"Error cargando familia {family_id}: {e}")
            except Exception as e:
                print(f"Error cargando índice: {e}")
                self.families = {}
    
    def _save_index(self):
        """Guarda el índice de familias"""
        data = {
            'version': '2.3',
            'updated_at': datetime.now().isoformat(),
            'families': {
                fid: fmeta.to_dict() for fid, fmeta in self.families.items()
            }
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def _generate_id(self, name: str) -> str:
        """Genera ID único para una familia"""
        slug = name.lower()
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
        for char, replacement in replacements.items():
            slug = slug.replace(char, replacement)
        slug = ''.join(c if c.isalnum() else '-' for c in slug)
        slug = '-'.join(filter(None, slug.split('-')))
        
        hash_suffix = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"
    
    def _get_family_path(self, family_id: str) -> Path:
        """Retorna la ruta de una familia"""
        return self.library_path / family_id
    
    def _extract_category_path(self, base_url: str) -> str:
        """Extrae el path de categoría de una URL base"""
        if not base_url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            return parsed.path or ""
        except Exception:
            return ""
    
    def list_families(self) -> List[Dict]:
        """Lista todas las familias disponibles como dicts"""
        return [
            {
                'id': fid,
                'name': fmeta.name,
                'description': fmeta.description,
                'base_url': fmeta.base_url,
                'total_urls': fmeta.total_urls,
                'urls_200': fmeta.urls_200,
                'urls_404': fmeta.urls_404,
                'total_traffic': fmeta.total_traffic,
                'updated_at': fmeta.updated_at,
                'has_crawl_master': fmeta.has_crawl_master,
                'has_adobe_urls': fmeta.has_adobe_urls,
                'has_adobe_filters': fmeta.has_adobe_filters,
                'has_semrush': fmeta.has_semrush,
                'source': 'local'
            }
            for fid, fmeta in self.families.items()
        ]
    
    def get_family(self, family_id: str) -> Optional[FamilyMetadata]:
        """Obtiene metadatos de una familia"""
        return self.families.get(family_id)
    
    def family_exists(self, family_id: str) -> bool:
        """Verifica si una familia existe"""
        return family_id in self.families
    
    def add_file_to_family(self,
                           family_id: str,
                           filepath: str,
                           file_type: FileType = None) -> Tuple[bool, str]:
        """
        Añade un archivo a una familia existente
        
        Args:
            family_id: ID de la familia
            filepath: Ruta al archivo a añadir
            file_type: Tipo de archivo (auto-detecta si no se especifica)
        
        Returns:
            (success, message)
        """
        if family_id not in self.families:
            return False, f"Familia '{family_id}' no encontrada"
        
        family_path = self._get_family_path(family_id)
        metadata = self.families[family_id]
        
        # Cargar y detectar tipo
        loader = DataLoader()
        result = loader.load_file(filepath, file_type)
        
        if not result.success:
            return False, f"Error cargando archivo: {result.error}"
        
        # Determinar nombre de almacenamiento
        storage_name = self.FILE_STORAGE_NAMES.get(result.file_type, Path(filepath).name)
        dest_path = family_path / storage_name
        
        # Copiar archivo
        shutil.copy(filepath, dest_path)
        
        # Actualizar metadatos
        file_info = FamilyFile(
            original_name=Path(filepath).name,
            stored_name=storage_name,
            file_type=result.file_type.value,
            row_count=result.row_count,
            columns=result.columns,
            added_at=datetime.now().isoformat(),
            metadata=result.metadata
        )
        
        metadata.files[result.file_type.value] = file_info
        
        # Actualizar flags
        self._update_availability_flags(metadata)
        
        # Si es crawl maestro, recalcular estadísticas
        if result.file_type == FileType.CRAWL_MASTER:
            self._update_crawl_stats(metadata, result.dataframe)
            # Guardar versión procesada
            try:
                result.dataframe.to_parquet(family_path / 'crawl_master_processed.parquet', index=False)
            except Exception:
                pass
        
        # Si es Adobe URLs, actualizar tráfico
        if result.file_type == FileType.ADOBE_URLS and 'visits_seo' in result.dataframe.columns:
            metadata.total_traffic = int(result.dataframe['visits_seo'].sum())
        
        # Si es Adobe Filters, actualizar demanda
        if result.file_type == FileType.ADOBE_FILTERS and 'visits_seo' in result.dataframe.columns:
            metadata.total_demand = int(result.dataframe['visits_seo'].sum())
        
        metadata.updated_at = datetime.now().isoformat()
        
        # Guardar metadatos
        with open(family_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        
        self._save_index()
        
        return True, f"Archivo añadido como {storage_name}"
    
    def _update_availability_flags(self, metadata: FamilyMetadata):
        """Actualiza flags de disponibilidad basados en archivos"""
        files = metadata.files
        metadata.has_crawl_master = FileType.CRAWL_MASTER.value in files
        metadata.has_crawl_gsc = FileType.CRAWL_SF_GSC.value in files
        metadata.has_adobe_urls = FileType.ADOBE_URLS.value in files
        metadata.has_adobe_filters = FileType.ADOBE_FILTERS.value in files
        metadata.has_semrush = FileType.SEMRUSH.value in files
        metadata.has_keyword_planner = FileType.KEYWORD_PLANNER.value in files
        metadata.has_crawl_historical = FileType.CRAWL_HISTORICAL.value in files
    
    def _update_crawl_stats(self, metadata: FamilyMetadata, df: pd.DataFrame):
        """Actualiza estadísticas del crawl"""
        metadata.total_urls = len(df)
        
        if 'Código de respuesta' in df.columns:
            metadata.urls_200 = len(df[df['Código de respuesta'] == 200])
            metadata.urls_404 = len(df[df['Código de respuesta'] == 404])
            metadata.urls_301 = len(df[df['Código de respuesta'] == 301])
        
        if 'has_wrapper' in df.columns:
            crawl_200 = df[df['Código de respuesta'] == 200] if 'Código de respuesta' in df.columns else df
            metadata.with_wrapper = len(crawl_200[crawl_200['has_wrapper'] == True])
            metadata.without_wrapper = len(crawl_200[crawl_200['has_wrapper'] == False])
    
    def create_family(self,
                      name: str,
                      description: str,
                      base_url: str,
                      crawl_file: str = None,
                      adobe_urls_file: str = None,
                      adobe_filters_file: str = None,
                      gsc_file: str = None,
                      semrush_file: str = None,
                      keyword_planner_file: str = None,
                      crawl_historical_file: str = None) -> FamilyMetadata:
        """Crea una nueva familia de productos"""
        family_id = self._generate_id(name)
        family_path = self._get_family_path(family_id)
        family_path.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now().isoformat()
        
        metadata = FamilyMetadata(
            id=family_id,
            name=name,
            slug=name.lower().replace(' ', '-'),
            description=description,
            created_at=now,
            updated_at=now,
            base_url=base_url,
            category_path=self._extract_category_path(base_url),
            files={}
        )
        
        self.families[family_id] = metadata
        
        file_map = [
            (crawl_file, FileType.CRAWL_MASTER),
            (adobe_urls_file, FileType.ADOBE_URLS),
            (adobe_filters_file, FileType.ADOBE_FILTERS),
            (gsc_file, FileType.CRAWL_SF_GSC),
            (semrush_file, FileType.SEMRUSH),
            (keyword_planner_file, FileType.KEYWORD_PLANNER),
            (crawl_historical_file, FileType.CRAWL_HISTORICAL),
        ]
        
        for filepath, file_type in file_map:
            if filepath and os.path.exists(filepath):
                success, msg = self.add_file_to_family(family_id, filepath, file_type)
                if not success:
                    print(f"Warning: {msg}")
        
        with open(family_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        
        self._save_index()
        
        return metadata
    
    def load_family_data(self, family_id: str) -> Dict[str, pd.DataFrame]:
        """
        Carga todos los datos de una familia con claves unificadas
        
        Args:
            family_id: ID de la familia
        
        Returns:
            Dict con DataFrames usando claves unificadas
        """
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        family_path = self._get_family_path(family_id)
        metadata = self.families[family_id]
        data = {}
        loader = DataLoader()
        
        # Mapeo de tipos a claves y archivos
        load_map = [
            (metadata.has_crawl_master, 'crawl_master', 'crawl_master.csv', 'crawl_master_processed.parquet', FileType.CRAWL_MASTER),
            (metadata.has_crawl_gsc, 'crawl_gsc', 'crawl_gsc.csv', None, FileType.CRAWL_SF_GSC),
            (metadata.has_crawl_historical, 'crawl_historical', 'crawl_historical.csv', None, FileType.CRAWL_HISTORICAL),
            (metadata.has_adobe_urls, 'adobe_urls', 'adobe_urls.csv', None, FileType.ADOBE_URLS),
            (metadata.has_adobe_filters, 'adobe_filters', 'adobe_filters.csv', None, FileType.ADOBE_FILTERS),
            (metadata.has_semrush, 'semrush', 'semrush.csv', None, FileType.SEMRUSH),
            (metadata.has_keyword_planner, 'keyword_planner', 'keyword_planner.csv', None, FileType.KEYWORD_PLANNER),
        ]
        
        for has_file, key, csv_name, parquet_name, file_type in load_map:
            if has_file:
                # Preferir parquet si existe
                if parquet_name:
                    parquet_path = family_path / parquet_name
                    if parquet_path.exists():
                        try:
                            data[key] = pd.read_parquet(parquet_path)
                            continue
                        except Exception:
                            pass
                
                # Cargar CSV
                csv_path = family_path / csv_name
                if csv_path.exists():
                    result = loader.load_file(str(csv_path), file_type)
                    if result.success:
                        data[key] = result.dataframe
                        
                        # Guardar parquet para próxima vez si es crawl master
                        if file_type == FileType.CRAWL_MASTER and parquet_name:
                            try:
                                result.dataframe.to_parquet(family_path / parquet_name, index=False)
                            except Exception:
                                pass
        
        return data
    
    def update_family(self,
                      family_id: str,
                      **file_kwargs) -> FamilyMetadata:
        """Actualiza archivos de una familia existente"""
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        kwarg_to_type = {
            'crawl_file': FileType.CRAWL_MASTER,
            'adobe_urls_file': FileType.ADOBE_URLS,
            'adobe_filters_file': FileType.ADOBE_FILTERS,
            'gsc_file': FileType.CRAWL_SF_GSC,
            'semrush_file': FileType.SEMRUSH,
            'keyword_planner_file': FileType.KEYWORD_PLANNER,
            'crawl_historical_file': FileType.CRAWL_HISTORICAL,
        }
        
        for kwarg, file_type in kwarg_to_type.items():
            filepath = file_kwargs.get(kwarg)
            if filepath and os.path.exists(filepath):
                self.add_file_to_family(family_id, filepath, file_type)
        
        return self.families[family_id]
    
    def delete_family(self, family_id: str) -> bool:
        """Elimina una familia y todos sus datos"""
        if family_id not in self.families:
            return False
        
        family_path = self._get_family_path(family_id)
        
        if family_path.exists():
            shutil.rmtree(family_path)
        
        del self.families[family_id]
        self._save_index()
        
        return True
    
    def export_family(self, family_id: str, output_path: str) -> str:
        """Exporta una familia a un archivo ZIP"""
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        family_path = self._get_family_path(family_id)
        output_base = output_path.replace('.zip', '')
        
        shutil.make_archive(output_base, 'zip', family_path)
        
        return output_path
    
    def import_family(self, zip_path: str, new_name: str = None) -> FamilyMetadata:
        """Importa una familia desde un archivo ZIP"""
        import zipfile
        
        temp_path = self.library_path / '_temp_import'
        temp_path.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_path)
        
        metadata_file = temp_path / 'metadata.json'
        if not metadata_file.exists():
            shutil.rmtree(temp_path)
            raise ValueError("ZIP no contiene metadata.json válido")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_dict = json.load(f)
        
        old_name = metadata_dict.get('name', 'Imported')
        new_id = self._generate_id(new_name or old_name)
        metadata_dict['id'] = new_id
        if new_name:
            metadata_dict['name'] = new_name
        metadata_dict['updated_at'] = datetime.now().isoformat()
        
        final_path = self._get_family_path(new_id)
        shutil.move(str(temp_path), str(final_path))
        
        with open(final_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False, default=str)
        
        metadata = FamilyMetadata.from_dict(metadata_dict)
        self.families[new_id] = metadata
        self._save_index()
        
        return metadata
    
    def get_family_files_info(self, family_id: str) -> List[Dict]:
        """Obtiene información de los archivos de una familia"""
        if family_id not in self.families:
            return []
        
        metadata = self.families[family_id]
        family_path = self._get_family_path(family_id)
        
        files_info = []
        for file_type, file_info in metadata.files.items():
            if isinstance(file_info, FamilyFile):
                info = {
                    'type': file_type,
                    'original_name': file_info.original_name,
                    'stored_name': file_info.stored_name,
                    'row_count': file_info.row_count,
                    'added_at': file_info.added_at,
                    'exists': (family_path / file_info.stored_name).exists()
                }
            else:
                info = {
                    'type': file_type,
                    'stored_name': file_info,
                    'exists': (family_path / file_info).exists() if isinstance(file_info, str) else False
                }
            files_info.append(info)
        
        return files_info


def get_default_library() -> FamilyLibrary:
    """Retorna la biblioteca por defecto"""
    return FamilyLibrary('./library')


def quick_create_family(name: str,
                        crawl_path: str,
                        base_url: str,
                        **kwargs) -> FamilyMetadata:
    """Atajo para crear una familia rápidamente"""
    library = get_default_library()
    return library.create_family(
        name=name,
        description=f"Familia de productos: {name}",
        base_url=base_url,
        crawl_file=crawl_path,
        **kwargs
    )
