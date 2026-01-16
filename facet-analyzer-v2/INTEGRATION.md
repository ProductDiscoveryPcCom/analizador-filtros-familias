# 🔧 Guía de Integración - Nuevos Módulos v2.1

Esta guía explica cómo integrar los nuevos módulos en la aplicación.

## 📦 Nuevos Módulos Disponibles

### 1. `data/data_config.py` - Configuración de Períodos y Facetas

```python
from data.data_config import (
    DataSourceConfig,      # Metadatos de fuente de datos con período
    FacetMapping,          # Mapeo de faceta con verificación humana
    DatasetContext,        # Contexto completo para el chat
    FacetDetector,         # Auto-detección de facetas
    render_data_period_config,   # UI para configurar períodos
    render_facet_mapping_ui,     # UI para mapear facetas
)

# Ejemplo: Detectar facetas automáticamente
detector = FacetDetector(crawl_df)
facetas = detector.detect_all()
desconocidos = detector.detect_unknown_patterns()
```

### 2. `data/drive_storage.py` - Persistencia en Google Drive

```python
from data.drive_storage import (
    GoogleDriveStorage,    # Cliente de Drive
    HybridLibraryStorage,  # Local + Drive
    render_drive_config_ui # UI para configurar Drive
)

# Ejemplo: Sincronizar biblioteca
storage = HybridLibraryStorage()
if storage.is_drive_enabled():
    storage.sync_from_drive()
```

### 3. `chat/contextual_chat.py` - Chat estilo NotebookLM

```python
from chat.contextual_chat import (
    ContextualChat,         # Chat con contexto de datos
    render_contextual_chat_ui  # UI completa del chat
)

# Ejemplo: Crear chat con contexto
context = DatasetContext(...)  # Del análisis
chat = ContextualChat(context)
response = chat.chat("¿Cuáles son las principales fugas?")
```

### 4. `analysis/scoring.py` - Scoring Configurable

```python
from analysis.scoring import (
    ScoringWeights,        # Ponderaciones configurables
    FacetScorer,           # Calculador de scores
    ScoreBreakdown,        # Desglose detallado
    render_scoring_config_ui,    # UI para configurar pesos
    render_score_breakdown_ui,   # UI para mostrar desglose
)

# Ejemplo: Calcular score con desglose
scorer = FacetScorer(weights=custom_weights)
breakdown = scorer.calculate_score(
    facet_name="RAM",
    urls_200=2260,
    urls_404=6034,
    demand_adobe=40328,
    demand_semrush=5000,
    traffic_seo=15000,
    in_wrapper=False
)
print(f"Score: {breakdown.total_score}")
print(f"Acción: {breakdown.action_type}")
```

---

## 🔌 Integración en app.py

### Paso 1: Añadir imports

```python
# Nuevos imports
from data.data_config import (
    DataSourceConfig, FacetMapping, DatasetContext, 
    FacetDetector, render_data_period_config, render_facet_mapping_ui
)
from data.drive_storage import HybridLibraryStorage, render_drive_config_ui
from chat.contextual_chat import ContextualChat, render_contextual_chat_ui
from analysis.scoring import FacetScorer, render_scoring_config_ui, render_score_breakdown_ui
```

### Paso 2: Añadir Tab de Configuración

```python
# En los tabs principales
tab_config, tab1, tab2, ... = st.tabs([
    "⚙️ Configurar Datos",
    "📊 Dashboard",
    ...
])

with tab_config:
    st.subheader("Configuración de Datos")
    
    # Paso 1: Períodos
    if uploaded_files:
        source_configs = render_data_period_config(uploaded_files)
    
    # Paso 2: Detectar facetas
    if st.button("🔍 Detectar Facetas"):
        detector = FacetDetector(crawl_df)
        detected = detector.detect_all()
        unknown = detector.detect_unknown_patterns()
        st.session_state.detected_facets = detected
    
    # Paso 3: Mapear facetas (interacción humana)
    if 'detected_facets' in st.session_state:
        verified_facets = render_facet_mapping_ui(
            st.session_state.detected_facets,
            unknown
        )
        st.session_state.facet_mappings = verified_facets
```

### Paso 3: Crear Contexto para Chat

```python
# Después de ejecutar análisis
if st.session_state.get('authority_result') and st.session_state.get('facet_result'):
    context = DatasetContext(
        family_name=st.session_state.get('current_family', {}).get('name', 'Dataset'),
        base_url=base_url,
        sources=source_configs,
        facet_mappings=st.session_state.facet_mappings,
        total_urls=len(crawl),
        urls_200=len(crawl[crawl['Código de respuesta'] == 200]),
        urls_404=len(crawl[crawl['Código de respuesta'] == 404]),
        total_traffic=adobe_urls['visits_seo'].sum(),
        authority_analysis_done=True,
        facet_analysis_done=True,
        authority_summary=st.session_state.authority_result.summary,
        facet_summary=st.session_state.facet_result.summary,
        top_leaks=[...],  # Convertir a dict
        top_opportunities=[...]  # Convertir a dict
    )
    st.session_state.dataset_context = context
```

### Paso 4: Usar Chat Contextual

```python
# En el tab de Chat
with tab_chat:
    context = st.session_state.get('dataset_context')
    render_contextual_chat_ui(context)
```

### Paso 5: Añadir Drive al Sidebar

```python
# En sidebar, sección de biblioteca
with st.expander("☁️ Google Drive"):
    render_drive_config_ui()
```

---

## 🔑 Configuración de Secretos

### Streamlit Cloud

En tu app de Streamlit Cloud: Settings → Secrets

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
OPENAI_API_KEY = "sk-..."
GOOGLE_DRIVE_FOLDER_ID = "1ABC..."

[google_credentials]
type = "service_account"
project_id = "..."
# ... resto de credenciales
```

### Local

Archivo `.streamlit/secrets.toml`:
```toml
# Mismo formato que arriba
```

O variables de entorno:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

---

## 📝 Checklist de Integración

- [ ] Añadir imports de nuevos módulos
- [ ] Crear tab de configuración de datos
- [ ] Implementar detección de facetas
- [ ] Añadir UI de mapeo de facetas
- [ ] Crear DatasetContext después de análisis
- [ ] Reemplazar chat antiguo con ContextualChat
- [ ] Añadir configuración de Drive en sidebar
- [ ] Configurar secretos en Streamlit Cloud
- [ ] Probar flujo completo

---

## 🧪 Testing

```bash
# Verificar módulos
python -c "from data.data_config import *; print('OK')"
python -c "from data.drive_storage import *; print('OK')"
python -c "from chat.contextual_chat import *; print('OK')"
python -c "from analysis.scoring import *; print('OK')"
```
