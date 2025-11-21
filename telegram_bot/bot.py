# telegram_bot/bot.py
import asyncio
import logging
import json
import re
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx
import ssl

from .config import TELEGRAM_BOT_TOKEN, API_BASE_URL, ADMIN_IDS
from .database import telegram_db
from .backup_service import BackupService

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AgroTelegramBot:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado")
        
        logger.info(f"🔑 Inicializando bot com API: {API_BASE_URL}")
        
        # Configuração SSL mais permissiva
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.api_client = httpx.AsyncClient(
            timeout=30.0,
            verify=False  # Desabilita verificação SSL para Render
        )
        self.database = telegram_db
        self.backup_service = BackupService(self.database)
        
        self.setup_handlers()
        
        logger.info("🤖 Bot Telegram inicializado")
    
    def setup_handlers(self):
        """Configura handlers do bot"""
        # Comandos básicos
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Comandos de admin
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("backup", self.backup_command))
        self.app.add_handler(CommandHandler("users", self.users_command))
        
        # Handler de mensagens
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_question))
        
        # Error handler para conflitos e outros erros
        self.app.add_error_handler(self.error_handler)
        
        logger.info("✅ Handlers configurados")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Lida com erros da aplicação"""
        error_msg = str(context.error)
        logger.error(f"❌ Erro capturado: {error_msg}")
        
        # Se for erro de conflito, ignora (não envia mensagem para usuário)
        if "Conflict" in error_msg or "terminated by other getUpdates" in error_msg:
            logger.warning("⚠️ Conflito de instância detectado - ignorando")
            return
        
        # Para outros erros, tenta enviar mensagem se houver update válido
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Ocorreu um erro temporário. Tente novamente em alguns segundos."
                )
            except Exception:
                pass  # Ignora se não conseguir enviar mensagem
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start - VERSÃO CORRIGIDA COM AUTO-INICIALIZAÇÃO"""
        logger.info(f"🎯 COMANDO /START RECEBIDO!")
        logger.info(f"👤 Usuário: {update.effective_user.id} - {update.effective_user.first_name}")
        
        try:
            user_data = self._extract_user_data(update)
            logger.info(f"📊 User data extraído: {user_data}")
            
            # Tenta registrar usuário, se falhar, inicializa banco
            try:
                await self.database.registrar_usuario(user_data)
                logger.info("✅ Usuário registrado no banco")
            except Exception as db_error:
                logger.warning(f"⚠️ Erro no banco: {db_error}")
                logger.info("🔄 Inicializando banco de dados...")
                await self.database.initialize()
                await self.database.registrar_usuario(user_data)
                logger.info("✅ Banco inicializado e usuário registrado")
            
            welcome_text = f"""
🌾 **Bot Agrícola Expert**

Olá {user_data.get('first_name', 'Usuário')}! 

Sou seu assistente especializado em máquinas agrícolas.

**🚜 Marcas suportadas:**
• Case IH • John Deere • New Holland
• Valtra • FENDT • Massey Ferguson

**📝 Como usar:**
Envie sua pergunta sobre:
• Especificações técnicas
• Configurações

**💡 Exemplo:**
"Qual a potência do motor da Case IH 4150?"

**🔧 Comandos disponíveis:**
/help - Ajuda detalhada
/stats - Suas estatísticas
/status - Status da API

Vamos começar! Envie sua primeira pergunta! 🚀
            """
            
            await update.message.reply_text(welcome_text, parse_mode='Markdown')
            logger.info("✅ Mensagem de boas-vindas enviada")
            
        except Exception as e:
            logger.error(f"❌ Erro no comando start: {str(e)}")
            await update.message.reply_text(
                "❌ Erro interno. O sistema está sendo inicializado. Tente novamente em alguns segundos."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        help_text = """
🔧 **Como usar o Bot Agrícola:**

**📋 Tipos de pergunta:**
• Especificações de motores e potência
• Configurações
• Características Gerais de Colheitadeiras, Tratores, Pulverizadores e Plantadeiras

**💡 Dicas importantes:**
• Seja específico com marca e modelo
• Uma marca por pergunta para melhor precisão
• Aguarde alguns segundos para a resposta
• Use termos técnicos quando possível

**🤖 Comandos disponíveis:**
/start - Iniciar/reiniciar bot
/help - Esta ajuda
/stats - Suas estatísticas pessoais
/status - Verificar status da API

**📝 Exemplos de perguntas:**
• "Motor da colheitadeira Case IH 4150"
• "Capacidade do Tanque de Grãos da Série S John Deere"
• "Quais Modelos disponíveis na Série TX das Colheitadeiras John Deere"
• "Qual modelo de transmissão do Trator MF 4707 da Massey Ferguson"

**🆘 Suporte:**
Se encontrar problemas, entre em contato com nossa equipe.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        try:
            # Testa múltiplos endpoints da API
            api_status = "❌ Offline"
            api_data = {}
            
            # Lista de endpoints para testar
            endpoints_to_test = [
                f"{API_BASE_URL}/health",
                f"{API_BASE_URL}/",
                f"{API_BASE_URL}/docs",
                f"{API_BASE_URL}/api/health"
            ]
            
            for endpoint in endpoints_to_test:
                try:
                    logger.info(f"🔍 Testando endpoint: {endpoint}")
                    response = await self.api_client.get(endpoint, timeout=10.0)
                    
                    if response.status_code == 200:
                        api_status = "✅ Online"
                        api_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                        logger.info(f"✅ Endpoint funcionando: {endpoint}")
                        break
                    else:
                        logger.warning(f"⚠️ Endpoint {endpoint} retornou: {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro no endpoint {endpoint}: {str(e)}")
                    continue
            
            # Estatísticas do banco
            try:
                stats = await self.database.get_estatisticas_gerais()
            except Exception as db_error:
                logger.warning(f"⚠️ Erro ao acessar estatísticas: {db_error}")
                await self.database.initialize()
                stats = await self.database.get_estatisticas_gerais()
            
            status_text = f"""
🔍 **Status do Sistema:**

**🌐 API Principal:** {api_status}
**📊 Base de Dados:** ✅ Funcionando

**📈 Estatísticas Gerais:**
• Total de usuários: {stats.get('total_usuarios', 0)}
• Interações registradas: {stats.get('total_interacoes', 0)}
• Usuários ativos (7d): {stats.get('usuarios_ativos_7d', 0)}
• Perguntas hoje: {stats.get('perguntas_hoje', 0)}

**🏆 Categoria mais perguntada:** {stats.get('categoria_mais_perguntada', 'N/A')}

**🔧 URL da API:** `{API_BASE_URL}`

**⏰ Última verificação:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro no comando status: {str(e)}")
            await update.message.reply_text(f"❌ Erro ao verificar status: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats - Estatísticas do usuário"""
        user_id = update.effective_user.id
        
        try:
            # Tenta buscar estatísticas, se falhar, inicializa banco
            try:
                stats = await self.database.get_estatisticas_usuario(user_id)
            except Exception as db_error:
                logger.warning(f"⚠️ Erro ao acessar estatísticas: {db_error}")
                await self.database.initialize()
                stats = await self.database.get_estatisticas_usuario(user_id)
            
            if not stats:
                await update.message.reply_text("❌ Nenhuma estatística encontrada. Use /start para se registrar.")
                return
            
            # Formata datas
            membro_desde = stats.get('membro_desde', '')
            if membro_desde:
                try:
                    dt = datetime.fromisoformat(membro_desde.replace('Z', '+00:00'))
                    membro_desde_fmt = dt.strftime('%d/%m/%Y')
                except:
                    membro_desde_fmt = membro_desde[:10]
            else:
                membro_desde_fmt = 'N/A'
            
            ultima_interacao = stats.get('ultima_interacao', '')
            if ultima_interacao:
                try:
                    dt = datetime.fromisoformat(ultima_interacao.replace('Z', '+00:00'))
                    ultima_interacao_fmt = dt.strftime('%d/%m/%Y %H:%M')
                except:
                    ultima_interacao_fmt = ultima_interacao[:16]
            else:
                ultima_interacao_fmt = 'N/A'
            
            confianca_media = stats.get('confianca_media', 0)
            confianca_pct = f"{confianca_media:.1%}" if confianca_media else "N/A"
            
            stats_text = f"""
📊 **Suas Estatísticas:**

**👤 Perfil:**
• Membro desde: {membro_desde_fmt}
• Última interação: {ultima_interacao_fmt}

**📈 Atividade:**
• Total de perguntas: {stats.get('total_perguntas', 0)}
• Interações registradas: {stats.get('interacoes_registradas', 0)}

**🎯 Qualidade:**
• Confiança média das respostas: {confianca_pct}
• Tokens utilizados: {stats.get('tokens_total', 0):,}

**💡 Dica:** Continue fazendo perguntas para melhorar suas estatísticas!
            """
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas: {str(e)}")
            await update.message.reply_text("❌ Erro ao buscar suas estatísticas. Tente novamente.")
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /admin - Estatísticas gerais (apenas admins)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            # Tenta buscar estatísticas, se falhar, inicializa banco
            try:
                stats = await self.database.get_estatisticas_gerais()
                top_users = await self.database.get_top_usuarios(5)
            except Exception as db_error:
                logger.warning(f"⚠️ Erro ao acessar dados admin: {db_error}")
                await self.database.initialize()
                stats = await self.database.get_estatisticas_gerais()
                top_users = await self.database.get_top_usuarios(5)
            
            # Formata top usuários
            top_users_text = ""
            for i, user in enumerate(top_users, 1):
                nome = user.get('first_name', 'N/A')
                username = user.get('username', '')
                username_fmt = f"@{username}" if username else ""
                perguntas = user.get('total_perguntas', 0)
                top_users_text += f"{i}. {nome} {username_fmt} - {perguntas} perguntas\n"
            
            admin_text = f"""
🔧 **Painel Administrativo:**

**📊 Estatísticas Gerais:**
• Total de usuários: {stats.get('total_usuarios', 0)}
• Total de interações: {stats.get('total_interacoes', 0)}
• Usuários ativos (7d): {stats.get('usuarios_ativos_7d', 0)}

**📅 Hoje:**
• Perguntas: {stats.get('perguntas_hoje', 0)}
• Usuários únicos: {stats.get('usuarios_hoje', 0)}
• Confiança média: {stats.get('confianca_media_hoje', 0):.1%}

**🏆 Top 5 Usuários:**
{top_users_text}

**🎯 Categoria mais perguntada:** {stats.get('categoria_mais_perguntada', 'N/A')}

**🔧 Comandos de admin:**
/backup - Gerar backup do banco
/users - Listar usuários ativos
            """
            
            await update.message.reply_text(admin_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao buscar estatísticas administrativas: {str(e)}")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /backup - Gerar backup (apenas admin)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            await update.message.reply_text("🔄 Gerando backup do banco de dados...")
            
            # Cria arquivo de backup
            backup_file = await self.backup_service.create_backup_file()
            
            # Exporta dados para estatísticas
            data = await self.database.export_to_json()
            stats_text = self.backup_service.format_backup_stats(data)
            
            # Envia arquivo
            backup_file.seek(0)  # Volta para o início do arquivo
            await update.message.reply_document(
                document=backup_file,
                caption=stats_text,
                parse_mode='Markdown'
            )
            
            logger.info(f"📤 Backup enviado para admin {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar backup: {str(e)}")
            await update.message.reply_text(f"❌ Erro ao gerar backup: {str(e)}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /users - Listar usuários (apenas admin)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            # Tenta buscar usuários, se falhar, inicializa banco
            try:
                top_users = await self.database.get_top_usuarios(10)
            except Exception as db_error:
                logger.warning(f"⚠️ Erro ao acessar usuários: {db_error}")
                await self.database.initialize()
                top_users = await self.database.get_top_usuarios(10)
            
            if not top_users:
                await update.message.reply_text("📭 Nenhum usuário encontrado")
                return
            
            users_text = "👥 **Top 10 Usuários Ativos:**\n\n"
            
            for i, user in enumerate(top_users, 1):
                nome = user.get('first_name', 'N/A')
                username = user.get('username', '')
                username_fmt = f"@{username}" if username else ""
                perguntas = user.get('total_perguntas', 0)
                
                # Formata última interação
                ultima = user.get('last_interaction', '')
                if ultima:
                    try:
                        dt = datetime.fromisoformat(ultima.replace('Z', '+00:00'))
                        ultima_fmt = dt.strftime('%d/%m %H:%M')
                    except:
                        ultima_fmt = ultima[:10]
                else:
                    ultima_fmt = 'N/A'
                
                users_text += f"{i}. **{nome}** {username_fmt}\n"
                users_text += f"   📊 {perguntas} perguntas | 🕒 {ultima_fmt}\n\n"
            
            await update.message.reply_text(users_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao listar usuários: {str(e)}")
    
    async def handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa perguntas dos usuários com fallback robusto"""
        user_data = self._extract_user_data(update)
        pergunta = update.message.text
        
        logger.info(f"❓ Pergunta de {user_data.get('first_name')} (@{user_data.get('username')}): {pergunta[:50]}...")
        
        # Registra usuário com tratamento de erro
        try:
            await self.database.registrar_usuario(user_data)
        except Exception as db_error:
            logger.warning(f"⚠️ Erro ao registrar usuário: {db_error}")
            await self.database.initialize()
            await self.database.registrar_usuario(user_data)
        
        # Envia "digitando..."
        await update.message.reply_chat_action("typing")
        
        try:
            # Chama API
            resposta_api = await self.call_api(pergunta)
            
            if resposta_api:
                # Registra interação no banco
                try:
                    await self.database.registrar_interacao(user_data["id"], pergunta, resposta_api)
                except Exception as db_error:
                    logger.warning(f"⚠️ Erro ao registrar interação: {db_error}")
                    # Continua mesmo se não conseguir registrar
                
                # Formata e envia resposta com fallback
                await self.send_formatted_response(update, resposta_api, user_data)
            else:
                await update.message.reply_text(
                    "❌ Não consegui processar sua pergunta no momento. "
                    "Verifique se a API está funcionando com /status e tente novamente."
                )
                
        except Exception as e:
            logger.error(f"Erro ao processar pergunta: {str(e)}")
            await update.message.reply_text(
                "⚠️ Ocorreu um erro interno. Nossa equipe foi notificada. "
                "Tente novamente em alguns segundos."
            )
    
    async def send_formatted_response(self, update: Update, resposta_api: dict, user_data: dict):
        """Envia resposta formatada com fallback automático"""
        try:
            # Tenta enviar com Markdown primeiro
            formatted_response = self.format_response_markdown(resposta_api)
            await update.message.reply_text(formatted_response, parse_mode='Markdown')
            logger.info(f"✅ Resposta enviada para {user_data.get('first_name')} (Markdown)")
            
        except Exception as markdown_error:
            logger.warning(f"⚠️ Erro no Markdown: {markdown_error}")
            
            try:
                # Fallback: tenta com HTML
                formatted_response = self.format_response_html(resposta_api)
                await update.message.reply_text(formatted_response, parse_mode='HTML')
                logger.info(f"✅ Resposta enviada para {user_data.get('first_name')} (HTML)")
                
            except Exception as html_error:
                logger.warning(f"⚠️ Erro no HTML: {html_error}")
                
                # Fallback final: texto simples
                resposta_simples = self.format_response_plain(resposta_api)
                await update.message.reply_text(resposta_simples)
                logger.info(f"✅ Resposta enviada para {user_data.get('first_name')} (Texto simples)")
    
    def sanitize_markdown(self, text: str) -> str:
        """Sanitiza texto para Markdown do Telegram"""
        if not text:
            return ""
        
        # Remove/substitui caracteres problemáticos
        replacements = {
            '`': "'",      # Backticks
            #'\': '/',     # Barras invertidas - CORRIGIDO
            '[': '(',      # Colchetes
            ']': ')',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        # Remove sequências de caracteres especiais
        text = re.sub(r'[*_`\[\]\]{2,}', '', text)
        
        # Escapa caracteres especiais restantes
        special_chars = ['*', '_', '`', '[', ']']
        for char in special_chars:
            text = text.replace(char, f'\{char}')
        
        return text
    
    def format_response_markdown(self, api_response: dict) -> str:
        """Formata resposta para Markdown"""
        resposta = api_response.get("resposta", "")
        categoria = api_response.get("categoria", "")
        confianca = api_response.get("confianca", 0)
        referencias = api_response.get("referencias", [])
        tempo = api_response.get("tempo_processamento", 0)
        
        # Sanitiza conteúdo
        resposta_limpa = self.sanitize_markdown(resposta)
        categoria_limpa = self.sanitize_markdown(categoria)
        
        # Limita tamanho
        if len(resposta_limpa) > 3500:
            resposta_limpa = resposta_limpa[:3500] + "\n\n[...resposta truncada...]"
        
        # Monta resposta
        formatted = f"🤖 **Resposta:**\n\n{resposta_limpa}\n\n"
        formatted += f"📊 **Categoria:** {categoria_limpa}\n"
        formatted += f"🎯 **Confiança:** {confianca:.0%}\n"
        formatted += f"⏱️ **Tempo:** {tempo:.1f}s\n"
        
        # Adiciona referências
        if referencias:
            formatted += f"\n📚 **Fontes consultadas:**\n"
            for i, ref in enumerate(referencias[:3], 1):
                arquivo = self.sanitize_markdown(ref.get("arquivo", "")).replace(".md", "")
                relevancia = ref.get("relevancia", 0)
                formatted += f"{i}. {arquivo} (relevância: {relevancia:.1%})\n"
        
        return formatted
    
    def format_response_html(self, api_response: dict) -> str:
        """Formata resposta para HTML"""
        resposta = api_response.get("resposta", "")
        categoria = api_response.get("categoria", "")
        confianca = api_response.get("confianca", 0)
        referencias = api_response.get("referencias", [])
        tempo = api_response.get("tempo_processamento", 0)
        
        # Escapa HTML
        import html
        resposta = html.escape(resposta)
        categoria = html.escape(categoria)
        
        # Limita tamanho
        if len(resposta) > 3500:
            resposta = resposta[:3500] + "\n\n[...resposta truncada...]"
        
        # Monta resposta
        formatted = f"🤖 <b>Resposta:</b>\n\n{resposta}\n\n"
        formatted += f"📊 <b>Categoria:</b> {categoria}\n"
        formatted += f"🎯 <b>Confiança:</b> {confianca:.0%}\n"
        formatted += f"⏱️ <b>Tempo:</b> {tempo:.1f}s\n"
        
        # Adiciona referências
        if referencias:
            formatted += f"\n📚 <b>Fontes consultadas:</b>\n"
            for i, ref in enumerate(referencias[:3], 1):
                arquivo = html.escape(ref.get("arquivo", "")).replace(".md", "")
                relevancia = ref.get("relevancia", 0)
                formatted += f"{i}. {arquivo} (relevância: {relevancia:.1%})\n"
        
        return formatted
    
    def format_response_plain(self, api_response: dict) -> str:
        """Formata resposta para texto simples"""
        resposta = api_response.get("resposta", "")
        categoria = api_response.get("categoria", "")
        confianca = api_response.get("confianca", 0)
        referencias = api_response.get("referencias", [])
        tempo = api_response.get("tempo_processamento", 0)
        
        # Limita tamanho
        if len(resposta) > 3500:
            resposta = resposta[:3500] + "\n\n[...resposta truncada...]"
        
        # Monta resposta simples
        formatted = f"🤖 Resposta:\n\n{resposta}\n\n"
        formatted += f"📊 Categoria: {categoria}\n"
        formatted += f"🎯 Confiança: {confianca:.0%}\n"
        formatted += f"⏱️ Tempo: {tempo:.1f}s\n"
        
        # Adiciona referências
        if referencias:
            formatted += f"\n📚 Fontes consultadas:\n"
            for i, ref in enumerate(referencias[:3], 1):
                arquivo = ref.get("arquivo", "").replace(".md", "")
                relevancia = ref.get("relevancia", 0)
                formatted += f"{i}. {arquivo} (relevância: {relevancia:.1%})\n"
        
        return formatted
    
    # Método antigo mantido para compatibilidade
    def format_response(self, api_response: dict) -> str:
        """Método de compatibilidade - usa Markdown"""
        return self.format_response_markdown(api_response)
    
    async def call_api(self, pergunta: str) -> dict:
        """Chama API de manuais"""
        # Lista de endpoints para tentar
        endpoints_to_try = [
            f"{API_BASE_URL}/pergunta",
            f"{API_BASE_URL}/api/pergunta",
            f"{API_BASE_URL}/query",
            f"{API_BASE_URL}/api/query"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                logger.info(f"🔍 Tentando endpoint: {endpoint}")
                
                response = await self.api_client.post(
                    endpoint,
                    json={"pergunta": pergunta},
                    timeout=25.0
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Sucesso no endpoint: {endpoint}")
                    return response.json()
                else:
                    logger.warning(f"⚠️ Endpoint {endpoint} retornou: {response.status_code}")
                    
            except asyncio.TimeoutError:
                logger.error(f"⏰ Timeout no endpoint: {endpoint}")
                continue
            except Exception as e:
                logger.error(f"❌ Erro no endpoint {endpoint}: {str(e)}")
                continue
        
        logger.error("❌ Todos os endpoints falharam")
        return None
    
    def _extract_user_data(self, update: Update) -> dict:
        """Extrai dados do usuário do update"""
        user = update.effective_user
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code
        }

# Instância global
agro_bot = AgroTelegramBot()
