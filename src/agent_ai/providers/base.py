"""Interface/abstract base untuk semua provider AI.

Agent Core nantinya cukup memanggil `provider.generate(...)` tanpa perlu
tahu apakah provider tersebut Ollama, DeepSeek, OpenAI, Gemini, atau lainnya.
Semua provider konkret WAJIB mengimplementasikan interface ini.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Nama tool provider-safe (reversible)
# ---------------------------------------------------------------------------
# API OpenAI-compatible (mis. DeepSeek) hanya menerima nama function/tool yang
# cocok pola `^[a-zA-Z0-9_-]+$`. Nama tool internal AETHER boleh memuat karakter
# lain — terutama TITIK pada id Extension yang di-namespacekan (mis.
# "aether.playwright.browser_click"). Mengirim nama bertitik apa adanya membuat
# provider menolak SELURUH request (HTTP 400: Invalid 'tools[i].function.name':
# string does not match pattern), sehingga Run Task gagal total.
#
# Solusi minimal di boundary provider: nama di-ENCODE saat keluar (tool
# definitions + nama di riwayat pesan) dan di-DECODE kembali saat masuk (nama
# tool_call pada response). Identitas nama di registry/tool definitions AETHER
# TIDAK berubah — hanya representasi yang dikirim ke API.
#
# Encoding dipilih REVERSIBLE dan NO-OP untuk nama yang sudah aman:
#   * nama yang cocok `^[a-zA-Z0-9_]+$` (mis. read_file) dibiarkan APA ADANYA;
#   * karakter lain (termasuk '-') dipetakan ke escape "-<hex>-" sehingga hasil
#     selalu cocok `^[a-zA-Z0-9_-]+$` (mis. "." -> "-2e-").
# Karena output "sudah aman" TIDAK pernah memuat '-' dan output hasil encoding
# SELALU memuat '-', proses decode tidak ambigu.
_PROVIDER_SAFE_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def to_provider_safe_tool_name(name: str) -> str:
    """Encode nama tool agar valid untuk API provider (openai-compatible).

    Returns:
        Nama provider-safe. Nama yang sudah aman dikembalikan apa adanya.
    """
    if not name or _PROVIDER_SAFE_TOOL_NAME_RE.match(name):
        return name
    out: List[str] = []
    for ch in name:
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            out.append(ch)
        else:
            out.append("-" + format(ord(ch), "x") + "-")
    return "".join(out)


def from_provider_safe_tool_name(name: str) -> str:
    """Kebalikan `to_provider_safe_tool_name` (nama provider-safe -> asli)."""
    if not name or "-" not in name:
        return name
    out: List[str] = []
    index = 0
    length = len(name)
    while index < length:
        ch = name[index]
        if ch == "-":
            end = name.find("-", index + 1)
            if end != -1:
                try:
                    out.append(chr(int(name[index + 1 : end], 16)))
                    index = end + 1
                    continue
                except ValueError:
                    pass
            out.append(ch)
            index += 1
        else:
            out.append(ch)
            index += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Metadata runtime internal (bukan parameter HTTP wire API provider)
# ---------------------------------------------------------------------------
INTERNAL_RUNTIME_KEYS: frozenset = frozenset({
    "event_sink",
    "execution_policy",
    "mode",
    "workspace_root",
    "runtime_context",
})


def filter_provider_extra(extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Saring opsi tambahan agar parameter internal runtime tidak masuk ke HTTP payload.

    Args:
        extra: Dict opsi tambahan (mis. dari GenerateOptions.extra).

    Returns:
        Dict baru yang hanya memuat parameter yang aman dikirim ke provider wire.
    """
    if not extra:
        return {}
    filtered = {}
    for key, value in extra.items():
        if key in INTERNAL_RUNTIME_KEYS:
            continue
        # Jangan kirim objek yang jelas tidak serializable ke JSON (mis. callable)
        if callable(value):
            continue
        filtered[key] = value
    return filtered


# ---------------------------------------------------------------------------
# Exception hierarchy untuk provider
# ---------------------------------------------------------------------------
# Status HTTP yang bersifat INFRASTRUKTUR (sementara) sehingga layak di-retry di
# layer provider. Status lain (mis. 400/401/403/404) adalah kegagalan
# permanen/konfigurasi dan TIDAK boleh di-retry.
RETRYABLE_HTTP_STATUSES: frozenset = frozenset({429, 500, 529})


class ProviderErrorCategory(str, Enum):
    """Kategori kanonik untuk ProviderError (Fase 3 Normalisasi Boundary Provider)."""

    AUTHENTICATION = "authentication"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    NETWORK_UNAVAILABLE = "network_unavailable"
    INVALID_REQUEST = "invalid_request"
    RESPONSE_MALFORMED = "response_malformed"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """Base exception untuk semua error provider.

    Class attribute `retryable` menandai apakah error bersifat INFRASTRUKTUR
    (sementara) sehingga layak di-retry di layer provider. Default False:
    retry HANYA untuk kegagalan teknis (network/timeout/HTTP 429/5xx), BUKAN
    untuk kegagalan logika agent (tool/command/validation/prompt).

    Skema Kanonik (Fase 3):
        kategori: kategori error terstandardisasi (authentication, rate_limit, dll).
        retryable: True bila error layak di-retry di infrastruktur.
        provider: nama provider pemancar error (mis. 'antigravity', 'ollama').
        raw_reference: rujukan diagnostik mentah (endpoint, error code, atau body).
    """

    #: True bila error bersifat infrastruktur sementara (boleh di-retry).
    retryable: bool = False
    kategori: str = "unknown"
    provider: str = ""
    raw_reference: Optional[str] = None

    def __init__(
        self,
        message: str,
        *,
        kategori: Optional[str] = None,
        retryable: Optional[bool] = None,
        provider: Optional[str] = None,
        raw_reference: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        if kategori is not None:
            self.kategori = str(kategori)
        if retryable is not None:
            self.retryable = bool(retryable)
        if provider is not None:
            self.provider = str(provider)
        if raw_reference is not None:
            self.raw_reference = str(raw_reference)

    @property
    def category(self) -> str:
        """Alias bahasa Inggris untuk kompatibilitas."""
        return self.kategori


class ProviderNotConfiguredError(ProviderError):
    """Provider belum dikonfigurasi (mis. API key / base URL kosong)."""

    retryable = False
    kategori = ProviderErrorCategory.CONFIGURATION.value

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        raw_reference: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            kategori=ProviderErrorCategory.CONFIGURATION.value,
            retryable=False,
            provider=provider,
            raw_reference=raw_reference,
        )


class ProviderUnavailableError(ProviderError):
    """Provider tidak dapat dihubungi (connection error / server mati).

    Kegagalan koneksi/timeout bersifat sementara -> layak di-retry di layer
    provider (bounded) sebelum diserahkan ke Provider Fallback (#45).
    """

    retryable = True
    kategori = ProviderErrorCategory.NETWORK_UNAVAILABLE.value

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        raw_reference: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            kategori=ProviderErrorCategory.NETWORK_UNAVAILABLE.value,
            retryable=True,
            provider=provider,
            raw_reference=raw_reference,
        )


class ProviderAPIError(ProviderError):
    """Provider mengembalikan HTTP/API error.

    Attributes:
        status_code: kode HTTP dari response (bila tersedia).
        endpoint: URL endpoint yang gagal (diagnostik; TANPA credential).
        response_body: potongan body respons (diagnostik, sudah dipotong +
            credential bergaya "Bearer <token>" disamarkan). Bila kosong,
            body tidak tersedia / tidak dapat dibaca.
        provider: nama provider pemancar error.
        raw_reference: rujukan diagnostik endpoint atau body.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        response_body: Optional[str] = None,
        *,
        provider: Optional[str] = None,
        raw_reference: Optional[str] = None,
        kategori: Optional[str] = None,
    ) -> None:
        if kategori is None:
            if status_code in (401, 403):
                kategori = ProviderErrorCategory.AUTHENTICATION.value
            elif status_code == 404:
                kategori = ProviderErrorCategory.NOT_FOUND.value
            elif status_code == 429:
                kategori = ProviderErrorCategory.RATE_LIMIT.value
            elif status_code in (500, 502, 503, 504, 529):
                kategori = ProviderErrorCategory.SERVER_ERROR.value
            elif status_code is not None and 400 <= status_code < 500:
                kategori = ProviderErrorCategory.INVALID_REQUEST.value
            else:
                kategori = ProviderErrorCategory.UNKNOWN.value

        is_retry = status_code is not None and status_code in RETRYABLE_HTTP_STATUSES
        ref = raw_reference or endpoint or (response_body[:100] if response_body else None)

        super().__init__(
            message,
            kategori=kategori,
            retryable=is_retry,
            provider=provider,
            raw_reference=ref,
        )
        self.status_code = status_code
        #: Endpoint/URL yang gagal (diagnostik). Tidak pernah berisi secret.
        self.endpoint = endpoint
        #: Potongan body respons (diagnostik). Tidak pernah berisi secret.
        self.response_body = response_body
#: Panjang maksimum potongan body respons provider yang disertakan pada pesan
#: error (diagnostik). Cukup untuk membedakan 404 "model not found" (body JSON
#: pendek) dari 404 "page not found" (body non-JSON) tanpa membanjiri log/UI.
MAX_ERROR_BODY_CHARS: int = 400


def _raw_response_text(response: Any) -> str:
    """Ambil teks body respons mentah (defensif, tidak pernah melempar).

    Toleran terhadap respons None, tanpa atribut `.text`, `.text` bukan string,
    ataupun atribut yang melempar exception. Hanya membaca BODY respons —
    tidak pernah menyentuh header/credential.
    """
    if response is None:
        return ""
    try:
        text = getattr(response, "text", None)
        if text is None:
            content = getattr(response, "content", None)
            if isinstance(content, (bytes, bytearray)):
                text = bytes(content).decode("utf-8", errors="replace")
            elif isinstance(content, str):
                text = content
            elif content is not None:
                text = str(content)
        if text is None:
            return ""
        return str(text).strip()
    except Exception:  # noqa: BLE001 - diagnostik TIDAK boleh menutupi error asli
        return ""


def _redact_secrets(text: str) -> str:
    """Samarkan pola credential bergaya Authorization agar tidak bocor.

    Hanya menyasar skema "Bearer <token>" (pola header Authorization standar).
    Provider AETHER TIDAK pernah menambahkan header/API key ke detail error;
    lapisan ini sekadar jaring pengaman bila body respons memantulkan token.
    """
    import re

    return re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", text)


def _compact(text: str, limit: int = MAX_ERROR_BODY_CHARS) -> str:
    """Padatkan whitespace lalu potong pada `limit` karakter (+ elipsis)."""
    compacted = " ".join((text or "").split())
    if limit > 0 and len(compacted) > limit:
        compacted = compacted[:limit].rstrip() + "…"
    return compacted


def extract_error_message(text: str) -> str:
    """Ambil pesan error ringkas dari body JSON provider (bila berbentuk itu).

    Mendukung bentuk umum tanpa mengunci ke satu provider:
        {"error": "model 'x' not found"}      -> Ollama native
        {"error": {"message": "..."}}         -> OpenAI-compatible
        {"message": "..."} / {"detail": "..."}
    Bila body bukan JSON / tidak dikenali -> "" (pemanggil memakai body apa
    adanya sebagai fallback).
    """
    import json

    stripped = (text or "").strip()
    if not stripped or stripped[0] not in "{[":
        return ""
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    for key in ("message", "detail"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def error_detail(response: Any, limit: int = MAX_ERROR_BODY_CHARS) -> str:
    """Detail ringkas & diagnosable dari respons error (tanpa secret).

    Prioritas: pesan error JSON provider (mis. "model 'x' not found") bila ada;
    bila tidak, potongan body apa adanya (mis. "404 page not found" dari HTML/
    teks biasa). Credential bergaya "Bearer <token>" disamarkan LEBIH DULU,
    lalu dipotong `limit` karakter.
    """
    raw = _raw_response_text(response)
    if not raw:
        return ""
    parsed = extract_error_message(raw)
    text = parsed if parsed else raw
    return _compact(_redact_secrets(text), limit)


def build_provider_api_error(
    provider_name: str,
    status_code: Optional[int],
    *,
    method: str = "",
    url: str = "",
    response: Any = None,
    body_limit: int = MAX_ERROR_BODY_CHARS,
) -> ProviderAPIError:
    """Bangun `ProviderAPIError` DIAGNOSABLE (ADDITIVE).

    Mempertahankan prefix pesan LAMA "Provider '<name>' mengembalikan HTTP
    <status>" (kompatibilitas substring verifier), lalu MENAMBAHKAN endpoint
    (method + URL) dan potongan body respons, contoh:

        Provider 'ollama' mengembalikan HTTP 404 (POST http://localhost:11434/api/chat): model 'x' not found

    Aturan keamanan & ketahanan:
        - hanya BODY respons + endpoint yang disertakan; header/API key TIDAK
          pernah disertakan;
        - body dipotong (`body_limit`) dan pola "Bearer <token>" disamarkan;
        - body kosong / tidak dapat dibaca -> pesan tetap valid (tanpa detail);
        - `status_code`/`retryable` dipertahankan persis seperti sebelumnya.
    """
    status_text = "" if status_code is None else f" {status_code}"
    message = f"Provider '{provider_name}' mengembalikan HTTP{status_text}"

    endpoint = " ".join(
        part for part in (str(method or "").strip(), str(url or "").strip()) if part
    )
    if endpoint:
        message += f" ({endpoint})"

    detail = error_detail(response, body_limit)
    message += f": {detail}" if detail else "."

    return ProviderAPIError(
        message,
        status_code=status_code,
        endpoint=(url or None),
        response_body=(detail or None),
        provider=provider_name,
        raw_reference=(url or None),
    )


class ProviderResponseError(ProviderError):
    """Response dari provider tidak valid atau tidak dapat diparse."""

    retryable = False
    kategori = ProviderErrorCategory.RESPONSE_MALFORMED.value

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        raw_reference: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            kategori=ProviderErrorCategory.RESPONSE_MALFORMED.value,
            retryable=False,
            provider=provider,
            raw_reference=raw_reference,
        )


@dataclass
class Message:
    """Representasi satu pesan dalam percakapan (format netral/agnostik).

    Attributes:
        role: "system" | "user" | "assistant".
        content: teks pesan (jalur text-only, perilaku lama tidak berubah).
        parts: content blocks tambahan (mis. image) untuk pesan multimodal.
            Format internal AETHER, provider-agnostic: list dict dengan
            ``{"type": "image", "mime_type": ..., "encoding": "base64",
            "data": ...}`` (lihat ``agent_ai.vision.preprocessing``). Provider
            adapter yang menerjemahkan ke format API masing-masing. Kosong
            (default) = pesan text-only seperti sebelumnya.
    """

    role: str  # "system" | "user" | "assistant"
    content: str
    parts: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.parts:
            data["parts"] = [dict(p) for p in self.parts]
        return data


@dataclass
class GenerateOptions:
    """Opsi generasi yang bersifat umum (tidak terikat provider tertentu)."""

    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Definisi tool yang provider-agnostic.

    Format internal AETHER, BUKAN format OpenAI/DeepSeek/Ollama. Provider
    bertanggung jawab mengonversi ke format API masing-masing.

    Attributes:
        name: nama tool.
        description: deskripsi singkat.
        parameters: JSON-schema-like untuk argumen tool.
    """

    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )

    @classmethod
    def from_spec(cls, spec: Dict[str, Any]) -> "ToolDefinition":
        """Bangun ToolDefinition dari spec tool (mis. BaseTool.to_spec())."""
        return cls(
            name=spec.get("name", ""),
            description=spec.get("description", ""),
            parameters=spec.get("input_schema")
            or spec.get("parameters")
            or {"type": "object", "properties": {}},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ToolChoice:
    """Preferensi pemilihan tool (provider-agnostic).

    Attributes:
        mode: "auto" | "none" | "required" | "specific".
        name: nama tool bila mode == "specific".
    """

    mode: str = "auto"
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"mode": self.mode, "name": self.name}


@dataclass
class GenerateResult:
    """Hasil standar dari sebuah pemanggilan generate()."""

    text: str
    model: str = ""
    provider: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None


class ProviderEventType(str, Enum):
    """Jenis event kanonik dari provider (Fase 3 Normalisasi Boundary Provider)."""

    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    USAGE = "usage"
    ERROR = "error"
    DONE = "done"


@dataclass
class ProviderEvent:
    """Skema kanonik event provider (Fase 3 Normalisasi Boundary Provider).

    Varian event:
    - text: potongan teks keluaran model
    - reasoning: penalaran/chain-of-thought (thinking)
    - tool_call: pemanggilan tool terstruktur
    - usage: informasi penggunaan token (input, output, total)
    - error: galat saat inferensi atau streaming
    - done: penanda selesai
    """

    event_type: str
    text: Optional[str] = None
    reasoning: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, int]] = None
    error: Optional[Any] = None
    done: bool = False
    raw: Optional[Dict[str, Any]] = None

    @classmethod
    def text_event(cls, text: str, raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.TEXT.value, text=text, raw=raw)

    @classmethod
    def reasoning_event(cls, reasoning: str, raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.REASONING.value, reasoning=reasoning, raw=raw)

    @classmethod
    def tool_call_event(cls, tool_call: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.TOOL_CALL.value, tool_call=tool_call, raw=raw)

    @classmethod
    def usage_event(cls, usage: Dict[str, int], raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.USAGE.value, usage=usage, raw=raw)

    @classmethod
    def error_event(cls, error: Any, raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.ERROR.value, error=error, raw=raw)

    @classmethod
    def done_event(cls, raw: Optional[Dict[str, Any]] = None) -> "ProviderEvent":
        return cls(event_type=ProviderEventType.DONE.value, done=True, raw=raw)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "text": self.text,
            "reasoning": self.reasoning,
            "tool_call": self.tool_call,
            "usage": self.usage,
            "error": str(self.error) if self.error is not None else None,
            "done": self.done,
            "raw": self.raw,
        }


@dataclass
class ProviderRequest:
    """Skema kanonik permintaan provider (Fase 3 Normalisasi Boundary Provider).

    Attributes:
        model: Nama/ID model yang dituju.
        messages: Daftar pesan percakapan (Message).
        tools: Daftar definisi tool (ToolDefinition).
        generation_options: Opsi inferensi (GenerateOptions).
        runtime_context: Konteks runtime operasional (metadata, environment, dll).
    """

    model: str = ""
    messages: List[Message] = field(default_factory=list)
    tools: Optional[List[ToolDefinition]] = None
    generation_options: Optional[GenerateOptions] = None
    runtime_context: Optional[Dict[str, Any]] = None

    @classmethod
    def from_legacy(
        cls,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        options: Optional[GenerateOptions] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
        runtime_context: Optional[Dict[str, Any]] = None,
        default_model: str = "",
    ) -> "ProviderRequest":
        """Bangun ProviderRequest dari parameter legacy generate()."""
        norm_messages: List[Message] = []
        if messages:
            norm_messages = list(messages)
        elif prompt:
            norm_messages = [Message(role="user", content=prompt)]

        model = (options.model if options and options.model else default_model) or ""

        ctx = dict(runtime_context or {})
        if tool_choice:
            ctx["tool_choice"] = tool_choice.to_dict()
        if options and options.extra:
            for k, v in options.extra.items():
                if k not in ctx:
                    ctx[k] = v

        return cls(
            model=model,
            messages=norm_messages,
            tools=tools,
            generation_options=options,
            runtime_context=ctx or None,
        )

    def to_legacy_kwargs(self) -> Dict[str, Any]:
        """Konversi kembali ke kwargs yang kompatibel dengan signature generate() lama."""
        return {
            "prompt": None,
            "messages": self.messages,
            "options": self.generation_options,
            "tools": self.tools,
        }


class BaseProvider(ABC):
    """Abstract base class untuk semua provider AI.

    Kontrak utama:
        - name: nama unik provider (mis. "ollama", "deepseek", "openai").
        - generate(...): menerima prompt atau daftar pesan, mengembalikan GenerateResult.
        - is_available(): cek apakah provider siap dipakai (mis. API key ada / server hidup).
    """

    #: Nama unik provider. Wajib di-override oleh subclass.
    name: str = "base"

    #: True bila provider membutuhkan model untuk beroperasi.
    #: Provider seperti 9Router yang menentukan model sendiri dapat set ini ke False.
    requires_model: bool = True

    #: Kapabilitas LLM (PR-07 / AEG-16)
    context_window: int = 128000
    supports_thinking: bool = False
    reasoning_budget: Optional[int] = None

    def _resolve_request(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        options: Optional[GenerateOptions] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
        request: Optional[ProviderRequest] = None,
    ) -> ProviderRequest:
        """Selesaikan parameter input menjadi ProviderRequest kanonik tunggal."""
        if request is not None:
            return request
        return ProviderRequest.from_legacy(
            prompt=prompt,
            messages=messages,
            options=options,
            tools=tools,
            tool_choice=tool_choice,
            default_model=getattr(self, "model", "") or getattr(self, "name", ""),
        )

    @abstractmethod
    def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        options: Optional[GenerateOptions] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
        request: Optional[ProviderRequest] = None,
    ) -> GenerateResult:
        """Hasilkan teks dari model.

        Args:
            prompt: prompt tunggal (string). Alternatif dari `messages`.
            messages: daftar Message untuk mode chat.
            options: opsi generasi (temperature, max_tokens, model, dll).
            tools: definisi tool (provider-agnostic) untuk native tool calling.
            tool_choice: preferensi pemilihan tool (opsional).
            request: skema kanonik ProviderRequest (opsional, alternatif terpadu).

        Returns:
            GenerateResult berisi teks hasil dan metadata.

        Catatan:
            Minimal salah satu dari `prompt`, `messages`, atau `request` harus diisi.
        """
        raise NotImplementedError
    def is_available(self) -> bool:
        """Cek apakah provider siap dipakai. Default: True.

        Provider cloud dapat meng-override untuk mengecek keberadaan API key.
        """

        return True

    def knowledge_budget_tokens(self) -> Optional[int]:
        """Sisa token yang aman untuk KONTEKS PENGETAHUAN (mis. Project Bible).

        Provider yang context window-nya terbatas (mis. server lokal Ollama)
        dapat melaporkan berapa token yang benar-benar dapat diterima prompt.
        Pemanggil (AgentOrchestrator) memakai angka ini untuk MEMOTONG konteks
        pengetahuan secara terkendali pada batas baris — bukan membiarkan
        server memotongnya sembarangan (Ollama membuang bagian DEPAN prompt,
        sehingga system prompt + awal Project Bible hilang tanpa error).

        Default None = tidak diketahui: konteks pengetahuan disertakan apa
        adanya (perilaku lama). Provider cloud (OpenAI-compatible) tidak
        meng-override, sehingga perilakunya TIDAK berubah.

        Returns:
            Anggaran token untuk konteks pengetahuan, atau None bila tidak
            diketahui.
        """
        return None

    def normalize_response(self, result: "GenerateResult") -> "LLMResponse":
        """Ubah GenerateResult menjadi LLMResponse (provider-agnostic).

        Implementasi default: text-only, tanpa tool call. Provider yang
        mendukung tool call dapat meng-override method ini.
        Args:
            result: hasil dari generate().
        Returns:
            LLMResponse ternormalisasi.
        """
        # Import lokal untuk menghindari import cycle (core <-> providers).
        from agent_ai.core.response import FinishReason, LLMResponse

        return LLMResponse(
            text=result.text or "",
            actions=[],
            finish_reason=FinishReason.STOP,
            raw=result.raw,
            provider=result.provider or self.name,
            model=result.model,
        )

    @staticmethod
    def _build_messages(
        prompt: Optional[str],
        messages: Optional[List[Any]],
    ) -> List[Dict[str, Any]]:
        """Normalisasi input menjadi daftar pesan format chat.

        Args:
            prompt: prompt tunggal (string).
            messages: daftar Message ATAU dict bentuk provider (mis. hasil
                `ConversationHistory.to_provider_format()` yang memuat
                "tool_calls"/"tool_call_id" untuk Native Tool Calling). Dict
                diteruskan apa adanya agar skema tool tetap utuh.

        Returns:
            Daftar dict pesan siap kirim ke API ({"role", ...}).

        Raises:
            ValueError: bila keduanya kosong, atau tipe pesan tidak didukung.
        """
        if messages:
            normalized: List[Dict[str, Any]] = []
            for m in messages:
                if isinstance(m, dict):
                    normalized.append(dict(m))
                elif isinstance(m, Message):
                    normalized.append(m.to_dict())
                else:
                    raise ValueError(
                        "messages harus berisi Message atau dict provider-format, "
                        f"bukan {type(m).__name__}."
                    )
            return normalized
        if prompt is not None:
            return [{"role": "user", "content": prompt}]
        raise ValueError("Salah satu dari 'prompt' atau 'messages' harus diisi.")

    @staticmethod
    def _build_tool_definitions(
        tools: Optional[List[ToolDefinition]],
    ) -> List[ToolDefinition]:
        """Normalisasi input tools menjadi daftar ToolDefinition.

        Menerima ToolDefinition atau spec dict (mis. BaseTool.to_spec()).
        """
        if not tools:
            return []
        normalized: List[ToolDefinition] = []
        for tool in tools:
            if isinstance(tool, ToolDefinition):
                normalized.append(tool)
            elif isinstance(tool, dict):
                normalized.append(ToolDefinition.from_spec(tool))
            else:
                raise ValueError(
                    "Tool harus berupa ToolDefinition atau spec dict."
                )
        return normalized

    def __repr__(self) -> str:  # pragma: no cover - bantuan debug
        return f"<{self.__class__.__name__} name={self.name!r}>"

