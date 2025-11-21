# 🌾 Bot Agrícola - API + Telegram

Sistema completo de consultas sobre máquinas agrícolas com busca semântica e bot Telegram.

## 🚀 Features

### API Principal
- ✅ Busca semântica com embeddings OpenAI
- ✅ 156+ manuais técnicos indexados
- ✅ Suporte a múltiplas marcas (Case IH, John Deere, etc.)
- ✅ API REST com FastAPI

### Bot Telegram
- ✅ Interface conversacional
- ✅ Banco de dados SQLite com backup automático
- ✅ Estatísticas de usuários e interações
- ✅ Comandos administrativos
- ✅ Sistema de backup em tempo real

## 🔗 Links

- **API:** https://bot-agro-api-rev1.onrender.com
- **Docs:** https://bot-agro-api-rev1.onrender.com/docs
- **Bot Telegram:** @agro_expert_bot

## 🧪 Teste Rápido

### API
```bash
curl -X POST https://bot-agro-api-rev1.onrender.com/pergunta \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual motor da Case IH 4150?"}'

```bash
curl -X POST "https://sua-app.onrender.com/perguntar" \
     -H "Content-Type: application/json" \
     -d '{"pergunta": "Como fazer manutenção do motor John Deere?"}'
