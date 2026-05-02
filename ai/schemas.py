"""
JSON Schemas para Structured Outputs da OpenAI.

Define os schemas usados em response_format para garantir respostas confiáveis.
"""

RESUME_SCHEMA = {
    "name": "resume_profile",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "nome": {"type": "string"},
            "email": {"type": "string"},
            "telefone": {"type": "string"},
            "cidade": {"type": "string"},
            "resumo_profissional": {"type": "string"},
            "skills_tecnicas": {
                "type": "array",
                "items": {"type": "string"},
            },
            "skills_comportamentais": {
                "type": "array",
                "items": {"type": "string"},
            },
            "anos_experiencia": {"type": "number"},
            "ultimo_cargo": {"type": "string"},
            "idiomas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "idioma": {"type": "string"},
                        "nivel": {"type": "string"},
                    },
                    "required": ["idioma", "nivel"],
                    "additionalProperties": False,
                },
            },
            "formacao": {
                "type": "array",
                "items": {"type": "string"},
            },
            "experiencias_resumidas": {
                "type": "array",
                "items": {"type": "string"},
            },
            "certificacoes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "nome",
            "email",
            "telefone",
            "cidade",
            "resumo_profissional",
            "skills_tecnicas",
            "skills_comportamentais",
            "anos_experiencia",
            "ultimo_cargo",
            "idiomas",
            "formacao",
            "experiencias_resumidas",
            "certificacoes",
        ],
        "additionalProperties": False,
    },
}

MATCH_SCHEMA = {
    "name": "match_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "requisitos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "possui": {"type": "boolean"},
                    },
                    "required": ["nome", "possui"],
                    "additionalProperties": False,
                },
            },
            "deve_aplicar": {"type": "boolean"},
            "justificativa": {"type": "string"},
            "email_personalizado": {"type": "string"},
        },
        "required": [
            "score",
            "requisitos",
            "deve_aplicar",
            "justificativa",
            "email_personalizado",
        ],
        "additionalProperties": False,
    },
}

CV_ANALYSIS_SCHEMA = {
    "name": "cv_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "skills_faltantes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "palavras_chave_sugeridas": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cargos_correlatos": {
                "type": "array",
                "items": {"type": "string"},
            },
            "melhorias_gerais": {
                "type": "array",
                "items": {"type": "string"},
            },
            "resumo": {"type": "string"},
        },
        "required": [
            "skills_faltantes",
            "palavras_chave_sugeridas",
            "cargos_correlatos",
            "melhorias_gerais",
            "resumo",
        ],
        "additionalProperties": False,
    },
}
