import copy
import customtkinter as ctk
from tkinter import filedialog
import threading
import os
from state_manager import StateManager
from ai_handler import AIHandler


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.sm = StateManager()
        self.ai = AIHandler(self.sm)
        config = self.sm.load_app_config()
        self.title("Infinite AI Book Series Generator")
        self.geometry(config.get("window_size", "1000x750"))
        self.is_generating = False
        self.current_loaded_series_dir = None
        self.is_ai_tested_and_working = False
        self._suspend_auto_save = False
        self.provider_settings = copy.deepcopy(config.get("provider_settings", self.sm.get_default_provider_settings()))
        self._active_provider = config.get("api_provider", "OpenAI")

        self.tabview = ctk.CTkTabview(self, command=self.update_action_button)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=5)
        self.tab_ai = self.tabview.add("AI")
        self.tab_new = self.tabview.add("New Series")
        self.tab_continue = self.tabview.add("Continue Series")
        self.tab_settings = self.tabview.add("Settings")
        self._init_variables(config)
        self._build_ai_tab()
        self._build_new_series_tab()
        self._build_continue_series_tab()
        self._build_settings_tab()
        self.log_frame = ctk.CTkFrame(self, height=30)
        self.log_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.log_label = ctk.CTkLabel(self.log_frame, text="", text_color="red", wraplength=900)
        self.log_label.pack(pady=2, padx=10)
        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Idle", width=250, anchor="w")
        self.status_label.pack(side="left", padx=10)
        self.progress_bar = ctk.CTkProgressBar(self.bottom_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=10)
        self.action_btn = ctk.CTkButton(self.bottom_frame, text="Start", state="disabled")
        self.action_btn.pack(side="right", padx=10)
        self.update_action_button()

    def _trace_var(self, tk_var, callback=None):
        tk_var.trace_add("write", callback or self._auto_save)

    def _init_variables(self, config):
        provider = config.get("api_provider", "OpenAI")
        self.api_provider_var = ctk.StringVar(value=provider)
        self.api_mode_var = ctk.StringVar(value=config.get("api_mode", "Cloud"))
        self.api_model_var = ctk.StringVar(value="")
        self.api_key_var = ctk.StringVar(value="")
        self.local_url_var = ctk.StringVar(value=config.get("local_url", ""))
        self.cloud_temperature_var = ctk.StringVar(value="")
        self.max_completion_tokens_var = ctk.StringVar(value="")
        self.openai_reasoning_effort_var = ctk.StringVar(value="")
        self.anthropic_max_tokens_var = ctk.StringVar(value="")
        self.anthropic_thinking_enabled_var = ctk.BooleanVar(value=False)
        self.anthropic_thinking_effort_var = ctk.StringVar(value="")
        self.google_max_output_tokens_var = ctk.StringVar(value="")
        self.google_top_p_var = ctk.StringVar(value="")
        self.google_top_k_var = ctk.StringVar(value="")
        self.google_thinking_mode_var = ctk.StringVar(value="")
        self.google_thinking_level_var = ctk.StringVar(value="")
        self.google_thinking_budget_var = ctk.StringVar(value="")
        self.window_size_var = ctk.StringVar(value=config.get("window_size", "1000x750"))
        self.cooldown_enabled_var = ctk.BooleanVar(value=config.get("cooldown_enabled", False))
        self.cooldown_minutes_var = ctk.StringVar(value=str(config.get("cooldown_minutes", 10.0)))
        self.ns_name_var = ctk.StringVar(value=config.get("ns_name", ""))
        self.ns_lang_var = ctk.StringVar(value=config.get("ns_lang", "English"))
        self.ns_freq_var = ctk.StringVar(value=config.get("ns_freq", "3"))
        self.ns_points_var = ctk.StringVar(value=config.get("ns_points", "12"))
        self.ns_guide_first_val = config.get("ns_guide_first", "")
        self.ns_guide_series_val = config.get("ns_guide_series", "")

        tracked_vars = [
            self.api_model_var,
            self.api_mode_var,
            self.api_key_var,
            self.local_url_var,
            self.cloud_temperature_var,
            self.max_completion_tokens_var,
            self.openai_reasoning_effort_var,
            self.anthropic_max_tokens_var,
            self.anthropic_thinking_effort_var,
            self.google_max_output_tokens_var,
            self.google_top_p_var,
            self.google_top_k_var,
            self.google_thinking_mode_var,
            self.google_thinking_level_var,
            self.google_thinking_budget_var,
            self.cooldown_minutes_var,
            self.ns_name_var,
            self.ns_lang_var,
            self.ns_freq_var,
            self.ns_points_var,
        ]
        for var in tracked_vars:
            self._trace_var(var)

        self._trace_var(self.cooldown_enabled_var)
        self.window_size_var.trace_add("write", self._on_window_size_change)
        self.anthropic_thinking_enabled_var.trace_add("write", self._on_anthropic_thinking_toggle)
        self.google_thinking_mode_var.trace_add("write", self._on_google_thinking_mode_change)

        self._load_provider_settings_into_vars(provider)

    def _current_provider_values(self):
        return {
            "model": self.api_model_var.get().strip(),
            "temperature": self.cloud_temperature_var.get().strip(),
            "max_completion_tokens": self.max_completion_tokens_var.get().strip(),
            "reasoning_effort": self.openai_reasoning_effort_var.get().strip(),
            "anthropic_max_tokens": self.anthropic_max_tokens_var.get().strip(),
            "anthropic_thinking_enabled": bool(self.anthropic_thinking_enabled_var.get()),
            "anthropic_thinking_effort": self.anthropic_thinking_effort_var.get().strip(),
            "google_max_output_tokens": self.google_max_output_tokens_var.get().strip(),
            "google_top_p": self.google_top_p_var.get().strip(),
            "google_top_k": self.google_top_k_var.get().strip(),
            "google_thinking_mode": self.google_thinking_mode_var.get().strip(),
            "google_thinking_level": self.google_thinking_level_var.get().strip(),
            "google_thinking_budget": self.google_thinking_budget_var.get().strip(),
        }

    def _save_current_provider_values(self):
        provider = self.api_provider_var.get()
        self.provider_settings[provider] = self._current_provider_values()
        self.sm.save_api_key(provider, self.api_key_var.get())

    def _load_provider_settings_into_vars(self, provider):
        settings = copy.deepcopy(self.sm.get_default_provider_settings().get(provider, {}))
        settings.update(self.provider_settings.get(provider, {}))

        self._suspend_auto_save = True
        self.api_key_var.set(self.sm.get_api_key(provider))
        self.api_model_var.set(settings.get("model", "") or "")
        self.cloud_temperature_var.set(settings.get("temperature", "") or "")
        self.max_completion_tokens_var.set(settings.get("max_completion_tokens", "") or "")
        self.openai_reasoning_effort_var.set(settings.get("reasoning_effort", "") or "")
        self.anthropic_max_tokens_var.set(settings.get("anthropic_max_tokens", "") or "")
        self.anthropic_thinking_enabled_var.set(bool(settings.get("anthropic_thinking_enabled", False)))
        self.anthropic_thinking_effort_var.set(settings.get("anthropic_thinking_effort", "") or "")
        self.google_max_output_tokens_var.set(settings.get("google_max_output_tokens", "") or "")
        self.google_top_p_var.set(settings.get("google_top_p", "") or "")
        self.google_top_k_var.set(settings.get("google_top_k", "") or "")
        self.google_thinking_mode_var.set(settings.get("google_thinking_mode", "") or "")
        self.google_thinking_level_var.set(settings.get("google_thinking_level", "") or "")
        self.google_thinking_budget_var.set(settings.get("google_thinking_budget", "") or "")
        self._suspend_auto_save = False
        if hasattr(self, "anthropic_thinking_effort_label"):
            self._refresh_provider_optional_fields()

    def _build_config_payload(self):
        try:
            cd_mins = float(self.cooldown_minutes_var.get())
        except ValueError:
            cd_mins = 10.0

        active_provider = self.api_provider_var.get()
        provider_settings = copy.deepcopy(self.provider_settings)
        provider_settings[active_provider] = self._current_provider_values()

        return {
            "api_mode": self.api_mode_var.get(),
            "api_provider": active_provider,
            "api_model": provider_settings.get(active_provider, {}).get("model", ""),
            "cloud_temperature": provider_settings.get(active_provider, {}).get("temperature", ""),
            "provider_settings": provider_settings,
            "local_url": self.local_url_var.get(),
            "cooldown_enabled": self.cooldown_enabled_var.get(),
            "cooldown_minutes": cd_mins,
            "window_size": self.window_size_var.get(),
            "ns_name": self.ns_name_var.get(),
            "ns_lang": self.ns_lang_var.get(),
            "ns_freq": self.ns_freq_var.get(),
            "ns_points": self.ns_points_var.get(),
            "ns_guide_first": self.ns_guide_first.get("1.0", "end-1c") if hasattr(self, 'ns_guide_first') else self.ns_guide_first_val,
            "ns_guide_series": self.ns_guide_series.get("1.0", "end-1c") if hasattr(self, 'ns_guide_series') else self.ns_guide_series_val,
        }

    def _on_provider_change(self, provider):
        previous_provider = self._active_provider
        if previous_provider in ["OpenAI", "Anthropic", "Google"]:
            self.provider_settings[previous_provider] = self._current_provider_values()
            self.sm.save_api_key(previous_provider, self.api_key_var.get())

        self._active_provider = provider
        self._load_provider_settings_into_vars(provider)
        self._toggle_ai_fields()
        self._auto_save()

    def _on_anthropic_thinking_toggle(self, *args):
        if self._suspend_auto_save:
            return
        self._refresh_provider_optional_fields()
        self._auto_save()

    def _on_google_thinking_mode_change(self, *args):
        if self._suspend_auto_save:
            return
        self._refresh_provider_optional_fields()
        self._auto_save()

    def _auto_save(self, *args):
        if self._suspend_auto_save:
            return

        self.provider_settings[self.api_provider_var.get()] = self._current_provider_values()
        config = self._build_config_payload()
        self.sm.save_app_config(config)
        self.sm.save_api_key(self.api_provider_var.get(), self.api_key_var.get())
        self.ai.config = self.sm.load_app_config()
        self.is_ai_tested_and_working = False
        if hasattr(self, 'test_status_label'):
            self.test_status_label.configure(text="", text_color="gray")
        self.update_action_button()

    def _on_window_size_change(self, *args):
        self.geometry(self.window_size_var.get())
        self._auto_save()

    def _open_txt_file(self, filename):
        filepath = os.path.join(self.sm.app_dir, "prompts", filename)
        if os.path.exists(filepath):
            os.startfile(filepath)

    def _build_ai_tab(self):
        mode_frame = ctk.CTkFrame(self.tab_ai)
        mode_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkLabel(mode_frame, text="API Mode:").pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Cloud API", variable=self.api_mode_var, value="Cloud", command=self._toggle_ai_fields).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Local AI", variable=self.api_mode_var, value="Local", command=self._toggle_ai_fields).pack(side="left", padx=10)

        self.ai_dynamic_frame = ctk.CTkFrame(self.tab_ai)
        self.ai_dynamic_frame.pack(fill="x", pady=10, padx=20)

        self.provider_label = ctk.CTkLabel(self.ai_dynamic_frame, text="API Provider - required")
        self.st_provider = ctk.CTkOptionMenu(
            self.ai_dynamic_frame,
            variable=self.api_provider_var,
            values=["OpenAI", "Anthropic", "Google"],
            command=self._on_provider_change,
        )
        self.model_label = ctk.CTkLabel(self.ai_dynamic_frame, text="Model Name - required")
        self.st_model = ctk.CTkEntry(self.ai_dynamic_frame, textvariable=self.api_model_var, width=400)
        self.apikey_label = ctk.CTkLabel(self.ai_dynamic_frame, text="API Key - required")
        self.st_apikey = ctk.CTkEntry(self.ai_dynamic_frame, textvariable=self.api_key_var, width=400, show="*")
        self.temperature_label = ctk.CTkLabel(self.ai_dynamic_frame, text="Temperature - optional")
        self.st_temperature = ctk.CTkEntry(self.ai_dynamic_frame, textvariable=self.cloud_temperature_var, width=400)
        self.local_label = ctk.CTkLabel(self.ai_dynamic_frame, text="Local URL - required")
        self.st_local = ctk.CTkEntry(self.ai_dynamic_frame, textvariable=self.local_url_var, width=400)

        self.optional_frame = ctk.CTkFrame(self.ai_dynamic_frame, fg_color="transparent")

        self.openai_max_completion_tokens_label = ctk.CTkLabel(self.optional_frame, text="Max completion tokens - optional")
        self.openai_max_completion_tokens = ctk.CTkEntry(self.optional_frame, textvariable=self.max_completion_tokens_var, width=400)
        self.openai_reasoning_effort_label = ctk.CTkLabel(self.optional_frame, text="Reasoning effort - optional")
        self.openai_reasoning_effort = ctk.CTkOptionMenu(self.optional_frame, variable=self.openai_reasoning_effort_var, values=["", "minimal", "low", "medium", "high"])

        self.anthropic_max_tokens_label = ctk.CTkLabel(self.optional_frame, text="Max tokens - optional")
        self.anthropic_max_tokens = ctk.CTkEntry(self.optional_frame, textvariable=self.anthropic_max_tokens_var, width=400)
        self.anthropic_thinking_enabled_label = ctk.CTkLabel(self.optional_frame, text="Adaptive thinking - optional")
        self.anthropic_thinking_enabled = ctk.CTkCheckBox(self.optional_frame, text="Enable", variable=self.anthropic_thinking_enabled_var)
        self.anthropic_thinking_effort_label = ctk.CTkLabel(self.optional_frame, text="Thinking effort - optional")
        self.anthropic_thinking_effort = ctk.CTkOptionMenu(self.optional_frame, variable=self.anthropic_thinking_effort_var, values=["", "low", "medium", "high"])

        self.google_max_output_tokens_label = ctk.CTkLabel(self.optional_frame, text="Max output tokens - optional")
        self.google_max_output_tokens = ctk.CTkEntry(self.optional_frame, textvariable=self.google_max_output_tokens_var, width=400)
        self.google_top_p_label = ctk.CTkLabel(self.optional_frame, text="Top P - optional")
        self.google_top_p = ctk.CTkEntry(self.optional_frame, textvariable=self.google_top_p_var, width=400)
        self.google_top_k_label = ctk.CTkLabel(self.optional_frame, text="Top K - optional")
        self.google_top_k = ctk.CTkEntry(self.optional_frame, textvariable=self.google_top_k_var, width=400)
        self.google_thinking_mode_label = ctk.CTkLabel(self.optional_frame, text="Thinking mode - optional")
        self.google_thinking_mode = ctk.CTkOptionMenu(self.optional_frame, variable=self.google_thinking_mode_var, values=["", "level", "budget"])
        self.google_thinking_level_label = ctk.CTkLabel(self.optional_frame, text="Thinking level - optional")
        self.google_thinking_level = ctk.CTkOptionMenu(self.optional_frame, variable=self.google_thinking_level_var, values=["", "minimal", "low", "medium", "high"])
        self.google_thinking_budget_label = ctk.CTkLabel(self.optional_frame, text="Thinking budget - optional")
        self.google_thinking_budget = ctk.CTkEntry(self.optional_frame, textvariable=self.google_thinking_budget_var, width=400)

        self._toggle_ai_fields()

        self.test_btn = ctk.CTkButton(self.tab_ai, text="Test Connection", command=self._test_ai_connection)
        self.test_btn.pack(pady=10)
        self.test_status_label = ctk.CTkLabel(self.tab_ai, text="", text_color="gray", wraplength=700)
        self.test_status_label.pack(pady=5)

    def _hide_provider_optional_widgets(self):
        widgets = [
            self.openai_max_completion_tokens_label,
            self.openai_max_completion_tokens,
            self.openai_reasoning_effort_label,
            self.openai_reasoning_effort,
            self.anthropic_max_tokens_label,
            self.anthropic_max_tokens,
            self.anthropic_thinking_enabled_label,
            self.anthropic_thinking_enabled,
            self.anthropic_thinking_effort_label,
            self.anthropic_thinking_effort,
            self.google_max_output_tokens_label,
            self.google_max_output_tokens,
            self.google_top_p_label,
            self.google_top_p,
            self.google_top_k_label,
            self.google_top_k,
            self.google_thinking_mode_label,
            self.google_thinking_mode,
            self.google_thinking_level_label,
            self.google_thinking_level,
            self.google_thinking_budget_label,
            self.google_thinking_budget,
        ]
        for widget in widgets:
            widget.pack_forget()

    def _refresh_provider_optional_fields(self):
        self.optional_frame.pack_forget()
        self._hide_provider_optional_widgets()

        if self.api_mode_var.get() != "Cloud":
            return

        provider = self.api_provider_var.get()
        self.optional_frame.pack(fill="x", pady=(5, 0))

        if provider == "OpenAI":
            self.openai_max_completion_tokens_label.pack(pady=(5, 0))
            self.openai_max_completion_tokens.pack(pady=5)
            self.openai_reasoning_effort_label.pack(pady=(5, 0))
            self.openai_reasoning_effort.pack(pady=5)
        elif provider == "Anthropic":
            self.anthropic_max_tokens_label.pack(pady=(5, 0))
            self.anthropic_max_tokens.pack(pady=5)
            self.anthropic_thinking_enabled_label.pack(pady=(5, 0))
            self.anthropic_thinking_enabled.pack(pady=5)
            if self.anthropic_thinking_enabled_var.get():
                self.anthropic_thinking_effort_label.pack(pady=(5, 0))
                self.anthropic_thinking_effort.pack(pady=5)
        elif provider == "Google":
            self.google_max_output_tokens_label.pack(pady=(5, 0))
            self.google_max_output_tokens.pack(pady=5)
            self.google_top_p_label.pack(pady=(5, 0))
            self.google_top_p.pack(pady=5)
            self.google_top_k_label.pack(pady=(5, 0))
            self.google_top_k.pack(pady=5)
            self.google_thinking_mode_label.pack(pady=(5, 0))
            self.google_thinking_mode.pack(pady=5)
            mode = self.google_thinking_mode_var.get().strip()
            if mode == "level":
                self.google_thinking_level_label.pack(pady=(5, 0))
                self.google_thinking_level.pack(pady=5)
            elif mode == "budget":
                self.google_thinking_budget_label.pack(pady=(5, 0))
                self.google_thinking_budget.pack(pady=5)

    def _toggle_ai_fields(self):
        mode = self.api_mode_var.get()

        self.provider_label.pack_forget()
        self.st_provider.pack_forget()
        self.model_label.pack_forget()
        self.st_model.pack_forget()
        self.apikey_label.pack_forget()
        self.st_apikey.pack_forget()
        self.temperature_label.pack_forget()
        self.st_temperature.pack_forget()
        self.local_label.pack_forget()
        self.st_local.pack_forget()
        self.optional_frame.pack_forget()
        self._hide_provider_optional_widgets()

        if mode == "Cloud":
            self.provider_label.pack(pady=(5, 0))
            self.st_provider.pack(pady=5)
            self.model_label.pack(pady=(5, 0))
            self.st_model.pack(pady=5)
            self.apikey_label.pack(pady=(5, 0))
            self.st_apikey.pack(pady=5)
            self.temperature_label.pack(pady=(5, 0))
            self.st_temperature.pack(pady=5)
            self._refresh_provider_optional_fields()
        else:
            self.local_label.pack(pady=(5, 0))
            self.st_local.pack(pady=5)

    def _test_ai_connection(self):
        self.test_status_label.configure(text="Testing...", text_color="yellow")
        self.update()
        threading.Thread(target=self._run_ai_test, daemon=True).start()

    def _run_ai_test(self):
        success, msg = self.ai.test_connection()
        if success:
            self.is_ai_tested_and_working = True
            self.after(0, lambda m=msg: self.test_status_label.configure(text=m, text_color="green"))
        else:
            self.is_ai_tested_and_working = False
            self.after(0, lambda m=msg: self.test_status_label.configure(text=m, text_color="red"))
        self.after(0, self.update_action_button)

    def _build_new_series_tab(self):
        self.tab_new.grid_columnconfigure(0, weight=1)
        self.tab_new.grid_columnconfigure(1, weight=1)
        left_frame = ctk.CTkFrame(self.tab_new)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(left_frame, text="Series Name:").pack(pady=(10, 0))
        self.ns_name_var.trace_add("write", self._update_path_label)
        self.ns_name = ctk.CTkEntry(left_frame, textvariable=self.ns_name_var, width=300)
        self.ns_name.pack(pady=5)
        ctk.CTkLabel(left_frame, text="Workspace Base Path:").pack(pady=(10, 0))
        path_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        path_frame.pack(pady=5)
        self.ns_base_path_var = ctk.StringVar(value=self.sm.workspace_dir)
        self.ns_base_path_var.trace_add("write", self._update_path_label)
        self.ns_base_path = ctk.CTkEntry(path_frame, textvariable=self.ns_base_path_var, width=220)
        self.ns_base_path.pack(side="left", padx=(0, 5))
        ctk.CTkButton(path_frame, text="Browse", width=70, command=self._browse_base_path).pack(side="left")
        self.ns_full_path_label = ctk.CTkLabel(left_frame, text="", text_color="gray", height=40, wraplength=350)
        self.ns_full_path_label.pack(pady=(0, 10))
        ctk.CTkLabel(left_frame, text="Language:").pack(pady=(10, 0))
        self.ns_lang = ctk.CTkEntry(left_frame, textvariable=self.ns_lang_var, width=300)
        self.ns_lang.pack(pady=5)
        ctk.CTkLabel(left_frame, text="Number of plot points:").pack(pady=(10, 0))
        self.ns_points = ctk.CTkEntry(left_frame, textvariable=self.ns_points_var, width=300)
        self.ns_points.pack(pady=5)
        ctk.CTkLabel(left_frame, text="Generate summary after every X books:").pack(pady=(10, 0))
        self.ns_freq = ctk.CTkEntry(left_frame, textvariable=self.ns_freq_var, width=300)
        self.ns_freq.pack(pady=5)
        right_frame = ctk.CTkFrame(self.tab_new)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(right_frame, text="Guidelines for the series:").pack(pady=(10, 0))
        self.ns_guide_series = ctk.CTkTextbox(right_frame, width=400, height=100)
        self.ns_guide_series.insert("1.0", self.ns_guide_series_val)
        self.ns_guide_series.bind("<KeyRelease>", lambda e: self._auto_save())
        self.ns_guide_series.pack(pady=5)
        ctk.CTkLabel(right_frame, text="Guidelines for the first book:").pack(pady=(10, 0))
        self.ns_guide_first = ctk.CTkTextbox(right_frame, width=400, height=100)
        self.ns_guide_first.insert("1.0", self.ns_guide_first_val)
        self.ns_guide_first.bind("<KeyRelease>", lambda e: self._auto_save())
        self.ns_guide_first.pack(pady=5)
        ctk.CTkButton(right_frame, text="Edit Initial Book Prompt", command=lambda: self._open_txt_file("novel_init_prompt.txt")).pack(pady=10)
        ctk.CTkButton(right_frame, text="Edit Next Book Prompt", command=lambda: self._open_txt_file("next_book_prompt.txt")).pack(pady=5)
        self._update_path_label()

    def _browse_base_path(self):
        folder = filedialog.askdirectory(initialdir=self.ns_base_path_var.get(), title="Select Base Workspace Folder")
        if folder:
            self.ns_base_path_var.set(folder)

    def _update_path_label(self, *args):
        base = self.ns_base_path_var.get().strip()
        name = self.ns_name_var.get().strip()
        if not name:
            name = "[Series Name]"
        full = os.path.join(base, name)
        self.ns_full_path_label.configure(text=f"Will save to: {full}")

    def _build_continue_series_tab(self):
        ctk.CTkButton(self.tab_continue, text="Select Series", command=self._select_series_folder).pack(pady=20)
        self.cs_stats_frame = ctk.CTkFrame(self.tab_continue)
        self.cs_stats_frame.pack(fill="x", padx=40, pady=10)
        self.cs_stats_label = ctk.CTkLabel(self.cs_stats_frame, text="No series loaded.", justify="left")
        self.cs_stats_label.pack(pady=20, padx=20)
        ctk.CTkButton(self.tab_continue, text="Edit Next Book Prompt", command=lambda: self._open_txt_file("next_book_prompt.txt")).pack(pady=20)

    def _load_series_to_continue_tab(self, folder):
        state = self.sm.load_series_state(folder)
        if state and "series_name" in state:
            self.current_loaded_series_dir = folder
            self._update_gui_stats(state)
            self.update_action_button()
        else:
            self.cs_stats_label.configure(text="Invalid folder selected.\nPlease make sure you choose the main series folder.")
            self.current_loaded_series_dir = None
            self.update_action_button()

    def _select_series_folder(self):
        folder = filedialog.askdirectory(initialdir=self.sm.workspace_dir, title="Select Series Folder")
        if folder:
            self._load_series_to_continue_tab(folder)

    def _build_settings_tab(self):
        win_frame = ctk.CTkFrame(self.tab_settings)
        win_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkLabel(win_frame, text="Window Size:").pack(side="left", padx=10)
        ctk.CTkOptionMenu(win_frame, variable=self.window_size_var, values=["800x600", "1000x750", "1200x900", "1600x900"]).pack(side="left", padx=10)
        cd_frame = ctk.CTkFrame(self.tab_settings)
        cd_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkCheckBox(cd_frame, text="Enable Cooldown", variable=self.cooldown_enabled_var).pack(side="left", padx=10)
        ctk.CTkLabel(cd_frame, text="Minutes:").pack(side="left", padx=(10, 5))
        ctk.CTkEntry(cd_frame, textvariable=self.cooldown_minutes_var, width=60).pack(side="left")
        prompt_frame = ctk.CTkFrame(self.tab_settings)
        prompt_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkLabel(prompt_frame, text="Prompts Settings:").pack(pady=5)
        ctk.CTkButton(prompt_frame, text="Edit Summary Instructions", command=lambda: self._open_txt_file("summary_prompt.txt")).pack(pady=5)
        ctk.CTkButton(prompt_frame, text="Edit Part Writing Instructions", command=lambda: self._open_txt_file("writing_start_prompt.txt")).pack(pady=5)

    def update_action_button(self):
        if self.is_generating:
            self.action_btn.configure(text="Stop Generation", state="normal", fg_color="red", command=self.stop_generation)
            return
        current_tab = self.tabview.get()
        self.action_btn.configure(fg_color=["#3a7ebf", "#1f538d"])
        api_ready = False
        mode = self.api_mode_var.get()
        if mode == "Cloud" and self.api_key_var.get().strip() and self.api_model_var.get().strip():
            api_ready = True
        elif mode == "Local" and self.local_url_var.get().strip():
            api_ready = True
        if current_tab in ["AI", "Settings"]:
            self.action_btn.configure(text="Start Generation", state="disabled", command=None)
        elif current_tab == "New Series":
            if api_ready:
                self.action_btn.configure(text="Start Generation", state="normal", command=self.start_new_series)
            else:
                self.action_btn.configure(text="Start Generation", state="disabled", command=None)
        elif current_tab == "Continue Series":
            if not self.current_loaded_series_dir:
                self.action_btn.configure(text="Continue Series", state="disabled", command=None)
            else:
                state = self.sm.load_series_state(self.current_loaded_series_dir)
                is_resume = state and (state["status"]["current_part"] > 0 or (not state["status"]["outline_done"] and len(state["context"]) > 0))
                base_text = "Resume Generation" if is_resume else "Continue Series"
                if api_ready:
                    self.action_btn.configure(text=base_text, state="normal", command=self.resume_series)
                else:
                    self.action_btn.configure(text=base_text, state="disabled", command=None)

    def start_new_series(self):
        name = self.ns_name_var.get().strip()
        base_path = self.ns_base_path_var.get().strip()
        if not name or not base_path:
            return
        target_dir = os.path.normpath(os.path.abspath(os.path.join(base_path, name)))
        curr_dir = os.path.normpath(os.path.abspath(self.current_loaded_series_dir)) if self.current_loaded_series_dir else None
        if curr_dir and curr_dir == target_dir:
            self.tabview.set("Continue Series")
            self.resume_series()
            return
        series_dir = self.sm.create_series(
            series_name=name,
            guidelines_first=self.ns_guide_first.get("1.0", "end-1c"),
            guidelines_series=self.ns_guide_series.get("1.0", "end-1c"),
            language=self.ns_lang_var.get().strip(),
            summary_freq=int(self.ns_freq_var.get() or 3),
            outline_points=int(self.ns_points_var.get() or 12),
            base_path=base_path
        )
        self._load_series_to_continue_tab(series_dir)
        self.tabview.set("Continue Series")
        self.run_generation_thread(series_dir)

    def resume_series(self):
        if self.current_loaded_series_dir:
            self.run_generation_thread(self.current_loaded_series_dir)

    def run_generation_thread(self, series_dir):
        self.is_generating = True
        self.log_label.configure(text="")
        self.update_action_button()
        threading.Thread(target=self.ai.start_generation_loop, args=(series_dir, self.update_gui_progress, self.update_gui_log, self.generation_finished, self.update_gui_stats), daemon=True).start()

    def stop_generation(self):
        self.ai.stop_flag = True
        self.status_label.configure(text="Stopping... Please wait for current task to finish.")
        self.action_btn.configure(state="disabled")

    def update_gui_progress(self, text, percent):
        self.after(0, self._update_gui, text, percent)

    def _update_gui(self, text, percent):
        self.status_label.configure(text=text)
        if percent >= 0:
            self.progress_bar.set(percent)

    def update_gui_log(self, text, is_error=True):
        self.after(0, self._update_gui_log, text, is_error)

    def _update_gui_log(self, text, is_error):
        color = "red" if is_error else "green"
        self.log_label.configure(text=text, text_color=color)

    def update_gui_stats(self, state):
        self.after(0, self._update_gui_stats, state)

    def _update_gui_stats(self, state):
        b_num = state["status"]["current_book"]
        p_num = state["status"]["current_part"]
        total_p = state.get("outline_points", 12)
        c_books = state["history"]["completed_books"]
        c_sums = state["history"]["completed_summaries"]
        stats_text = f"Series Name: {state['series_name']}\n\n"
        stats_text += f"Completed Books: {c_books}\n"
        stats_text += f"Completed Summaries: {c_sums}\n\n"
        stats_text += f"Current Progress:\n"
        if not state["status"]["outline_done"]:
            stats_text += f"Working on Book {b_num}, Outline"
        else:
            stats_text += f"Working on Book {b_num}, Part {p_num + 1}/{total_p}"
        self.cs_stats_label.configure(text=stats_text)

    def generation_finished(self, final_status):
        self.is_generating = False
        self.after(0, lambda: self.status_label.configure(text=final_status))
        self.after(0, lambda: self.progress_bar.set(0))
        self.after(0, self.update_action_button)
