# 🔍 Facet Architecture Analyzer v2.3

Herramienta de análisis SEO para optimizar la arquitectura de enlaces internos en páginas de filtros/facetas de e-commerce.

## 🎯 ¿Qué hace?

1. **Análisis de Fuga de Autoridad**: Detecta páginas que no distribuyen PageRank a través del seoFilterWrapper
2. **Análisis de Facetas**: Evalúa la demanda vs el estado actual de cada faceta
3. **Scoring de Facetas**: Prioriza facetas por potencial SEO usando múltiples métricas
4. **Estrategia de Enlazado**: Genera recomendaciones de enlazado interno

## 📁 Archivos Soportados

| Tipo | Descripción | Obligatorio |
|------|-------------|-------------|
| **Crawl Master** | Screaming Frog + extracción de seoFilterWrapper | ✅ Sí |
| **Crawl GSC** | Screaming Frog + datos de Search Console | ❌ No |
| **Adobe URLs** | Tráfico SEO por URL | 🔶 Recomendado |
| **Adobe Filters** | Demanda por filtros | 🔶 Recomendado |
| **SEMrush** | Keywords con volumen, KD, intent | ❌ No |
| **Keyword Planner** | Volúmenes de Google Ads | ❌ No |
| **Crawl Histórico** | URLs con tráfico histórico | ❌ No |

## 🚀 Instalación Local

```bash
# Clonar repositorio
git clone <repo-url>
cd facet-analyzer-v2

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
streamlit run app.py
```

## ☁️ Despliegue en Streamlit Cloud

1. Fork este repositorio
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repo y selecciona `app.py`
4. (Opcional) Configura secrets para Google Drive

## 📊 Estructura del Proyecto

```
facet-analyzer-v2/
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias
├── README.md
├── .streamlit/
│   ├── config.toml       # Configuración de Streamlit
│   └── secrets.toml.example
├── config/
│   ├── __init__.py
│   └── settings.py       # Configuración central
├── data/
│   ├── __init__.py
│   ├── loaders.py        # Carga y normalización de datos
│   ├── data_config.py    # Configuración de facetas
│   ├── family_library.py # Gestión de familias
│   └── drive_storage.py  # Integración con Google Drive
└── analysis/
    ├── __init__.py
    ├── authority_analyzer.py  # Análisis de fuga de autoridad
    ├── facet_analyzer.py      # Análisis de facetas
    └── scoring.py             # Sistema de puntuación
```

## 🔧 Configuración de Screaming Frog

Para obtener el crawl maestro con extracción de seoFilterWrapper:

### Custom Extraction
1. Configuration → Custom → Extraction
2. Añadir extracción CSS:
   - Name: `seoFilterWrapper_exists`
   - Selector: `.seoFilterWrapper`
   - Extract: Inner HTML (o Text)
3. Añadir extracción para enlaces:
   - Name: `seoFilterWrapper_hrefs_1` (hasta _20)
   - Selector: `.seoFilterWrapper a:nth-child(1)` (incrementar)
   - Extract: Attribute `href`

### Integración GSC
1. Configuration → API Access → Google Search Console
2. Conectar cuenta y seleccionar propiedad
3. Habilitar "Connect to GSC"

## 📈 Métricas Clave

### Análisis de Autoridad
- **Fuga Tipo 1**: Páginas con tráfico pero sin seoFilterWrapper
- **Fuga Tipo 2**: Páginas con muchos enlaces y poco tráfico (dilución)
- **Fuga Tipo 3**: URLs 404 (dead ends)

### Scoring de Facetas
- **Demanda (35%)**: Volumen de búsqueda y uso de filtros
- **Rendimiento (25%)**: Tráfico SEO actual
- **Cobertura (20%)**: URLs activas y presencia en wrapper
- **Oportunidad (20%)**: Potencial sin explotar

### Tiers
- **S**: Score ≥90 - Facetas estrella
- **A**: Score ≥75 - Alto rendimiento
- **B**: Score ≥50 - Rendimiento medio
- **C**: Score ≥25 - Bajo rendimiento
- **D**: Score <25 - Sin prioridad

## 🔒 Seguridad

- Los datos se procesan localmente
- No se envía información a servidores externos
- Google Drive es opcional y usa OAuth2

## 📝 Changelog

### v2.3 (Actual)
- ✅ Claves de datos unificadas
- ✅ Mejor detección de homepage
- ✅ Validación de patrones regex
- ✅ Feedback de errores mejorado
- ✅ Soporte genérico para cualquier categoría

### v2.2
- Sistema de scoring configurable
- Biblioteca de familias
- Integración con Google Drive

### v2.1
- Detección automática de tipos de archivo
- Múltiples encodings soportados

### v2.0
- Arquitectura modular
- Soporte para 7 tipos de archivos

## 📄 Licencia

MIT License

## 👤 Autor

Product Discovery & Content - PCComponentes
