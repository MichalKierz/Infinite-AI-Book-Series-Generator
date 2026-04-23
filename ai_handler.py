import time
import os
import json
import openai
from google import genai
from google.genai import types
import anthropic
from pdf_maker import PDFMaker


class AIHandler:
    def __init__(self, state_manager):
        self.sm = state_manager
        self.config = self.sm.load_app_config()
        self.stop_flag = False
        self.pdf_maker = PDFMaker()

    def _get_provider_settings(self, provider=None):
        provider = provider or self.config.get("api_provider", "OpenAI")
        settings = self.config.get("provider_settings", {}) or {}
        return settings.get(provider, {}) or {}

    def _get_model_name(self, provider=None):
        provider = provider or self.config.get("api_provider", "OpenAI")
        settings = self._get_provider_settings(provider)
        model_name = str(settings.get("model", "")).strip()
        if model_name:
            return model_name
        return str(self.config.get("api_model", "")).strip()

    def _get_float_setting(self, key, provider=None):
        settings = self._get_provider_settings(provider)
        raw_value = str(settings.get(key, "")).strip()
        if raw_value == "":
            return None
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _get_int_setting(self, key, provider=None):
        settings = self._get_provider_settings(provider)
        raw_value = str(settings.get(key, "")).strip()
        if raw_value == "":
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def _get_text_setting(self, key, provider=None):
        settings = self._get_provider_settings(provider)
        return str(settings.get(key, "") or "").strip()

    def _get_temperature(self, provider=None):
        return self._get_float_setting("temperature", provider)

    def _get_openai_request_options(self, for_test=False):
        options = {}
        max_completion_tokens = self._get_int_setting("max_completion_tokens", "OpenAI")
        if max_completion_tokens is not None:
            options["max_completion_tokens"] = max_completion_tokens
        elif for_test:
            options["max_completion_tokens"] = 32

        reasoning_effort = self._get_text_setting("reasoning_effort", "OpenAI")
        if reasoning_effort:
            options["reasoning_effort"] = reasoning_effort

        temperature = self._get_temperature("OpenAI")
        if temperature is not None:
            options["temperature"] = temperature

        return options

    def _get_anthropic_request_options(self, for_test=False):
        options = {}
        max_tokens = self._get_int_setting("anthropic_max_tokens", "Anthropic")
        if max_tokens is not None:
            options["max_tokens"] = max_tokens
        elif for_test:
            options["max_tokens"] = 32
        else:
            options["max_tokens"] = 4000

        if self._get_provider_settings("Anthropic").get("anthropic_thinking_enabled", False):
            thinking_effort = self._get_text_setting("anthropic_thinking_effort", "Anthropic")
            thinking_payload = {}
            if thinking_effort:
                thinking_payload["effort"] = thinking_effort
            if thinking_payload:
                options["thinking"] = thinking_payload
        else:
            temperature = self._get_temperature("Anthropic")
            if temperature is not None:
                options["temperature"] = temperature

        return options

    def _get_google_config(self, system_instruction=None):
        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        temperature = self._get_temperature("Google")
        if temperature is not None:
            config_kwargs["temperature"] = temperature

        max_output_tokens = self._get_int_setting("google_max_output_tokens", "Google")
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens

        top_p = self._get_float_setting("google_top_p", "Google")
        if top_p is not None:
            config_kwargs["top_p"] = top_p

        top_k = self._get_int_setting("google_top_k", "Google")
        if top_k is not None:
            config_kwargs["top_k"] = top_k

        thinking_mode = self._get_text_setting("google_thinking_mode", "Google")
        if thinking_mode == "level":
            thinking_level = self._get_text_setting("google_thinking_level", "Google")
            if thinking_level:
                config_kwargs["thinking_config"] = {"thinking_level": thinking_level}
        elif thinking_mode == "budget":
            thinking_budget = self._get_int_setting("google_thinking_budget", "Google")
            if thinking_budget is not None:
                config_kwargs["thinking_config"] = {"thinking_budget": thinking_budget}

        if not config_kwargs:
            return None

        return types.GenerateContentConfig(**config_kwargs)

    def _format_error_message(self, error):
        text = str(error)
        compact = " ".join(text.split())
        lowered = compact.lower()
        if "max_tokens limit was reached" in lowered or "max token limit was reached" in lowered:
            return "Connection reached the response token limit. Increase the optional max tokens field or leave it empty."
        return f"Error: {compact}"

    def test_connection(self):
        self.config = self.sm.load_app_config()
        mode = self.config.get("api_mode", "Cloud")
        provider = self.config.get("api_provider", "OpenAI")
        api_key = self.sm.get_api_key(provider)
        model_name = self._get_model_name(provider)

        try:
            if mode == "Local" or provider == "OpenAI":
                key_to_use = api_key if mode == "Cloud" else "local"
                base_url = None if mode == "Cloud" else self.config.get("local_url", "").strip()

                if mode == "Local" and base_url:
                    if base_url.endswith("/chat/completions"):
                        base_url = base_url.replace("/chat/completions", "")
                    if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                        if base_url.endswith("/"):
                            base_url += "v1"
                        else:
                            base_url += "/v1"

                client = openai.OpenAI(api_key=key_to_use, base_url=base_url, timeout=5.0)

                if mode == "Local":
                    try:
                        client.models.list()
                    except Exception:
                        pass
                    return True, "Connection successful"

                test_model = model_name if model_name else "gpt-4o-mini"
                request_kwargs = {
                    "model": test_model,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                }
                request_kwargs.update(self._get_openai_request_options(for_test=True))
                client.chat.completions.create(**request_kwargs)
                return True, "Connection successful"

            elif provider == "Anthropic" and mode == "Cloud":
                client = anthropic.Anthropic(api_key=api_key, timeout=5.0)
                test_model = model_name if model_name else "claude-3-haiku-20240307"
                request_kwargs = {
                    "model": test_model,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                }
                request_kwargs.update(self._get_anthropic_request_options(for_test=True))
                client.messages.create(**request_kwargs)
                return True, "Connection successful"

            elif provider == "Google" and mode == "Cloud":
                client = genai.Client(api_key=api_key)
                test_model = model_name if model_name else "gemini-2.0-flash"
                client.models.generate_content(
                    model=test_model,
                    contents="Reply with OK.",
                    config=self._get_google_config(),
                )
                return True, "Connection successful"

            return False, "Unknown API provider."
        except Exception as e:
            return False, self._format_error_message(e)

    def _get_response(self, messages):
        self.config = self.sm.load_app_config()
        mode = self.config.get("api_mode", "Cloud")
        provider = self.config.get("api_provider", "OpenAI")
        api_key = self.sm.get_api_key(provider)
        model_name = self._get_model_name(provider)

        if mode == "Local" or provider == "OpenAI":
            key_to_use = api_key if mode == "Cloud" else "local"
            base_url = None if mode == "Cloud" else self.config.get("local_url", "").strip()

            if mode == "Local" and base_url:
                if base_url.endswith("/chat/completions"):
                    base_url = base_url.replace("/chat/completions", "")
                if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                    if base_url.endswith("/"):
                        base_url += "v1"
                    else:
                        base_url += "/v1"

            model_to_use = "local-model" if mode == "Local" else model_name

            client = openai.OpenAI(api_key=key_to_use, base_url=base_url)
            request_kwargs = {
                "model": model_to_use,
                "messages": messages,
            }
            if mode == "Cloud":
                request_kwargs.update(self._get_openai_request_options())
            response = client.chat.completions.create(**request_kwargs)

            if response and getattr(response, 'choices', None) and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                raise ValueError("API returned an invalid or empty JSON structure without 'choices'. Check URL endpoint.")

        elif provider == "Anthropic" and mode == "Cloud":
            client = anthropic.Anthropic(api_key=api_key)
            system_msg = ""
            user_msgs = []
            for m in messages:
                if m["role"] == "system":
                    system_msg += m["content"] + "\n"
                else:
                    user_msgs.append({"role": m["role"], "content": m["content"]})

            request_kwargs = {
                "model": model_name,
                "system": system_msg,
                "messages": user_msgs,
            }
            request_kwargs.update(self._get_anthropic_request_options())
            response = client.messages.create(**request_kwargs)
            return response.content[0].text

        elif provider == "Google" and mode == "Cloud":
            client = genai.Client(api_key=api_key)
            formatted_messages = []
            system_instruction = None

            for m in messages:
                if m["role"] == "system":
                    if system_instruction is None:
                        system_instruction = m["content"]
                    else:
                        system_instruction += "\n" + m["content"]
                else:
                    role = "model" if m["role"] == "assistant" else "user"
                    formatted_messages.append(
                        types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
                    )

            response = client.models.generate_content(
                model=model_name,
                contents=formatted_messages,
                config=self._get_google_config(system_instruction=system_instruction),
            )
            return response.text

        return ""

    def _sleep_cooldown(self, progress_callback):
        if not self.config.get("cooldown_enabled", False):
            return

        try:
            cooldown_minutes = float(self.config.get("cooldown_minutes", 10.0))
        except ValueError:
            cooldown_minutes = 10.0

        cooldown_seconds = int(cooldown_minutes * 60)
        for i in range(cooldown_seconds, 0, -1):
            if self.stop_flag:
                break
            progress_callback(f"Cooldown: Waiting {i} seconds...", -1)
            time.sleep(1)

    def _build_system_prompt(self, state):
        init_prompt = self.sm.read_prompt("novel_init_prompt.txt")
        init_prompt = init_prompt.replace("[number]", str(state.get("outline_points", 12)))
        current_book = state["status"]["current_book"]
        series_dir = os.path.join(self.sm.workspace_dir, state["series_name"])
        summary_freq = int(state.get("summary_frequency", 3))
        completed_books = state["history"]["completed_books"]

        series_guide = state.get("guidelines_series", state.get("guidelines", ""))
        first_guide = state.get("guidelines_first", "")

        if current_book == 1:
            system_content = init_prompt + "\n\nSeries Guidelines:\n" + series_guide + "\n\nGuidelines for the first book:\n" + first_guide
        else:
            next_prompt = self.sm.read_prompt("next_book_prompt.txt")
            system_content = init_prompt + "\n\n" + next_prompt + "\n\nSeries Guidelines:\n" + series_guide

            latest_summary = state["history"]["latest_summary"]
            if latest_summary:
                sum_path = os.path.join(series_dir, "data", os.path.basename(latest_summary))
                if os.path.exists(sum_path):
                    with open(sum_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        system_content += "\n\nStory Summary so far:\n" + data.get("text", "")

            recent_books = state["history"]["recent_books"]

            books_to_include = []
            cycle_pos = completed_books % summary_freq

            if cycle_pos == 0:
                if len(recent_books) >= 1:
                    books_to_include = [recent_books[-1]]
            elif cycle_pos == 1:
                if len(recent_books) >= 1:
                    books_to_include = [recent_books[-1]]
            else:
                books_to_include = recent_books[-2:]

            for rb in books_to_include:
                file_path = os.path.join(series_dir, "data", os.path.basename(rb))
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        system_content += f"\n\nContext from recent book:\n{data.get('text', '')}\n"

        return {"role": "system", "content": system_content}

    def start_generation_loop(self, series_dir, progress_callback, log_callback, finish_callback, stats_callback):
        self.stop_flag = False
        self.config = self.sm.load_app_config()
        error_occurred = False

        while not self.stop_flag:
            state = self.sm.load_series_state(series_dir)
            if not state:
                log_callback("Failed to load series state.", True)
                error_occurred = True
                break

            current_book = state["status"]["current_book"]
            total_parts = state.get("outline_points", 12)
            stats_callback(state)

            if not state["context"]:
                state["context"].append(self._build_system_prompt(state))
                self.sm.save_series_state(series_dir, state)

            if not state["status"]["outline_done"]:
                self._sleep_cooldown(progress_callback)
                if self.stop_flag:
                    break
                progress_callback(f"Book {current_book}: Generating Outline...", 0.1)

                try:
                    outline_req = {"role": "user", "content": "Please write the plot outline."}
                    state["context"].append(outline_req)
                    outline_text = self._get_response(state["context"])

                    if not outline_text:
                        raise ValueError("Received empty response from API")

                    state["context"].append({"role": "assistant", "content": outline_text})
                    state["status"]["outline_done"] = True
                    self.sm.save_series_state(series_dir, state)
                    stats_callback(state)
                except Exception as e:
                    progress_callback("Stopped.", 0)
                    log_callback(f"Error generating outline: {str(e)}", True)
                    error_occurred = True
                    break

            while state["status"]["current_part"] < total_parts and not self.stop_flag:
                part = state["status"]["current_part"] + 1
                self._sleep_cooldown(progress_callback)
                if self.stop_flag:
                    break
                progress_callback(f"Book {current_book}: Writing Part {part}/{total_parts}...", part / float(total_parts))

                writing_start = self.sm.read_prompt("writing_start_prompt.txt")
                lang = state["language"]
                user_msg = f"{writing_start}\nThe book will be written in {lang} language.\nPlease write part {part}."

                try:
                    state["context"].append({"role": "user", "content": user_msg})
                    part_text = self._get_response(state["context"])

                    if not part_text:
                        raise ValueError("Received empty response from API")

                    state["context"].append({"role": "assistant", "content": part_text})
                    state["status"]["current_part"] = part
                    self.sm.save_series_state(series_dir, state)
                    stats_callback(state)
                except Exception as e:
                    progress_callback("Stopped.", 0)
                    log_callback(f"Error writing part {part}: {str(e)}", True)
                    error_occurred = True
                    break

            if error_occurred:
                break

            if state["status"]["current_part"] == total_parts and not self.stop_flag:
                progress_callback(f"Book {current_book}: Compiling PDF...", 1.0)
                book_texts = [m["content"] for m in state["context"] if m["role"] == "assistant"][1:]

                pdf_filename = f"{state['series_name']}_{current_book}.pdf"
                pdf_path = os.path.join(series_dir, "novels", pdf_filename)

                data_filename = f"{state['series_name']}_{current_book}.json"
                data_path = os.path.join(series_dir, "data", data_filename)

                full_text = "\n\n".join(book_texts)

                with open(data_path, 'w', encoding='utf-8') as f:
                    json.dump({"text": full_text}, f, ensure_ascii=False)

                self.pdf_maker.create_pdf(f"{state['series_name']} - {current_book}", full_text, pdf_path)

                state["history"]["completed_books"] += 1
                state["history"]["recent_books"].append(data_filename)
                if len(state["history"]["recent_books"]) > 3:
                    state["history"]["recent_books"].pop(0)

                self.sm.save_series_state(series_dir, state)
                stats_callback(state)

                needs_summary = (state["history"]["completed_books"] % int(state["summary_frequency"])) == 0

                if needs_summary:
                    progress_callback(f"Generating Summary for recent books...", 1.0)
                    self._sleep_cooldown(progress_callback)
                    sum_prompt = self.sm.read_prompt("summary_prompt.txt")

                    recent_texts = ""
                    for rb in state["history"]["recent_books"]:
                        file_path = os.path.join(series_dir, "data", os.path.basename(rb))
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                recent_texts += data.get("text", "") + "\n\n"

                    user_msg = f"{sum_prompt}\n\nTEXT TO SUMMARIZE:\n{recent_texts}"
                    sum_req = [{"role": "user", "content": user_msg}]

                    try:
                        summary_text = self._get_response(sum_req)

                        if not summary_text:
                            raise ValueError("Received empty response from API")

                        state["history"]["completed_summaries"] += 1
                        sum_idx = state["history"]["completed_summaries"]

                        sum_pdf_filename = f"{state['series_name']}_Summary_{sum_idx}.pdf"
                        sum_pdf_path = os.path.join(series_dir, "summaries", sum_pdf_filename)

                        sum_data_filename = f"{state['series_name']}_Summary_{sum_idx}.json"
                        sum_data_path = os.path.join(series_dir, "data", sum_data_filename)

                        with open(sum_data_path, 'w', encoding='utf-8') as f:
                            json.dump({"text": summary_text}, f, ensure_ascii=False)

                        self.pdf_maker.create_pdf(f"{state['series_name']} - Summary {sum_idx}", summary_text, sum_pdf_path)
                        state["history"]["latest_summary"] = sum_data_filename

                        if state["history"]["recent_books"]:
                            state["history"]["recent_books"] = [state["history"]["recent_books"][-1]]

                    except Exception as e:
                        progress_callback("Stopped.", 0)
                        log_callback(f"Error generating summary: {str(e)}", True)
                        error_occurred = True
                        break

                state["status"]["current_book"] += 1
                state["status"]["current_part"] = 0
                state["status"]["outline_done"] = False
                state["context"] = []
                self.sm.save_series_state(series_dir, state)
                stats_callback(state)

        if error_occurred:
            finish_callback("Stopped due to error")
        elif self.stop_flag:
            finish_callback("Stopped manually")
        else:
            finish_callback("Finished")
