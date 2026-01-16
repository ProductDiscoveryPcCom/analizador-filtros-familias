"""
Clientes de API para validación dual
Conecta con Claude (Anthropic) y GPT (OpenAI)
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class AIResponse:
    """Respuesta de un modelo AI"""
    content: str
    model: str
    tokens_input: int
    tokens_output: int
    cost_estimate: float


class AnthropicClient:
    """Cliente para API de Anthropic (Claude)"""
    
    def __init__(self, api_key: str = None):
        """
        Inicializa el cliente de Anthropic
        
        Args:
            api_key: API key de Anthropic. Si no se proporciona, 
                     busca en variable de entorno ANTHROPIC_API_KEY
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.base_url = "https://api.anthropic.com/v1"
        
        if not self.api_key:
            raise ValueError(
                "API key de Anthropic no configurada. "
                "Configura ANTHROPIC_API_KEY en variables de entorno o pásala al constructor."
            )
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    
    def chat(self, 
             messages: list,
             model: str = "claude-sonnet-4-20250514",
             max_tokens: int = 4096,
             system: str = None) -> AIResponse:
        """
        Envía mensaje a Claude
        
        Args:
            messages: Lista de mensajes [{"role": "user", "content": "..."}]
            model: Modelo a usar
            max_tokens: Máximo de tokens en respuesta
            system: Prompt de sistema opcional
        """
        import requests
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages
        }
        
        if system:
            payload["system"] = system
        
        response = requests.post(
            f"{self.base_url}/messages",
            headers=self._get_headers(),
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"Error de API Anthropic: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Calcular costo estimado
        input_tokens = data.get('usage', {}).get('input_tokens', 0)
        output_tokens = data.get('usage', {}).get('output_tokens', 0)
        
        # Precios aproximados (actualizar según pricing actual)
        prices = {
            'claude-sonnet-4-20250514': {'input': 3.0, 'output': 15.0},
            'claude-opus-4-20250514': {'input': 15.0, 'output': 75.0},
        }
        price = prices.get(model, {'input': 3.0, 'output': 15.0})
        cost = (input_tokens * price['input'] + output_tokens * price['output']) / 1_000_000
        
        return AIResponse(
            content=data['content'][0]['text'],
            model=model,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cost_estimate=cost
        )


class OpenAIClient:
    """Cliente para API de OpenAI (GPT)"""
    
    def __init__(self, api_key: str = None):
        """
        Inicializa el cliente de OpenAI
        
        Args:
            api_key: API key de OpenAI. Si no se proporciona,
                     busca en variable de entorno OPENAI_API_KEY
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.base_url = "https://api.openai.com/v1"
        
        if not self.api_key:
            raise ValueError(
                "API key de OpenAI no configurada. "
                "Configura OPENAI_API_KEY en variables de entorno o pásala al constructor."
            )
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self,
             messages: list,
             model: str = "gpt-4o",
             max_tokens: int = 4096,
             system: str = None) -> AIResponse:
        """
        Envía mensaje a GPT
        
        Args:
            messages: Lista de mensajes [{"role": "user", "content": "..."}]
            model: Modelo a usar
            max_tokens: Máximo de tokens en respuesta
            system: Prompt de sistema opcional
        """
        import requests
        
        # Añadir system message si se proporciona
        if system:
            messages = [{"role": "system", "content": system}] + messages
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"Error de API OpenAI: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Extraer uso de tokens
        usage = data.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        
        # Precios aproximados
        prices = {
            'gpt-4o': {'input': 2.5, 'output': 10.0},
            'gpt-4-turbo': {'input': 10.0, 'output': 30.0},
        }
        price = prices.get(model, {'input': 2.5, 'output': 10.0})
        cost = (input_tokens * price['input'] + output_tokens * price['output']) / 1_000_000
        
        return AIResponse(
            content=data['choices'][0]['message']['content'],
            model=model,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cost_estimate=cost
        )


class DualAIClient:
    """
    Cliente unificado para validación dual
    Maneja ambas APIs y coordina las llamadas
    """
    
    def __init__(self, 
                 anthropic_key: str = None,
                 openai_key: str = None,
                 mode: str = 'hybrid'):
        """
        Inicializa el cliente dual
        
        Args:
            anthropic_key: API key de Anthropic (o env ANTHROPIC_API_KEY)
            openai_key: API key de OpenAI (o env OPENAI_API_KEY)
            mode: 'economic' | 'hybrid' | 'premium'
        """
        self.mode = mode
        self.anthropic = None
        self.openai = None
        self.total_cost = 0.0
        
        # Intentar inicializar clientes
        try:
            self.anthropic = AnthropicClient(anthropic_key)
        except ValueError as e:
            print(f"⚠️ Anthropic no configurado: {e}")
        
        try:
            self.openai = OpenAIClient(openai_key)
        except ValueError as e:
            print(f"⚠️ OpenAI no configurado: {e}")
        
        # Configuración de modelos por modo
        self.model_config = {
            'economic': {
                'primary': ('anthropic', 'claude-sonnet-4-20250514'),
                'validation': ('openai', 'gpt-4o'),
            },
            'hybrid': {
                'primary': ('anthropic', 'claude-sonnet-4-20250514'),
                'validation': ('openai', 'gpt-4-turbo'),
                'critical': ('anthropic', 'claude-opus-4-20250514'),
            },
            'premium': {
                'primary': ('anthropic', 'claude-opus-4-20250514'),
                'validation': ('openai', 'gpt-4-turbo'),
            }
        }
    
    def is_configured(self) -> Dict[str, bool]:
        """Verifica qué APIs están configuradas"""
        return {
            'anthropic': self.anthropic is not None,
            'openai': self.openai is not None,
            'dual_validation_available': self.anthropic is not None and self.openai is not None
        }
    
    def _call_model(self, provider: str, model: str, prompt: str, system: str = None) -> AIResponse:
        """Llama a un modelo específico"""
        messages = [{"role": "user", "content": prompt}]
        
        if provider == 'anthropic':
            if not self.anthropic:
                raise ValueError("Cliente Anthropic no configurado")
            return self.anthropic.chat(messages, model=model, system=system)
        elif provider == 'openai':
            if not self.openai:
                raise ValueError("Cliente OpenAI no configurado")
            return self.openai.chat(messages, model=model, system=system)
        else:
            raise ValueError(f"Proveedor desconocido: {provider}")
    
    def analyze_with_validation(self, 
                                 prompt: str,
                                 context: str = None,
                                 task_type: str = 'analysis') -> Dict[str, Any]:
        """
        Ejecuta análisis con validación dual
        
        Args:
            prompt: Pregunta o tarea a analizar
            context: Contexto adicional (datos, resultados de queries)
            task_type: 'analysis' | 'critical' | 'chat'
        
        Returns:
            Dict con respuestas de ambos modelos y resultado de consenso
        """
        config = self.model_config.get(self.mode, self.model_config['hybrid'])
        
        # Determinar qué modelos usar
        if task_type == 'critical' and 'critical' in config:
            primary_config = config['critical']
        else:
            primary_config = config['primary']
        
        validation_config = config['validation']
        
        # Construir prompt completo
        full_prompt = prompt
        if context:
            full_prompt = f"CONTEXTO (datos reales):\n{context}\n\nPREGUNTA:\n{prompt}"
        
        system_prompt = """Eres un analista SEO experto. Analiza los datos proporcionados y responde de forma precisa.
        
REGLAS CRÍTICAS:
1. SOLO usa datos del contexto proporcionado
2. Si no tienes datos suficientes, di "No tengo datos para responder esto"
3. Incluye números específicos cuando sea posible
4. Nunca inventes datos"""
        
        results = {
            'primary': None,
            'validation': None,
            'consensus': False,
            'confidence': 'LOW',
            'merged_response': None,
            'cost': 0.0,
            'errors': []
        }
        
        # Llamada primaria (Claude)
        try:
            primary_response = self._call_model(
                primary_config[0], 
                primary_config[1], 
                full_prompt,
                system_prompt
            )
            results['primary'] = {
                'content': primary_response.content,
                'model': primary_response.model,
                'cost': primary_response.cost_estimate
            }
            results['cost'] += primary_response.cost_estimate
        except Exception as e:
            results['errors'].append(f"Error en modelo primario: {e}")
        
        # Llamada de validación (GPT)
        validation_prompt = f"""Valida esta respuesta de otro modelo AI:

RESPUESTA A VALIDAR:
{results['primary']['content'] if results['primary'] else 'No disponible'}

DATOS ORIGINALES:
{context if context else 'No proporcionados'}

PREGUNTA ORIGINAL:
{prompt}

Indica si los números y conclusiones son correctos según los datos. 
Responde: VÁLIDO/PARCIAL/INVÁLIDO + explicación breve."""

        try:
            validation_response = self._call_model(
                validation_config[0],
                validation_config[1],
                validation_prompt,
                "Eres un validador de análisis. Verifica que los datos mencionados sean correctos."
            )
            results['validation'] = {
                'content': validation_response.content,
                'model': validation_response.model,
                'cost': validation_response.cost_estimate
            }
            results['cost'] += validation_response.cost_estimate
        except Exception as e:
            results['errors'].append(f"Error en validación: {e}")
        
        # Determinar consenso
        if results['primary'] and results['validation']:
            val_content = results['validation']['content'].upper()
            if 'VÁLIDO' in val_content or 'VALID' in val_content:
                results['consensus'] = True
                results['confidence'] = 'HIGH'
                results['merged_response'] = results['primary']['content']
            elif 'PARCIAL' in val_content or 'PARTIAL' in val_content:
                results['consensus'] = True
                results['confidence'] = 'MEDIUM'
                results['merged_response'] = f"{results['primary']['content']}\n\n⚠️ *Validación parcial: {results['validation']['content']}*"
            else:
                results['consensus'] = False
                results['confidence'] = 'LOW'
                results['merged_response'] = f"⚠️ **Conflicto de validación**\n\nAnálisis: {results['primary']['content']}\n\nValidación: {results['validation']['content']}"
        elif results['primary']:
            results['merged_response'] = f"{results['primary']['content']}\n\n⚠️ *Sin validación dual disponible*"
            results['confidence'] = 'MEDIUM'
        
        self.total_cost += results['cost']
        
        return results
    
    def get_session_cost(self) -> float:
        """Retorna el costo acumulado de la sesión"""
        return self.total_cost
    
    def reset_session_cost(self):
        """Reinicia el contador de costos"""
        self.total_cost = 0.0


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def check_api_configuration() -> Dict[str, Any]:
    """
    Verifica la configuración de APIs
    Busca en: st.secrets (Streamlit Cloud) → variables de entorno → session_state
    """
    import streamlit as st
    
    def get_secret(key: str) -> str:
        """Busca una clave en múltiples fuentes"""
        # 1. Streamlit secrets (para Streamlit Cloud)
        try:
            if hasattr(st, 'secrets') and key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
        
        # 2. Variables de entorno
        env_val = os.getenv(key)
        if env_val:
            return env_val
        
        # 3. Session state (configuración manual en UI)
        if key.lower().replace('_', '') in ['anthropicapikey', 'anthropic_api_key']:
            return st.session_state.get('anthropic_key', '')
        if key.lower().replace('_', '') in ['openaiapikey', 'openai_api_key']:
            return st.session_state.get('openai_key', '')
        
        return ''
    
    anthropic_key = get_secret('ANTHROPIC_API_KEY')
    openai_key = get_secret('OPENAI_API_KEY')
    
    status = {
        'anthropic': {
            'configured': bool(anthropic_key),
            'env_var': 'ANTHROPIC_API_KEY',
            'key_preview': None
        },
        'openai': {
            'configured': bool(openai_key),
            'env_var': 'OPENAI_API_KEY',
            'key_preview': None
        }
    }
    
    # Mostrar preview de keys (primeros/últimos caracteres)
    if anthropic_key:
        status['anthropic']['key_preview'] = f"{anthropic_key[:8]}...{anthropic_key[-4:]}"
    
    if openai_key:
        status['openai']['key_preview'] = f"{openai_key[:8]}...{openai_key[-4:]}"
    
    return status


def create_env_template():
    """Genera contenido para archivo .env de ejemplo"""
    return """# Facet Architecture Analyzer v2 - Configuración de APIs

# API de Anthropic (Claude)
# Obtener en: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# API de OpenAI (GPT)
# Obtener en: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-xxxxx

# Modo de validación por defecto (economic | hybrid | premium)
DEFAULT_AI_MODE=hybrid
"""
