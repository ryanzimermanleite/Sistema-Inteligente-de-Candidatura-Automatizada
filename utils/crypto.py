"""
Criptografia de credenciais com Fernet.

Gerencia a chave de criptografia e encripta/decripta dados sensíveis.
"""

from __future__ import annotations

import json
import os
import stat
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from core.exceptions import CryptoError


def _get_data_dir() -> str:
    """Retorna o diretório de dados da aplicação."""
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_key_path() -> str:
    """Retorna o caminho do arquivo de chave Fernet."""
    return os.path.join(_get_data_dir(), ".key")


def _get_secrets_path() -> str:
    """Retorna o caminho do arquivo de segredos criptografados."""
    return os.path.join(_get_data_dir(), "secrets.enc")


def _get_or_create_key() -> bytes:
    """
    Obtém ou gera a chave Fernet.

    Na primeira execução, gera uma nova chave e salva com permissões restritas.

    Returns:
        Chave Fernet em bytes.
    """
    key_path = _get_key_path()

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
        logger.debug("Chave Fernet carregada do disco")
        return key

    # Gera nova chave
    key = Fernet.generate_key()

    with open(key_path, "wb") as f:
        f.write(key)

    # Tenta restringir permissões (Windows: readonly para o dono)
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows pode não suportar totalmente

    logger.info("Nova chave Fernet gerada e salva")
    return key


def _get_fernet() -> Fernet:
    """Retorna uma instância de Fernet com a chave da aplicação."""
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_string(plaintext: str) -> str:
    """
    Criptografa uma string.

    Args:
        plaintext: Texto em claro.

    Returns:
        Texto criptografado em base64.
    """
    try:
        f = _get_fernet()
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")
    except Exception as e:
        raise CryptoError(f"Erro ao criptografar: {e}") from e


def decrypt_string(ciphertext: str) -> str:
    """
    Decripta uma string.

    Args:
        ciphertext: Texto criptografado em base64.

    Returns:
        Texto em claro.
    """
    try:
        f = _get_fernet()
        decrypted = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken as e:
        raise CryptoError("Chave inválida ou dados corrompidos") from e
    except Exception as e:
        raise CryptoError(f"Erro ao decriptar: {e}") from e


def save_secrets(secrets: dict[str, str]) -> None:
    """
    Salva um dicionário de segredos criptografados.

    Args:
        secrets: Dicionário com chaves e valores a serem salvos.
    """
    try:
        # Carrega segredos existentes e faz merge
        existing = load_secrets()
        existing.update(secrets)

        # Serializa e criptografa
        plaintext = json.dumps(existing, ensure_ascii=False)
        encrypted = encrypt_string(plaintext)

        secrets_path = _get_secrets_path()
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.write(encrypted)

        logger.info(f"Segredos salvos com sucesso ({len(secrets)} chaves atualizadas)")
    except CryptoError:
        raise
    except Exception as e:
        raise CryptoError(f"Erro ao salvar segredos: {e}") from e


def load_secrets() -> dict[str, str]:
    """
    Carrega e decripta os segredos salvos.

    Returns:
        Dicionário com os segredos. Vazio se não existir arquivo.
    """
    secrets_path = _get_secrets_path()

    if not os.path.exists(secrets_path):
        return {}

    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            encrypted = f.read()

        if not encrypted.strip():
            return {}

        plaintext = decrypt_string(encrypted)
        return json.loads(plaintext)
    except CryptoError:
        raise
    except Exception as e:
        logger.warning(f"Não foi possível carregar segredos: {e}")
        return {}


def get_secret(key: str) -> Optional[str]:
    """
    Retorna um segredo específico.

    Args:
        key: Nome do segredo.

    Returns:
        Valor do segredo ou None se não existir.
    """
    secrets = load_secrets()
    return secrets.get(key)


def has_api_key() -> bool:
    """Verifica se a API Key da OpenAI está configurada."""
    key = get_secret("openai_api_key")
    return key is not None and len(key) > 0


def get_api_key() -> Optional[str]:
    """Retorna a API Key da OpenAI."""
    return get_secret("openai_api_key")


def get_model() -> str:
    """Retorna o modelo da OpenAI configurado."""
    model = get_secret("openai_model")
    return model if model else "gpt-4o-mini"


def get_smtp_password() -> Optional[str]:
    """Retorna a senha SMTP."""
    return get_secret("smtp_password")
