import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import aiofiles
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.manuais_cache = {}
        self.manuais_embeddings = {}
        self.manuais_carregados = 0
        self.openai_client = None
        self.embeddings_gerados = False
        
    async def initialize(self):
        """Carrega todos os manuais e gera embeddings na inicialização"""
        await self.carregar_manuais()
        await self.gerar_embeddings_titulos()
        
    async def carregar_manuais(self) -> Dict[str, str]:
        """Carrega todos os manuais .md de forma assíncrona"""
        if self.manuais_cache:
            return self.manuais_cache
            
        try:
            pattern = os.path.join(settings.MANUAIS_PATH, "*.md")
            arquivos_md = glob.glob(pattern)
            
            logger.info(f"🔍 Encontrados {len(arquivos_md)} arquivos .md em {settings.MANUAIS_PATH}")
            
            if not arquivos_md:
                logger.error(f"❌ Nenhum arquivo .md encontrado em {settings.MANUAIS_PATH}")
                return {}
            
            tasks = []
            for arquivo in arquivos_md:
                tasks.append(self._carregar_arquivo(arquivo))
            
            resultados = await asyncio.gather(*tasks, return_exceptions=True)
            
            for resultado in resultados:
                if isinstance(resultado, tuple):
                    nome_arquivo, conteudo = resultado
                    if conteudo and len(conteudo.strip()) > 100:  # Só adiciona se tem conteúdo substancial
                        self.manuais_cache[nome_arquivo] = conteudo
                        logger.info(f"✅ Carregado: {nome_arquivo} ({len(conteudo)} chars)")
                    else:
                        logger.warning(f"⚠️ Arquivo vazio ou muito pequeno: {nome_arquivo}")
                    
            self.manuais_carregados = len(self.manuais_cache)
            logger.info(f"📚 Total carregados: {self.manuais_carregados} manuais")
            
            # Lista alguns manuais para debug
            for nome in list(self.manuais_cache.keys())[:5]:
                logger.info(f"📄 Manual disponível: {nome}")
            
            return self.manuais_cache
            
        exceptimport os
import glob
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.base_manuais = []  # Igual ao seu notebook
        self.manuais_carregados = 0
        self.openai_client = None
        self.inicializado = False

    async def initialize(self):
        """Inicializa EXATAMENTE como seu notebook"""
        if self.inicializado:
            return

        try:
            # Importa OpenAI
            import openai

            if not settings.OPENAI_API_KEY:
                logger.error("❌ OpenAI API key não configurada")
                return

            # Cliente OpenAI (igual ao seu notebook)
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            # Carrega manuais EXATAMENTE como seu notebook
            await self._carregar_manuais_como_notebook()

            self.inicializado = True
            logger.info(f"✅ {len(self.base_manuais)} manuais carregados e embeddings gerados com sucesso.")

        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {str(e)}")

    async def _carregar_manuais_como_notebook(self):
        """Carrega manuais EXATAMENTE como seu notebook"""
        try:
            # Lista arquivos .md (igual ao notebook)
            pattern = os.path.join(settings.MANUAIS_PATH, "*.md")
            manuais = glob.glob(pattern)

            logger.info(f"📁 Encontrados {len(manuais)} arquivos .md")

            if not manuais:
                logger.error(f"❌ Nenhum arquivo encontrado em {settings.MANUAIS_PATH}")
                return

            # Para cada manual (IGUAL AO NOTEBOOK)
            for caminho in manuais:
                try:
                    # Título (igual ao notebook)
                    titulo = os.path.basename(caminho).replace(".md", "")

                    # Carrega conteúdo (igual ao notebook)
                    conteudo = await self._carregar_arquivo(caminho)

                    if not conteudo or len(conteudo.strip()) < 100:
                        logger.warning(f"⚠️ Arquivo vazio: {titulo}")
                        continue

                    # Gera embedding do título (IGUAL AO NOTEBOOK)
                    emb_titulo = await asyncio.to_thread(
                        self._gerar_embeddings_texto, titulo
                    )

                    # Adiciona à base (IGUAL AO NOTEBOOK)
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
        """Carrega arquivo (igual ao notebook)"""
        try:
            # Usa encoding igual ao notebook
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.error(f"❌ Erro ao ler {caminho}: {str(e)}")
            return ""

    def _gerar_embeddings_texto(self, texto: str) -> np.ndarray:
        """Gera embedding EXATAMENTE como seu notebook"""
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
        """Calcula similaridade EXATAMENTE como seu notebook"""
        try:
            return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        except:
            return 0.0

    def _detectar_marcas_na_pergunta(self, pergunta: str) -> List[str]:
        """Detecta marcas EXATAMENTE como seu notebook"""
        marcas = ["john deere", "new holland", "case ih", "fendt", "valtra", "massey"]
        return [m for m in marcas if m in pergunta.lower()]

    def _selecionar_top_manuais_por_titulo(self, pergunta: str, top_n: int = 3) -> List[Dict]:
        """Seleciona manuais EXATAMENTE como seu notebook"""
        try:
            # Gera embedding da pergunta
            emb_pergunta = self._gerar_embeddings_texto(pergunta)

            if len(emb_pergunta) == 0:
                logger.error("❌ Falha ao gerar embedding da pergunta")
                return []

            # Calcula similaridades (IGUAL AO NOTEBOOK)
            similaridades = []
            for m in self.base_manuais:
                sim = self._similaridade(emb_pergunta, m["embedding_titulo"])
                similaridades.append((m, sim))
                logger.info(f"📊 {m['titulo']}: similaridade = {sim:.3f}")

            # Ordena e retorna top N (IGUAL AO NOTEBOOK)
            similares_ordenados = sorted(similaridades, key=lambda x: x[1], reverse=True)

            # Log dos selecionados
            for i, (manual, sim) in enumerate(similares_ordenados[:top_n]):
                logger.info(f"🏆 Top {i+1}: {manual['titulo']} (sim: {sim:.3f})")

            return [x[0] for x in similares_ordenados[:top_n]]

        except Exception as e:
            logger.error(f"❌ Erro na seleção de manuais: {str(e)}")
            return []

    def buscar_contexto_relevante(self, pergunta: str, modelo_maquina: str = None) -> Tuple[str, List[Dict]]:
        """
        Função principal EXATAMENTE como seu notebook
        """
        if not self.inicializado or not self.base_manuais:
            return "Sistema não inicializado ou sem manuais carregados.", []

        try:
            logger.info(f"🔍 Processando pergunta: '{pergunta}'")

            # 1. Detecta múltiplas marcas (IGUAL AO NOTEBOOK)
            marcas = self._detectar_marcas_na_pergunta(pergunta)

            if len(marcas) > 1:
                marcas_fmt = ", ".join([m.title() for m in marcas])
                mensagem = (f"⚠️ Percebi que sua pergunta envolve múltiplas marcas ({marcas_fmt}). "
                           "Para garantir uma resposta precisa e detalhada, "
                           "por favor pergunte sobre uma marca por vez. 😊")
                return mensagem, []

            # 2. Seleciona top manuais (IGUAL AO NOTEBOOK)
            top_manuais = self._selecionar_top_manuais_por_titulo(pergunta, top_n=3)

            if not top_manuais:
                logger.warning("❌ Nenhum manual relevante encontrado")
                return "Nenhum manual relevante encontrado para sua pergunta.", []

            # 3. Monta contexto (IGUAL AO NOTEBOOK)
            contexto = ""
            for m in top_manuais:
                contexto += f"\n\n### {m['titulo']} ###\n{m['texto']}"

            # 4. Monta prompt EXATAMENTE como seu notebook
            prompt_completo = f"""
Você é um especialista técnico em máquinas agrícolas.
Use apenas o conteúdo dos manuais abaixo para responder à pergunta do usuário.

Instruções:
- Se a pergunta envolver marcas diferentes, peça educadamente para o usuário perguntar uma por vez.
- Se a pergunta não tiver relação com máquinas agrícolas, RESPONDA usando seu conhecimento geral,
  mas explique gentilmente que seu foco é máquinas agrícolas.
- Se a pergunta mencionar várias máquinas da MESMA marca, responda com todas as informações relevantes.
- Mantenha um tom profissional e cordial.
- Cite sempre o nome do manual (APENAS 1 MANUAL) e a seção/subseção usada como base.

---
📘 CONTEXTO:
{contexto}
---
🧭 PERGUNTA:
{pergunta}
"""

            # 5. Prepara referências
            referencias = []
            for manual in top_manuais:
                referencias.append({
                    "arquivo": manual['titulo'] + '.md',
                    "relevancia": 0.9,  # Placeholder
                    "trecho": manual['texto'][:300] + "..."
                })

            logger.info(f"✅ Contexto montado com {len(top_manuais)} manuais")

            return prompt_completo, referencias

        except Exception as e:
            logger.error(f"❌ Erro na busca: {str(e)}")
            return f"Erro interno: {str(e)}", []

# Instância global
manual_processor = ManualProcessor()

