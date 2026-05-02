# 🎯 Match Vagas — Sistema de Match Automático com IA

Sistema desktop em Python que automatiza busca, análise e candidatura em vagas de emprego no portal **Emprega Campinas**, usando IA da OpenAI para match inteligente entre currículo e vagas.

## ✨ Funcionalidades

- 📎 **Análise de Currículo com IA** — Extrai perfil estruturado de PDF/DOCX
- 🕷️ **Web Scraping Inteligente** — Busca vagas no Emprega Campinas com anti-detecção
- 📧 **Filtro por E-mail** — Só mostra vagas com e-mail do recrutador na descrição
- 🤖 **Match com IA** — Score de compatibilidade (0-100%) entre perfil e vaga
- ✉️ **Envio Automatizado** — E-mail personalizado com currículo anexado
- 📝 **Carta de Apresentação** — Gerada pela IA sob demanda
- 💡 **Análise de CV** — Sugestões de melhoria baseadas nas vagas
- 🧪 **Modo Dry Run** — Testa sem enviar e-mails reais
- 🔔 **Notificações Desktop** — Alerta ao encontrar vagas com score ≥ 90%
- 🔐 **Segurança** — Credenciais criptografadas com Fernet

## 📋 Pré-requisitos

- **Python 3.11+**
- **API Key da OpenAI** ([obter aqui](https://platform.openai.com/api-keys))
- **Playwright browsers** (instalados automaticamente)

## 🚀 Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/match-vagas.git
cd match-vagas/match_vagas

# 2. Crie um ambiente virtual (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Instale o browser do Playwright
playwright install chromium

# 5. Execute
python main.py
```

## 🎮 Como Usar

1. **Na primeira execução**, configure sua API Key da OpenAI no modal de boas-vindas
2. **Anexe seu currículo** (PDF ou DOCX) — a IA analisará automaticamente
3. **Configure os filtros** de busca (cargo, cidade, modalidade, etc.)
4. **Clique em "🚀 Iniciar Busca"** — o sistema irá:
   - Buscar vagas no Emprega Campinas
   - Filtrar apenas vagas com e-mail do recrutador
   - Analisar cada vaga com IA e gerar score de match
5. **Revise as vagas** ordenadas por score
6. **Envie candidaturas** com e-mail personalizado pela IA

## ⚙️ Configurações

Acesse **⚙️ Configurações** para:
- **OpenAI**: Trocar API Key e modelo (gpt-4o-mini recomendado)
- **E-mail (SMTP)**: Configurar servidor, porta, credenciais
- **Template**: Editar modelo de e-mail com variáveis
- **Aparência**: Dark/Light mode, tamanho da fonte

## 💰 Custos da OpenAI

| Modelo | Custo por 50 vagas (aprox.) |
|--------|---------------------------|
| gpt-4o-mini | ~US$ 0.01 |
| gpt-4o | ~US$ 0.15 |
| gpt-4-turbo | ~US$ 0.50 |
| gpt-3.5-turbo | ~US$ 0.03 |

## 📁 Estrutura do Projeto

```
match_vagas/
├── main.py                  # Entry point
├── requirements.txt         # Dependências
├── config/                  # Configurações e prompts
├── core/                    # Modelos, banco de dados, exceções
├── scraper/                 # Web scraping + extração de e-mail
├── ai/                      # Cliente OpenAI, parser de CV, matcher
├── email_sender/            # SMTP + templates
├── gui/                     # Interface CustomTkinter
├── utils/                   # Logger, crypto, helpers
└── data/                    # SQLite, logs, uploads (gerado na 1ª execução)
```

## ❓ FAQ e Troubleshooting

### API Key inválida
- Verifique se a key começa com `sk-`
- Confirme que tem créditos na conta da OpenAI

### SMTP recusado (Gmail)
- Ative "Senhas de App" em myaccount.google.com
- Use a senha de app em vez da senha da conta
- Porta 587 com TLS ativado

### Scraping bloqueado
- O sistema usa anti-detecção automática
- Tente novamente após alguns minutos
- Aumente o delay entre páginas nas configurações

## 📄 Licença

MIT License
