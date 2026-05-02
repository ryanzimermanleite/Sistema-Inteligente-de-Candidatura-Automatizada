"""
Diálogo de configurações com abas para OpenAI, SMTP, Template, Aparência.
"""

from __future__ import annotations

import asyncio
import json
import threading
import webbrowser

import customtkinter as ctk
from loguru import logger

from config.settings import (
    AVAILABLE_MODELS,
    get_appearance,
    get_email_template,
    get_smtp_config,
    save_appearance,
    save_email_template,
    save_smtp_config,
)
from utils.crypto import get_api_key, get_model, get_smtp_password, save_secrets


class SettingsDialog(ctk.CTkToplevel):
    """Diálogo de configurações com múltiplas abas."""

    def __init__(self, parent, on_save=None) -> None:
        super().__init__(parent)

        self.on_save = on_save
        self.title("⚙️ Configurações")
        self.geometry("580x520")
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 290
        y = (self.winfo_screenheight() // 2) - 260
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self) -> None:
        """Constrói interface com tabs."""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        self._build_openai_tab()
        self._build_smtp_tab()
        self._build_template_tab()
        self._build_appearance_tab()

    def _build_openai_tab(self) -> None:
        """Aba OpenAI."""
        tab = self.tabview.add("OpenAI")

        ctk.CTkLabel(tab, text="API Key:", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(10, 2))
        self.api_key_entry = ctk.CTkEntry(tab, show="•", height=36)
        current_key = get_api_key() or ""
        if current_key:
            self.api_key_entry.insert(0, current_key)
        self.api_key_entry.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(tab, text="Modelo:", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(5, 2))
        model_names = [name for _, name in AVAILABLE_MODELS]
        current_model = get_model()
        current_name = model_names[0]
        for mid, mname in AVAILABLE_MODELS:
            if mid == current_model:
                current_name = mname
        self.model_var = ctk.StringVar(value=current_name)
        ctk.CTkOptionMenu(tab, values=model_names, variable=self.model_var, height=36).pack(fill="x", pady=(0, 10))

        self.openai_status = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=12))
        self.openai_status.pack(pady=(5, 5))

        ctk.CTkButton(
            tab, text="✅ Validar e Salvar", height=38,
            fg_color="#22c55e", hover_color="#16a34a",
            command=self._save_openai,
        ).pack(fill="x", pady=(5, 10))

    def _build_smtp_tab(self) -> None:
        """Aba SMTP."""
        tab = self.tabview.add("E-mail (SMTP)")
        config = get_smtp_config()

        fields = [
            ("Servidor SMTP:", "host", config.get("host", "smtp.gmail.com")),
            ("Porta:", "port", str(config.get("port", "587"))),
            ("Usuário (e-mail):", "username", config.get("username", "")),
            ("Nome do remetente:", "sender_name", config.get("sender_name", "")),
        ]
        self.smtp_entries = {}
        for label, key, default in fields:
            ctk.CTkLabel(tab, text=label, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 0))
            entry = ctk.CTkEntry(tab, height=32)
            entry.insert(0, default)
            entry.pack(fill="x", pady=(0, 3))
            self.smtp_entries[key] = entry

        ctk.CTkLabel(tab, text="Senha:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 0))
        self.smtp_password = ctk.CTkEntry(tab, show="•", height=32)
        pwd = get_smtp_password() or ""
        if pwd:
            self.smtp_password.insert(0, pwd)
        self.smtp_password.pack(fill="x", pady=(0, 3))

        self.tls_var = ctk.BooleanVar(value=config.get("use_tls", True))
        ctk.CTkCheckBox(tab, text="Usar TLS", variable=self.tls_var).pack(anchor="w", pady=(5, 5))

        ctk.CTkLabel(tab, text="Assinatura:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 0))
        self.smtp_signature = ctk.CTkTextbox(tab, height=60, font=ctk.CTkFont(size=11))
        self.smtp_signature.insert("1.0", config.get("signature", ""))
        self.smtp_signature.pack(fill="x", pady=(0, 5))

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))
        ctk.CTkButton(btn_frame, text="💾 Salvar", height=34, command=self._save_smtp, fg_color="#22c55e").pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_frame, text="🧪 Testar", height=34, command=self._test_smtp, fg_color="#3b82f6").pack(side="right", fill="x", expand=True)

    def _build_template_tab(self) -> None:
        """Aba Template."""
        tab = self.tabview.add("Template")
        template = get_email_template()

        ctk.CTkLabel(tab, text="Assunto:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10, 2))
        self.template_subject = ctk.CTkEntry(tab, height=32)
        self.template_subject.insert(0, template.get("subject", ""))
        self.template_subject.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(tab, text="Corpo:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 2))
        self.template_body = ctk.CTkTextbox(tab, height=200, font=ctk.CTkFont(size=11))
        self.template_body.insert("1.0", template.get("body", ""))
        self.template_body.pack(fill="both", expand=True, pady=(0, 5))

        vars_text = "Variáveis: {vaga_titulo}, {empresa}, {ai_paragrafo}, {meu_nome}, {meu_email}, {meu_telefone}, {minha_assinatura}, {data}"
        ctk.CTkLabel(tab, text=vars_text, font=ctk.CTkFont(size=10), text_color="gray", wraplength=500).pack(pady=(0, 5))

        ctk.CTkButton(tab, text="💾 Salvar Template", height=34, fg_color="#22c55e", command=self._save_template).pack(fill="x")

    def _build_appearance_tab(self) -> None:
        """Aba Aparência."""
        tab = self.tabview.add("Aparência")
        config = get_appearance()

        ctk.CTkLabel(tab, text="Tema:", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(15, 5))
        self.theme_var = ctk.StringVar(value=config.get("theme", "dark"))
        ctk.CTkOptionMenu(tab, values=["dark", "light", "system"], variable=self.theme_var, height=36).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(tab, text="Tamanho da fonte:", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(10, 5))
        self.font_var = ctk.IntVar(value=config.get("font_size", 14))
        ctk.CTkSlider(tab, from_=10, to=20, variable=self.font_var).pack(fill="x", pady=(0, 15))

        ctk.CTkButton(tab, text="💾 Salvar", height=36, fg_color="#22c55e", command=self._save_appearance).pack(fill="x")

    def _save_openai(self) -> None:
        """Salva configurações OpenAI."""
        api_key = self.api_key_entry.get().strip()
        selected = self.model_var.get()
        model_id = "gpt-4o-mini"
        for mid, mname in AVAILABLE_MODELS:
            if mname == selected:
                model_id = mid

        if api_key:
            self.openai_status.configure(text="⏳ Validando...", text_color="gray")

            def validate():
                try:
                    from ai.client import OpenAIClient, reset_ai_client
                    client = OpenAIClient(api_key=api_key)
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(client.validate_key())
                    loop.close()
                    save_secrets({"openai_api_key": api_key, "openai_model": model_id})
                    reset_ai_client()
                    self.after(0, lambda: self.openai_status.configure(text="✅ Salvo!", text_color="#22c55e"))
                except Exception as e:
                    self.after(0, lambda: self.openai_status.configure(text=f"❌ {e}", text_color="#ef4444"))

            threading.Thread(target=validate, daemon=True).start()

    def _save_smtp(self) -> None:
        """Salva configurações SMTP."""
        config = {
            "host": self.smtp_entries["host"].get(),
            "port": int(self.smtp_entries["port"].get() or "587"),
            "username": self.smtp_entries["username"].get(),
            "sender_name": self.smtp_entries["sender_name"].get(),
            "use_tls": self.tls_var.get(),
            "signature": self.smtp_signature.get("1.0", "end-1c"),
        }
        save_smtp_config(config)

        pwd = self.smtp_password.get()
        if pwd:
            save_secrets({"smtp_password": pwd})

        logger.info("Configurações SMTP salvas")

    def _test_smtp(self) -> None:
        """Testa conexão SMTP."""
        self._save_smtp()
        try:
            from email_sender.smtp_client import test_smtp_connection
            config = get_smtp_config()
            test_smtp_connection(config)
            logger.info("Teste SMTP: OK")
        except Exception as e:
            logger.error(f"Teste SMTP falhou: {e}")

    def _save_template(self) -> None:
        """Salva template de e-mail."""
        template = {
            "subject": self.template_subject.get(),
            "body": self.template_body.get("1.0", "end-1c"),
        }
        save_email_template(template)
        logger.info("Template de e-mail salvo")

    def _save_appearance(self) -> None:
        """Salva configurações de aparência."""
        config = {"theme": self.theme_var.get(), "font_size": self.font_var.get()}
        save_appearance(config)
        ctk.set_appearance_mode(config["theme"])
        logger.info("Aparência salva")
