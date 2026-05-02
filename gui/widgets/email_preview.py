"""
Modal de preview e edição de e-mail antes do envio.
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk


class EmailPreviewDialog(ctk.CTkToplevel):
    """Modal para preview e edição do e-mail antes do envio."""

    def __init__(
        self,
        parent,
        recipient: str,
        subject: str,
        body: str,
        attachment_name: str = "",
        on_send=None,
        dry_run: bool = False,
    ) -> None:
        super().__init__(parent)

        self.on_send = on_send
        self.result = None

        self.title("Preview do E-mail")
        self.geometry("600x550")
        self.transient(parent)
        self.grab_set()

        # Centraliza
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 300
        y = (self.winfo_screenheight() // 2) - 275
        self.geometry(f"+{x}+{y}")

        self._build_ui(recipient, subject, body, attachment_name, dry_run)

    def _build_ui(
        self, recipient: str, subject: str, body: str,
        attachment_name: str, dry_run: bool,
    ) -> None:
        """Constrói a interface do preview."""

        ctk.CTkLabel(
            self, text="📧 Preview do E-mail",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(15, 10))

        # Destinatário
        ctk.CTkLabel(self, text="Para:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.to_entry = ctk.CTkEntry(self, height=32)
        self.to_entry.insert(0, recipient)
        self.to_entry.pack(fill="x", padx=20, pady=(2, 8))

        # Assunto
        ctk.CTkLabel(self, text="Assunto:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.subject_entry = ctk.CTkEntry(self, height=32)
        self.subject_entry.insert(0, subject)
        self.subject_entry.pack(fill="x", padx=20, pady=(2, 8))

        # Corpo
        ctk.CTkLabel(self, text="Corpo:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.body_text = ctk.CTkTextbox(self, height=250, font=ctk.CTkFont(size=12))
        self.body_text.insert("1.0", body)
        self.body_text.pack(fill="both", expand=True, padx=20, pady=(2, 8))

        # Anexo
        if attachment_name:
            ctk.CTkLabel(
                self, text=f"📎 Anexo: {attachment_name}",
                font=ctk.CTkFont(size=11), text_color="gray",
            ).pack(anchor="w", padx=20, pady=(0, 8))

        # Botões
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 15))

        prefix = "🧪 " if dry_run else ""
        ctk.CTkButton(
            btn_frame,
            text=f"{prefix}Enviar agora",
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#22c55e" if not dry_run else "#eab308",
            hover_color="#16a34a" if not dry_run else "#ca8a04",
            command=self._send,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btn_frame, text="Cancelar", height=38,
            font=ctk.CTkFont(size=13),
            fg_color="gray30", hover_color="gray40",
            command=self.destroy,
        ).pack(side="right", fill="x", expand=True, padx=(5, 0))

    def _send(self) -> None:
        """Envia o e-mail."""
        self.result = {
            "recipient": self.to_entry.get(),
            "subject": self.subject_entry.get(),
            "body": self.body_text.get("1.0", "end-1c"),
        }
        if self.on_send:
            self.on_send(self.result)
        self.destroy()
