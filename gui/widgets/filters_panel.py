"""
Painel compacto de busca — currículo, cargo, score e ações.
"""

from __future__ import annotations

import os
from typing import Optional

import customtkinter as ctk

from core.models import SearchFilters


class FiltersPanel(ctk.CTkFrame):
    """Painel compacto com os controles essenciais de busca."""

    def __init__(self, parent, on_search=None, on_settings=None, on_resume=None, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        self.on_search = on_search
        self.on_settings = on_settings
        self.on_resume = on_resume
        self._resume_path: Optional[str] = None
        self._resume_analyzed = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Constrói a interface compacta."""

        # === CURRÍCULO ===
        ctk.CTkLabel(
            self, text="📋 Currículo",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(15, 4), padx=15)

        self.attach_btn = ctk.CTkButton(
            self, text="📎 Anexar Currículo", height=40,
            font=ctk.CTkFont(size=13),
            command=self._attach_resume,
        )
        self.attach_btn.pack(fill="x", padx=15, pady=(0, 2))

        self.cv_status = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.cv_status.pack(fill="x", padx=15, pady=(0, 8))

        # === BUSCA ===
        ctk.CTkLabel(
            self, text="🔍 Cargo / Palavra-chave",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(8, 4), padx=15)

        self.query_entry = ctk.CTkEntry(
            self, placeholder_text="Ex: Programador Java Pleno", height=40,
            font=ctk.CTkFont(size=13),
        )
        self.query_entry.pack(fill="x", padx=15, pady=(0, 10))

        # === BOTÕES ===
        self.search_btn = ctk.CTkButton(
            self, text="🚀 Iniciar Busca", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#3b82f6", hover_color="#2563eb",
            command=self._start_search,
        )
        self.search_btn.pack(fill="x", padx=15, pady=(5, 5))

        self.cancel_btn = ctk.CTkButton(
            self, text="⏹️ Cancelar Busca", height=38,
            font=ctk.CTkFont(size=13),
            fg_color="#ef4444", hover_color="#dc2626",
            command=self._cancel_search,
        )
        self.cancel_btn.pack(fill="x", padx=15, pady=(0, 5))
        self.cancel_btn.pack_forget()  # Esconde inicialmente

        ctk.CTkButton(
            self, text="⚙️ Configurações", height=38,
            font=ctk.CTkFont(size=13),
            fg_color="gray30", hover_color="gray40",
            command=lambda: self.on_settings() if self.on_settings else None,
        ).pack(fill="x", padx=15, pady=(5, 15))



    def _attach_resume(self) -> None:
        """Abre diálogo para selecionar currículo."""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title="Selecione seu Currículo",
            filetypes=[
                ("Documentos", "*.pdf *.docx"),
                ("PDF", "*.pdf"),
                ("DOCX", "*.docx"),
            ],
        )
        if file_path:
            self._resume_path = file_path
            fname = os.path.basename(file_path)
            self.cv_status.configure(
                text=f"📄 {fname}\n⏳ Analisando com IA...",
                text_color="#eab308",
            )
            # Chama callback direto no app principal
            if self.on_resume:
                self.on_resume(file_path)

    def set_resume_analyzed(self, name: str) -> None:
        """Atualiza o status após análise do CV."""
        self._resume_analyzed = True
        self.cv_status.configure(
            text=f"📄 {name}\n✅ Currículo analisado pela IA",
            text_color="#22c55e",
        )
        self.attach_btn.configure(text="🔄 Trocar Currículo")

    def get_resume_path(self) -> Optional[str]:
        """Retorna o caminho do currículo anexado."""
        return self._resume_path

    def get_filters(self) -> SearchFilters:
        """Coleta e retorna os filtros configurados."""
        return SearchFilters(
            query=self.query_entry.get().strip() or "programador",
            city="",
            state="SP",
            modalities=[],
            salary_min=None,
            salary_max=None,
            min_score=0,
        )

    def set_searching(self, searching: bool) -> None:
        """Alterna entre estado de busca e idle."""
        if searching:
            self.search_btn.configure(state="disabled", text="⏳ Buscando...")
            self.cancel_btn.pack(fill="x", padx=15, pady=(0, 5))
        else:
            self.search_btn.configure(state="normal", text="🚀 Iniciar Busca")
            self.cancel_btn.pack_forget()

    def _start_search(self) -> None:
        """Inicia a busca."""
        if self.on_search:
            self.on_search()

    def _cancel_search(self) -> None:
        """Cancela a busca."""
        self.event_generate("<<CancelSearch>>")
