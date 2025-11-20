"""
Processamento avançado de texto
"""

import re
import math
from typing import List, Dict, Set, Tuple
from collections import Counter

class TextProcessor:
    """Classe para processamento avançado de texto"""
    
    def __init__(self):
        self.stop_words = {
            'a', 'o', 'e', 'de', 'do', 'da', 'em', 'um', 'uma', 'para', 'com', 
            'não', 'que', 'se', 'na', 'por', 'mais', 'as', 'os', 'como', 'mas',
            'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser',
            'quando', 'muito', 'há', 'nos', 'já', 'está', 'eu', 'também', 'só',
            'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era', 'depois',
            'sem', 'mesmo', 'aos', 'ter', 'seus', 'suas', 'numa', 'pelos',
            'pelas', 'esse', 'essa', 'num', 'nem', 'suas', 'meu', 'às', 'minha',
            'têm', 'numa', 'pelos', 'pelas', 'qual', 'será', 'nós', 'tenho',
            'lhe', 'deles', 'essas', 'esses', 'pelas', 'este', 'del', 'tu',
            'te', 'vocês', 'vos', 'lhes', 'meus', 'minhas', 'teu', 'tua',
            'teus', 'tuas', 'nosso', 'nossa', 'nossos', 'nossas', 'dela',
            'delas', 'esta', 'estes', 'estas', 'aquele', 'aquela', 'aqueles',
            'aquelas', 'isto', 'aquilo', 'estou', 'está', 'estamos', 'estão',
            'estive', 'esteve', 'estivemos', 'estiveram', 'estava', 'estávamos',
            'estavam', 'estivera', 'estivéramos', 'esteja', 'estejamos', 'estejam',
            'estivesse', 'estivéssemos', 'estivessem', 'estiver', 'estivermos',
            'estiverem', 'hei', 'há', 'havemos', 'hão', 'houve', 'houvemos',
            'houveram', 'houvera', 'houvéramos', 'haja', 'hajamos', 'hajam',
            'houvesse', 'houvéssemos', 'houvessem', 'houver', 'houvermos',
            'houverem', 'houverei', 'houverá', 'houveremos', 'houverão',
            'houveria', 'houveríamos', 'houveriam', 'sou', 'somos', 'são',
            'era', 'éramos', 'eram', 'fui', 'foi', 'fomos', 'foram', 'fora',
            'fôramos', 'seja', 'sejamos', 'sejam', 'fosse', 'fôssemos',
            'fossem', 'for', 'formos', 'forem', 'serei', 'será', 'seremos',
            'serão', 'seria', 'seríamos', 'seriam', 'tenho', 'tem', 'temos',
            'tém', 'tinha', 'tínhamos', 'tinham', 'tive', 'teve', 'tivemos',
            'tiveram', 'tivera', 'tivéramos', 'tenha', 'tenhamos', 'tenham',
            'tivesse', 'tivéssemos', 'tivessem', 'tiver', 'tivermos', 'tiverem',
            'terei', 'terá', 'teremos', 'terão', 'teria', 'teríamos', 'teriam'
        }
        
        self.agricultural_terms = {
            # Máquinas
            'trator', 'colheitadeira', 'plantadeira', 'pulverizador', 'cultivador',
            'arado', 'grade', 'semeadora', 'ceifadora', 'debulhadora',
            
            # Componentes
            'motor', 'transmissão', 'hidráulico', 'pneumático', 'eletrônico',
            'embreagem', 'diferencial', 'eixo', 'pneu', 'roda', 'chassi',
            'cabine', 'volante', 'pedal', 'alavanca', 'painel',
            
            # Manutenção
            'manutenção', 'lubrificação', 'óleo', 'filtro', 'correia',
            'vela', 'bateria', 'radiador', 'bomba', 'válvula', 'vedação',
            'calibragem', 'ajuste', 'regulagem', 'limpeza', 'inspeção',
            
            # Operação
            'plantio', 'colheita', 'pulverização', 'cultivo', 'preparo',
            'velocidade', 'rotação', 'pressão', 'temperatura', 'combustível'
        }

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extrai palavras-chave mais relevantes do texto
        
        Args:
            text: Texto para análise
            max_keywords: Número máximo de palavras-chave
            
        Returns:
            Lista de palavras-chave ordenadas por relevância
        """
        if not text:
            return []
        
        # Normaliza texto
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Tokeniza
        words = text.split()
        
        # Remove stop words e palavras muito curtas
        filtered_words = [
            word for word in words 
            if word not in self.stop_words and len(word) > 2
        ]
        
        # Calcula frequência
        word_freq = Counter(filtered_words)
        
        # Aplica peso para termos agrícolas
        weighted_words = {}
        for word, freq in word_freq.items():
            weight = freq
            if word in self.agricultural_terms:
                weight *= 2  # Dobra peso para termos agrícolas
            weighted_words[word] = weight
        
        # Ordena por peso e retorna top keywords
        sorted_words = sorted(weighted_words.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in sorted_words[:max_keywords]]

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similaridade entre dois textos usando TF-IDF simplificado
        
        Args:
            text1: Primeiro texto
            text2: Segundo texto
            
        Returns:
            Score de similaridade (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # Extrai palavras-chave de ambos os textos
        keywords1 = set(self.extract_keywords(text1, 20))
        keywords2 = set(self.extract_keywords(text2, 20))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # Calcula interseção e união
        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)
        
        # Similaridade de Jaccard
        jaccard_similarity = len(intersection) / len(union) if union else 0.0
        
        # Bonus para termos agrícolas em comum
        agricultural_intersection = intersection.intersection(self.agricultural_terms)
        agricultural_bonus = len(agricultural_intersection) * 0.1
        
        return min(1.0, jaccard_similarity + agricultural_bonus)

    def extract_technical_specifications(self, text: str) -> Dict[str, List[str]]:
        """
        Extrai especificações técnicas do texto
        
        Args:
            text: Texto para análise
            
        Returns:
            Dicionário com especificações categorizadas
        """
        specs = {
            'potencia': [],
            'capacidade': [],
            'dimensoes': [],
            'peso': [],
            'velocidade': [],
            'pressao': [],
            'temperatura': [],
            'combustivel': []
        }
        
        # Padrões para diferentes tipos de especificações
        patterns = {
            'potencia': [
                r'(\d+(?:\.\d+)?)\s*(?:cv|hp|kw)',
                r'potência.*?(\d+(?:\.\d+)?)\s*(?:cv|hp|kw)'
            ],
            'capacidade': [
                r'(\d+(?:\.\d+)?)\s*(?:l|litros?|ml|galões?)',
                r'capacidade.*?(\d+(?:\.\d+)?)\s*(?:l|litros?)'
            ],
            'dimensoes': [
                r'(\d+(?:\.\d+)?)\s*(?:m|mm|cm|metros?)',
                r'(?:comprimento|largura|altura).*?(\d+(?:\.\d+)?)\s*(?:m|mm|cm)'
            ],
            'peso': [
                r'(\d+(?:\.\d+)?)\s*(?:kg|ton|toneladas?)',
                r'peso.*?(\d+(?:\.\d+)?)\s*(?:kg|ton)'
            ],
            'velocidade': [
                r'(\d+(?:\.\d+)?)\s*(?:km/h|mph|rpm)',
                r'velocidade.*?(\d+(?:\.\d+)?)\s*(?:km/h|rpm)'
            ],
            'pressao': [
                r'(\d+(?:\.\d+)?)\s*(?:bar|psi|kpa)',
                r'pressão.*?(\d+(?:\.\d+)?)\s*(?:bar|psi)'
            ],
            'temperatura': [
                r'(\d+(?:\.\d+)?)\s*(?:°c|°f|celsius|fahrenheit)',
                r'temperatura.*?(\d+(?:\.\d+)?)\s*(?:°c|°f)'
            ],
            'combustivel': [
                r'(\d+(?:\.\d+)?)\s*(?:l/h|gal/h)',
                r'consumo.*?(\d+(?:\.\d+)?)\s*(?:l/h|gal/h)'
            ]
        }
        
        text_lower = text.lower()
        
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                specs[category].extend(matches)
        
        # Remove duplicatas e ordena
        for category in specs:
            specs[category] = sorted(list(set(specs[category])))
        
        return specs

    def identify_maintenance_procedures(self, text: str) -> List[Dict[str, str]]:
        """
        Identifica procedimentos de manutenção no texto
        
        Args:
            text: Texto para análise
            
        Returns:
            Lista de procedimentos identificados
        """
        procedures = []
        
        # Padrões de procedimentos
        procedure_patterns = [
            r'(?:verificar|checar|inspecionar)\s+([^.!?]+)',
            r'(?:trocar|substituir|mudar)\s+([^.!?]+)',
            r'(?:limpar|lavar)\s+([^.!?]+)',
            r'(?:lubrificar|aplicar óleo)\s+([^.!?]+)',
            r'(?:ajustar|regular|calibrar)\s+([^.!?]+)',
            r'(?:apertar|fixar)\s+([^.!?]+)'
        ]
        
        action_map = {
            'verificar': 'INSPEÇÃO',
            'checar': 'INSPEÇÃO',
            'inspecionar': 'INSPEÇÃO',
            'trocar': 'SUBSTITUIÇÃO',
            'substituir': 'SUBSTITUIÇÃO',
            'mudar': 'SUBSTITUIÇÃO',
            'limpar': 'LIMPEZA',
            'lavar': 'LIMPEZA',
            'lubrificar': 'LUBRIFICAÇÃO',
            'aplicar óleo': 'LUBRIFICAÇÃO',
            'ajustar': 'AJUSTE',
            'regular': 'AJUSTE',
            'calibrar': 'AJUSTE',
            'apertar': 'FIXAÇÃO',
            'fixar': 'FIXAÇÃO'
        }
        
        for pattern in procedure_patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                full_match = match.group(0)
                component = match.group(1).strip()
                
                # Identifica tipo de ação
                action_type = 'MANUTENÇÃO'
                for action, type_name in action_map.items():
                    if action in full_match.lower():
                        action_type = type_name
                        break
                
                procedures.append({
                    'tipo': action_type,
                    'componente': component,
                    'procedimento_completo': full_match
                })
        
        return procedures

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Função de conveniência para extrair palavras-chave"""
    processor = TextProcessor()
    return processor.extract_keywords(text, max_keywords)

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Função de conveniência para calcular similaridade"""
    processor = TextProcessor()
    return processor.calculate_text_similarity(text1, text2)

def normalize_brand_name(brand: str) -> str:
    """
    Normaliza nome de marca para formato padrão
    
    Args:
        brand: Nome da marca
        
    Returns:
        Nome normalizado
    """
    if not brand:
        return ""
    
    brand_lower = brand.lower().strip()
    
    # Mapeamento de normalizações
    brand_mapping = {
        'case': 'Case IH',
        'case ih': 'Case IH',
        'caseih': 'Case IH',
        'john deere': 'John Deere',
        'johndeere': 'John Deere',
        'deere': 'John Deere',
        'new holland': 'New Holland',
        'newholland': 'New Holland',
        'nh': 'New Holland',
        'valtra': 'Valtra'
    }
    
    return brand_mapping.get(brand_lower, brand.title())

def extract_model_number(text: str) -> str:
    """
    Extrai número/código de modelo do texto
    
    Args:
        text: Texto contendo modelo
        
    Returns:
        Modelo extraído ou string vazia
    """
    # Padrões comuns de modelos
    model_patterns = [
        r'\b([A-Z]+\d+[A-Z]*)\b',  # Ex: MX285, T7060
        r'\b(\d+[A-Z]+\d*)\b',     # Ex: 7230J, 8360R
        r'\b([A-Z]\d+)\b',         # Ex: A955, N121
        r'(?:modelo|mod\.?)\s*([A-Za-z0-9\-]+)',  # Modelo explícito
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return ""