import os
import glob
import logging
import numpy as np
import re
from typing import List, Dict, Tuple, Optional
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.base_manuais = []
        self.manuais_carregados = 0
        self.openai_client = None
        self.inicializado = False
        
    async def initialize(self):
        if self.inicializado:
            return
            
        try:
            import openai
            
            if not settings.OPENAI_API_KEY:
                logger.error("❌ OpenAI API key não configurada")
                return
            
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            await self._carregar_manuais_como_notebook()
            
            self.inicializado = True
            logger.info(f"✅ {len(self.base_manuais)} manuais carregados e embeddings gerados com sucesso.")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {str(e)}")
    
    async def _carregar_manuais_como_notebook(self):
        try:
            pattern = os.path.join(settings.MANUAIS_PATH, "*.md")
            manuais = glob.glob(pattern)
            
            logger.info(f"📁 Encontrados {len(manuais)} arquivos .md")
            
            if not manuais:
                logger.error(f"❌ Nenhum arquivo encontrado em {settings.MANUAIS_PATH}")
                return
            
            for caminho in manuais:
                try:
                    titulo = os.path.basename(caminho).replace(".md", "")
                    conteudo = await self._carregar_arquivo(caminho)
                    
                    if not conteudo or len(conteudo.strip()) < 100:
                        logger.warning(f"⚠️ Arquivo vazio: {titulo}")
                        continue
                    
                    emb_titulo = await asyncio.to_thread(
                        self._gerar_embeddings_texto, titulo
                    )
                    
                    self.base_manuais.append({
                        "arquivo": caminho,
                        "titulo": titulo,
                        "texto": conteudo,
                        "embedding_titulo": emb_titulo
                    })
                    
                    logger.info(f"✅ Carregado: {titulo}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao carregar {caminho}: {str(e)}")
                    continue
            
            self.manuais_carregados = len(self.base_manuais)
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar manuais: {str(e)}")
    
    async def _carregar_arquivo(self, caminho: str) -> str:
        try:
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error(f"❌ Erro ao ler {caminho}: {str(e)}")
            return ""
    
    def _gerar_embeddings_texto(self, texto: str) -> np.ndarray:
        try:
            resposta = self.openai_client.embeddings.create(
                model="text-embedding-3-small", 
                input=texto
            )
            return np.array(resposta.data[0].embedding)
        except Exception as e:
            logger.error(f"❌ Erro ao gerar embedding: {str(e)}")
            return np.array([])
    
    def _similaridade(self, v1: np.ndarray, v2: np.ndarray) -> float:
        try:
            return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        except:
            return 0.0
    
    # ✅ MELHORIA: Regex mais robusto
    def _detectar_marcas_na_pergunta(self, pergunta: str) -> List[str]:
        mapa_marcas = {
            "john deere": r"\b(john\s?deere|jd)\b",
            "case ih": r"\b(case\s?ih|case)\b",
            "new holland": r"\b(new\s?holland|nh)\b",
            "valtra": r"\b(valtra)\b",
            "fendt": r"\b(fendt)\b",
            "massey": r"\b(massey|mf|massey\s?ferguson)\b"
        }
        
        pergunta_lower = pergunta.lower()
        encontradas = []
        
        for nome, padrao in mapa_marcas.items():
            if re.search(padrao, pergunta_lower):
                encontradas.append(nome)
        
        return encontradas
    
    def _selecionar_top_manuais_por_titulo(self, pergunta: str, top_n: int = 3) -> List[Dict]:
        try:
            emb_pergunta = self._gerar_embeddings_texto(pergunta)
            
            if len(emb_pergunta) == 0:
                logger.error("❌ Falha ao gerar embedding da pergunta")
                return []
            
            similaridades = []
            for m in self.base_manuais:
                sim = self._similaridade(emb_pergunta, m["embedding_titulo"])
                similaridades.append((m, sim))
                logger.info(f"📊 {m['titulo']}: similaridade = {sim:.3f}")
            
            similares_ordenados = sorted(similaridades, key=lambda x: x[1], reverse=True)
            
            for i, (manual, sim) in enumerate(similares_ordenados[:top_n]):
                logger.info(f"🏆 Top {i+1}: {manual['titulo']} (sim: {sim:.3f})")
            
            return [x[0] for x in similares_ordenados[:top_n]]
            
        except Exception as e:
            logger.error(f"❌ Erro na seleção de manuais: {str(e)}")
            return []
    
    def buscar_contexto_relevante(self, pergunta: str, modelo_maquina: str = None) -> Tuple[str, List[Dict]]:
        if not self.inicializado or not self.base_manuais:
            return "Sistema não inicializado ou sem manuais carregados.", []
        
        try:
            logger.info(f"🔍 Processando pergunta: '{pergunta}'")
            
            marcas = self._detectar_marcas_na_pergunta(pergunta)
            
            # ✅ Resposta mais amigável para múltiplas marcas
            if len(marcas) > 1:
                marcas_fmt = ", ".join([m.title() for m in marcas])
                mensagem = (
                    f"😊 Notei que você mencionou mais de uma marca ({marcas_fmt}). "
                    "Para te ajudar da melhor forma possível, me pergunte sobre uma marca por vez, combinado?"
                )
                return mensagem, []
            
            top_manuais = self._selecionar_top_manuais_por_titulo(pergunta, top_n=3)
            
            # ✅ Caso não encontre manuais — nova lógica amigável
            if not top_manuais:
                return (
                    "🤖 Não encontrei um manual específico para essa pergunta.\n\n"
                    "Posso te ajudar com uma resposta mais geral 😊\n"
                    "Mas para respostas mais técnicas e precisas, me diga a marca e o modelo da máquina.",
                    []
                )
            
            contexto = ""
            for m in top_manuais:
                contexto += f"\n\n### {m['titulo']} ###\n{m['texto']}"
            
            # ✅ PROMPT MAIS AMIGÁVEL E SIMPLES
            prompt_completo = f"""
Você é um assistente amigável e especialista em máquinas agrícolas.
Fale de forma simples, clara e educada.

Regras importantes:
- Se a pergunta for genérica sobre máquinas agrícolas, responda usando seu conhecimento geral
  e explique de forma amigável que respostas mais precisas acontecem quando o usuário informa
  marca e modelo de uma máquina por vez.
- Se a pergunta NÃO for sobre máquinas agrícolas, responda normalmente,
  mas avise com carinho que seu foco principal é ajudar com máquinas agrícolas.
- Se o usuário citar várias marcas, peça para escolher uma.
- Quando usar os manuais, cite apenas 1 manual e mantenha o tom leve e próximo.

IMPORTANTE:
Se a resposta for baseada em conhecimento geral (e não nos manuais),
deixe claro algo como: "Essa resposta é baseada em conhecimento geral sobre máquinas agrícolas."

---
📘 CONTEXTO (manuais):
{contexto}

---
🧭 PERGUNTA DO USUÁRIO:
{pergunta}
"""
            
            referencias = []
            for manual in top_manuais:
                referencias.append({
                    "arquivo": manual['titulo'] + '.md',
                    "relevancia": 0.9,
                    "trecho": manual['texto'][:300] + "..."
                })
            
            logger.info(f"✅ Contexto montado com {len(top_manuais)} manuais")
            
            return prompt_completo, referencias
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {str(e)}")
            return f"Erro interno: {str(e)}", []

# Instância global
manual_processor = ManualProcessor()

