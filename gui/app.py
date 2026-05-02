"""
Janela principal da aplicação Match Vagas.

Fluxo: Tela compacta → Progress bar → Modal de resultados.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from loguru import logger

from config.settings import get_appearance, get_email_template, get_smtp_config
from core.database import JobRecord, SearchRecord, get_session
from core.models import JobListing, MatchResult, ResumeProfile, SearchFilters, SessionStats
from gui.widgets.api_key_setup import APIKeySetupDialog
from gui.widgets.email_preview import EmailPreviewDialog
from gui.widgets.filters_panel import FiltersPanel
from gui.widgets.job_card import JobCard
from gui.widgets.settings_dialog import SettingsDialog
from utils.crypto import has_api_key
from utils.helpers import deduplicate_jobs
from utils.logger import add_gui_log_handler, gui_log_handler


class MatchVagasApp(ctk.CTk):
    """Janela principal da aplicação."""

    def __init__(self) -> None:
        super().__init__()

        # Estado
        self._profile: Optional[ResumeProfile] = None
        self._resume_path: Optional[str] = None
        self._jobs: list[tuple[JobListing, Optional[MatchResult]]] = []
        self._stats = SessionStats()
        self._cancel_event: Optional[asyncio.Event] = None
        self._is_searching = False
        self._job_cards: list[JobCard] = []
        self._results_window: Optional[ctk.CTkToplevel] = None

        # Configura aparência
        appearance = get_appearance()
        ctk.set_appearance_mode(appearance.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        # Config da janela — compacta
        self.title("🎯 Match Vagas — Caça Talentos")
        self.geometry("420x370")
        self.minsize(380, 340)
        self.resizable(False, False)

        # Registra handler de log para GUI
        add_gui_log_handler()
        gui_log_handler.register_callback(self._on_log_message)

        # Constrói UI
        self._build_ui()

        # Verifica API Key na inicialização
        self.after(500, self._check_api_key)

    def _build_ui(self) -> None:
        """Constrói o layout com 2 telas sobrepostas."""

        # === TELA 1: Painel de busca (compacto) ===
        self.filters_panel = FiltersPanel(
            self,
            on_search=self._start_search,
            on_settings=self._open_settings,
            on_resume=self._on_resume_selected,
            fg_color="transparent",
        )
        self.filters_panel.pack(fill="both", expand=True)

        # Bind cancel event
        self.filters_panel.bind("<<CancelSearch>>", lambda e: self._cancel_search())

        # === TELA 2: Progress bar (escondida inicialmente) ===
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Spacer superior para centralizar verticalmente
        self.progress_frame.grid_rowconfigure(0, weight=1)
        self.progress_frame.grid_rowconfigure(2, weight=1)
        self.progress_frame.grid_columnconfigure(0, weight=1)

        progress_content = ctk.CTkFrame(self.progress_frame, fg_color=("gray90", "gray17"), corner_radius=14)
        progress_content.grid(row=1, column=0, padx=30, sticky="ew")

        # Ícone animado
        self.progress_emoji = ctk.CTkLabel(
            progress_content, text="🔍",
            font=ctk.CTkFont(size=36),
        )
        self.progress_emoji.pack(pady=(25, 5))

        # Label de estágio
        self.stage_label = ctk.CTkLabel(
            progress_content, text="Iniciando busca...",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.stage_label.pack(pady=(0, 5))

        # Sub-label de detalhe
        self.detail_label = ctk.CTkLabel(
            progress_content, text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.detail_label.pack(pady=(0, 10))

        # Barra de progresso
        self.progress_bar = ctk.CTkProgressBar(progress_content, height=12, width=300)
        self.progress_bar.pack(padx=30, pady=(0, 5))
        self.progress_bar.set(0)

        # Label percentual
        self.pct_label = ctk.CTkLabel(
            progress_content, text="0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3b82f6",
        )
        self.pct_label.pack(pady=(0, 5))

        # Botão cancelar na tela de progresso
        self.progress_cancel_btn = ctk.CTkButton(
            progress_content, text="⏹️ Cancelar", height=34,
            font=ctk.CTkFont(size=12),
            fg_color="#ef4444", hover_color="#dc2626",
            command=self._cancel_search,
        )
        self.progress_cancel_btn.pack(pady=(5, 20))

    # ============================================================
    #  API Key
    # ============================================================

    def _check_api_key(self) -> None:
        """Verifica se a API Key está configurada."""
        if not has_api_key():
            APIKeySetupDialog(self, on_complete=self._on_api_key_set)

    def _on_api_key_set(self, result: Optional[dict]) -> None:
        """Callback após configuração da API Key."""
        if result:
            logger.info("API Key configurada com sucesso")
        else:
            logger.warning("API Key não configurada")

    def _open_settings(self) -> None:
        """Abre o diálogo de configurações."""
        SettingsDialog(self)

    # ============================================================
    #  Currículo
    # ============================================================

    def _on_resume_selected(self, path: str) -> None:
        """Callback quando um currículo é selecionado."""
        if not path:
            return

        self._resume_path = path

        def analyze():
            try:
                from ai.resume_parser import parse_resume

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                profile = loop.run_until_complete(parse_resume(path))
                loop.close()

                self._profile = profile
                self.after(0, lambda: self.filters_panel.set_resume_analyzed(os.path.basename(path)))
                logger.info(f"CV analisado: {profile.nome}")

            except Exception as e:
                logger.error(f"Erro ao analisar CV: {e}")
                self.after(0, lambda: self.filters_panel.cv_status.configure(
                    text=f"❌ Erro ao analisar CV",
                    text_color="#ef4444",
                ))

        threading.Thread(target=analyze, daemon=True).start()

    # ============================================================
    #  Transição de telas
    # ============================================================

    def _show_progress_screen(self) -> None:
        """Esconde o painel de busca e mostra a progress bar."""
        self.filters_panel.pack_forget()
        self.progress_frame.pack(fill="both", expand=True)
        self.progress_bar.set(0)
        self.pct_label.configure(text="0%")
        self.stage_label.configure(text="Iniciando busca...")
        self.detail_label.configure(text="")
        self.progress_emoji.configure(text="🔍")

    def _show_search_screen(self) -> None:
        """Volta para a tela de busca."""
        self.progress_frame.pack_forget()
        self.filters_panel.pack(fill="both", expand=True)
        self.filters_panel.set_searching(False)

    # ============================================================
    #  Pipeline de busca
    # ============================================================

    def _start_search(self) -> None:
        """Inicia o pipeline completo de busca."""
        if self._is_searching:
            return

        if not self._profile:
            # Mostra aviso rápido
            self._show_quick_warning("⚠️ Anexe um currículo antes de buscar")
            return

        if not has_api_key():
            self._show_quick_warning("⚠️ Configure sua API Key da OpenAI")
            self._check_api_key()
            return

        filters = self.filters_panel.get_filters()
        self._is_searching = True
        self._cancel_event = asyncio.Event()
        self._stats = SessionStats()
        self._jobs.clear()

        # Limpa cards anteriores
        for card in self._job_cards:
            card.destroy()
        self._job_cards.clear()

        # Transição para tela de progresso
        self.filters_panel.set_searching(True)
        self._show_progress_screen()

        def run_pipeline():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._search_pipeline(filters))
                loop.close()
            except Exception as e:
                logger.error(f"Erro no pipeline: {e}")
            finally:
                self.after(0, self._search_completed)

        threading.Thread(target=run_pipeline, daemon=True).start()

    async def _search_pipeline(self, filters: SearchFilters) -> None:
        """Pipeline assíncrono: scraping → filtragem → IA."""
        from ai.client import get_ai_client
        from ai.matcher import match_jobs_batch

        all_scraped_jobs: list[JobListing] = []

        # --- Emprega Campinas (única fonte) ---
        self.after(0, lambda: self._update_progress(
            "Buscando vagas no Emprega Campinas...", 0.0, "🌐"
        ))

        from scraper.emprega_campinas import scrape_jobs

        def on_ec_progress(msg, current, total):
            self.after(0, lambda: self._update_detail(f"{msg}"))
            if total > 0:
                self.after(0, lambda: self._set_progress(current / total * 0.3))

        try:
            ec_jobs = await scrape_jobs(
                filters=filters,
                on_progress=on_ec_progress,
                cancel_event=self._cancel_event,
                headless=True,
            )
            all_scraped_jobs.extend(ec_jobs)
            self.after(0, lambda: self._update_detail(
                f"✅ {len(ec_jobs)} vagas com e-mail encontradas"
            ))
        except Exception as e:
            logger.error(f"Erro no scraper Emprega Campinas: {e}")
            self.after(0, lambda: self._update_detail(f"❌ Erro: {e}"))

        if self._cancel_event and self._cancel_event.is_set():
            return

        # Deduplicação
        total_before = len(all_scraped_jobs)
        jobs = deduplicate_jobs(all_scraped_jobs)
        duplicates_removed = total_before - len(jobs)
        if duplicates_removed > 0:
            logger.info(f"Deduplicação: {total_before} → {len(jobs)} ({duplicates_removed} removidas)")

        # Atualiza stats
        self._stats.total_raw = len(jobs)
        self._stats.total_with_email = sum(1 for j in jobs if j.contact_emails)

        if not jobs:
            self.after(0, lambda: self._update_progress(
                "Nenhuma vaga encontrada", 1.0, "😔"
            ))
            return

        self.after(0, lambda: self._set_progress(0.35))

        # Etapa 2: Estimativa de custo
        client = get_ai_client()
        client.reset_counters()

        # Etapa 3: Match com IA
        self.after(0, lambda: self._update_progress(
            "Analisando vagas com IA...", 0.35, "🤖"
        ))
        self.after(0, lambda: self._update_detail(
            f"0 / {len(jobs)} vagas analisadas"
        ))

        def on_match_result(job, match, index):
            self._jobs.append((job, match))
            self._stats.total_matched += 1
            self._stats.tokens_used = client.total_tokens
            self._stats.estimated_cost = client.total_cost

            progress = 0.35 + (index / len(jobs)) * 0.65
            self.after(0, lambda i=index: self._update_detail(
                f"{i + 1} / {len(jobs)} vagas analisadas"
            ))
            self.after(0, lambda: self._set_progress(min(progress, 0.99)))

        results = await match_jobs_batch(
            profile=self._profile,
            jobs=jobs,
            max_concurrent=5,
            on_result=on_match_result,
            cancel_event=self._cancel_event,
        )

        # Salva busca no banco
        self._save_search_record(filters, results)

    # ============================================================
    #  Progress helpers
    # ============================================================

    def _update_progress(self, stage: str, progress: float, emoji: str = "🔍") -> None:
        """Atualiza a tela de progresso."""
        self.stage_label.configure(text=stage)
        self.progress_emoji.configure(text=emoji)
        self._set_progress(progress)

    def _update_detail(self, detail: str) -> None:
        """Atualiza o detalhe do progresso."""
        self.detail_label.configure(text=detail)

    def _set_progress(self, value: float) -> None:
        """Atualiza a barra e percentual."""
        self.progress_bar.set(value)
        self.pct_label.configure(text=f"{int(value * 100)}%")

    def _show_quick_warning(self, msg: str) -> None:
        """Mostra um aviso temporário."""
        warn = ctk.CTkToplevel(self)
        warn.title("Aviso")
        warn.geometry("320x100")
        warn.transient(self)
        warn.grab_set()
        warn.resizable(False, False)

        ctk.CTkLabel(
            warn, text=msg,
            font=ctk.CTkFont(size=13),
        ).pack(expand=True, padx=20, pady=(15, 5))

        ctk.CTkButton(
            warn, text="OK", width=80,
            command=warn.destroy,
        ).pack(pady=(0, 15))

    # ============================================================
    #  Busca concluída → Modal de resultados
    # ============================================================

    def _search_completed(self) -> None:
        """Callback quando a busca termina."""
        self._is_searching = False
        self._set_progress(1.0)
        self.stage_label.configure(text="Concluído!")
        self.progress_emoji.configure(text="✅")

        logger.info(f"Busca concluída: {len(self._jobs)} vagas analisadas")

        # Notificação desktop
        high_score = [m.score for _, m in self._jobs if m and m.score >= 90]
        if high_score:
            try:
                from plyer import notification
                notification.notify(
                    title="🎯 Match Vagas",
                    message=f"{len(high_score)} vagas com score ≥ 90%!",
                    timeout=10,
                )
            except Exception:
                pass

        # Abre modal de resultados após breve delay
        if self._jobs:
            self.after(800, self._open_results_modal)
        else:
            self.after(1500, self._show_search_screen)

    def _open_results_modal(self) -> None:
        """Abre o modal com os resultados."""
        # Volta para a tela de busca por trás
        self._show_search_screen()

        # Cria janela de resultados
        self._results_window = ctk.CTkToplevel(self)
        self._results_window.title("🎯 Resultados da Busca")
        self._results_window.geometry("900x700")
        self._results_window.minsize(700, 500)
        self._results_window.transient(self)
        self._results_window.protocol("WM_DELETE_WINDOW", self._close_results_modal)

        # Tenta maximizar
        try:
            self._results_window.state("zoomed")
        except Exception:
            pass

        # === Header ===
        header_frame = ctk.CTkFrame(
            self._results_window,
            fg_color=("gray90", "gray17"),
            corner_radius=0,
            height=50,
        )
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        visible_count = sum(1 for _, m in self._jobs if not m or m.score > 0)
        hidden_count = len(self._jobs) - visible_count

        header_text = f"🎯 {visible_count} vagas compatíveis"
        if hidden_count > 0:
            header_text += f" • {hidden_count} ocultas (0% match)"

        self.results_label = ctk.CTkLabel(
            header_frame,
            text=header_text,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.results_label.pack(side="left", padx=15, pady=10)

        # Stats compactos
        stats_text = (
            f"📊 Brutas: {self._stats.total_raw}  |  "
            f"📧 Com e-mail: {self._stats.total_with_email}  |  "
            f"🤖 Analisadas: {self._stats.total_matched}  |  "
            f"💰 Custo: ${self._stats.estimated_cost:.4f}"
        )
        ctk.CTkLabel(
            header_frame, text=stats_text,
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(side="right", padx=15)

        # === Controles ===
        controls_frame = ctk.CTkFrame(self._results_window, fg_color="transparent", height=40)
        controls_frame.pack(fill="x", padx=10, pady=(5, 0))

        # Ordenação
        self.sort_var = ctk.StringVar(value="Score ↓")
        ctk.CTkOptionMenu(
            controls_frame,
            values=["Score ↓", "Data ↓", "Salário ↓"],
            variable=self.sort_var,
            width=130, height=32,
            command=self._sort_results,
        ).pack(side="left", padx=5)

        # Botão fechar
        ctk.CTkButton(
            controls_frame, text="✕ Fechar", height=32, width=100,
            font=ctk.CTkFont(size=12),
            fg_color="gray30", hover_color="#ef4444",
            command=self._close_results_modal,
        ).pack(side="right", padx=5)

        # === ScrollableFrame para os cards ===
        self.jobs_scroll = ctk.CTkScrollableFrame(
            self._results_window,
            fg_color="transparent",
        )
        self.jobs_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Configura grid de 2 colunas
        self.jobs_scroll.grid_columnconfigure(0, weight=1)
        self.jobs_scroll.grid_columnconfigure(1, weight=1)

        # Ordena por score e filtra score=0 (nenhum requisito atendido)
        self._jobs.sort(key=lambda x: x[1].score if x[1] else 0, reverse=True)
        visible_jobs = [(j, m) for j, m in self._jobs if not m or m.score > 0]
        
        card_index = 0
        for job, match in visible_jobs:
            self._add_job_card(job, match, card_index)
            card_index += 1

    def _close_results_modal(self) -> None:
        """Fecha o modal de resultados."""
        if self._results_window:
            # Limpa cards
            for card in self._job_cards:
                card.destroy()
            self._job_cards.clear()

            self._results_window.destroy()
            self._results_window = None

    def _add_job_card(self, job: JobListing, match: Optional[MatchResult], index: int = 0) -> None:
        """Adiciona um card de vaga na lista de resultados."""
        card = JobCard(
            self.jobs_scroll,
            job=job,
            match=match,
            on_send_email=self._on_send_email,
            on_save=self._on_save_job,
            on_discard=self._on_discard_job,
            on_cover_letter=self._on_cover_letter,
            on_reanalyze=self._on_reanalyze,
        )
        # Posiciona no grid: 2 colunas
        row = index // 2
        col = index % 2
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        self._job_cards.append(card)

    # ============================================================
    #  Ações de vaga
    # ============================================================

    def _on_send_email(self, job: JobListing, match: Optional[MatchResult]) -> None:
        """Abre preview de e-mail para envio."""
        if not match or not self._profile:
            return

        from email_sender.templates import render_email_template

        template = get_email_template()
        smtp_config = get_smtp_config()

        subject, body = render_email_template(
            template["subject"], template["body"],
            self._profile, job, match, smtp_config,
        )

        recipient = job.contact_emails[0] if job.contact_emails else ""
        attachment = os.path.basename(self._resume_path) if self._resume_path else ""

        def on_send(data):
            self._send_email_action(job, data, match)

        EmailPreviewDialog(
            self._results_window or self,
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_name=attachment,
            on_send=on_send,
            dry_run=False,
        )

    def _send_email_action(self, job: JobListing, email_data: dict, match: Optional[MatchResult]) -> None:
        """Executa o envio de e-mail em thread separada."""
        def send():
            try:
                from email_sender.smtp_client import send_email

                result = send_email(
                    recipient=email_data["recipient"],
                    subject=email_data["subject"],
                    body=email_data["body"],
                    attachment_path=self._resume_path,
                    dry_run=False,
                )

                if result["success"]:
                    self._stats.emails_sent += 1
                    ts = datetime.now().strftime("%d/%m %H:%M")
                    # Marca card como enviado
                    for card in self._job_cards:
                        if card.job.external_id == job.external_id:
                            self.after(0, lambda c=card: c.mark_as_sent(ts))
                else:
                    logger.error(f"Falha no envio: {result['error']}")

            except Exception as e:
                logger.error(f"Erro ao enviar: {e}")

        threading.Thread(target=send, daemon=True).start()

    def _on_save_job(self, job: JobListing, is_saved: bool) -> None:
        """Salva/dessalva uma vaga."""
        logger.info(f"Vaga {'salva' if is_saved else 'dessalva'}: {job.title}")

    def _on_discard_job(self, job: JobListing) -> None:
        """Descarta uma vaga (adiciona empresa à blacklist da sessão)."""
        logger.info(f"Vaga descartada: {job.title} ({job.company})")

    def _on_cover_letter(self, job: JobListing, match: Optional[MatchResult]) -> None:
        """Gera carta de apresentação."""
        if not self._profile:
            return

        logger.info(f"Gerando carta para: {job.title}...")

        def generate():
            try:
                from ai.matcher import generate_cover_letter

                loop = asyncio.new_event_loop()
                letter = loop.run_until_complete(generate_cover_letter(self._profile, job))
                loop.close()

                self.after(0, lambda: self._show_text_dialog("Carta de Apresentação", str(letter)))
            except Exception as e:
                logger.error(f"Erro: {e}")

        threading.Thread(target=generate, daemon=True).start()

    def _on_reanalyze(self, job: JobListing) -> None:
        """Re-analisa vaga com modelo diferente."""
        logger.info(f"Re-analisando: {job.title}")

    def _show_text_dialog(self, title: str, text: str) -> None:
        """Mostra um diálogo com texto."""
        parent = self._results_window or self
        dialog = ctk.CTkToplevel(parent)
        dialog.title(title)
        dialog.geometry("550x450")
        dialog.transient(parent)

        textbox = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=12))
        textbox.insert("1.0", text)
        textbox.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkButton(dialog, text="Fechar", command=dialog.destroy).pack(pady=(0, 15))

    # ============================================================
    #  Ordenação
    # ============================================================

    def _sort_results(self, sort_by: str) -> None:
        """Reordena os resultados."""
        if not self._jobs:
            return

        if sort_by == "Score ↓":
            self._jobs.sort(key=lambda x: x[1].score if x[1] else 0, reverse=True)
        elif sort_by == "Salário ↓":
            self._jobs.sort(key=lambda x: x[0].salary_max or x[0].salary_min or 0, reverse=True)

        # Reconstrói cards (filtra score=0)
        for card in self._job_cards:
            card.destroy()
        self._job_cards.clear()

        visible_jobs = [(j, m) for j, m in self._jobs if not m or m.score > 0]
        for i, (job, match) in enumerate(visible_jobs):
            self._add_job_card(job, match, i)

    # ============================================================
    #  Cancelamento
    # ============================================================

    def _cancel_search(self) -> None:
        """Cancela a busca em andamento."""
        if self._cancel_event:
            self._cancel_event.set()
            self.stage_label.configure(text="Cancelando...")
            self.progress_emoji.configure(text="⏹️")

    # ============================================================
    #  Logging
    # ============================================================

    def _on_log_message(self, message: str) -> None:
        """Callback do handler de log — roda na thread do logger."""
        # Logs vão apenas para o arquivo/console, não mais para a GUI
        pass

    # ============================================================
    #  Persistência
    # ============================================================

    def _save_search_record(self, filters: SearchFilters, results) -> None:
        """Salva o registro da busca no banco."""
        try:
            session = get_session()
            record = SearchRecord(
                query=filters.query,
                filters_json=filters.model_dump_json(),
                finished_at=datetime.utcnow(),
                total_raw=self._stats.total_raw,
                total_with_email=self._stats.total_with_email,
                total_matched=self._stats.total_matched,
            )
            session.add(record)
            session.commit()

            # Salva vagas
            for job, match in results:
                try:
                    existing = session.query(JobRecord).filter_by(external_id=job.external_id).first()
                    if not existing:
                        jr = JobRecord(
                            search_id=record.id,
                            external_id=job.external_id,
                            title=job.title,
                            company=job.company,
                            city=job.city,
                            state=job.state,
                            modality=job.modality,
                            salary_text=job.salary_text,
                            salary_min=job.salary_min,
                            salary_max=job.salary_max,
                            description=job.description[:5000],
                            contact_emails=json.dumps(job.contact_emails),
                            posted_at=job.posted_at,
                            url=job.url,
                            match_score=match.score if match else None,
                            match_data_json=json.dumps({
                                "requisitos": match.requisitos,
                                "lacunas": match.lacunas,
                                "justificativa": match.justificativa,
                            }) if match else None,
                        )
                        session.add(jr)
                except Exception:
                    pass

            session.commit()
            session.close()
        except Exception as e:
            logger.warning(f"Erro ao salvar busca: {e}")
