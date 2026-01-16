"""
Gestor de Biblioteca de Familias de Productos
Almacena y gestiona datos de diferentes categorías para reutilización
"""

import os
import json
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class FamilyMetadata:
    """Metadatos de una familia de productos"""
    id: str
    name: str                      # Ej: "Smartphones", "Electrodomésticos"
    slug: str                      # Ej: "smartphones", "electrodomesticos"
    description: str
    created_at: str
    updated_at: str
    base_url: str                  # Ej: "https://www.pccomponentes.com/smartphone-moviles"
    
    # Estadísticas
    total_urls: int
    urls_200: int
    urls_404: int
    has_adobe_urls: bool
    has_adobe_filters: bool
    has_gsc: bool
    has_semrush: bool
    
    # Archivos incluidos
    files: Dict[str, str]          # {tipo: filename}


class FamilyLibrary:
    """
    Biblioteca de familias de productos
    Gestiona almacenamiento y carga de datos por categoría
    """
    
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
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for family_id, family_data in data.get('families', {}).items():
                    self.families[family_id] = FamilyMetadata(**family_data)
    
    def _save_index(self):
        """Guarda el índice de familias"""
        data = {
            'version': '2.0',
            'updated_at': datetime.now().isoformat(),
            'families': {
                fid: asdict(fmeta) for fid, fmeta in self.families.items()
            }
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_id(self, name: str) -> str:
        """Genera ID único para una familia"""
        slug = name.lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        # Añadir hash corto para unicidad
        hash_suffix = hashlib.md5(f"{name}{datetime.now().isoformat()}".encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"
    
    def _get_family_path(self, family_id: str) -> Path:
        """Retorna la ruta de una familia"""
        return self.library_path / family_id
    
    def list_families(self) -> List[FamilyMetadata]:
        """Lista todas las familias disponibles"""
        return list(self.families.values())
    
    def get_family(self, family_id: str) -> Optional[FamilyMetadata]:
        """Obtiene metadatos de una familia"""
        return self.families.get(family_id)
    
    def family_exists(self, family_id: str) -> bool:
        """Verifica si una familia existe"""
        return family_id in self.families
    
    def create_family(self,
                      name: str,
                      description: str,
                      base_url: str,
                      crawl_file: str,
                      adobe_urls_file: str = None,
                      adobe_filters_file: str = None,
                      gsc_file: str = None,
                      semrush_file: str = None) -> FamilyMetadata:
        """
        Crea una nueva familia de productos
        
        Args:
            name: Nombre de la familia (ej: "Smartphones")
            description: Descripción
            base_url: URL base de la categoría
            crawl_file: Ruta al archivo de crawl principal (obligatorio)
            adobe_urls_file: Ruta al archivo de URLs de Adobe (opcional)
            adobe_filters_file: Ruta al archivo de filtros de Adobe (opcional)
            gsc_file: Ruta al archivo de GSC (opcional)
            semrush_file: Ruta al archivo de SEMrush (opcional)
        
        Returns:
            FamilyMetadata de la familia creada
        """
        # Generar ID
        family_id = self._generate_id(name)
        family_path = self._get_family_path(family_id)
        family_path.mkdir(parents=True, exist_ok=True)
        
        files = {}
        
        # Copiar y procesar crawl principal
        crawl_dest = family_path / 'crawl.csv'
        shutil.copy(crawl_file, crawl_dest)
        files['crawl'] = 'crawl.csv'
        
        # Cargar crawl para estadísticas
        df_crawl = pd.read_csv(crawl_dest, low_memory=False)
        total_urls = len(df_crawl)
        urls_200 = len(df_crawl[df_crawl['Código de respuesta'] == 200])
        urls_404 = len(df_crawl[df_crawl['Código de respuesta'] == 404])
        
        # Preprocesar crawl (calcular wrapper_count)
        href_cols = [f'seoFilterWrapper_hrefs {i}' for i in range(1, 84)]
        def count_wrapper_links(row):
            count = 0
            for col in href_cols:
                if col in df_crawl.columns:
                    val = row.get(col)
                    if pd.notna(val) and str(val).strip() and str(val).startswith('http'):
                        count += 1
            return count
        
        df_crawl['wrapper_link_count'] = df_crawl.apply(count_wrapper_links, axis=1)
        df_crawl['has_wrapper'] = df_crawl['wrapper_link_count'] > 0
        
        # Guardar versión preprocesada
        df_crawl.to_parquet(family_path / 'crawl_processed.parquet', index=False)
        files['crawl_processed'] = 'crawl_processed.parquet'
        
        # Copiar archivos opcionales
        if adobe_urls_file and os.path.exists(adobe_urls_file):
            shutil.copy(adobe_urls_file, family_path / 'adobe_urls.csv')
            files['adobe_urls'] = 'adobe_urls.csv'
        
        if adobe_filters_file and os.path.exists(adobe_filters_file):
            shutil.copy(adobe_filters_file, family_path / 'adobe_filters.csv')
            files['adobe_filters'] = 'adobe_filters.csv'
        
        if gsc_file and os.path.exists(gsc_file):
            shutil.copy(gsc_file, family_path / 'gsc.csv')
            files['gsc'] = 'gsc.csv'
        
        if semrush_file and os.path.exists(semrush_file):
            shutil.copy(semrush_file, family_path / 'semrush.csv')
            files['semrush'] = 'semrush.csv'
        
        # Crear metadatos
        now = datetime.now().isoformat()
        metadata = FamilyMetadata(
            id=family_id,
            name=name,
            slug=name.lower().replace(' ', '-'),
            description=description,
            created_at=now,
            updated_at=now,
            base_url=base_url,
            total_urls=total_urls,
            urls_200=urls_200,
            urls_404=urls_404,
            has_adobe_urls='adobe_urls' in files,
            has_adobe_filters='adobe_filters' in files,
            has_gsc='gsc' in files,
            has_semrush='semrush' in files,
            files=files
        )
        
        # Guardar metadatos de familia
        with open(family_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
        
        # Actualizar índice
        self.families[family_id] = metadata
        self._save_index()
        
        return metadata
    
    def load_family_data(self, family_id: str) -> Dict[str, pd.DataFrame]:
        """
        Carga todos los datos de una familia
        
        Args:
            family_id: ID de la familia
        
        Returns:
            Dict con DataFrames cargados
        """
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        family_path = self._get_family_path(family_id)
        metadata = self.families[family_id]
        data = {}
        
        # Cargar crawl preprocesado (más rápido)
        if 'crawl_processed' in metadata.files:
            data['crawl_adobe'] = pd.read_parquet(family_path / 'crawl_processed.parquet')
        elif 'crawl' in metadata.files:
            data['crawl_adobe'] = pd.read_csv(family_path / 'crawl.csv', low_memory=False)
        
        # Cargar Adobe URLs
        if metadata.has_adobe_urls:
            df = pd.read_csv(family_path / 'adobe_urls.csv', skiprows=13, encoding='utf-8-sig')
            df.columns = ['url', 'visits_seo']
            df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
            df['url_full'] = df['url'].apply(
                lambda x: 'https://' + str(x) if not str(x).startswith('http') else str(x)
            )
            data['adobe_urls'] = df
        
        # Cargar Adobe Filters
        if metadata.has_adobe_filters:
            df = pd.read_csv(family_path / 'adobe_filters.csv', skiprows=13, encoding='utf-8-sig')
            df.columns = ['filter_name', 'visits_seo']
            df['visits_seo'] = pd.to_numeric(df['visits_seo'], errors='coerce').fillna(0)
            data['adobe_filters'] = df
        
        # Cargar GSC
        if metadata.has_gsc:
            data['gsc'] = pd.read_csv(family_path / 'gsc.csv')
        
        # Cargar SEMrush
        if metadata.has_semrush:
            data['semrush'] = pd.read_csv(family_path / 'semrush.csv')
        
        return data
    
    def update_family(self, 
                      family_id: str,
                      crawl_file: str = None,
                      adobe_urls_file: str = None,
                      adobe_filters_file: str = None,
                      gsc_file: str = None,
                      semrush_file: str = None) -> FamilyMetadata:
        """
        Actualiza archivos de una familia existente
        """
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        family_path = self._get_family_path(family_id)
        metadata = self.families[family_id]
        
        # Actualizar archivos proporcionados
        if crawl_file:
            shutil.copy(crawl_file, family_path / 'crawl.csv')
            # Reprocesar
            df = pd.read_csv(family_path / 'crawl.csv', low_memory=False)
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
            df.to_parquet(family_path / 'crawl_processed.parquet', index=False)
            
            # Actualizar estadísticas
            metadata.total_urls = len(df)
            metadata.urls_200 = len(df[df['Código de respuesta'] == 200])
            metadata.urls_404 = len(df[df['Código de respuesta'] == 404])
        
        if adobe_urls_file:
            shutil.copy(adobe_urls_file, family_path / 'adobe_urls.csv')
            metadata.has_adobe_urls = True
            metadata.files['adobe_urls'] = 'adobe_urls.csv'
        
        if adobe_filters_file:
            shutil.copy(adobe_filters_file, family_path / 'adobe_filters.csv')
            metadata.has_adobe_filters = True
            metadata.files['adobe_filters'] = 'adobe_filters.csv'
        
        if gsc_file:
            shutil.copy(gsc_file, family_path / 'gsc.csv')
            metadata.has_gsc = True
            metadata.files['gsc'] = 'gsc.csv'
        
        if semrush_file:
            shutil.copy(semrush_file, family_path / 'semrush.csv')
            metadata.has_semrush = True
            metadata.files['semrush'] = 'semrush.csv'
        
        metadata.updated_at = datetime.now().isoformat()
        
        # Guardar
        with open(family_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)
        
        self.families[family_id] = metadata
        self._save_index()
        
        return metadata
    
    def delete_family(self, family_id: str) -> bool:
        """
        Elimina una familia y todos sus datos
        
        Args:
            family_id: ID de la familia a eliminar
        
        Returns:
            True si se eliminó correctamente
        """
        if family_id not in self.families:
            return False
        
        family_path = self._get_family_path(family_id)
        
        # Eliminar carpeta
        if family_path.exists():
            shutil.rmtree(family_path)
        
        # Eliminar del índice
        del self.families[family_id]
        self._save_index()
        
        return True
    
    def export_family(self, family_id: str, output_path: str) -> str:
        """
        Exporta una familia a un archivo ZIP
        
        Args:
            family_id: ID de la familia
            output_path: Ruta de salida para el ZIP
        
        Returns:
            Ruta del archivo ZIP creado
        """
        if family_id not in self.families:
            raise ValueError(f"Familia '{family_id}' no encontrada")
        
        family_path = self._get_family_path(family_id)
        
        # Crear ZIP
        shutil.make_archive(output_path.replace('.zip', ''), 'zip', family_path)
        
        return output_path
    
    def import_family(self, zip_path: str) -> FamilyMetadata:
        """
        Importa una familia desde un archivo ZIP
        
        Args:
            zip_path: Ruta al archivo ZIP
        
        Returns:
            Metadatos de la familia importada
        """
        import zipfile
        
        # Extraer a carpeta temporal
        temp_path = self.library_path / '_temp_import'
        temp_path.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_path)
        
        # Cargar metadatos
        metadata_file = temp_path / 'metadata.json'
        if not metadata_file.exists():
            shutil.rmtree(temp_path)
            raise ValueError("Archivo ZIP no contiene metadata.json válido")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_dict = json.load(f)
        
        # Generar nuevo ID para evitar colisiones
        old_id = metadata_dict['id']
        new_id = self._generate_id(metadata_dict['name'])
        metadata_dict['id'] = new_id
        metadata_dict['updated_at'] = datetime.now().isoformat()
        
        # Mover a ubicación final
        final_path = self._get_family_path(new_id)
        shutil.move(str(temp_path), str(final_path))
        
        # Actualizar metadata en disco
        with open(final_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
        
        # Añadir al índice
        metadata = FamilyMetadata(**metadata_dict)
        self.families[new_id] = metadata
        self._save_index()
        
        return metadata


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def get_default_library() -> FamilyLibrary:
    """Retorna la biblioteca por defecto"""
    return FamilyLibrary('./library')


def quick_create_family(name: str, 
                        crawl_path: str,
                        base_url: str,
                        **kwargs) -> FamilyMetadata:
    """
    Atajo para crear una familia rápidamente
    
    Args:
        name: Nombre de la familia
        crawl_path: Ruta al archivo de crawl
        base_url: URL base
        **kwargs: Archivos adicionales (adobe_urls_file, etc.)
    """
    library = get_default_library()
    return library.create_family(
        name=name,
        description=f"Familia de productos: {name}",
        base_url=base_url,
        crawl_file=crawl_path,
        **kwargs
    )
