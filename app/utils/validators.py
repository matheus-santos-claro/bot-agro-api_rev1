"""
Validadores de entrada e dados
"""

import re
from typing import Optional, List, Dict, Tuple
from app.models.schemas import QueryType

def validate_question(question: str) -> Tuple[bool, Optional[str]]:
    """
    Valida pergunta do usuário
    
    Args:
        question: Pergunta a ser validada
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not question or not question.strip():
        return False, "Pergunta não pode estar vazia"
    
    if len(question.strip()) < 5:
        return False, "Pergunta muito curta (mínimo 5 caracteres)"
    
    if len(question) > 500:
        return False, "Pergunta muito longa (máximo 500 caracteres)"
    
    # Verifica se contém apenas espaços ou caracteres especiais
    if not re.search(r'[a-zA-ZÀ-ÿ0-9]', question):
        return False, "Pergunta deve conter pelo menos uma letra ou número"
    
    # Verifica padrões suspeitos
    suspicious_patterns = [
        r'(.)\1{10,}',  # Caracteres repetidos
        r'[<>{}[\]\]',  # Caracteres de código
        r'(?:script|javascript|eval|exec)',  # Termos suspeitos
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return False, "Pergunta contém caracteres ou padrões não permitidos"
    
    return True, None

def validate_machine_model(model: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Valida modelo de máquina
    
    Args:
        model: Modelo a ser validado
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not model:
        return True, None  # Modelo é opcional
    
    model = model.strip()
    
    if len(model) > 50:
        return False, "Modelo muito longo (máximo 50 caracteres)"
    
    # Padrão básico para modelos (letras, números, hífens, espaços)
    if not re.match(r'^[a-zA-Z0-9\s\-]+$', model):
        return False, "Modelo contém caracteres não permitidos"
    
    return True, None

def validate_brand(brand: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Valida marca da máquina
    
    Args:
        brand: Marca a ser validada
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not brand:
        return True, None  # Marca é opcional
    
    valid_brands = [
        'case ih', 'case', 'john deere', 'deere', 
        'new holland', 'nh', 'valtra'
    ]
    
    brand_lower = brand.lower().strip()
    
    if brand_lower not in valid_brands:
        return False, f"Marca não suportada. Marcas válidas: {', '.join(set([b.title() for b in valid_brands if len(b) > 2]))}"
    
    return True, None

def sanitize_input(text: str) -> str:
    """
    Sanitiza entrada do usuário
    
    Args:
        text: Texto a ser sanitizado
        
    Returns:
        Texto sanitizado
    """
    if not text:
        return ""
    
    # Remove caracteres de controle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Remove múltiplos espaços
    text = re.sub(r'\s+', ' ', text)
    
    # Remove caracteres potencialmente perigosos
    text = re.sub(r'[<>{}[\]\]', '', text)
    
    return text.strip()

def validate_query_type(query_type: str) -> bool:
    """
    Valida tipo de consulta
    
    Args:
        query_type: Tipo de consulta
        
    Returns:
        True se válido
    """
    valid_types = [e.value for e in QueryType]
    return query_type in valid_types

def validate_confidence_score(score: float) -> bool:
    """
    Valida score de confiança
    
    Args:
        score: Score a ser validado
        
    Returns:
        True se válido (entre 0 e 1)
    """
    return 0.0 <= score <= 1.0

def validate_processing_time(time_seconds: float) -> bool:
    """
    Valida tempo de processamento
    
    Args:
        time_seconds: Tempo em segundos
        
    Returns:
        True se válido (positivo e razoável)
    """
    return 0.0 <= time_seconds <= 60.0  # Máximo 60 segundos

def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Valida extensão de arquivo
    
    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas
        
    Returns:
        True se extensão é válida
    """
    if not filename or '.' not in filename:
        return False
    
    extension = filename.lower().split('.')[-1]
    return extension in [ext.lower().lstrip('.') for ext in allowed_extensions]

def validate_manual_content(content: str) -> Tuple[bool, Optional[str]]:
    """
    Valida conteúdo de manual
    
    Args:
        content: Conteúdo do manual
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not content or not content.strip():
        return False, "Conteúdo do manual está vazio"
    
    if len(content) < 100:
        return False, "Conteúdo do manual muito curto (mínimo 100 caracteres)"
    
    # Verifica se parece ser texto técnico
    technical_indicators = [
        'manutenção', 'especificação', 'operação', 'motor', 'transmissão',
        'hidráulico', 'lubrificação', 'ajuste', 'calibragem', 'procedimento'
    ]
    
    content_lower = content.lower()
    found_indicators = sum(1 for indicator in technical_indicators if indicator in content_lower)
    
    if found_indicators < 2:
        return False, "Conteúdo não parece ser um manual técnico válido"
    
    return True, None

def validate_api_response(response_data: Dict) -> List[str]:
    """
    Valida estrutura de resposta da API
    
    Args:
        response_data: Dados da resposta
        
    Returns:
        Lista de erros encontrados (vazia se válida)
    """
    errors = []
    
    required_fields = ['resposta', 'categoria', 'confianca', 'tempo_processamento']
    
    for field in required_fields:
        if field not in response_data:
            errors.append(f"Campo obrigatório '{field}' ausente")
    
    # Validações específicas
    if 'confianca' in response_data:
        if not validate_confidence_score(response_data['confianca']):
            errors.append("Score de confiança inválido (deve estar entre 0 e 1)")
    
    if 'tempo_processamento' in response_data:
        if not validate_processing_time(response_data['tempo_processamento']):
            errors.append("Tempo de processamento inválido")
    
    if 'categoria' in response_data:
        if not validate_query_type(response_data['categoria']):
            errors.append("Categoria de consulta inválida")
    
    return errors