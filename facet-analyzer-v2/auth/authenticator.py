"""
Módulo de Autenticación
Login con verificación por email para dominio @pccomponentes.com
"""

import streamlit as st
import smtplib
import secrets
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os
import json


# Configuración
ALLOWED_DOMAIN = "pccomponentes.com"
CODE_EXPIRY_MINUTES = 10
CODE_LENGTH = 6


class EmailAuthenticator:
    """
    Sistema de autenticación por email con código OTP
    """
    
    def __init__(self):
        """Inicializa el autenticador con configuración SMTP"""
        self.smtp_config = self._load_smtp_config()
        
        # Almacenamiento de códigos pendientes (en memoria)
        # En producción, usar Redis o base de datos
        if 'auth_codes' not in st.session_state:
            st.session_state.auth_codes = {}
        
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        
        if 'user_email' not in st.session_state:
            st.session_state.user_email = None
        
        if 'auth_timestamp' not in st.session_state:
            st.session_state.auth_timestamp = None
    
    def _load_smtp_config(self) -> dict:
        """Carga configuración SMTP desde secrets o env vars"""
        config = {
            'host': None,
            'port': 587,
            'username': None,
            'password': None,
            'from_email': None,
            'from_name': 'Facet Analyzer'
        }
        
        # Intentar cargar desde st.secrets
        try:
            if hasattr(st, 'secrets'):
                config['host'] = st.secrets.get('SMTP_HOST', config['host'])
                config['port'] = st.secrets.get('SMTP_PORT', config['port'])
                config['username'] = st.secrets.get('SMTP_USERNAME', config['username'])
                config['password'] = st.secrets.get('SMTP_PASSWORD', config['password'])
                config['from_email'] = st.secrets.get('SMTP_FROM_EMAIL', config['from_email'])
                config['from_name'] = st.secrets.get('SMTP_FROM_NAME', config['from_name'])
        except Exception:
            pass
        
        # Fallback a variables de entorno
        config['host'] = config['host'] or os.getenv('SMTP_HOST')
        config['port'] = int(os.getenv('SMTP_PORT', config['port']))
        config['username'] = config['username'] or os.getenv('SMTP_USERNAME')
        config['password'] = config['password'] or os.getenv('SMTP_PASSWORD')
        config['from_email'] = config['from_email'] or os.getenv('SMTP_FROM_EMAIL')
        
        return config
    
    def is_smtp_configured(self) -> bool:
        """Verifica si SMTP está configurado"""
        required = ['host', 'username', 'password', 'from_email']
        return all(self.smtp_config.get(k) for k in required)
    
    def validate_email_domain(self, email: str) -> Tuple[bool, str]:
        """
        Valida que el email sea del dominio permitido
        
        Returns:
            (is_valid, message)
        """
        email = email.strip().lower()
        
        if not email:
            return False, "Email requerido"
        
        if '@' not in email:
            return False, "Email inválido"
        
        domain = email.split('@')[1]
        
        if domain != ALLOWED_DOMAIN:
            return False, f"Solo se permiten emails @{ALLOWED_DOMAIN}"
        
        return True, "Email válido"
    
    def generate_code(self) -> str:
        """Genera código OTP de 6 dígitos"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(CODE_LENGTH)])
    
    def _hash_code(self, code: str) -> str:
        """Hash del código para almacenamiento seguro"""
        return hashlib.sha256(code.encode()).hexdigest()
    
    def send_verification_code(self, email: str) -> Tuple[bool, str]:
        """
        Envía código de verificación al email
        
        Returns:
            (success, message)
        """
        # Validar email
        is_valid, msg = self.validate_email_domain(email)
        if not is_valid:
            return False, msg
        
        # Verificar SMTP
        if not self.is_smtp_configured():
            return False, "Servidor de email no configurado. Contacta al administrador."
        
        # Generar código
        code = self.generate_code()
        expiry = datetime.now() + timedelta(minutes=CODE_EXPIRY_MINUTES)
        
        # Almacenar código (hasheado)
        st.session_state.auth_codes[email] = {
            'code_hash': self._hash_code(code),
            'expiry': expiry.isoformat(),
            'attempts': 0
        }
        
        # Enviar email
        try:
            self._send_email(email, code)
            return True, f"Código enviado a {email}. Válido por {CODE_EXPIRY_MINUTES} minutos."
        except Exception as e:
            return False, f"Error enviando email: {str(e)}"
    
    def _send_email(self, to_email: str, code: str):
        """Envía el email con el código"""
        cfg = self.smtp_config
        
        # Crear mensaje
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🔐 Tu código de acceso: {code}'
        msg['From'] = f"{cfg['from_name']} <{cfg['from_email']}>"
        msg['To'] = to_email
        
        # Contenido texto plano
        text_content = f"""
Hola,

Tu código de acceso a Facet Architecture Analyzer es:

    {code}

Este código expira en {CODE_EXPIRY_MINUTES} minutos.

Si no solicitaste este código, ignora este email.

---
Facet Architecture Analyzer
PCComponentes SEO Team
        """
        
        # Contenido HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .code-box {{ 
            background: #f5f5f5; 
            border: 2px solid #007bff; 
            border-radius: 8px; 
            padding: 20px; 
            text-align: center; 
            margin: 20px 0;
        }}
        .code {{ 
            font-size: 32px; 
            font-weight: bold; 
            letter-spacing: 8px; 
            color: #007bff;
        }}
        .footer {{ 
            margin-top: 30px; 
            padding-top: 20px; 
            border-top: 1px solid #eee; 
            font-size: 12px; 
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🔐 Código de Acceso</h2>
        
        <p>Hola,</p>
        
        <p>Tu código de acceso a <strong>Facet Architecture Analyzer</strong> es:</p>
        
        <div class="code-box">
            <span class="code">{code}</span>
        </div>
        
        <p>⏰ Este código expira en <strong>{CODE_EXPIRY_MINUTES} minutos</strong>.</p>
        
        <p>Si no solicitaste este código, ignora este email.</p>
        
        <div class="footer">
            <p>
                <strong>Facet Architecture Analyzer</strong><br>
                PCComponentes SEO Team
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        # Enviar
        with smtplib.SMTP(cfg['host'], cfg['port']) as server:
            server.starttls()
            server.login(cfg['username'], cfg['password'])
            server.send_message(msg)
    
    def verify_code(self, email: str, code: str) -> Tuple[bool, str]:
        """
        Verifica el código ingresado
        
        Returns:
            (success, message)
        """
        email = email.strip().lower()
        code = code.strip()
        
        # Verificar que existe código pendiente
        if email not in st.session_state.auth_codes:
            return False, "No hay código pendiente para este email. Solicita uno nuevo."
        
        stored = st.session_state.auth_codes[email]
        
        # Verificar expiración
        expiry = datetime.fromisoformat(stored['expiry'])
        if datetime.now() > expiry:
            del st.session_state.auth_codes[email]
            return False, "Código expirado. Solicita uno nuevo."
        
        # Verificar intentos (máximo 5)
        if stored['attempts'] >= 5:
            del st.session_state.auth_codes[email]
            return False, "Demasiados intentos fallidos. Solicita un código nuevo."
        
        # Verificar código
        if self._hash_code(code) != stored['code_hash']:
            st.session_state.auth_codes[email]['attempts'] += 1
            remaining = 5 - st.session_state.auth_codes[email]['attempts']
            return False, f"Código incorrecto. {remaining} intentos restantes."
        
        # ¡Éxito!
        del st.session_state.auth_codes[email]
        
        # Marcar como autenticado
        st.session_state.authenticated = True
        st.session_state.user_email = email
        st.session_state.auth_timestamp = datetime.now().isoformat()
        
        return True, "¡Autenticación exitosa!"
    
    def is_authenticated(self) -> bool:
        """Verifica si el usuario está autenticado"""
        return st.session_state.get('authenticated', False)
    
    def get_current_user(self) -> Optional[str]:
        """Retorna el email del usuario autenticado"""
        if self.is_authenticated():
            return st.session_state.get('user_email')
        return None
    
    def logout(self):
        """Cierra la sesión"""
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.session_state.auth_timestamp = None


def render_login_page() -> bool:
    """
    Renderiza la página de login
    
    Returns:
        True si el usuario está autenticado
    """
    auth = EmailAuthenticator()
    
    # Si ya está autenticado, mostrar opción de logout
    if auth.is_authenticated():
        return True
    
    # Página de login
    st.set_page_config(
        page_title="Login - Facet Analyzer",
        page_icon="🔐",
        layout="centered"
    )
    
    # Estilos
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-header h1 {
            color: #1f77b4;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='login-header'>", unsafe_allow_html=True)
        st.title("🔐 Acceso")
        st.markdown("**Facet Architecture Analyzer**")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Inicializar estado del formulario
    if 'login_step' not in st.session_state:
        st.session_state.login_step = 'email'  # 'email' o 'code'
    if 'login_email' not in st.session_state:
        st.session_state.login_email = ''
    
    # Verificar si SMTP está configurado
    if not auth.is_smtp_configured():
        st.error("""
        ⚠️ **Sistema de email no configurado**
        
        El administrador debe configurar los siguientes secretos:
        - `SMTP_HOST`
        - `SMTP_USERNAME`
        - `SMTP_PASSWORD`
        - `SMTP_FROM_EMAIL`
        """)
        st.stop()
    
    # Paso 1: Introducir email
    if st.session_state.login_step == 'email':
        with st.form("email_form"):
            st.markdown(f"Introduce tu email corporativo **@{ALLOWED_DOMAIN}**")
            
            email = st.text_input(
                "Email",
                placeholder=f"tu.nombre@{ALLOWED_DOMAIN}",
                key="email_input"
            )
            
            submitted = st.form_submit_button("📧 Enviar código", use_container_width=True)
            
            if submitted:
                if email:
                    success, message = auth.send_verification_code(email)
                    
                    if success:
                        st.session_state.login_email = email.strip().lower()
                        st.session_state.login_step = 'code'
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Introduce tu email")
    
    # Paso 2: Introducir código
    elif st.session_state.login_step == 'code':
        st.info(f"📧 Código enviado a **{st.session_state.login_email}**")
        
        with st.form("code_form"):
            st.markdown("Introduce el código de 6 dígitos que recibiste:")
            
            code = st.text_input(
                "Código",
                max_chars=6,
                placeholder="000000",
                key="code_input"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                submitted = st.form_submit_button("✅ Verificar", use_container_width=True)
            
            with col2:
                back = st.form_submit_button("← Volver", use_container_width=True)
            
            if submitted:
                if code and len(code) == 6:
                    success, message = auth.verify_code(
                        st.session_state.login_email, 
                        code
                    )
                    
                    if success:
                        st.success(message)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Introduce el código de 6 dígitos")
            
            if back:
                st.session_state.login_step = 'email'
                st.rerun()
        
        # Opción de reenviar
        st.markdown("---")
        if st.button("🔄 Reenviar código"):
            success, message = auth.send_verification_code(st.session_state.login_email)
            if success:
                st.success("Código reenviado")
            else:
                st.error(message)
    
    # Footer
    st.markdown("---")
    st.caption(f"Solo usuarios con email @{ALLOWED_DOMAIN} pueden acceder")
    
    return False


def require_auth(func):
    """
    Decorador para requerir autenticación
    
    Uso:
        @require_auth
        def main():
            st.write("Contenido protegido")
    """
    def wrapper(*args, **kwargs):
        auth = EmailAuthenticator()
        
        if not auth.is_authenticated():
            render_login_page()
            st.stop()
        
        return func(*args, **kwargs)
    
    return wrapper


def render_user_menu():
    """Renderiza menú de usuario en el sidebar"""
    auth = EmailAuthenticator()
    
    if auth.is_authenticated():
        user = auth.get_current_user()
        
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"👤 **{user}**")
            
            if st.button("🚪 Cerrar sesión", use_container_width=True):
                auth.logout()
                st.rerun()
