"""
Módulo de validación dual de AI
Implementa consenso entre Claude y GPT para evitar alucinaciones
"""

import re
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd


class ConsensusLevel(Enum):
    """Niveles de consenso entre modelos"""
    FULL = "full"           # Ambos modelos coinciden completamente
    PARTIAL = "partial"     # Coincidencia parcial, algunas diferencias menores
    CONFLICT = "conflict"   # Los modelos no coinciden


@dataclass
class ValidationResult:
    """Resultado de validación dual"""
    consensus: ConsensusLevel
    confidence: float           # 0.0 - 1.0
    primary_response: str       # Respuesta del modelo principal
    validation_response: str    # Respuesta del modelo de validación
    numbers_match: bool
    conclusions_match: bool
    data_grounded: bool
    merged_response: str        # Respuesta final consensuada
    caveats: List[str]
    source_data: Dict[str, Any]
    query_code: str


@dataclass
class ChatResponse:
    """Respuesta validada del chat"""
    answer: str
    source_file: str
    query_code: str
    raw_result: Any
    claude_interpretation: str
    gpt_validation: str
    consensus: bool
    confidence: str  # 'HIGH' | 'MEDIUM' | 'LOW'
    caveats: List[str]


class DualValidator:
    """Validador dual usando dos modelos de AI"""
    
    def __init__(self, config_mode: str = 'hybrid'):
        """
        Inicializa el validador dual
        
        Args:
            config_mode: 'economic' | 'hybrid' | 'premium'
        """
        from config.settings import AI_CONFIGS
        self.config = AI_CONFIGS.get(config_mode, AI_CONFIGS['hybrid'])
        self.mode = config_mode
        
    def extract_numbers(self, text: str) -> List[float]:
        """Extrae todos los números de un texto"""
        # Manejar formatos con comas como separador de miles
        text = text.replace(',', '')
        
        # Buscar números (enteros y decimales)
        pattern = r'-?\d+\.?\d*'
        numbers = re.findall(pattern, text)
        
        return [float(n) for n in numbers if n and n != '.']
    
    def numbers_match(self, response_a: str, response_b: str, tolerance: float = 0.01) -> bool:
        """
        Verifica si los números mencionados en ambas respuestas coinciden
        
        Args:
            response_a: Primera respuesta
            response_b: Segunda respuesta
            tolerance: Tolerancia porcentual (0.01 = 1%)
        """
        nums_a = set(self.extract_numbers(response_a))
        nums_b = set(self.extract_numbers(response_b))
        
        if not nums_a and not nums_b:
            return True  # Ninguno menciona números
        
        if not nums_a or not nums_b:
            return False  # Solo uno menciona números
        
        # Verificar que cada número en A tiene equivalente en B
        for num_a in nums_a:
            found = False
            for num_b in nums_b:
                if num_a == 0 and num_b == 0:
                    found = True
                    break
                elif num_a != 0 and abs(num_a - num_b) / abs(num_a) < tolerance:
                    found = True
                    break
            if not found:
                return False
        
        return True
    
    def conclusions_match(self, response_a: str, response_b: str) -> bool:
        """
        Verifica si las conclusiones son similares
        Busca palabras clave y sentimiento general
        """
        # Palabras clave positivas/negativas
        positive = ['sí', 'correcto', 'válido', 'existe', 'activo', 'recomendar', 'oportunidad']
        negative = ['no', 'incorrecto', 'inválido', 'eliminado', '404', 'no existe', 'no recomendar']
        
        def get_sentiment(text: str) -> int:
            text_lower = text.lower()
            pos_count = sum(1 for p in positive if p in text_lower)
            neg_count = sum(1 for n in negative if n in text_lower)
            return pos_count - neg_count
        
        sentiment_a = get_sentiment(response_a)
        sentiment_b = get_sentiment(response_b)
        
        # Coinciden si tienen el mismo sentido (ambos positivos, negativos o neutros)
        return (sentiment_a > 0 and sentiment_b > 0) or \
               (sentiment_a < 0 and sentiment_b < 0) or \
               (sentiment_a == 0 and sentiment_b == 0)
    
    def data_is_grounded(self, response: str, source_data: Dict[str, Any]) -> bool:
        """
        Verifica que los datos mencionados existan en los datos fuente
        """
        numbers_in_response = self.extract_numbers(response)
        
        # Extraer todos los números de los datos fuente
        numbers_in_data = set()
        for key, value in source_data.items():
            if isinstance(value, (int, float)):
                numbers_in_data.add(float(value))
            elif isinstance(value, pd.DataFrame):
                for col in value.select_dtypes(include=['number']).columns:
                    numbers_in_data.update(value[col].dropna().astype(float).tolist())
        
        # Verificar que los números importantes estén en los datos
        # (números grandes, probablemente métricas importantes)
        important_numbers = [n for n in numbers_in_response if n > 100]
        
        for num in important_numbers:
            found = any(
                abs(num - data_num) / max(num, 1) < 0.01 
                for data_num in numbers_in_data
            )
            if not found:
                return False
        
        return True
    
    def check_consensus(self, response_a: str, response_b: str, 
                        source_data: Dict[str, Any]) -> ValidationResult:
        """
        Verifica el consenso entre dos respuestas
        """
        nums_match = self.numbers_match(response_a, response_b)
        conc_match = self.conclusions_match(response_a, response_b)
        grounded_a = self.data_is_grounded(response_a, source_data)
        grounded_b = self.data_is_grounded(response_b, source_data)
        
        # Determinar nivel de consenso
        if nums_match and conc_match and grounded_a and grounded_b:
            consensus = ConsensusLevel.FULL
            confidence = 0.95
        elif nums_match and (grounded_a or grounded_b):
            consensus = ConsensusLevel.PARTIAL
            confidence = 0.75
        else:
            consensus = ConsensusLevel.CONFLICT
            confidence = 0.5
        
        # Generar respuesta fusionada
        if consensus == ConsensusLevel.FULL:
            merged = response_a  # Usar respuesta principal
        elif consensus == ConsensusLevel.PARTIAL:
            merged = f"{response_a}\n\n⚠️ *Nota: Validación parcial. Verificar datos.*"
        else:
            merged = f"⚠️ **Conflicto de validación**\n\n**Análisis principal:**\n{response_a}\n\n**Análisis de validación:**\n{response_b}"
        
        # Caveats
        caveats = []
        if not nums_match:
            caveats.append("Los números mencionados difieren entre análisis")
        if not conc_match:
            caveats.append("Las conclusiones no coinciden completamente")
        if not grounded_a:
            caveats.append("Algunos datos del análisis principal no están verificados")
        if not grounded_b:
            caveats.append("Algunos datos de validación no están verificados")
        
        return ValidationResult(
            consensus=consensus,
            confidence=confidence,
            primary_response=response_a,
            validation_response=response_b,
            numbers_match=nums_match,
            conclusions_match=conc_match,
            data_grounded=grounded_a and grounded_b,
            merged_response=merged,
            caveats=caveats,
            source_data=source_data,
            query_code=""
        )


class QueryGenerator:
    """Genera queries de Pandas a partir de lenguaje natural"""
    
    def __init__(self, dataframes: Dict[str, pd.DataFrame]):
        self.dataframes = dataframes
        self.df_schemas = self._get_schemas()
    
    def _get_schemas(self) -> Dict[str, str]:
        """Obtiene esquemas de los DataFrames para contexto"""
        schemas = {}
        for name, df in self.dataframes.items():
            cols = df.columns.tolist()[:20]  # Primeras 20 columnas
            dtypes = df.dtypes.head(20).to_dict()
            schemas[name] = f"Columnas: {cols}\nTipos: {dtypes}"
        return schemas
    
    def generate_query(self, question: str) -> Tuple[str, str]:
        """
        Genera código Pandas para responder una pregunta
        
        Returns:
            Tuple[str, str]: (código, dataframe_a_usar)
        """
        question_lower = question.lower()
        
        # Patrones de preguntas comunes
        if 'tráfico' in question_lower or 'visitas' in question_lower:
            if 'pulgadas' in question_lower:
                return (
                    "df[df['url'].str.contains('pulgadas', case=False, na=False)]['visits_seo'].sum()",
                    'adobe_urls'
                )
            elif 'sin wrapper' in question_lower or 'sin seofilterwrapper' in question_lower:
                return (
                    "df[(df['wrapper_link_count'] == 0) & (df['Código de respuesta'] == 200)].merge(adobe_urls, left_on='Dirección', right_on='url_full')['visits_seo'].sum()",
                    'crawl_adobe'
                )
            else:
                return ("df['visits_seo'].sum()", 'adobe_urls')
        
        elif 'urls' in question_lower or 'páginas' in question_lower:
            if '404' in question_lower:
                return (
                    "len(df[df['Código de respuesta'] == 404])",
                    'crawl_adobe'
                )
            elif '200' in question_lower:
                return (
                    "len(df[df['Código de respuesta'] == 200])",
                    'crawl_adobe'
                )
        
        elif 'demanda' in question_lower:
            if 'pulgadas' in question_lower:
                return (
                    "df[df['filter_name'].str.contains('pulgadas:', case=False, na=False)]['visits_seo'].sum()",
                    'adobe_filters'
                )
            elif 'ram' in question_lower:
                return (
                    "df[df['filter_name'].str.contains('memoria ram:', case=False, na=False)]['visits_seo'].sum()",
                    'adobe_filters'
                )
        
        elif 'oportunidad' in question_lower or 'potencial' in question_lower:
            return (
                "# Análisis de oportunidad requiere evaluación completa",
                'analysis'
            )
        
        # Query genérico
        return ("# Query no generada automáticamente - requiere análisis manual", 'unknown')
    
    def execute_query(self, code: str, df_name: str) -> Tuple[Any, bool, str]:
        """
        Ejecuta una query de Pandas
        
        Returns:
            Tuple[result, success, error_message]
        """
        if df_name not in self.dataframes:
            return None, False, f"DataFrame '{df_name}' no disponible"
        
        try:
            df = self.dataframes[df_name]
            # Ejecutar en contexto seguro
            result = eval(code, {"df": df, "pd": pd})
            return result, True, ""
        except Exception as e:
            return None, False, str(e)


def create_validated_response(question: str, 
                              primary_answer: str,
                              validation_answer: str,
                              source_file: str,
                              query_code: str,
                              raw_result: Any,
                              source_data: Dict[str, Any]) -> ChatResponse:
    """
    Crea una respuesta validada para el chat
    """
    validator = DualValidator()
    validation = validator.check_consensus(primary_answer, validation_answer, source_data)
    
    return ChatResponse(
        answer=validation.merged_response,
        source_file=source_file,
        query_code=query_code,
        raw_result=raw_result,
        claude_interpretation=primary_answer,
        gpt_validation=validation_answer,
        consensus=validation.consensus == ConsensusLevel.FULL,
        confidence='HIGH' if validation.confidence > 0.9 else ('MEDIUM' if validation.confidence > 0.7 else 'LOW'),
        caveats=validation.caveats
    )
