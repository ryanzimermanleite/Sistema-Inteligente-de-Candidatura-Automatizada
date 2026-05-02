"""
Exceções customizadas da aplicação.
"""


class MatchVagasError(Exception):
    """Exceção base da aplicação."""

    pass


class ScraperError(MatchVagasError):
    """Erro durante web scraping."""

    pass


class ScraperTimeoutError(ScraperError):
    """Timeout durante scraping."""

    pass


class ScraperBlockedError(ScraperError):
    """Scraper detectado e bloqueado pelo site."""

    pass


class AIError(MatchVagasError):
    """Erro ao interagir com a API da OpenAI."""

    pass


class AIKeyInvalidError(AIError):
    """API Key da OpenAI inválida ou expirada."""

    pass


class AIQuotaExceededError(AIError):
    """Quota da OpenAI excedida."""

    pass


class AIRateLimitError(AIError):
    """Rate limit da OpenAI atingido."""

    pass


class ResumeParsingError(MatchVagasError):
    """Erro ao processar currículo."""

    pass


class ResumeFileTooLargeError(ResumeParsingError):
    """Arquivo de currículo excede 10MB."""

    pass


class ResumeUnsupportedFormatError(ResumeParsingError):
    """Formato de currículo não suportado."""

    pass


class EmailError(MatchVagasError):
    """Erro ao enviar e-mail."""

    pass


class SmtpConnectionError(EmailError):
    """Erro de conexão SMTP."""

    pass


class SmtpAuthError(EmailError):
    """Erro de autenticação SMTP."""

    pass


class CryptoError(MatchVagasError):
    """Erro de criptografia."""

    pass


class DatabaseError(MatchVagasError):
    """Erro do banco de dados."""

    pass
