"""
Funções auxiliares gerais
"""

import re
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

def format_response_time(seconds: float) -> str:
    """
    Formata tempo de resposta de forma legível
    
    Args:
        seconds: Tempo em segundos
        
    Returns:
        String formatada (ex: "1.23s", "850ms")
    """
    if seconds >= 1:
        return f"{seconds:.2f}s"
    else:
        return f"{int(seconds * 1000)}ms"

def clean_text(text: str) -> str:
    """
    Limpa e normaliza texto
    
    Args:
        text: Texto a ser limpo
        
    Returns:
        Texto limpo e normalizado
    """
    if not text:
        return ""
    
    # Remove caracteres especiais desnecessários
    text = re.sub(r'[^\w\s\-\.\,\;\:\!\?\(\)]', '', text)
    
    # Remove espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    
    # Remove quebras de linha múltiplas
    text = re.sub(r'\n+', '\n', text)
    
    return text.strip()

def extract_machine_info(text: str) -> Dict[str, Optional[str]]:
    """
    Extrai informações sobre máquina do texto
    
    Args:
        text: Texto contendo informações da máquina
        
    Returns:
        Dicionário com marca, modelo e tipo extraídos
    """
    text_lower = text.lower()
    
    # Marcas conhecidas
    marcas = {
        'case ih': ['case ih', 'case', 'caseih'],
        'john deere': ['john deere', 'johndeere', 'deere'],
        'new holland': ['new holland', 'newholland', 'nh'],
        'valtra': ['valtra']
    }
    
    # Tipos de máquinas
    tipos = ['trator', 'colheitadeira', 'plantadeira', 'pulverizador', 'cultivador']
    
    marca_encontrada = None
    tipo_encontrado = None
    modelo_encontrado = None
    
    # Busca marca
    for marca_oficial, variantes in marcas.items():
        for variante in variantes:
            if variante in text_lower:
                marca_encontrada = marca_oficial
                break
        if marca_encontrada:
            break
    
    # Busca tipo
    for tipo in tipos:
        if tipo in text_lower:
            tipo_encontrado = tipo
            break
    
    # Busca padrões de modelo (números/letras)
    modelo_patterns = [
        r'(?:modelo|mod\.?)\s*([a-z0-9\-]+)',
        r'([a-z]+\s*\d+[a-z]*)',
        r'(\d+[a-z]+\d*)'
    ]
    
    for pattern in modelo_patterns:
        match = re.search(pattern, text_lower)
        if match:
            modelo_encontrado = match.group(1).upper()
            break
    
    return {
        'marca': marca_encontrada,
        'tipo': tipo_encontrado,
        'modelo': modelo_encontrado
    }

def calculate_confidence_score(
    context_relevance: float,
    ai_response_quality: float,
    manual_matches: int,
    processing_time: float
) -> float:
    """
    Calcula score de confiança da resposta
    
    Args:
        context_relevance: Relevância do contexto (0-1)
        ai_response_quality: Qualidade da resposta IA (0-1)
        manual_matches: Número de manuais encontrados
        processing_time: Tempo de processamento em segundos
        
    Returns:
        Score de confiança (0-1)
    """
    # Peso base da relevância e qualidade
    base_score = (context_relevance * 0.4) + (ai_response_quality * 0.4)
    
    # Bonus por múltiplos manuais encontrados
    manual_bonus = min(manual_matches * 0.05, 0.15)
    
    # Penalidade por tempo excessivo (>10s)
    time_penalty = max(0, (processing_time - 10) * 0.01)
    
    final_score = base_score + manual_bonus - time_penalty
    
    return max(0.0, min(1.0, final_score))

def generate_request_id() -> str:
    """
    Gera ID único para requisição
    
    Returns:
        ID único baseado em timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    microseconds = datetime.now().microsecond
    return f"req_{timestamp}_{microseconds}"

def format_manual_reference(filename: str, relevance: float, excerpt: str) -> Dict[str, str]:
    """
    Formata referência de manual de forma padronizada
    
    Args:
        filename: Nome do arquivo
        relevance: Score de relevância
        excerpt: Trecho relevante
        
    Returns:
        Referência formatada
    """
    # Extrai informações do nome do arquivo
    clean_name = filename.replace('.md', '').replace('_', ' ').title()
    
    # Limita tamanho do trecho
    if len(excerpt) > 300:
        excerpt = excerpt[:297] + "..."
    
    return {
        'arquivo': clean_name,
        'relevancia_pct': f"{relevance * 100:.1f}%",
        'trecho': clean_text(excerpt),
        'arquivo_original': filename
    }

def validate_processing_time(start_time: float, max_time: int = 15) -> Tuple[float, bool]:
    """
    Valida tempo de processamento
    
    Args:
        start_time: Timestamp de início
        max_time: Tempo máximo permitido em segundos
        
    Returns:
        Tupla com (tempo_decorrido, dentro_do_limite)
    """
    elapsed = time.time() - start_time
    within_limit = elapsed <= max_time
    
    return elapsed, within_limit

def extract_technical_terms(text: str) -> List[str]:
    """
    Extrai termos técnicos do texto
    
    Args:
        text: Texto para análise
        
    Returns:
        Lista de termos técnicos encontrados
    """
    technical_patterns = [
        r'\b\d+\s*(?:cv|hp|rpm|bar|psi|kg|ton|l|ml)\b',  # Unidades técnicas
        r'\b(?:motor|transmissão|hidráulico|pneumático|eletrônico)\b',  # Componentes
        r'\b(?:manutenção|lubrificação|calibragem|ajuste)\b',  # Procedimentos
        r'\b[A-Z]{2,}\d+[A-Z]*\b'  # Códigos de peças
    ]
    
    terms = []
    text_lower = text.lower()
    
    for pattern in technical_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        terms.extend(matches)
    
    return list(set(terms))  # Remove duplicatas

def sanitize_filename(filename: str) -> str:
    """
    Sanitiza nome de arquivo para uso seguro
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        Nome sanitizado
    """
    # Remove caracteres perigosos
    safe_name = re.sub(r'[<>:"/\|?*]', '', filename)
    
    # Limita tamanho
    if len(safe_name) > 100:
        safe_name = safe_name[:97] + "..."
    
    return safe_name.strip()