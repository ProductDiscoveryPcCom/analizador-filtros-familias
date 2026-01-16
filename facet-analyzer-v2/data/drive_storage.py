"""
Integración con Google Drive para persistencia de biblioteca
Permite guardar y cargar familias de productos en Drive
"""

import os
import json
import io
import tempfile
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import streamlit as st


class GoogleDriveStorage:
    """
    Almacenamiento en Google Drive para la biblioteca de familias
    
    Requiere configurar:
    1. Credenciales de servicio de Google Cloud
    2. ID de carpeta de Drive donde guardar
    """
    
    def __init__(self, credentials_json: str = None, folder_id: str = None):
        """
        Inicializa el cliente de Google Drive
        
        Args:
            credentials_json: JSON de credenciales de servicio (o env GOOGLE_CREDENTIALS)
            folder_id: ID de la carpeta de Drive (o env GOOGLE_DRIVE_FOLDER_ID)
        """
        self.credentials_json = credentials_json or os.getenv('GOOGLE_CREDENTIALS')
        self.folder_id = folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        self.service = None
        self._initialized = False
        
        # Intentar inicializar si hay credenciales
        if self.credentials_json and self.folder_id:
            self._initialize()
    
    def _initialize(self):
        """Inicializa el servicio de Google Drive"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            # Parsear credenciales
            if isinstance(self.credentials_json, str):
                creds_dict = json.loads(self.credentials_json)
            else:
                creds_dict = self.credentials_json
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            self._initialized = True
            
        except ImportError:
            st.warning("⚠️ Instala google-api-python-client: `pip install google-api-python-client google-auth`")
        except Exception as e:
            st.error(f"Error inicializando Google Drive: {e}")
    
    def is_configured(self) -> bool:
        """Verifica si Drive está configurado"""
        return self._initialized and self.service is not None
    
    def list_families(self) -> List[Dict]:
        """Lista todas las familias guardadas en Drive"""
        if not self.is_configured():
            return []
        
        try:
            # Buscar carpetas en la carpeta principal
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name, modifiedTime)"
            ).execute()
            
            families = []
            for folder in results.get('files', []):
                # Buscar metadata.json en cada carpeta
                metadata = self._get_file_content(folder['id'], 'metadata.json')
                if metadata:
                    families.append({
                        'drive_folder_id': folder['id'],
                        'name': folder['name'],
                        'modified': folder['modifiedTime'],
                        'metadata': json.loads(metadata)
                    })
            
            return families
            
        except Exception as e:
            st.error(f"Error listando familias: {e}")
            return []
    
    def _get_file_content(self, folder_id: str, filename: str) -> Optional[str]:
        """Obtiene contenido de un archivo en una carpeta"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and name='{filename}'",
                fields="files(id)"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return None
            
            content = self.service.files().get_media(fileId=files[0]['id']).execute()
            return content.decode('utf-8')
            
        except Exception:
            return None
    
    def save_family(self, family_id: str, local_path: Path) -> bool:
        """
        Guarda una familia en Drive
        
        Args:
            family_id: ID de la familia
            local_path: Ruta local de la carpeta de la familia
        
        Returns:
            True si se guardó correctamente
        """
        if not self.is_configured():
            return False
        
        try:
            from googleapiclient.http import MediaFileUpload
            
            # Crear carpeta para la familia
            folder_metadata = {
                'name': family_id,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.folder_id]
            }
            
            # Buscar si ya existe
            existing = self.service.files().list(
                q=f"'{self.folder_id}' in parents and name='{family_id}'",
                fields="files(id)"
            ).execute().get('files', [])
            
            if existing:
                family_folder_id = existing[0]['id']
                # Eliminar archivos existentes
                old_files = self.service.files().list(
                    q=f"'{family_folder_id}' in parents",
                    fields="files(id)"
                ).execute().get('files', [])
                for f in old_files:
                    self.service.files().delete(fileId=f['id']).execute()
            else:
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                family_folder_id = folder['id']
            
            # Subir archivos
            for file_path in local_path.iterdir():
                if file_path.is_file():
                    file_metadata = {
                        'name': file_path.name,
                        'parents': [family_folder_id]
                    }
                    
                    # Determinar MIME type
                    mime_type = 'application/octet-stream'
                    if file_path.suffix == '.json':
                        mime_type = 'application/json'
                    elif file_path.suffix == '.csv':
                        mime_type = 'text/csv'
                    elif file_path.suffix == '.parquet':
                        mime_type = 'application/octet-stream'
                    
                    media = MediaFileUpload(
                        str(file_path),
                        mimetype=mime_type,
                        resumable=True
                    )
                    
                    self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Error guardando familia en Drive: {e}")
            return False
    
    def load_family(self, family_id: str, local_path: Path) -> bool:
        """
        Carga una familia desde Drive a local
        
        Args:
            family_id: ID de la familia
            local_path: Ruta local donde guardar
        
        Returns:
            True si se cargó correctamente
        """
        if not self.is_configured():
            return False
        
        try:
            # Buscar carpeta de la familia
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and name='{family_id}'",
                fields="files(id)"
            ).execute()
            
            folders = results.get('files', [])
            if not folders:
                return False
            
            family_folder_id = folders[0]['id']
            
            # Crear directorio local
            local_path.mkdir(parents=True, exist_ok=True)
            
            # Listar y descargar archivos
            files = self.service.files().list(
                q=f"'{family_folder_id}' in parents",
                fields="files(id, name)"
            ).execute().get('files', [])
            
            for file_info in files:
                content = self.service.files().get_media(fileId=file_info['id']).execute()
                
                file_path = local_path / file_info['name']
                with open(file_path, 'wb') as f:
                    f.write(content)
            
            return True
            
        except Exception as e:
            st.error(f"Error cargando familia desde Drive: {e}")
            return False
    
    def delete_family(self, family_id: str) -> bool:
        """Elimina una familia de Drive"""
        if not self.is_configured():
            return False
        
        try:
            # Buscar carpeta
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and name='{family_id}'",
                fields="files(id)"
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                self.service.files().delete(fileId=folders[0]['id']).execute()
                return True
            
            return False
            
        except Exception as e:
            st.error(f"Error eliminando familia: {e}")
            return False


class HybridLibraryStorage:
    """
    Almacenamiento híbrido: local + Google Drive
    Usa local como caché y Drive como persistencia
    """
    
    def __init__(self, local_path: str = './library'):
        self.local_path = Path(local_path)
        self.local_path.mkdir(parents=True, exist_ok=True)
        
        # Inicializar Drive si está configurado
        self.drive = GoogleDriveStorage()
        
        # Índice local
        self.index_file = self.local_path / 'index.json'
        self._load_index()
    
    def _load_index(self):
        """Carga índice local"""
        self.index = {}
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
    
    def _save_index(self):
        """Guarda índice local"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def is_drive_enabled(self) -> bool:
        """Verifica si Drive está habilitado"""
        return self.drive.is_configured()
    
    def sync_from_drive(self) -> int:
        """
        Sincroniza familias desde Drive a local
        
        Returns:
            Número de familias sincronizadas
        """
        if not self.is_drive_enabled():
            return 0
        
        synced = 0
        drive_families = self.drive.list_families()
        
        for family in drive_families:
            family_id = family['metadata'].get('id', family['name'])
            local_family_path = self.local_path / family_id
            
            # Si no existe local o está desactualizado, descargar
            if not local_family_path.exists():
                if self.drive.load_family(family_id, local_family_path):
                    self.index[family_id] = family['metadata']
                    synced += 1
        
        self._save_index()
        return synced
    
    def sync_to_drive(self, family_id: str) -> bool:
        """Sincroniza una familia a Drive"""
        if not self.is_drive_enabled():
            return False
        
        local_path = self.local_path / family_id
        if not local_path.exists():
            return False
        
        return self.drive.save_family(family_id, local_path)
    
    def list_families(self, include_drive: bool = True) -> List[Dict]:
        """Lista todas las familias disponibles"""
        families = []
        
        # Familias locales
        for family_id, metadata in self.index.items():
            families.append({
                'id': family_id,
                'source': 'local',
                **metadata
            })
        
        # Familias solo en Drive
        if include_drive and self.is_drive_enabled():
            drive_families = self.drive.list_families()
            local_ids = set(self.index.keys())
            
            for df in drive_families:
                family_id = df['metadata'].get('id', df['name'])
                if family_id not in local_ids:
                    families.append({
                        'id': family_id,
                        'source': 'drive',
                        **df['metadata']
                    })
        
        return families


def render_drive_config_ui():
    """Renderiza UI para configurar Google Drive"""
    st.subheader("☁️ Configurar Google Drive")
    
    st.info("""
    Conecta con Google Drive para que tus familias de productos persistan
    entre sesiones, incluso en Streamlit Cloud.
    """)
    
    # Verificar si ya está configurado
    drive = GoogleDriveStorage()
    
    if drive.is_configured():
        st.success("✅ Google Drive conectado")
        
        # Mostrar familias en Drive
        families = drive.list_families()
        st.caption(f"Familias en Drive: {len(families)}")
        
        if st.button("🔄 Sincronizar desde Drive"):
            storage = HybridLibraryStorage()
            synced = storage.sync_from_drive()
            st.success(f"✅ {synced} familias sincronizadas")
    else:
        st.warning("Google Drive no configurado")
        
        with st.expander("📋 Instrucciones de configuración"):
            st.markdown("""
            ### Paso 1: Crear credenciales de servicio
            
            1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
            2. Crea un proyecto o selecciona uno existente
            3. Habilita la API de Google Drive
            4. Ve a "Credenciales" → "Crear credenciales" → "Cuenta de servicio"
            5. Descarga el JSON de credenciales
            
            ### Paso 2: Crear carpeta en Drive
            
            1. Crea una carpeta en Google Drive
            2. Comparte la carpeta con el email de la cuenta de servicio
            3. Copia el ID de la carpeta (está en la URL)
            
            ### Paso 3: Configurar secretos
            
            En Streamlit Cloud, añade estos secretos:
            
            ```toml
            [secrets]
            GOOGLE_CREDENTIALS = '{"type": "service_account", ...}'
            GOOGLE_DRIVE_FOLDER_ID = "tu-folder-id"
            ```
            """)
        
        # Permitir configuración manual
        col1, col2 = st.columns(2)
        
        with col1:
            creds = st.text_area(
                "Credenciales JSON",
                height=100,
                placeholder='{"type": "service_account", ...}'
            )
        
        with col2:
            folder_id = st.text_input(
                "ID de carpeta de Drive",
                placeholder="1ABC..."
            )
        
        if st.button("🔗 Conectar") and creds and folder_id:
            try:
                test_drive = GoogleDriveStorage(creds, folder_id)
                if test_drive.is_configured():
                    # Guardar en session state para esta sesión
                    st.session_state['google_credentials'] = creds
                    st.session_state['google_drive_folder'] = folder_id
                    os.environ['GOOGLE_CREDENTIALS'] = creds
                    os.environ['GOOGLE_DRIVE_FOLDER_ID'] = folder_id
                    st.success("✅ Conectado correctamente")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
