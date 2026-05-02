"""
Templates de prompts para a IA.

Centraliza todos os prompts usados nas chamadas à OpenAI.
"""

# ========== PARSER DE CURRÍCULO ==========

RESUME_PARSER_SYSTEM = """Você é um especialista em análise de currículos brasileiros. 
Extraia informações estruturadas do currículo fornecido de forma precisa e completa.
Retorne APENAS o JSON solicitado, sem texto adicional."""

RESUME_PARSER_USER = """Analise o currículo abaixo e extraia as informações no formato JSON especificado.

CURRÍCULO:
{resume_text}

Extraia todas as informações disponíveis. Se alguma informação não estiver presente, 
use string vazia "" para textos, 0 para números, e lista vazia [] para arrays.
Para anos_experiencia, calcule com base nas datas das experiências profissionais."""

# ========== MATCHER ==========

MATCHER_SYSTEM = """Você analisa vagas de emprego.
Sua ÚNICA tarefa: ler a descrição da vaga, extrair os requisitos técnicos QUE A VAGA PEDE, 
e verificar se o candidato possui cada um.
REGRA ABSOLUTA: Os requisitos vêm da VAGA e SOMENTE da vaga. Retorne JSON."""

MATCHER_USER = """
=== DESCRIÇÃO DA VAGA (leia PRIMEIRO) ===
Título: {vaga_titulo}
Empresa: {empresa}
Localização: {cidade}/{estado} — {modalidade}
Salário: {salario}

{descricao_vaga}

=== PERFIL DO CANDIDATO (leia DEPOIS) ===
{perfil_json}

=== TAREFA ===

PASSO 1 - EXTRAIR REQUISITOS DA VAGA:
Leia o texto da VAGA acima. Identifique APENAS as tecnologias, ferramentas, linguagens, 
formações e habilidades que a VAGA PEDE nos seus requisitos/responsabilidades.

REGRA CRÍTICA: NÃO copie a lista de skills do candidato. Os requisitos devem existir 
no texto da vaga. Se a vaga pede "Excel, Administração, Engenharia", os requisitos são 
SOMENTE esses 3 — NÃO adicione Python, SQL, JavaScript se a vaga NÃO menciona essas palavras.

REGRA DE NOMES CURTOS: O campo "nome" de cada requisito deve ter NO MÁXIMO 3-4 palavras.
Extraia APENAS o nome da skill/ferramenta/formação, SEM frases longas.
IMPORTANTE: Se a vaga lista múltiplos itens juntos (ex: "Formação em Administração, Engenharia, Economia"), SEPARE-OS em requisitos distintos!

EXEMPLOS DE NOMES CURTOS E SEPARAÇÃO:
- "Ensino superior CONCLUÍDO em análise de sistemas" → nome: "Ensino Superior Completo"
- "Formação em Administração, Engenharia, Economia" → SEPARAR EM: "Administração", "Engenharia", "Economia"
- "Experiência em desenvolvimento web com PHP" → nome: "PHP"
- "Conhecimento em metodologias ágeis" → nome: "Metodologias Ágeis"
- "Experiência com sistema ERP" → nome: "Sistema ERP"
- "Conhecimento em Excel nível intermediário" → nome: "Excel Intermediário"
- "Vivência em indústria de cosméticos" → nome: "Indústria de Cosméticos"
- "Experiência na área de PCP" → nome: "PCP"
- "CNH categoria B" → nome: "CNH B"

PASSO 2 - VERIFICAR CANDIDATO:
Para cada requisito da vaga, verifique se aparece em "skills_tecnicas" ou 
"experiencias_resumidas" do candidato. Se sim → "possui": true. Se não → false.

REGRA ESPECIAL DE FORMAÇÃO: Se o candidato possui formação superior (mesmo "Cursando"), 
isso IMPLICA que ele JÁ CONCLUIU o Ensino Médio. Portanto:
- Se a vaga pede "Ensino Médio Completo" e o candidato tem faculdade → possui: true
- Se a vaga pede "Ensino Superior Completo" e o candidato está "Cursando" → possui: false

PASSO 3 - CALCULAR SCORE:
score = (requisitos com possui=true / total de requisitos) × 100, arredondado.

Em "justificativa", 1 frase curta.
Em "email_personalizado", 2 parágrafos profissionais para candidatura (sem saudação/assinatura)."""

# ========== CARTA DE APRESENTAÇÃO ==========

COVER_LETTER_SYSTEM = """Você é um especialista em redação profissional brasileira.
Gere cartas de apresentação personalizadas, profissionais e convincentes."""

COVER_LETTER_USER = """Gere uma carta de apresentação personalizada para a vaga abaixo, 
com base no perfil do candidato.

PERFIL DO CANDIDATO:
{perfil_json}

VAGA:
Título: {vaga_titulo}
Empresa: {empresa}
Descrição: {descricao_vaga}

A carta deve:
- Ter aproximadamente 1 página (300-400 palavras)
- Ser em português brasileiro formal mas acessível
- Mencionar especificamente requisitos da vaga que o candidato atende
- Demonstrar entusiasmo genuíno pela oportunidade
- Incluir: saudação, 3-4 parágrafos, despedida
- Usar o nome do candidato na despedida

Retorne APENAS o texto da carta, sem formatação markdown."""

# ========== ANÁLISE DE CV ==========

CV_ANALYSIS_SYSTEM = """Você é um consultor de carreira sênior especializado no mercado brasileiro de TI.
Forneça feedback construtivo e acionável sobre currículos."""

CV_ANALYSIS_USER = """Com base nas {total_vagas} vagas analisadas e no perfil do candidato, 
forneça uma análise detalhada para melhorar o CV.

PERFIL DO CANDIDATO:
{perfil_json}

SKILLS MAIS PEDIDAS NAS VAGAS (com frequência):
{skills_demandadas}

VAGAS COM MAIOR MATCH (top 5):
{top_vagas}

VAGAS COM MENOR MATCH (bottom 5):
{bottom_vagas}

Forneça:
1. "skills_faltantes": lista das 10 skills mais pedidas que o candidato NÃO tem
2. "palavras_chave_sugeridas": palavras que o candidato deveria adicionar ao CV
3. "cargos_correlatos": 5 cargos alternativos que o candidato poderia buscar
4. "melhorias_gerais": 5 sugestões concretas para melhorar o CV
5. "resumo": análise geral em 3-4 frases"""
