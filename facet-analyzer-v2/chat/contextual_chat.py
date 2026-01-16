"""
Chat Contextual con Validación Dual
Funciona como NotebookLM: responde basándose en los datos analizados
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import streamlit as st


@dataclass
class ChatMessage:
    """Mensaje del chat"""
    role: str  # 'user' | 'assistant'
    content: str
    sources: List[str] = None
    confidence: str = None  # 'HIGH' | 'MEDIUM' | 'LOW'
    validated: bool = False


class ContextualChat:
    """
    Chat que responde basándose en el contexto de datos analizados
    Similar a NotebookLM
    """
    
    SYSTEM_PROMPT = """Eres un analista SEO experto especializado en arquitectura de facetas para e-commerce.

CONTEXTO DE DATOS DISPONIBLE:
{context}

REGLAS CRÍTICAS:
1. SOLO responde basándote en los datos del contexto anterior
2. Si la información no está en el contexto, di "No tengo datos sobre eso en el análisis actual"
3. Cita números específicos cuando sea posible
4. Si hay incertidumbre, indica el nivel de confianza
5. Sugiere acciones concretas cuando sea apropiado

FORMATO DE RESPUESTA:
- Sé directo y conciso
- Usa datos específicos del contexto
- Si mencionas una URL o faceta, incluye las métricas relevantes
- Al final, indica las fuentes de datos usadas"""

    def __init__(self, dataset_context: 'DatasetContext' = None):
        """
        Inicializa el chat con contexto de datos
        
        Args:
            dataset_context: Contexto del dataset analizado
        """
        self.context = dataset_context
        self.history: List[ChatMessage] = []
        self.ai_client = None
        
        # Intentar inicializar cliente AI
        self._init_ai_client()
    
    def _init_ai_client(self):
        """Inicializa el cliente AI si está configurado"""
        try:
            from ai.api_clients import DualAIClient, check_api_configuration
            
            status = check_api_configuration()
            if status['anthropic']['configured'] and status['openai']['configured']:
                self.ai_client = DualAIClient(mode=st.session_state.get('ai_mode', 'hybrid'))
        except Exception:
            self.ai_client = None
    
    def set_context(self, context: 'DatasetContext'):
        """Actualiza el contexto de datos"""
        self.context = context
    
    def _build_system_prompt(self) -> str:
        """Construye el prompt de sistema con el contexto actual"""
        if self.context:
            context_str = self.context.to_chat_context()
        else:
            context_str = "No hay datos cargados. El usuario debe cargar y analizar datos primero."
        
        return self.SYSTEM_PROMPT.format(context=context_str)
    
    def _build_conversation_history(self) -> List[Dict]:
        """Construye historial de conversación para la API"""
        messages = []
        for msg in self.history[-10:]:  # Últimos 10 mensajes
            messages.append({
                'role': msg.role,
                'content': msg.content
            })
        return messages
    
    def _extract_sources(self, response: str) -> List[str]:
        """Extrae fuentes mencionadas en la respuesta"""
        sources = []
        
        # Buscar menciones de fuentes de datos
        keywords = ['crawl', 'Adobe', 'GSC', 'SEMrush', 'tráfico', 'URLs']
        for kw in keywords:
            if kw.lower() in response.lower():
                sources.append(kw)
        
        return list(set(sources))
    
    def chat(self, user_message: str) -> ChatMessage:
        """
        Procesa un mensaje del usuario y genera respuesta
        
        Args:
            user_message: Mensaje del usuario
        
        Returns:
            ChatMessage con la respuesta
        """
        # Añadir mensaje del usuario al historial
        self.history.append(ChatMessage(
            role='user',
            content=user_message
        ))
        
        # Si no hay contexto, pedir que cargue datos
        if not self.context:
            response = ChatMessage(
                role='assistant',
                content="""⚠️ **No hay datos cargados**

Para usar el chat, primero debes:
1. Cargar una familia de productos desde la biblioteca, o
2. Subir archivos de datos y configurarlos

Una vez cargados los datos, ejecuta los análisis (Fuga de Autoridad y/o Análisis de Facetas) para que pueda responder preguntas sobre ellos.""",
                confidence='HIGH',
                validated=True
            )
            self.history.append(response)
            return response
        
        # Si hay cliente AI, usar validación dual
        if self.ai_client:
            return self._chat_with_ai(user_message)
        else:
            return self._chat_local(user_message)
    
    def _chat_with_ai(self, user_message: str) -> ChatMessage:
        """Chat usando APIs de AI con validación dual"""
        try:
            system_prompt = self._build_system_prompt()
            history = self._build_conversation_history()
            
            # Llamar a la API con validación dual
            result = self.ai_client.analyze_with_validation(
                prompt=user_message,
                context=self.context.to_chat_context(),
                task_type='chat'
            )
            
            response_text = result.get('merged_response', 'Error al procesar respuesta')
            confidence = result.get('confidence', 'LOW')
            validated = result.get('consensus', False)
            
            # Extraer fuentes
            sources = self._extract_sources(response_text)
            
            # Añadir info de costo si está disponible
            cost = result.get('cost', 0)
            if cost > 0:
                response_text += f"\n\n---\n*Costo de esta consulta: ${cost:.4f}*"
            
            response = ChatMessage(
                role='assistant',
                content=response_text,
                sources=sources,
                confidence=confidence,
                validated=validated
            )
            
            self.history.append(response)
            return response
            
        except Exception as e:
            error_response = ChatMessage(
                role='assistant',
                content=f"❌ Error al procesar con AI: {str(e)}\n\nUsando respuesta local...",
                confidence='LOW',
                validated=False
            )
            # Fallback a local
            return self._chat_local(user_message)
    
    def _chat_local(self, user_message: str) -> ChatMessage:
        """Chat local basado en patrones (sin AI)"""
        user_lower = user_message.lower()
        
        # Patrones de preguntas comunes
        if any(kw in user_lower for kw in ['fuga', 'leak', 'autoridad']):
            response_text = self._answer_authority_question(user_message)
        elif any(kw in user_lower for kw in ['faceta', 'oportunidad', 'score']):
            response_text = self._answer_facet_question(user_message)
        elif any(kw in user_lower for kw in ['tráfico', 'visitas', 'traffic']):
            response_text = self._answer_traffic_question(user_message)
        elif any(kw in user_lower for kw in ['url', 'página', '404', '200']):
            response_text = self._answer_url_question(user_message)
        elif any(kw in user_lower for kw in ['recomendar', 'priorizar', 'hacer']):
            response_text = self._answer_recommendation_question(user_message)
        else:
            response_text = self._answer_general_question(user_message)
        
        sources = self._extract_sources(response_text)
        
        response = ChatMessage(
            role='assistant',
            content=response_text + "\n\n---\n*⚠️ Respuesta generada localmente (sin validación AI)*",
            sources=sources,
            confidence='MEDIUM',
            validated=False
        )
        
        self.history.append(response)
        return response
    
    def _answer_authority_question(self, question: str) -> str:
        """Responde preguntas sobre autoridad"""
        if not self.context.authority_analysis_done:
            return "El análisis de autoridad no se ha ejecutado todavía. Ve al tab 'Fuga de Autoridad' y ejecútalo primero."
        
        response = f"""## Análisis de Autoridad

{self.context.authority_summary}

### Top Fugas Detectadas:
"""
        for i, leak in enumerate(self.context.top_leaks[:5], 1):
            response += f"{i}. **{leak.get('url', 'N/A')}**: {leak.get('traffic', 0):,} visitas ({leak.get('type', 'N/A')})\n"
        
        response += f"\n**Fuentes:** Crawl ({self.context.total_urls:,} URLs), Adobe URLs"
        
        return response
    
    def _answer_facet_question(self, question: str) -> str:
        """Responde preguntas sobre facetas"""
        if not self.context.facet_analysis_done:
            return "El análisis de facetas no se ha ejecutado todavía. Ve al tab 'Análisis de Facetas' y ejecútalo primero."
        
        response = f"""## Análisis de Facetas

{self.context.facet_summary}

### Top Oportunidades:
"""
        for i, opp in enumerate(self.context.top_opportunities[:5], 1):
            response += f"{i}. **{opp.get('name', 'N/A')}**: Score {opp.get('score', 0)}/100 | {opp.get('urls_200', 0)} URLs activas | {opp.get('demand', 0):,} demanda\n"
        
        return response
    
    def _answer_traffic_question(self, question: str) -> str:
        """Responde preguntas sobre tráfico"""
        response = f"""## Datos de Tráfico

- **Tráfico SEO total**: {self.context.total_traffic:,} visitas
- **URLs activas**: {self.context.urls_200:,}
- **Media por URL activa**: {self.context.total_traffic / max(self.context.urls_200, 1):,.0f} visitas

### Distribución:
"""
        # Añadir info de top leaks si está disponible
        if self.context.top_leaks:
            total_leak_traffic = sum(l.get('traffic', 0) for l in self.context.top_leaks)
            response += f"- Tráfico en páginas sin distribuir: {total_leak_traffic:,} visitas\n"
        
        return response
    
    def _answer_url_question(self, question: str) -> str:
        """Responde preguntas sobre URLs"""
        response = f"""## Estado de URLs

| Métrica | Valor |
|---------|-------|
| URLs totales | {self.context.total_urls:,} |
| URLs activas (200) | {self.context.urls_200:,} |
| URLs eliminadas (404) | {self.context.urls_404:,} |
| Ratio activas | {self.context.urls_200/max(self.context.total_urls, 1)*100:.1f}% |

"""
        return response
    
    def _answer_recommendation_question(self, question: str) -> str:
        """Responde preguntas sobre recomendaciones"""
        response = """## Recomendaciones Priorizadas

### 🔴 Alta Prioridad
"""
        # Usar top leaks si están disponibles
        if self.context.top_leaks:
            for leak in self.context.top_leaks[:3]:
                if leak.get('traffic', 0) > 1000:
                    response += f"- **{leak.get('url', 'N/A')}**: Añadir seoFilterWrapper ({leak.get('traffic', 0):,} visitas sin distribuir)\n"
        
        response += "\n### 🟠 Media Prioridad\n"
        
        # Usar top opportunities si están disponibles
        if self.context.top_opportunities:
            for opp in self.context.top_opportunities[:3]:
                if opp.get('urls_200', 0) > 0:
                    response += f"- **{opp.get('name', 'N/A')}**: Añadir enlaces a seoFilterWrapper ({opp.get('urls_200', 0)} URLs disponibles)\n"
        
        return response
    
    def _answer_general_question(self, question: str) -> str:
        """Respuesta general"""
        return f"""## Resumen del Dataset: {self.context.family_name}

### Métricas Generales
- **URLs totales**: {self.context.total_urls:,}
- **URLs activas**: {self.context.urls_200:,}
- **Tráfico SEO**: {self.context.total_traffic:,} visitas

### Análisis Disponibles
- Fuga de Autoridad: {'✅ Completado' if self.context.authority_analysis_done else '❌ No ejecutado'}
- Análisis de Facetas: {'✅ Completado' if self.context.facet_analysis_done else '❌ No ejecutado'}

### Facetas Configuradas
{len(self.context.facet_mappings)} facetas detectadas

¿Sobre qué aspecto específico te gustaría saber más?
- Fugas de autoridad
- Oportunidades de facetas
- Tráfico por URL/faceta
- Recomendaciones de implementación"""
    
    def clear_history(self):
        """Limpia el historial de chat"""
        self.history = []


def render_contextual_chat_ui(context: 'DatasetContext' = None):
    """
    Renderiza la UI del chat contextual
    
    Args:
        context: Contexto del dataset
    """
    # Inicializar chat en session state
    if 'contextual_chat' not in st.session_state:
        st.session_state.contextual_chat = ContextualChat(context)
    else:
        # Actualizar contexto si cambió
        st.session_state.contextual_chat.set_context(context)
    
    chat = st.session_state.contextual_chat
    
    # Header con estado
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("💬 Chat sobre tus Datos")
    with col2:
        if st.button("🗑️ Limpiar chat"):
            chat.clear_history()
            st.rerun()
    
    # Mostrar estado de validación
    if chat.ai_client:
        st.success("🔒 Validación dual activa (Claude + GPT)")
    else:
        st.warning("⚠️ Modo local (sin validación AI). Configura las API keys para mejor calidad.")
    
    # Mostrar historial
    for msg in chat.history:
        with st.chat_message(msg.role):
            st.markdown(msg.content)
            
            if msg.role == 'assistant':
                col1, col2, col3 = st.columns(3)
                with col1:
                    if msg.confidence:
                        color = {'HIGH': '🟢', 'MEDIUM': '🟡', 'LOW': '🔴'}.get(msg.confidence, '⚪')
                        st.caption(f"{color} Confianza: {msg.confidence}")
                with col2:
                    if msg.validated:
                        st.caption("✅ Validado")
                    else:
                        st.caption("⚠️ Sin validar")
                with col3:
                    if msg.sources:
                        st.caption(f"📊 Fuentes: {', '.join(msg.sources)}")
    
    # Input del usuario
    user_input = st.chat_input("Pregunta sobre tus datos...")
    
    if user_input:
        # Mostrar mensaje del usuario
        with st.chat_message('user'):
            st.markdown(user_input)
        
        # Generar respuesta
        with st.chat_message('assistant'):
            with st.spinner("Analizando..."):
                response = chat.chat(user_input)
                st.markdown(response.content)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if response.confidence:
                        color = {'HIGH': '🟢', 'MEDIUM': '🟡', 'LOW': '🔴'}.get(response.confidence, '⚪')
                        st.caption(f"{color} Confianza: {response.confidence}")
                with col2:
                    if response.validated:
                        st.caption("✅ Validado")
                    else:
                        st.caption("⚠️ Sin validar")
                with col3:
                    if response.sources:
                        st.caption(f"📊 Fuentes: {', '.join(response.sources)}")
    
    # Sugerencias de preguntas
    if not chat.history:
        st.markdown("---")
        st.markdown("**💡 Preguntas sugeridas:**")
        
        suggestions = [
            "¿Cuáles son las principales fugas de autoridad?",
            "¿Qué facetas tienen más oportunidad?",
            "¿Cuál es el tráfico total del hub?",
            "¿Qué acciones debería priorizar?",
            "¿Cuántas URLs están activas vs eliminadas?",
        ]
        
        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                if st.button(suggestion[:20] + "...", key=f"suggest_{i}"):
                    # Simular input
                    st.session_state['chat_input'] = suggestion
                    st.rerun()
