from __future__ import annotations

import asyncio, json, os, pathlib, ssl, urllib.request, urllib.error

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


class GroqLLM:
    def __init__(self, model: str, api_key: str, temperature: float = 0.2, max_tokens: int = 4096):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base = "https://api.groq.com/openai/v1/chat/completions"

    async def __call__(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode()
        last = None
        for attempt in range(6):
            req = urllib.request.Request(
                self.base, data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "S18Code-eval/1.0 (python-urllib)",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=120, context=_SSL) as r:
                    d = json.load(r)
                return d["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                err_body = e.read().decode() if e.fp else ""
                last = RuntimeError(f"groq HTTP {e.code}: {err_body[:200]}")
                if e.code in (429, 500, 502, 503) and attempt < 5:
                    await asyncio.sleep(15 * (attempt + 1))
                    continue
                raise last
            except Exception as e:
                last = RuntimeError(f"groq error: {type(e).__name__}: {e}")
                if attempt < 5:
                    await asyncio.sleep(10)
                    continue
                raise last
        raise last


class OllamaLLM:
    def __init__(self, model: str, host: str = "http://localhost:11434",
                 temperature: float = 0.2, num_predict: int = 1200):
        self.model = model
        self.host = host
        self.temperature = temperature
        self.num_predict = num_predict

    async def __call__(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": True,
            "keep_alive": "30m",
            "options": {"num_predict": self.num_predict, "temperature": self.temperature},
        }).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r).get("message", {}).get("content", "")


def load_llm():
    from dotenv import load_dotenv
    repo_env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(repo_env)
    load_dotenv()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        return GroqLLM(model, groq_key)
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.8:27b")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return OllamaLLM(ollama_model, ollama_host)
