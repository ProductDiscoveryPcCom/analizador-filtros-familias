# ⚠️ Limitaciones Conocidas - Facet Architecture Analyzer v2.1

Este documento lista las limitaciones actuales de la herramienta.

## 🔐 Autenticación

La herramienta requiere login con email **@pccomponentes.com**:

1. El usuario introduce su email corporativo
2. Recibe un código de 6 dígitos por email
3. Introduce el código para acceder

### Configuración SMTP Requerida

En Streamlit Secrets:
```toml
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "tu-email@gmail.com"
SMTP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"  # App Password
SMTP_FROM_EMAIL = "tu-email@gmail.com"
```

**Nota Gmail**: Usa una "App Password", no tu contraseña normal.
Crearla en: https://myaccount.google.com/apppasswords

---

## ✅ Limitaciones Resueltas en v2.1

### 1. Validación Dual - RESUELTO
**Solución**: Configura las API keys en:
- Streamlit Cloud: Settings → Secrets
- Local: `.streamlit/secrets.toml` o variables de entorno

La app ahora lee automáticamente de `st.secrets`, env vars, o configuración manual en UI.

### 2. Chat Contextual - MEJORADO
**Antes**: Query generator muy básico
**Ahora**: Chat contextual estilo NotebookLM que:
- Usa el contexto completo de los análisis ejecutados
- Responde basándose en los datos cargados
- Muestra fuentes y nivel de confianza

### 3. Biblioteca Persistente - RESUELTO
**Solución**: Integración con Google Drive
- Configura credenciales de servicio en secretos
- Las familias se sincronizan automáticamente
- Exportar/importar ZIP como backup

### 4. Scores de Oportunidad - MEJORADO
**Solución**: Sistema de scoring configurable
- Ponderaciones ajustables
- Desglose detallado de cada componente
- Acciones recomendadas claras (link/recreate/maintain/ignore)

### 5. Períodos de Datos - RESUELTO
**Solución**: Interfaz para configurar períodos
- Cada archivo indica su rango de fechas (dd/mm/aaaa)
- El contexto del chat incluye esta información

### 6. Patrones de Facetas - RESUELTO
**Solución**: Interfaz interactiva de mapeo
- Auto-detección de facetas conocidas
- Revisión y ajuste manual por el usuario
- Patrones desconocidos mostrados para clasificar
- Verificación humana antes de procesar

## 🟡 Limitaciones Menores Actuales

### Rate Limiting en Verificación HTTP
**Estado**: Mejorado (5 workers, 0.3s delay)
**Nota**: Si tienes el crawl de Screaming Frog con status codes, NO necesitas verificación HTTP en tiempo real. Los datos del crawl ya incluyen el estado.

### Google Drive Requiere Configuración
La integración con Drive requiere:
1. Crear proyecto en Google Cloud
2. Habilitar Drive API
3. Crear cuenta de servicio
4. Compartir carpeta con la cuenta de servicio

Ver `.streamlit/secrets.toml.example` para detalles.

## ✅ Qué Funciona Bien

1. **Análisis de Autoridad**: Detecta fugas correctamente
2. **Análisis de Facetas**: Scores configurables y precisos
3. **Chat Contextual**: Respuestas basadas en datos reales
4. **Biblioteca**: Persistencia local + opción Drive
5. **Exportación**: CSVs y reportes
6. **Configuración de períodos**: Contexto temporal claro
7. **Mapeo de facetas**: Interacción humana para validar

---

*Última actualización: Enero 2026 - v2.1*
