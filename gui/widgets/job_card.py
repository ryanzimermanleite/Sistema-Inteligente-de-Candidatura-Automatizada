"""
Card moderno de vaga — layout com seções visuais separadas.

Projetado para layout em 2 colunas com tamanho fixo.
"""

from __future__ import annotations

import re
import webbrowser
from typing import Optional

import customtkinter as ctk

from core.models import JobListing, MatchResult
from utils.helpers import format_salary, score_color, truncate_text


# ============================================================
#  Encurtar nomes de requisitos longos
# ============================================================

# Mapeamento de padrões comuns → versão curta
_SHORTEN_PATTERNS = [
    # Formação
    (r"ensino\s+superior\s+(?:completo|conclu[ií]do).*", "Ensino Superior Completo"),
    (r"ensino\s+m[eé]dio\s+completo.*", "Ensino Médio Completo"),
    (r"ensino\s+t[eé]cnico.*", "Ensino Técnico"),
    (r"gradua[çc][aã]o\s+(?:em|completa).*", "Graduação"),
    (r"p[oó]s[- ]gradua[çc][aã]o.*", "Pós-Graduação"),
    (r"superior\s+(?:completo|conclu[ií]do)\s+em.*", "Ensino Superior Completo"),
    (r"forma[çc][aã]o\s+(?:superior|acad[eê]mica).*", "Formação Superior"),
    (r"curso\s+(?:superior|t[eé]cnico)\s+em.*", "Curso Superior/Técnico"),
    # Experiência genérica
    (r"experi[eê]ncia\s+(?:com|em|na\s+[aá]rea\s+de)\s+(.+)", r"\1"),
    (r"conhecimento\s+(?:em|de|com|no|na|nos|nas|do|da)\s+(.+)", r"\1"),
    (r"viv[eê]ncia\s+(?:em|com|na|no)\s+(.+)", r"\1"),
    (r"dom[ií]nio\s+(?:de|em|do|da)\s+(.+)", r"\1"),
    (r"habilidade\s+(?:com|em|de)\s+(.+)", r"\1"),
    (r"no[çc][oõ]es\s+(?:de|em|b[aá]sicas\s+de)\s+(.+)", r"\1 (noções)"),
]


def shorten_requirement(name: str) -> str:
    """Encurta nomes de requisitos verbosos para caber em tags compactas."""
    if not name:
        return name

    original = name.strip()
    lowered = original.lower()

    # Aplica padrões de encurtamento
    for pattern, replacement in _SHORTEN_PATTERNS:
        m = re.match(pattern, lowered, re.IGNORECASE)
        if m:
            try:
                result = re.sub(pattern, replacement, lowered, flags=re.IGNORECASE)
            except Exception:
                result = replacement
            # Capitaliza primeira letra
            result = result.strip()
            if result:
                result = result[0].upper() + result[1:]
            # Se ainda ficou longo, trunca
            if len(result) > 35:
                result = result[:32] + "..."
            return result

    # Se não bateu padrão mas é muito longo, trunca inteligentemente
    if len(original) > 35:
        # Remove prefixos comuns
        for prefix in ["Experiência em ", "Experiência com ", "Conhecimento em ",
                        "Conhecimento de ", "Conhecimento com ", "Vivência em ",
                        "Vivência com ", "Domínio de ", "Domínio em ",
                        "Habilidade com ", "Habilidade em ", "Habilidade de "]:
            if lowered.startswith(prefix.lower()):
                shortened = original[len(prefix):].strip()
                if shortened:
                    shortened = shortened[0].upper() + shortened[1:]
                if len(shortened) > 35:
                    shortened = shortened[:32] + "..."
                return shortened

        return original[:32] + "..."

    return original


# ============================================================
#  Parser de benefícios — extrai e categoriza com ícones
# ============================================================

# Mapeamento de palavras-chave → (ícone, label curto)
_BENEFIT_ICONS = [
    # Alimentação
    (r"vale\s*alimenta[çc][aã]o|VA\b", "🛒", "Vale Alimentação"),
    (r"refei[çc][aã]o\s*(?:no\s*local)?|VR\b|vale\s*refei[çc][aã]o", "🍽️", "Refeição"),
    (r"cesta\s*b[aá]sica", "🧺", "Cesta Básica"),
    # Transporte
    (r"transporte\s*fretado", "🚌", "Transporte Fretado"),
    (r"vale\s*transporte|VT\b", "🚍", "Vale Transporte"),
    (r"estacionamento", "🅿️", "Estacionamento"),
    # Saúde
    (r"conv[eê]nio\s*m[eé]dico|plano\s*(?:de\s*)?sa[uú]de|m[eé]dico|Amil|Unimed|SulAm[eé]rica", "🏥", "Plano Médico"),
    (r"conv[eê]nio\s*odontol[oó]gico|odontol[oó]gico|plano\s*dental|dental", "🦷", "Plano Odontológico"),
    (r"seguro\s*(?:de\s*)?vida", "🛡️", "Seguro de Vida"),
    (r"aux[ií]lio\s*farm[aá]cia|farm[aá]cia", "💊", "Auxílio Farmácia"),
    # Financeiro
    (r"PLR|participa[çc][aã]o\s*(?:nos\s*)?(?:lucros|resultados)", "💵", "PLR"),
    (r"PPR", "💵", "PPR"),
    (r"bonus|b[oô]nus", "💰", "Bônus"),
    (r"gympass|gym\s*pass|totalpass|academia", "🏋️", "Gympass/Academia"),
    (r"aux[ií]lio\s*creche|creche", "👶", "Auxílio Creche"),
    (r"aux[ií]lio\s*educa[çc][aã]o|bolsa\s*(?:de\s*)?estudo", "📚", "Auxílio Educação"),
    (r"aux[ií]lio\s*home\s*office|home\s*office", "🏠", "Auxílio Home Office"),
    (r"day\s*off|folga\s*(?:no\s*)?anivers[aá]rio", "🎂", "Day Off Aniversário"),
    # Valor monetário genérico (R$ XXX)
    (r"R\$\s*[\d.,]+", None, None),  # Capturado como valor, adicionado ao item anterior
]


def parse_benefits(text: str) -> list[tuple[str, str]]:
    """
    Analisa texto de benefícios e retorna lista de (ícone, label).
    
    Exemplo: 'Transporte fretado, Refeição no local, Vale Alimentação de R$ 400'
    → [('🚌', 'Transporte Fretado'), ('🍽️', 'Refeição'), ('🛒', 'VA R$ 400')]
    """
    if not text or len(text.strip()) < 3:
        return []

    import re as _re

    results: list[tuple[str, str]] = []
    seen_labels: set[str] = set()

    # Divide o texto em partes por vírgula, ponto-e-vírgula ou ponto
    parts = _re.split(r'[;,\.\n]+', text)

    for part in parts:
        part = part.strip()
        if not part or len(part) < 3:
            continue

        matched = False
        for pattern, icon, label in _BENEFIT_ICONS:
            if icon is None:
                continue  # Pula o padrão de valor monetário
            if _re.search(pattern, part, _re.IGNORECASE):
                if label not in seen_labels:
                    # Tenta capturar valor monetário associado
                    val_match = _re.search(r'R\$\s*[\d.,]+', part)
                    display = label
                    if val_match:
                        display = f"{label} {val_match.group()}"
                    results.append((icon, display))
                    seen_labels.add(label)
                matched = True
                break

        # Se não bateu nenhum padrão mas tem texto útil, usa ícone genérico
        if not matched and len(part) > 4:
            # Ignora textos muito genéricos ou avisos
            skip_words = ["atenção", "nunca pague", "processo seletivo", "observações",
                          "interessados", "enviar", "currículo", "encaminhar"]
            if not any(w in part.lower() for w in skip_words):
                clean = part.strip()
                if len(clean) > 40:
                    clean = clean[:37] + "..."
                if clean not in seen_labels:
                    results.append(("✨", clean))
                    seen_labels.add(clean)

    return results


# ============================================================
#  Helpers
# ============================================================

def _detect_modality_label(modality: str) -> tuple[str, str]:
    """Retorna (emoji, label) da modalidade."""
    mod_map = {
        "presencial": ("🏢", "Presencial"),
        "remoto": ("💻", "Remoto"),
        "hibrido": ("🔄", "Híbrido"),
    }
    return mod_map.get(modality, ("🏢", modality.capitalize() if modality else "—"))


def _extract_schedule(description: str) -> str:
    """Extrai horário da descrição."""
    if not description:
        return ""
    for marker in ["Horário de Trabalho:", "Horário de trabalho:", "Horário:", "Jornada:"]:
        idx = description.find(marker)
        if idx != -1:
            snippet = description[idx + len(marker):idx + len(marker) + 120].strip()
            snippet = snippet.split("\n")[0].strip()
            if snippet:
                return snippet
    return ""


# ============================================================
#  COLORS
# ============================================================

COLORS = {
    "card_bg": ("gray92", "gray17"),
    "section_bg": ("gray88", "gray20"),
    "header_bg": ("gray90", "#1a1a2e"),
    "divider": ("gray75", "gray35"),
    "green": "#22c55e",
    "yellow": "#eab308",
    "blue": "#3b82f6",
    "red": "#ef4444",
    "purple": "#a855f7",
    "teal": "#14b8a6",
    "orange": "#f97316",
    "text_primary": ("gray10", "gray90"),
    "text_muted": ("gray40", "gray60"),
    "text_secondary": ("gray30", "gray70"),
    "border": ("gray80", "gray30"),
    "accent": ("gray85", "#16213e"),
    "tag_bg_green": ("gray82", "#1a3a1a"),
    "tag_bg_red": ("gray82", "#3a1a1a"),
}

# Altura mínima do card
CARD_MIN_HEIGHT = 320


class JobCard(ctk.CTkFrame):
    """Card moderno de vaga — com seções visuais separadas."""

    def __init__(
        self,
        parent,
        job: JobListing,
        match: Optional[MatchResult] = None,
        on_send_email=None,
        on_save=None,
        on_discard=None,
        on_cover_letter=None,
        on_reanalyze=None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            corner_radius=14,
            border_width=2,
            border_color=COLORS["border"],
            **kwargs,
        )

        self.job = job
        self.match = match
        self.on_send_email = on_send_email
        self.on_save = on_save
        self.on_discard = on_discard
        self.on_cover_letter = on_cover_letter
        self.on_reanalyze = on_reanalyze
        self._is_sent = False
        self._is_saved = False

        # Tamanho fixo mínimo
        self.configure(height=CARD_MIN_HEIGHT)

        self._build_ui()

    def _add_divider(self, parent, color=None) -> None:
        """Adiciona um separador horizontal fino."""
        ctk.CTkFrame(
            parent,
            height=1,
            fg_color=color or COLORS["divider"],
        ).pack(fill="x", padx=10, pady=0)

    def _build_ui(self) -> None:
        """Constrói o card com seções visuais separadas."""
        self.configure(fg_color=COLORS["card_bg"])

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 1: HEADER — Título + Score    ║
        # ╚══════════════════════════════════════╝
        header = ctk.CTkFrame(self, fg_color=COLORS["header_bg"], corner_radius=12)
        header.pack(fill="x", padx=6, pady=(6, 0))
        header.grid_columnconfigure(0, weight=1)

        # Título
        ctk.CTkLabel(
            header,
            text=truncate_text(self.job.title, 75),
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            wraplength=340,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        # Empresa
        if self.job.company:
            ctk.CTkLabel(
                header,
                text=f"🏢  {self.job.company}",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        # Score badge (canto superior direito)
        if self.match:
            score = self.match.score
            color = score_color(score)

            score_container = ctk.CTkFrame(header, fg_color="transparent")
            score_container.grid(row=0, column=1, rowspan=2, padx=(0, 8), pady=6)

            # Score grande
            ctk.CTkLabel(
                score_container,
                text=f"{score}%",
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=color,
            ).pack()

            # Barra de score visual
            bar_bg = ctk.CTkFrame(score_container, height=4, width=50, fg_color="gray30", corner_radius=2)
            bar_bg.pack(pady=(2, 0))
            bar_bg.pack_propagate(False)
            bar_width = max(2, int(50 * score / 100))
            ctk.CTkFrame(bar_bg, height=4, width=bar_width, fg_color=color, corner_radius=2).place(x=0, y=0)

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 2: INFO — Local + Modelo      ║
        # ╚══════════════════════════════════════╝
        self._add_divider(self)

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=4)

        # Linha 1: Localização + Modalidade
        loc_line = ctk.CTkFrame(info_frame, fg_color="transparent")
        loc_line.pack(fill="x")

        if self.job.city:
            loc = self.job.city
            if self.job.state:
                loc += f"/{self.job.state}"
            ctk.CTkLabel(
                loc_line,
                text=f"📍 {loc}",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_muted"],
            ).pack(side="left", padx=(0, 12))

        mod_emoji, mod_label = _detect_modality_label(self.job.modality)
        ctk.CTkLabel(
            loc_line,
            text=f"{mod_emoji} {mod_label}",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["teal"],
        ).pack(side="left", padx=(0, 12))

        # Horário
        schedule = _extract_schedule(self.job.description or "")
        if schedule:
            ctk.CTkLabel(
                loc_line,
                text=f"🕐 {truncate_text(schedule, 40)}",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_muted"],
            ).pack(side="left")

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 3: SALÁRIO + EMAIL             ║
        # ╚══════════════════════════════════════╝
        self._add_divider(self)

        money_frame = ctk.CTkFrame(self, fg_color="transparent")
        money_frame.pack(fill="x", padx=10, pady=4)

        salary = format_salary(self.job.salary_min, self.job.salary_max, self.job.salary_text)
        sal_color = COLORS["green"] if salary != "Não informado" else COLORS["text_muted"]
        ctk.CTkLabel(
            money_frame,
            text=f"💰 {salary}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=sal_color,
        ).pack(side="left", padx=(0, 12))

        if self.job.contact_emails:
            email_label = ctk.CTkLabel(
                money_frame,
                text=f"📧 {self.job.contact_emails[0]}",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["blue"],
                cursor="hand2",
            )
            email_label.pack(side="left")
            email_label.bind("<Button-1>", lambda e: self._copy_email())

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 4: BENEFÍCIOS (tags estilizadas)║
        # ╚══════════════════════════════════════╝
        benefits_text = self.job.benefits or ""
        # Também tenta extrair da descrição se não tem benefits separado
        if not benefits_text and self.job.description:
            import re as _re
            ben_match = _re.search(
                r"Benef[ií]cios?:\s*(.+?)(?=ATENÇÃO:|Observa[çc][oõ]es?:|Os interessados|$)",
                self.job.description, _re.DOTALL | _re.I
            )
            if ben_match:
                benefits_text = ben_match.group(1).strip()

        if benefits_text:
            parsed = parse_benefits(benefits_text)
            if parsed:
                self._add_divider(self)
                ben_section = ctk.CTkFrame(self, fg_color=COLORS["section_bg"], corner_radius=8)
                ben_section.pack(fill="x", padx=6, pady=(4, 0))

                ctk.CTkLabel(
                    ben_section,
                    text="🎁 Benefícios",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_secondary"],
                    anchor="w",
                ).pack(fill="x", padx=10, pady=(6, 4))

                self._build_benefit_tags(ben_section, parsed)

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 5: REQUISITOS (✅/❌ tags)     ║
        # ╚══════════════════════════════════════╝
        if self.match and self.match.requisitos:
            self._add_divider(self)

            req_section = ctk.CTkFrame(self, fg_color=COLORS["section_bg"], corner_radius=8)
            req_section.pack(fill="x", padx=6, pady=(4, 0))

            # Header da seção
            req_header = ctk.CTkFrame(req_section, fg_color="transparent")
            req_header.pack(fill="x", padx=8, pady=(6, 4))

            total = len(self.match.requisitos)
            has_count = sum(1 for r in self.match.requisitos if r.get("possui", False))

            ctk.CTkLabel(
                req_header,
                text=f"📋 Requisitos  ({has_count}/{total})",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(side="left")

            # Tags com wrapping — usa um Frame que permite múltiplas linhas
            self._build_requirement_tags(req_section)

        if self.match and self.match.justificativa:
            ctk.CTkLabel(
                self,
                text=f"💬 {truncate_text(self.match.justificativa, 100)}",
                font=ctk.CTkFont(size=12),
                anchor="w",
                justify="left",
                wraplength=380,
                text_color=COLORS["text_muted"],
            ).pack(fill="x", padx=12, pady=(4, 0))

        # ╔══════════════════════════════════════╗
        # ║  SEÇÃO 6: BOTÕES DE AÇÃO              ║
        # ╚══════════════════════════════════════╝
        self._add_divider(self)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(6, 8))

        # Enviar CV
        if self.job.contact_emails:
            self.send_btn = ctk.CTkButton(
                actions, text="📧 Enviar CV", height=32,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=COLORS["blue"], hover_color="#2563eb",
                command=self._on_send,
            )
            self.send_btn.pack(side="left", padx=(0, 3))
        else:
            self.send_btn = ctk.CTkButton(
                actions, text="📧 Sem e-mail", height=32,
                font=ctk.CTkFont(size=13),
                fg_color="gray40", state="disabled",
            )
            self.send_btn.pack(side="left", padx=(0, 3))

        # Abrir
        ctk.CTkButton(
            actions, text="🔗 Abrir", height=32, width=70,
            font=ctk.CTkFont(size=13),
            fg_color="#16a34a", hover_color="#15803d",
            command=lambda: webbrowser.open(self.job.url),
        ).pack(side="left", padx=(0, 3))

        # Favoritar
        self.save_btn = ctk.CTkButton(
            actions, text="⭐", height=32, width=36,
            font=ctk.CTkFont(size=14),
            fg_color="gray30", hover_color="#eab308",
            command=self._on_save,
        )
        self.save_btn.pack(side="left", padx=(0, 3))

        # Descartar
        ctk.CTkButton(
            actions, text="🚫", height=32, width=36,
            font=ctk.CTkFont(size=14),
            fg_color="gray30", hover_color="#ef4444",
            command=self._on_discard,
        ).pack(side="left")

        # Carta (direita)
        if self.on_cover_letter:
            ctk.CTkButton(
                actions, text="📝", height=32, width=36,
                font=ctk.CTkFont(size=14),
                fg_color="gray30", hover_color="gray40",
                command=lambda: self.on_cover_letter(self.job, self.match),
            ).pack(side="right")

    def _build_requirement_tags(self, parent) -> None:
        """Constrói tags de requisitos com wrapping — exibe TODOS."""
        requisitos = self.match.requisitos if self.match else []
        if not requisitos:
            return

        # Exibe TODOS os requisitos (sem limite)
        current_line = ctk.CTkFrame(parent, fg_color="transparent")
        current_line.pack(fill="x", padx=6, pady=(0, 2))

        line_width = 0
        MAX_LINE_WIDTH = 760  # dobro do anterior — cabe mais tags

        for req in requisitos:
            possui = req.get("possui", False)
            nome_raw = req.get("nome", "")
            nome = shorten_requirement(nome_raw)

            if possui:
                emoji = "✅"
                tag_color = COLORS["tag_bg_green"]
                text_color = COLORS["green"]
            else:
                emoji = "❌"
                tag_color = COLORS["tag_bg_red"]
                text_color = COLORS["red"]

            tag_text = f"{emoji} {nome}"

            # Estima largura do tag (aprox 8.5px por char + padding maior)
            estimated_width = int(len(tag_text) * 8.5) + 20

            # Se ultrapassa a largura da linha, cria nova linha
            if line_width + estimated_width > MAX_LINE_WIDTH and line_width > 0:
                current_line = ctk.CTkFrame(parent, fg_color="transparent")
                current_line.pack(fill="x", padx=6, pady=(0, 2))
                line_width = 0

            ctk.CTkLabel(
                current_line,
                text=tag_text,
                font=ctk.CTkFont(size=13),
                text_color=text_color,
                fg_color=tag_color,
                corner_radius=6,
                height=28,
                padx=8,
            ).pack(side="left", padx=3, pady=2)

            line_width += estimated_width

        # Padding inferior da seção
        ctk.CTkFrame(parent, fg_color="transparent", height=4).pack()

    def _build_benefit_tags(self, parent, benefits: list[tuple[str, str]]) -> None:
        """Constrói tags de benefícios com wrapping."""
        current_line = ctk.CTkFrame(parent, fg_color="transparent")
        current_line.pack(fill="x", padx=6, pady=(0, 2))

        line_width = 0
        MAX_LINE_WIDTH = 760

        for icon, text in benefits:
            tag_text = text
            # Estima largura do tag (aprox 8.5px por char + padding maior)
            estimated_width = int(len(tag_text) * 8.5) + 20

            if line_width + estimated_width > MAX_LINE_WIDTH and line_width > 0:
                current_line = ctk.CTkFrame(parent, fg_color="transparent")
                current_line.pack(fill="x", padx=6, pady=(0, 2))
                line_width = 0

            ctk.CTkLabel(
                current_line,
                text=tag_text,
                font=ctk.CTkFont(size=13),
                text_color=COLORS["teal"],
                fg_color=("gray82", "#1a2a3a"),
                corner_radius=6,
                height=28,
                padx=8,
            ).pack(side="left", padx=3, pady=2)

            line_width += estimated_width

        ctk.CTkFrame(parent, fg_color="transparent", height=4).pack()

    # ============================================================
    #  Callbacks
    # ============================================================

    def _copy_email(self) -> None:
        """Copia o e-mail para a área de transferência."""
        if self.job.contact_emails:
            self.clipboard_clear()
            self.clipboard_append(self.job.contact_emails[0])

    def _on_send(self) -> None:
        """Callback para enviar e-mail."""
        if self.on_send_email and not self._is_sent:
            self.on_send_email(self.job, self.match)

    def _on_save(self) -> None:
        """Callback para salvar vaga."""
        self._is_saved = not self._is_saved
        self.save_btn.configure(
            fg_color="#eab308" if self._is_saved else "gray30",
            text="★" if self._is_saved else "⭐",
        )
        if self.on_save:
            self.on_save(self.job, self._is_saved)

    def _on_discard(self) -> None:
        """Callback para descartar vaga."""
        if self.on_discard:
            self.on_discard(self.job)
        self.grid_forget()

    def mark_as_sent(self, timestamp: str = "") -> None:
        """Marca o card como enviado."""
        self._is_sent = True
        self.send_btn.configure(
            state="disabled",
            text=f"✅ Enviado{' ' + timestamp if timestamp else ''}",
            fg_color="#16a34a",
        )
