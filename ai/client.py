"""
Wrapper do AsyncOpenAI com retry, logging e contagem de tokens.

Centraliza todas as interações com a API da OpenAI.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import tiktoken
from loguru import logger
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

from config.settings import MODEL_COSTS
from core.database import AILogRecord, get_session
from core.exceptions import AIError, AIKeyInvalidError, AIQuotaExceededError, AIRateLimitError
from utils.crypto import get_api_key, get_model


class OpenAIClient:
    """
    Wrapper assíncrono para o cliente OpenAI.

    Oferece retry automático, logging de chamadas e contagem de tokens/custo.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        """
        Inicializa o cliente OpenAI.

        Args:
            api_key: API Key (se None, carrega do crypto).
            model: Modelo a usar (se None, carrega da config).
        """
        self._api_key = api_key or get_api_key()
        self._model = model or get_model()
        self._client: Optional[AsyncOpenAI] = None
        self._total_tokens = 0
        self._total_cost = 0.0
        self._tokenizer = None

    @property
    def total_tokens(self) -> int:
        """Total de tokens usados na sessão."""
        return self._total_tokens

    @property
    def total_cost(self) -> float:
        """Custo total estimado na sessão."""
        return self._total_cost

    @property
    def model(self) -> str:
        """Modelo atual."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Define o modelo a usar."""
        self._model = value

    def _get_client(self) -> AsyncOpenAI:
        """Retorna o cliente AsyncOpenAI (cria se necessário)."""
        if self._client is None:
            if not self._api_key:
                raise AIKeyInvalidError("API Key da OpenAI não configurada")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    def _get_tokenizer(self):
        """Retorna o tokenizer para contagem de tokens."""
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.encoding_for_model(self._model)
            except KeyError:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """
        Conta os tokens em um texto.

        Args:
            text: Texto para contar tokens.

        Returns:
            Número de tokens.
        """
        enc = self._get_tokenizer()
        return len(enc.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estima o custo de uma chamada em USD.

        Args:
            input_tokens: Tokens de input.
            output_tokens: Tokens de output estimados.

        Returns:
            Custo estimado em USD.
        """
        costs = MODEL_COSTS.get(self._model, MODEL_COSTS["gpt-4o-mini"])
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost

    def estimate_batch_cost(self, texts: list[str], avg_output_tokens: int = 500) -> float:
        """
        Estima o custo total para processar um lote de textos.

        Args:
            texts: Lista de textos a processar.
            avg_output_tokens: Tokens de output estimados por chamada.

        Returns:
            Custo total estimado em USD.
        """
        total_input = sum(self.count_tokens(t) for t in texts)
        total_output = len(texts) * avg_output_tokens
        return self.estimate_cost(total_input, total_output)

    async def validate_key(self) -> bool:
        """
        Valida a API Key fazendo uma chamada de teste.

        Returns:
            True se a chave é válida.

        Raises:
            AIKeyInvalidError: Se a chave é inválida.
        """
        try:
            client = self._get_client()
            await client.models.list()
            logger.info("API Key da OpenAI validada com sucesso")
            return True
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "invalid" in error_msg.lower():
                raise AIKeyInvalidError("API Key inválida ou expirada")
            raise AIError(f"Erro ao validar API Key: {error_msg}") from e

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Optional[dict] = None,
        call_type: str = "general",
        max_retries: int = 3,
        model_override: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Faz uma chamada de chat completion com retry e logging.

        Args:
            system_prompt: Prompt do sistema.
            user_prompt: Prompt do usuário.
            response_schema: Schema JSON para structured output.
            call_type: Tipo da chamada para logging.
            max_retries: Número máximo de retentativas.
            model_override: Modelo alternativo para esta chamada específica.

        Returns:
            Dicionário com a resposta parsed.

        Raises:
            AIError: Em caso de erro irrecuperável.
        """
        client = self._get_client()
        model = model_override or self._model

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
        }

        if response_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": response_schema,
            }

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.chat.completions.create(**kwargs)

                # Extrai o conteúdo da resposta
                content = response.choices[0].message.content
                usage = response.usage

                # Atualiza contadores
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0
                cost = self.estimate_cost(prompt_tokens, completion_tokens)

                self._total_tokens += total_tokens
                self._total_cost += cost

                # Loga no banco
                self._log_call(
                    call_type=call_type,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    prompt_text=user_prompt[:2000],  # Trunca para o log
                    response_text=content[:2000] if content else "",
                )

                # Parse JSON
                if content:
                    try:
                        result = json.loads(content)
                        return result
                    except json.JSONDecodeError:
                        # Tenta extrair JSON do texto
                        import re
                        json_match = re.search(r"\{.*\}", content, re.DOTALL)
                        if json_match:
                            return json.loads(json_match.group())
                        raise AIError("Resposta da IA não contém JSON válido")

                raise AIError("Resposta vazia da IA")

            except RateLimitError as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(
                    f"Rate limit atingido (tentativa {attempt}/{max_retries}). "
                    f"Aguardando {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except (APIConnectionError, APITimeoutError) as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(
                    f"Erro de conexão (tentativa {attempt}/{max_retries}): {e}. "
                    f"Aguardando {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except AIError:
                raise

            except Exception as e:
                error_msg = str(e)
                if "insufficient_quota" in error_msg:
                    raise AIQuotaExceededError("Quota da OpenAI excedida") from e
                if "401" in error_msg:
                    raise AIKeyInvalidError("API Key inválida") from e
                last_error = e
                if attempt == max_retries:
                    break
                await asyncio.sleep(2 ** attempt)

        raise AIError(f"Falha após {max_retries} tentativas: {last_error}")

    def _log_call(
        self,
        call_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost: float,
        prompt_text: str,
        response_text: str,
    ) -> None:
        """Registra uma chamada à IA no banco de dados."""
        try:
            session = get_session()
            record = AILogRecord(
                call_type=call_type,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=cost,
                prompt_text=prompt_text,
                response_text=response_text,
            )
            session.add(record)
            session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"Erro ao registrar chamada IA no banco: {e}")

    def reset_counters(self) -> None:
        """Reseta os contadores de tokens e custo da sessão."""
        self._total_tokens = 0
        self._total_cost = 0.0

    def update_credentials(self, api_key: str, model: str) -> None:
        """
        Atualiza as credenciais e recria o cliente.

        Args:
            api_key: Nova API Key.
            model: Novo modelo.
        """
        self._api_key = api_key
        self._model = model
        self._client = None  # Força recriação
        self._tokenizer = None
        logger.info(f"Credenciais OpenAI atualizadas (modelo: {model})")


# Instância global do cliente
_global_client: Optional[OpenAIClient] = None


def get_ai_client() -> OpenAIClient:
    """Retorna a instância global do cliente OpenAI."""
    global _global_client
    if _global_client is None:
        _global_client = OpenAIClient()
    return _global_client


def reset_ai_client() -> None:
    """Reseta a instância global (usado ao trocar credenciais)."""
    global _global_client
    _global_client = None
