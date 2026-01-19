"""
Integración con Google Drive para persistencia de biblioteca - v2.3
Permite guardar y cargar familias de productos en Drive
"""

import os
import json
import tempfile
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

# Streamlit es opcional
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False


class GoogleDriveStorage:
    """
    Almacenamiento en Google Drive para la biblioteca de familias
    """
    
    def __init__(self, credentials_json: str = None, folder_id: str = None):
        """
        Inicializa el cliente de Google Drive
        
        Args:
            credentials_json: JSON de credenciales de servicio
            folder_id: ID de la carpeta de Drive
        """
        self.credentials_json = credentials_json
        self.folder_id = folder_id
        self.service = None
        self._initialized = False
        
        self._load_config()
        
        if self.credentials_json and self.folder_id:
            self._initialize()
    
    def _load_config(self):
        """Carga configuración desde st.secrets o env vars"""
        # Streamlit secrets
        if HAS_STREAMLIT:
            try:
                if hasattr(st, 'secrets'):
                    if 'GOOGLE_CREDENTIALS' in st.secrets:
                        self.credentials_json = self.credentials_json or st.secrets['GOOGLE_CREDENTIALS']
                    if 'google_credentials' in st.secrets:
                        self.credentials_json = self.credentials_json or dict(st.secrets['google_credentials'])
                    if 'GOOGLE_DRIVE_FOLDER_ID' in st.secrets:
                        self.folder_id = self.folder_id or st.secrets['GOOGLE_DRIVE_FOLDER_ID']
            except Exception:
                pass
            
            # Session state
            if not self.credentials_json:
                self.credentials_json = st.session_state.get('google_credentials')
            if not self.folder_id:
                self.folder_id = st.session_state.get('google_drive_folder')
        
        # Variables de entorno
        self.credentials_json = self.credentials_json or os.getenv('GOOGLE_CREDENTIALS')
        self.folder_id = self.folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    def _initialize(self):
        """Inicializa el servicio de Google Drive"""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            if isinstance(self.credentials_json, str):
                creds_dict = json.loads(self.credentials_json)
            elif isinstance(self.credentials_json, dict):
                creds_dict = self.credentials_json
            else:
                return
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            self._initialized = True
            
        except ImportError:
            pass
        except Exception as e:
            print(f"Error inicializando Google Drive: {e}")
    
    def is_configured(self) -> bool:
        """Verifica si Drive está configurado"""
        return self._initialized and self.service is not None
    
    def list_families(self) -> List[Dict]:
        """Lista todas las familias guardadas en Drive"""
        if not self.is_configured():
            return []
        
        try:
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name, modifiedTime)"
            ).execute()
            
            families = []
            for folder in results.get('files', []):
                metadata = self._get_file_content(folder['id'], 'metadata.json')
                if metadata:
                    try:
                        families.append({
                            'drive_folder_id': folder['id'],
                            'name': folder['name'],
                            'modified': folder['modifiedTime'],
                            'metadata': json.loads(metadata)
                        })
                    except json.JSONDecodeError:
                        pass
            
            return families
            
        except Exception as e:
            print(f"Error listando familias: {e}")
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
        """Guarda una familia en Drive"""
        if not self.is_configured():
            return False
        
        try:
            from googleapiclient.http import MediaFileUpload
            
            existing = self.service.files().list(
                q=f"'{self.folder_id}' in parents and name='{family_id}'",
                fields="files(id)"
            ).execute().get('files', [])
            
            if existing:
                family_folder_id = existing[0]['id']
                old_files = self.service.files().list(
                    q=f"'{family_folder_id}' in parents",
                    fields="files(id)"
                ).execute().get('files', [])
                for f in old_files:
                    self.service.files().delete(fileId=f['id']).execute()
            else:
                folder_metadata = {
                    'name': family_id,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [self.folder_id]
                }
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                family_folder_id = folder['id']
            
            for file_path in local_path.iterdir():
                if file_path.is_file():
                    file_metadata = {
                        'name': file_path.name,
                        'parents': [family_folder_id]
                    }
                    
                    mime_type = 'application/octet-stream'
                    if file_path.suffix == '.json':
                        mime_type = 'application/json'
                    elif file_path.suffix == '.csv':
                        mime_type = 'text/csv'
                    
                    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
                    self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error guardando familia en Drive: {e}")
            return False
    
    def load_family(self, family_id: str, local_path: Path) -> bool:
        """Carga una familia desde Drive a local"""
        if not self.is_configured():
            return False
        
        try:
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents and name='{family_id}'",
                fields="files(id)"
            ).execute()
            
            folders = results.get('files', [])
            if not folders:
                return False
            
            family_folder_id = folders[0]['id']
            local_path.mkdir(parents=True, exist_ok=True)
            
            files = self.service.files().list(
                q=f"'{family_folder_id}' in parents",
                fields="files(id, name)"
            ).execute().get('files', [])
            
            for file_info in files:
                content = self.service.files().get_media(fileId=file_info['id']).execute()
                with open(local_path / file_info['name'], 'wb') as f:
                    f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Error cargando familia: {e}")
            return False
    
    def delete_family(self, family_id: str) -> bool:
        """Elimina una familia de Drive"""
        if not self.is_configured():
            return False
        
        try:
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
            print(f"Error eliminando familia: {e}")
            return False


class HybridLibraryStorage:
    """
    Almacenamiento híbrido: local + Google Drive
    """
    
    def __init__(self, local_path: str = './library'):
        self.local_path = Path(local_path)
        self.local_path.mkdir(parents=True, exist_ok=True)
        
        self.drive = GoogleDriveStorage()
        
        self.index_file = self.local_path / 'index.json'
        self._load_index()
    
    def _load_index(self):
        """Carga índice local"""
        self.index = {}
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.index = data.get('families', data)
            except Exception:
                self.index = {}
    
    def _save_index(self):
        """Guarda índice local"""
        data = {
            'version': '2.3',
            'updated_at': datetime.now().isoformat(),
            'families': self.index
        }
        with open(self.index_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def is_drive_enabled(self) -> bool:
        """Verifica si Drive está habilitado"""
        return self.drive.is_configured()
    
    def sync_from_drive(self) -> int:
        """Sincroniza familias desde Drive a local"""
        if not self.is_drive_enabled():
            return 0
        
        synced = 0
        try:
            drive_families = self.drive.list_families()
            
            for family in drive_families:
                if not isinstance(family, dict):
                    continue
                
                metadata = family.get('metadata', {})
                if not isinstance(metadata, dict):
                    continue
                
                family_id = metadata.get('id', family.get('name', ''))
                if not family_id:
                    continue
                
                local_family_path = self.local_path / family_id
                
                if not local_family_path.exists():
                    if self.drive.load_family(family_id, local_family_path):
                        self.index[family_id] = metadata
                        synced += 1
            
            self._save_index()
        except Exception as e:
            print(f"Error sincronizando: {e}")
        
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
        
        for family_id, metadata in self.index.items():
            if isinstance(metadata, dict):
                families.append({
                    'id': family_id,
                    'source': 'local',
                    **metadata
                })
            else:
                families.append({
                    'id': family_id,
                    'source': 'local',
                    'name': family_id
                })
        
        if include_drive and self.is_drive_enabled():
            try:
                drive_families = self.drive.list_families()
                local_ids = set(self.index.keys())
                
                for df in drive_families:
                    if isinstance(df, dict) and 'metadata' in df:
                        meta = df.get('metadata', {})
                        if isinstance(meta, dict):
                            family_id = meta.get('id', df.get('name', 'unknown'))
                            if family_id not in local_ids:
                                families.append({
                                    'id': family_id,
                                    'source': 'drive',
                                    **meta
                                })
            except Exception:
                pass
        
        return families


def render_drive_config_ui():
    """Renderiza UI para configurar Google Drive"""
    if not HAS_STREAMLIT:
        raise ImportError("Streamlit no está instalado")
    
    st.subheader("☁️ Google Drive")
    
    drive = GoogleDriveStorage()
    
    if drive.is_configured():
        st.success("✅ Google Drive conectado")
        
        families = drive.list_families()
        st.caption(f"Familias en Drive: {len(families)}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Sincronizar desde Drive", use_container_width=True):
                storage = HybridLibraryStorage()
                synced = storage.sync_from_drive()
                st.success(f"✅ {synced} familias sincronizadas")
                st.rerun()
    else:
        st.warning("Google Drive no configurado")
        
        with st.expander("📋 Instrucciones"):
            st.markdown("""
            ### Configurar Google Drive
            
            1. **Google Cloud Console**: Crea un proyecto y habilita Drive API
            2. **Cuenta de servicio**: Crea credenciales de servicio
            3. **Carpeta Drive**: Crea una carpeta y compártela con la cuenta de servicio
            4. **Streamlit Secrets**: Añade las credenciales
            
            ```toml
            GOOGLE_DRIVE_FOLDER_ID = "tu-folder-id"
            
            [google_credentials]
            type = "service_account"
            project_id = "..."
            private_key = "..."
            client_email = "..."
            ```
            """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            creds = st.text_area(
                "Credenciales JSON",
                height=100,
                placeholder='{"type": "service_account", ...}'
            )
        
        with col2:
            folder_id = st.text_input("ID de carpeta Drive", placeholder="1ABC...")
        
        if st.button("🔗 Conectar") and creds and folder_id:
            try:
                test_drive = GoogleDriveStorage(creds, folder_id)
                if test_drive.is_configured():
                    st.session_state['google_credentials'] = creds
                    st.session_state['google_drive_folder'] = folder_id
                    st.success("✅ Conectado")
                    st.rerun()
                else:
                    st.error("No se pudo conectar")
            except Exception as e:
                st.error(f"Error: {e}")
