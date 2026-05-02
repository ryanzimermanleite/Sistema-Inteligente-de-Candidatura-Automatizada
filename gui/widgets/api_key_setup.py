"""
Modal de boas-vindas para configurar a API Key da OpenAI.
"""

from __future__ import annotations

import asyncio
import threading
import webbrowser
from typing import Optional

import customtkinter as ctk
from loguru import logger

from config.settings import AVAILABLE_MODELS
from utils.crypto import save_secrets


class APIKeySetupDialog(ctk.CTkToplevel):
    """Modal de boas-vindas para configuração da API Key."""

    def __init__(self, parent, on_complete=None) -> None:
        super().__init__(parent)

        self.on_complete = on_complete
        self._show_password = False
        self.result = None

        # Config da janela
        self.title("Configure sua OpenAI")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Centraliza
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 260
        y = (self.winfo_screenheight() // 2) - 240
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self) -> None:
        """Constrói a interface do modal."""
        # Título
        ctk.CTkLabel(
            self, text="🔑 Configure sua OpenAI",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            self,
            text="Informe sua API Key para usar a IA de análise",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).pack(pady=(0, 20))

        # Frame da API Key
        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.pack(fill="x", padx=30, pady=(0, 10))

        ctk.CTkLabel(key_frame, text="API Key da OpenAI:", font=ctk.CTkFont(size=13)).pack(anchor="w")

        input_frame = ctk.CTkFrame(key_frame, fg_color="transparent")
        input_frame.pack(fill="x", pady=(5, 0))

        self.key_entry = ctk.CTkEntry(
            input_frame, show="•", placeholder_text="sk-...", height=38
        )
        self.key_entry.pack(side="left", fill="x", expand=True)

        self.toggle_btn = ctk.CTkButton(
            input_frame, text="👁️", width=40, height=38,
            command=self._toggle_visibility,
            fg_color="gray30", hover_color="gray40",
        )
        self.toggle_btn.pack(side="right", padx=(5, 0))

        # Link para obter chave
        link = ctk.CTkLabel(
            self,
            text="🔗 Não tenho uma chave — como obter?",
            font=ctk.CTkFont(size=12, underline=True),
            text_color="#3b82f6",
            cursor="hand2",
        )
        link.pack(pady=(5, 15))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://platform.openai.com/api-keys"))

        # Dropdown de modelo
        model_frame = ctk.CTkFrame(self, fg_color="transparent")
        model_frame.pack(fill="x", padx=30, pady=(0, 15))

        ctk.CTkLabel(model_frame, text="Modelo:", font=ctk.CTkFont(size=13)).pack(anchor="w")

        model_names = [name for _, name in AVAILABLE_MODELS]
        self.model_var = ctk.StringVar(value=model_names[0])
        self.model_dropdown = ctk.CTkOptionMenu(
            model_frame, values=model_names, variable=self.model_var, height=38
        )
        self.model_dropdown.pack(fill="x", pady=(5, 0))

        # Status
        self.status_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status_label.pack(pady=(0, 10))

        # Botão
        self.save_btn = ctk.CTkButton(
            self, text="✅ Validar e Salvar", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._validate_and_save,
            fg_color="#22c55e", hover_color="#16a34a",
        )
        self.save_btn.pack(fill="x", padx=30, pady=(5, 20))

    def _toggle_visibility(self) -> None:
        """Alterna visibilidade da API Key."""
        self._show_password = not self._show_password
        self.key_entry.configure(show="" if self._show_password else "•")
        self.toggle_btn.configure(text="🙈" if self._show_password else "👁️")

    def _validate_and_save(self) -> None:
        """Valida a API Key e salva criptografada."""
        api_key = self.key_entry.get().strip()
        if not api_key:
            self.status_label.configure(text="❌ Informe a API Key", text_color="#ef4444")
            return

        if not api_key.startswith("sk-"):
            self.status_label.configure(text="❌ API Key deve começar com 'sk-'", text_color="#ef4444")
            return

        self.save_btn.configure(state="disabled", text="⏳ Validando...")
        self.status_label.configure(text="Validando API Key...", text_color="gray")

        # Valida em thread separada
        def validate():
            try:
                from ai.client import OpenAIClient

                client = OpenAIClient(api_key=api_key)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(client.validate_key())
                loop.close()

                # Determina o modelo selecionado
                selected_name = self.model_var.get()
                model_id = "gpt-4o-mini"
                for mid, mname in AVAILABLE_MODELS:
                    if mname == selected_name:
                        model_id = mid
                        break

                # Salva criptografado
                save_secrets({
                    "openai_api_key": api_key,
                    "openai_model": model_id,
                })

                self.result = {"api_key": api_key, "model": model_id}

                self.after(0, self._on_success)

            except Exception as e:
                error_msg = str(e)
                self.after(0, lambda: self._on_error(error_msg))

        threading.Thread(target=validate, daemon=True).start()

    def _on_success(self) -> None:
        """Callback de sucesso na validação."""
        self.status_label.configure(text="✅ API Key válida! Salvando...", text_color="#22c55e")
        logger.info("API Key configurada com sucesso")
        self.after(800, self._close_success)

    def _on_error(self, error: str) -> None:
        """Callback de erro na validação."""
        self.save_btn.configure(state="normal", text="✅ Validar e Salvar")
        self.status_label.configure(text=f"❌ {error}", text_color="#ef4444")

    def _close_success(self) -> None:
        """Fecha o modal com sucesso."""
        if self.on_complete:
            self.on_complete(self.result)
        self.destroy()
