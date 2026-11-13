"""Provider-independent AI adapter with a fallback router.

Default configuration makes ZERO external calls: the deterministic extractive engine answers every question.
A generative provider is consulted only when (a) GRANTH_GENERATIVE=on, (b) a credential is configured,
(c) the per-day call budget is not exhausted - and its output is used only if it passes independent
verification against the retrieved textbook evidence (granth.answer.verify_generated). Otherwise the
router falls back to the next provider and finally to the extractive answer.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config, db


class ProviderError(RuntimeError):
    pass


class Provider:
    name = "abstract"
    external = True

    def configured(self) -> bool:
        raise NotImplementedError

    def generate(self, prompt: str, max_tokens: int = 400) -> str:
        raise NotImplementedError


def _post_json(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # never echo request headers (they contain the credential)
        raise ProviderError(f"HTTP {e.code}") from None
    except Exception as e:
        raise ProviderError(type(e).__name__) from None


class GeminiProvider(Provider):
    """Google Gemini API (AI Studio key). Docs: https://ai.google.dev/gemini-api/docs"""
    name = "gemini"

    def __init__(self):
        self.key = config.get("GEMINI_API_KEY")
        self.model = config.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.timeout = config.get_int("GRANTH_PROVIDER_TIMEOUT", 12)

    def configured(self):
        return bool(self.key)

    def generate(self, prompt, max_tokens=400):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        data = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}},
                          {"x-goog-api-key": self.key}, self.timeout)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise ProviderError("unexpected response shape") from None


class OpenAICompatibleProvider(Provider):
    """Any OpenAI-compatible chat endpoint (Hugging Face router, Groq, OpenRouter, a local server ...)."""

    def __init__(self, name, key_var, base_url, model_var, default_model, external=True):
        self.name, self.external = name, external
        self.key = config.get(key_var)
        self.base = config.get(f"{name.upper()}_BASE_URL", base_url)
        self.model = config.get(model_var, default_model)
        self.timeout = config.get_int("GRANTH_PROVIDER_TIMEOUT", 12)
        self._needs_key = external

    def configured(self):
        return bool(self.base and self.model and (self.key or not self._needs_key))

    def generate(self, prompt, max_tokens=400):
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        data = _post_json(self.base.rstrip("/") + "/chat/completions",
                          {"model": self.model, "temperature": 0, "max_tokens": max_tokens,
                           "messages": [{"role": "user", "content": prompt}]}, headers, self.timeout)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ProviderError("unexpected response shape") from None


def default_providers() -> list[Provider]:
    return [
        GeminiProvider(),
        OpenAICompatibleProvider("huggingface", "HUGGINGFACE_API_TOKEN", "https://router.huggingface.co/v1",
                                 "HUGGINGFACE_MODEL", ""),
        OpenAICompatibleProvider("other", "OTHER_PROVIDER_API_KEY", "", "OTHER_PROVIDER_MODEL", ""),
        # local model server (e.g. Ollama / llama.cpp OpenAI-compatible endpoint); no key, no external traffic
        OpenAICompatibleProvider("local", "LOCAL_MODEL_API_KEY", config.get("LOCAL_MODEL_BASE_URL", ""),
                                 "LOCAL_MODEL_NAME", "", external=False),
    ]


PROMPT = """તમે ગુજરાતી પાઠ્યપુસ્તક સહાયક છો. નીચે આપેલા પાઠ્યપુસ્તકના પુરાવા સિવાય કોઈ પણ માહિતી વાપરશો નહીં.
પુરાવામાં ન હોય તેવી કોઈ હકીકત, સંખ્યા, નામ કે ઉદાહરણ ઉમેરશો નહીં. પાઠ્યપુસ્તકના શબ્દો જ વાપરો.
જો પુરાવો પૂરતો ન હોય તો ફક્ત આટલું લખો: INSUFFICIENT

પુરાવા:
{evidence}

પ્રશ્ન: {question}
ઉત્તર ({style}):"""


class Router:
    """Ordered fallback over configured providers with a hard daily budget for external calls."""

    def __init__(self, providers: list[Provider] | None = None, enabled: bool | None = None,
                 daily_limit: int | None = None):
        self.providers = providers if providers is not None else default_providers()
        self.enabled = (config.get("GRANTH_GENERATIVE", "off").lower() == "on") if enabled is None else enabled
        self.daily_limit = config.get_int("GRANTH_MAX_EXTERNAL_CALLS_PER_DAY", 50) if daily_limit is None else daily_limit
        order = [n.strip() for n in config.get("GRANTH_PROVIDER_ORDER", "").split(",") if n.strip()]
        if order and providers is None:
            self.providers.sort(key=lambda p: order.index(p.name) if p.name in order else 99)

    def status(self) -> list[dict]:
        return [{"name": p.name, "configured": p.configured(), "external": p.external} for p in self.providers] + [
            {"name": "extractive", "configured": True, "external": False}]

    def external_calls_today(self, con) -> int:
        day = db.now()[:10]
        return con.execute("SELECT COUNT(*) FROM usage_events WHERE kind IN ('external_api_call','external_api_error')"
                           " AND ts >= ?", (day,)).fetchone()[0]

    def synthesize(self, con, question: str, evidence_texts: list[str], style: str) -> dict | None:
        """Return {'text','provider','external_calls'} or None (-> caller keeps the extractive answer)."""
        if not self.enabled:
            return None
        prompt = PROMPT.format(evidence="\n".join(f"[{i + 1}] {t}" for i, t in enumerate(evidence_texts)),
                               question=question, style=style)
        calls = 0
        for p in self.providers:
            if not p.configured():
                continue
            if p.external and self.external_calls_today(con) >= self.daily_limit:
                con.execute("INSERT INTO usage_events(ts, kind, provider, detail) VALUES (?,?,?,?)",
                            (db.now(), "budget_exhausted", p.name, f"daily limit {self.daily_limit}"))
                con.commit()
                continue
            tin = len(prompt) // 4
            try:
                text = p.generate(prompt)
                kind = "external_api_call" if p.external else "local_model_call"
                con.execute("INSERT INTO usage_events(ts, kind, provider, tokens_in, tokens_out) VALUES (?,?,?,?,?)",
                            (db.now(), kind, p.name, tin, len(text) // 4))
                con.commit()
                calls += 1 if p.external else 0
                if text and "INSUFFICIENT" not in text:
                    return {"text": text.strip(), "provider": p.name, "external_calls": calls}
            except ProviderError as e:
                con.execute("INSERT INTO usage_events(ts, kind, provider, tokens_in, detail) VALUES (?,?,?,?,?)",
                            (db.now(), "external_api_error" if p.external else "local_model_error", p.name, tin, str(e)))
                con.commit()
                calls += 1 if p.external else 0
        return {"text": None, "provider": None, "external_calls": calls} if calls else None
