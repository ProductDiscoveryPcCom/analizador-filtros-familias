# Facet Architecture Analyzer v2.2

Herramienta de análisis SEO para arquitectura de facetas en e-commerce.
Genérico para cualquier categoría de productos.

## 🚀 Inicio Rápido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
streamlit run app.py
```

## 📁 Tipos de Archivos Soportados (7)

| # | Tipo | Descripción | Obligatorio |
|---|------|-------------|-------------|
| 1 | **Crawl SF + GSC** | Crawl con datos de Google Search Console | Base |
| 2 | **Keyword Planner** | Volúmenes de búsqueda Google Ads | Opcional |
| 3 | **SEMrush** | Keywords + KD + Intent | Opcional |
| 4 | **Adobe URLs SEO** | Tráfico SEO por URL + Revenue | Recomendado |
| 5 | **Crawl SF + Extracción** | Dataset maestro con seoFilterWrapper | **Crítico** |
| 6 | **Adobe Search Filters** | Demanda de facetas usadas en site | **Crítico** |
| 7 | **Crawl URLs Adobe** | URLs históricas + detección 404s | **Crítico** |

## 🔧 Extracción Custom en Screaming Frog

Para generar el archivo #5 (Crawl Maestro):

```
Configuration > Custom > Extraction

Extractores:
1. seoFilterWrapper_exists (CSSPath): div.seoFilterWrapper
2. seoFilterWrapper_hrefs (XPath): //div[contains(@class,'seoFilterWrapper')]//a/@href
3. top_content_seo (CSSPath): div.topContentSeo
4. bottom_content_seo (CSSPath): div.bottomContentSeo
```

## 📊 Funcionalidades

### 1. Análisis de Autoridad
- **Fuga Tipo 1**: Páginas con tráfico pero sin seoFilterWrapper
- **Fuga Tipo 2**: Dilución (muchos enlaces, poco tráfico)
- **Fuga Tipo 3**: Dead ends (URLs 404)

### 2. Análisis de Facetas
- Detección automática de facetas por patrones
- Scoring multi-criterio configurable
- Identificación de oportunidades

### 3. Scoring Configurable
- Demanda SEMrush + Keyword Planner (30%)
- Tráfico GSC + Adobe (25%)
- Ratio demanda orgánica (20%)
- Intent comercial (15%)
- Cobertura long-tail (10%)

## 🏗️ Estructura del Proyecto

```
facet-analyzer-v2/
├── app.py                 # Aplicación Streamlit principal
├── requirements.txt       # Dependencias
├── data/
│   ├── loaders.py        # Sistema de carga con auto-detección
│   ├── family_library.py # Gestión de familias de productos
│   ├── data_config.py    # Configuración y detector de facetas
│   └── drive_storage.py  # Persistencia en Google Drive
├── analysis/
│   ├── authority_analyzer.py  # Análisis de fuga de autoridad
│   ├── facet_analyzer.py      # Análisis de facetas
│   ├── scoring.py             # Sistema de puntuación
│   └── http_verifier.py       # Verificación HTTP de URLs
└── config/
    └── settings.py       # Configuración central
```

## 🔍 Auto-detección de Archivos

El sistema detecta automáticamente el tipo de archivo basándose en:
1. Nombre del archivo
2. Columnas presentes
3. Contenido de la primera fila

Ejemplos:
- Columna `seoFilterWrapper_hrefs` → Crawl Master
- Columna `Keyword` + `Volume` → SEMrush
- Columna con URLs + `Visits` → Adobe URLs
- Columna con formato `faceta:valor` → Adobe Filters

## 📈 Hallazgos Clave del Análisis (Ejemplo: Smartphones)

- **852 URLs indexables** con seoFilterWrapper vacío → Oportunidades de linking perdidas
- **17,482 URLs (66%)** con tráfico histórico devuelven 404 → Necesitan redirección
- **77% de páginas** tienen wrapper vacío → L2/L3 no distribuyen autoridad

## ☁️ Despliegue en Streamlit Cloud

1. Sube el proyecto a GitHub
2. Conecta con Streamlit Cloud
3. Configura secrets para Google Drive (opcional):

```toml
GOOGLE_DRIVE_FOLDER_ID = "tu-folder-id"

[google_credentials]
type = "service_account"
project_id = "..."
private_key = "..."
client_email = "..."
```

## 📝 Licencia

Uso interno PCComponentes - Equipo SEO
