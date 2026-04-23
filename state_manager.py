import copy
import sys
import json
import os
import keyring


class StateManager:
    KEYRING_SERVICE = "InfiniteNovelGenerator"

    def __init__(self):
        if getattr(sys, "frozen", False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.workspace_dir = os.path.join(self.app_dir, "Workspace")
        self.config_file = os.path.join(self.app_dir, "app_config.json")
        self._ensure_directories()

    def _ensure_directories(self):
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir)

        prompts_dir = os.path.join(self.app_dir, "prompts")
        if not os.path.exists(prompts_dir):
            os.makedirs(prompts_dir)
            self._create_empty_prompts(prompts_dir)

    def _create_empty_prompts(self, prompts_dir):
        files = ["novel_init_prompt.txt", "next_book_prompt.txt", "summary_prompt.txt", "writing_start_prompt.txt"]
        for f in files:
            path = os.path.join(prompts_dir, f)
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as file:
                    file.write("")

    def get_default_provider_settings(self):
        return {
            "OpenAI": {
                "model": "",
                "temperature": "",
                "max_completion_tokens": "",
                "reasoning_effort": "",
            },
            "Anthropic": {
                "model": "",
                "temperature": "",
                "anthropic_max_tokens": "",
                "anthropic_thinking_enabled": False,
                "anthropic_thinking_effort": "",
            },
            "Google": {
                "model": "",
                "temperature": "",
                "google_max_output_tokens": "",
                "google_top_p": "",
                "google_top_k": "",
                "google_thinking_mode": "",
                "google_thinking_level": "",
                "google_thinking_budget": "",
            },
        }

    def normalize_provider_settings(self, config):
        defaults = self.get_default_provider_settings()
        normalized = copy.deepcopy(defaults)
        incoming = config.get("provider_settings", {}) or {}

        for provider, provider_defaults in defaults.items():
            user_values = incoming.get(provider, {}) or {}
            normalized[provider].update({
                "model": str(user_values.get("model", provider_defaults.get("model", "")) or ""),
                "temperature": str(user_values.get("temperature", provider_defaults.get("temperature", "")) or ""),
            })

            if provider == "OpenAI":
                normalized[provider]["max_completion_tokens"] = str(user_values.get("max_completion_tokens", provider_defaults.get("max_completion_tokens", "")) or "")
                normalized[provider]["reasoning_effort"] = str(user_values.get("reasoning_effort", provider_defaults.get("reasoning_effort", "")) or "")
            elif provider == "Anthropic":
                normalized[provider]["anthropic_max_tokens"] = str(user_values.get("anthropic_max_tokens", provider_defaults.get("anthropic_max_tokens", "")) or "")
                normalized[provider]["anthropic_thinking_enabled"] = bool(user_values.get("anthropic_thinking_enabled", provider_defaults.get("anthropic_thinking_enabled", False)))
                normalized[provider]["anthropic_thinking_effort"] = str(user_values.get("anthropic_thinking_effort", provider_defaults.get("anthropic_thinking_effort", "")) or "")
            elif provider == "Google":
                normalized[provider]["google_max_output_tokens"] = str(user_values.get("google_max_output_tokens", provider_defaults.get("google_max_output_tokens", "")) or "")
                normalized[provider]["google_top_p"] = str(user_values.get("google_top_p", provider_defaults.get("google_top_p", "")) or "")
                normalized[provider]["google_top_k"] = str(user_values.get("google_top_k", provider_defaults.get("google_top_k", "")) or "")
                normalized[provider]["google_thinking_mode"] = str(user_values.get("google_thinking_mode", provider_defaults.get("google_thinking_mode", "")) or "")
                normalized[provider]["google_thinking_level"] = str(user_values.get("google_thinking_level", provider_defaults.get("google_thinking_level", "")) or "")
                normalized[provider]["google_thinking_budget"] = str(user_values.get("google_thinking_budget", provider_defaults.get("google_thinking_budget", "")) or "")

        if not incoming:
            active_provider = config.get("api_provider", "OpenAI")
            normalized.setdefault(active_provider, {})
            legacy_model = config.get("api_model", "")
            legacy_temperature = config.get("cloud_temperature", "")
            normalized[active_provider]["model"] = str(legacy_model or "")
            normalized[active_provider]["temperature"] = str(legacy_temperature or "")

        return normalized

    def get_default_config(self):
        return {
            "api_mode": "Cloud",
            "api_provider": "OpenAI",
            "api_model": "",
            "cloud_temperature": "",
            "local_url": "http://localhost:1234/v1",
            "cooldown_enabled": False,
            "cooldown_minutes": 10.0,
            "window_size": "1000x750",
            "ns_name": "",
            "ns_lang": "English",
            "ns_freq": "3",
            "ns_points": "12",
            "ns_guide_first": "",
            "ns_guide_series": "",
            "provider_settings": self.get_default_provider_settings(),
        }

    def load_app_config(self):
        config = self.get_default_config()

        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

            needs_save = False

            if "api_key" in loaded:
                del loaded["api_key"]
                needs_save = True

            if loaded.get("api_provider") == "Gemini":
                loaded["api_provider"] = "Google"
                needs_save = True

            config.update({k: v for k, v in loaded.items() if k != "provider_settings"})
            config["provider_settings"] = self.normalize_provider_settings(loaded)

            active_provider = config.get("api_provider", "OpenAI")
            active_settings = config["provider_settings"].get(active_provider, {})
            config["api_model"] = active_settings.get("model", "")
            config["cloud_temperature"] = active_settings.get("temperature", "")

            if needs_save or "provider_settings" not in loaded:
                self.save_app_config(config)

            return config

        return config

    def save_app_config(self, config_data):
        safe_config = copy.deepcopy(config_data)
        if "api_key" in safe_config:
            del safe_config["api_key"]

        safe_config["provider_settings"] = self.normalize_provider_settings(safe_config)
        active_provider = safe_config.get("api_provider", "OpenAI")
        active_settings = safe_config["provider_settings"].get(active_provider, {})
        safe_config["api_model"] = active_settings.get("model", "")
        safe_config["cloud_temperature"] = active_settings.get("temperature", "")

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(safe_config, f, indent=4)

    def get_api_key(self, provider):
        try:
            return keyring.get_password(self.KEYRING_SERVICE, f"api_key_{provider}") or ""
        except Exception:
            return ""

    def save_api_key(self, provider, api_key):
        try:
            if api_key:
                keyring.set_password(self.KEYRING_SERVICE, f"api_key_{provider}", api_key)
            else:
                try:
                    keyring.delete_password(self.KEYRING_SERVICE, f"api_key_{provider}")
                except keyring.errors.PasswordDeleteError:
                    pass
        except Exception:
            pass

    def create_series(self, series_name, guidelines_first, guidelines_series, language, summary_freq, outline_points, base_path):
        original_series_dir = os.path.join(base_path, series_name)
        series_dir = original_series_dir

        counter = 1
        while os.path.exists(series_dir):
            series_dir = f"{original_series_dir}_{counter}"
            counter += 1

        actual_series_name = os.path.basename(series_dir)

        os.makedirs(os.path.join(series_dir, "novels"), exist_ok=True)
        os.makedirs(os.path.join(series_dir, "summaries"), exist_ok=True)
        os.makedirs(os.path.join(series_dir, "data"), exist_ok=True)

        state = {
            "series_name": actual_series_name,
            "guidelines_first": guidelines_first,
            "guidelines_series": guidelines_series,
            "language": language,
            "summary_frequency": summary_freq,
            "outline_points": outline_points,
            "status": {
                "current_book": 1,
                "current_part": 0,
                "outline_done": False
            },
            "history": {
                "completed_books": 0,
                "completed_summaries": 0,
                "latest_summary": None,
                "recent_books": []
            },
            "context": []
        }
        self.save_series_state(series_dir, state)
        return series_dir

    def load_series_state(self, series_dir):
        state_file = os.path.join(series_dir, "series_state.json")
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_series_state(self, series_dir, state_data):
        state_file = os.path.join(series_dir, "series_state.json")
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)

    def read_prompt(self, filename):
        filepath = os.path.join(self.app_dir, "prompts", filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
