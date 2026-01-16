# 🔍 Facet Architecture Analyzer v2

Herramienta de análisis SEO para optimizar la arquitectura de facetas de navegación en e-commerce, con **validación dual de AI** para evitar alucinaciones y errores.

## 📋 Características

### Análisis de Fuga de Autoridad
- **Tipo 1 - Sin Distribución**: Páginas con tráfico SEO pero sin `seoFilterWrapper`
- **Tipo 2 - Dilución**: Páginas con muchos enlaces pero poco tráfico propio
- **Tipo 3 - Dead Ends**: URLs 404 que antes tenían tráfico

### Análisis de Facetas
- Estado actual de cada faceta (activa, parcial, eliminada, sin URLs)
- Score de oportunidad (0-100) basado en demanda y URLs disponibles
- Recomendaciones con nivel de confianza

### Validación Dual de AI
- **3 modos**: Economic (~$2-3), Hybrid (~$5-8), Premium (~$15-25)
- Todas las respuestas pasan por Claude + GPT antes de mostrarse
- Sistema de consenso para evitar alucinaciones

## 🚀 Instalación

```bash
# Clonar repositorio
cd facet-analyzer-v2

# Instalar dependencias
pip install -r requirements.txt

# Configurar APIs (opcional pero recomendado)
cp .env.example .env
# Editar .env con tus API keys

# Ejecutar aplicación
streamlit run app.py
```

## 🔑 Configuración de APIs

La herramienta funciona de dos formas:
1. **Sin APIs**: Análisis local con respuestas básicas
2. **Con APIs**: Validación dual completa (Claude + GPT)

### Opción A: Variables de Entorno

```bash
# Crear archivo .env
cp .env.example .env

# Editar con tus keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

### Opción B: Interfaz de Usuario

1. Abre la aplicación
2. En el sidebar, expande "🔑 Configurar APIs"
3. Introduce las keys (se guardan solo en la sesión)

### Obtener API Keys

| Proveedor | URL | Formato |
|-----------|-----|---------|
| Anthropic (Claude) | [console.anthropic.com](https://console.anthropic.com/settings/keys) | `sk-ant-api03-...` |
| OpenAI (GPT) | [platform.openai.com](https://platform.openai.com/api-keys) | `sk-...` |

## 🔍 Verificación HTTP

La herramienta incluye verificación HTTP en tiempo real para:
- Confirmar que las URLs recomendadas siguen activas (200)
- Detectar redirecciones (301/302)
- Identificar páginas eliminadas (404)
- Verificar indexabilidad (X-Robots-Tag)

### Uso

1. Ejecuta el análisis de autoridad
2. Click en "🔍 Verificar URLs Top 20"
3. Revisa el resumen de verificación
4. Las URLs con problemas se marcan automáticamente

## 📚 Biblioteca de Familias

La biblioteca permite guardar configuraciones de diferentes categorías de productos para reutilizarlas sin subir archivos cada vez.

### Crear una familia

1. En el sidebar, selecciona "📤 Subir archivos" → luego "➕ Nueva familia"
2. O desde el código:

```python
from data.family_library import FamilyLibrary

library = FamilyLibrary('./library')

# Crear familia
metadata = library.create_family(
    name="Smartphones",
    description="Móviles y accesorios",
    base_url="https://www.pccomponentes.com/smartphone-moviles",
    crawl_file="path/to/crawl.csv",
    adobe_urls_file="path/to/adobe_urls.csv",      # Opcional
    adobe_filters_file="path/to/adobe_filters.csv", # Opcional
    gsc_file="path/to/gsc.csv",                     # Opcional
    semrush_file="path/to/semrush.csv"              # Opcional
)

print(f"Familia creada: {metadata.id}")
```

### Cargar una familia

```python
# Desde la UI: Sidebar → 📚 Biblioteca → Seleccionar → Cargar

# Desde código:
data = library.load_family_data("smartphones-abc123")
# data = {'crawl_adobe': DataFrame, 'adobe_urls': DataFrame, ...}
```

### Características

- **Preprocesamiento automático**: El crawl se procesa (calcula `wrapper_link_count`) y guarda en Parquet para cargas más rápidas
- **Exportar/Importar**: Puedes exportar una familia a ZIP y compartirla o hacer backup
- **Actualización incremental**: Actualiza solo los archivos que cambien
- **Metadatos**: Guarda estadísticas y fecha de actualización

### Estructura de almacenamiento

```
library/
├── index.json                    # Índice de todas las familias
├── smartphones-abc123/
│   ├── metadata.json             # Metadatos de la familia
│   ├── crawl.csv                 # Crawl original
│   ├── crawl_processed.parquet   # Crawl preprocesado (rápido)
│   ├── adobe_urls.csv
│   └── adobe_filters.csv
├── electrodomesticos-def456/
│   └── ...
```

## 📁 Estructura del Proyecto

```
facet-analyzer-v2/
├── app.py                      # Aplicación principal Streamlit
├── config/
│   └── settings.py             # Configuración, patrones, modelos AI
├── data/
│   ├── loaders.py              # Cargadores de CSV con validación
│   └── family_library.py       # Gestión de biblioteca de familias
├── analysis/
│   ├── authority_analyzer.py   # Análisis de fuga de autoridad
│   ├── facet_analyzer.py       # Análisis de facetas
│   └── http_verifier.py        # Verificación HTTP en tiempo real
├── ai/
│   ├── dual_validator.py       # Sistema de validación dual
│   └── api_clients.py          # Clientes para Claude y GPT
├── export/
│   └── report_generator.py     # Generación de reportes
├── library/                    # Biblioteca de familias (se crea automáticamente)
├── .env.example                # Template de configuración
└── requirements.txt
```

## 📊 Datos Requeridos

| Archivo | Descripción |
|---------|-------------|
| `internos_html_smartphone_urls_adobe*.csv` | Crawl de URLs con datos de `seoFilterWrapper` |
| `Sesiones_por_filtro_-_SEO__5__*.csv` | Tráfico SEO por URL (Adobe Analytics) |
| `Sesiones_por_filtro_-_SEO__3__*.csv` | Demanda por filtros (Adobe Analytics) |
| `smartphone_crawl_internal_html_all.csv` | Crawl original de Screaming Frog |
| `smartphone_broad-match_es_*.csv` | Keywords de SEMrush |

## 🔧 Configuración de Modelos AI

```python
# config/settings.py

AI_CONFIGS = {
    'economic': {
        'primary_analysis': 'claude-sonnet-4',
        'validation': 'gpt-4o',
        'cost_estimate': '$2-3/sesión',
    },
    'hybrid': {  # RECOMENDADO
        'primary_analysis': 'claude-sonnet-4',
        'validation': 'gpt-4-turbo',
        'recommendations': 'claude-opus-4',
        'cost_estimate': '$5-8/sesión',
    },
    'premium': {
        'primary_analysis': 'claude-opus-4',
        'validation': 'gpt-4-turbo',
        'cost_estimate': '$15-25/sesión',
    },
}
```

## 📈 Métricas Verificadas

Todas las métricas han sido auditadas contra los datos reales:

| Métrica | Valor Verificado |
|---------|------------------|
| Total URLs crawleadas | 26,330 |
| URLs activas (200) | 8,170 |
| URLs eliminadas (404) | 17,482 |
| Páginas con seoFilterWrapper | 5,642 (69%) |
| Tráfico sin distribución | 67,312 visitas |
| Páginas con dilución | 37 |

## 🔒 Sistema de Validación Dual

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO DE VALIDACIÓN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Pregunta / Análisis                                           │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────┐                                           │
│   │ Ejecutar Query  │ (Pandas sobre CSVs reales)                │
│   └─────────────────┘                                           │
│          │                                                      │
│    ┌─────┴─────┐                                                │
│    ▼           ▼                                                │
│ ┌──────┐   ┌──────┐                                             │
│ │Claude│   │ GPT  │ (Validación paralela)                       │
│ └──────┘   └──────┘                                             │
│    │           │                                                │
│    └─────┬─────┘                                                │
│          ▼                                                      │
│   ┌─────────────────┐                                           │
│   │ Consenso Check  │                                           │
│   └─────────────────┘                                           │
│          │                                                      │
│    ┌─────┼─────┐                                                │
│    ▼     ▼     ▼                                                │
│   ✅    ⚠️    ❌                                                │
│  FULL PARTIAL CONFLICT                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📥 Exportación

La herramienta genera:
- `authority_leaks.csv` - Lista de fugas de autoridad
- `facet_analysis.csv` - Análisis de todas las facetas
- `implementation_report.md` - Reporte de implementación

## 🎯 Casos de Uso

1. **Auditoría de seoFilterWrapper**: Identificar páginas que deberían tener enlaces pero no los tienen
2. **Optimización de enlazado**: Reducir dilución en páginas con demasiados enlaces
3. **Recuperación de facetas**: Evaluar si vale la pena recrear URLs eliminadas
4. **Priorización de desarrollo**: Lista ordenada de cambios por impacto

## ⚠️ Limitaciones

- La validación dual simula llamadas a APIs (implementar conexión real)
- El análisis de tráfico es histórico (2025)
- No verifica HTTP en tiempo real (añadir verificación antes de implementar)

## 📄 Licencia

Uso interno - PCComponentes SEO Team

---

**Versión**: 2.0  
**Última actualización**: Enero 2026  
**Autor**: Claude + PCComponentes SEO Team
