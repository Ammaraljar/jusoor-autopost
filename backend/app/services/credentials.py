"""AI engines, API keys and publishing keys — editable from the dashboard.

Values live in the database (so nobody has to touch the hosting environment) and fall back to
environment variables. Secrets are write-only: the API reports whether a key is set, never
its value.

Engines (all OpenAI-compatible)
-------------------------------
mistral     Mistral AI (La Plateforme)
openrouter  OpenRouter — one key for many models, including free ones (openrouter/free, ":free")
groq        Groq — fast, with a free tier

Mode ``single`` uses the primary engine (and falls back to the other ready engines if it fails).
Mode ``ensemble`` asks every engine that has a key at the same time and lets a judge (the primary
engine) pick the best post.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import AppSetting, session_scope

SETTINGS_KEY = "credentials"
VERSION = "4.11-hdr-bright"

# Each engine carries what its own environment needs: suggested models, the key's format,
# where to get the key, and request tweaks applied in generator._tune_payload().
ENGINES: dict[str, dict[str, Any]] = {
    "claude": {
        "label": "Claude (Anthropic)", "kind": "openai", "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-6",
        "models": [
            {"id": "claude-sonnet-4-6", "note": "ممتاز بالعربية وسريع — الأنسب للمنشورات"},
            {"id": "claude-opus-5-5", "note": "الأعلى جودة — أبطأ وأغلى"},
        ],
        "key_url": "https://console.anthropic.com/settings/keys", "key_prefix": "sk-ant-", "key_placeholder": "sk-ant-…",
        "free": "مدفوع بالاستخدام (رصيد مسبق)",
    },
    "openai": {
        "label": "OpenAI (ChatGPT)", "kind": "openai", "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5-mini",
        "models": [
            {"id": "gpt-5-mini", "note": "سريع واقتصادي"},
            {"id": "gpt-5", "note": "الأعلى جودة"},
        ],
        "key_url": "https://platform.openai.com/api-keys", "key_prefix": "sk-", "key_placeholder": "sk-…",
        "free": "مدفوع بالاستخدام",
    },
    "kimi": {
        "label": "Kimi (Moonshot)", "kind": "openai", "base_url": "https://api.moonshot.ai/v1",
        "default_model": "kimi-k3",
        "models": [
            {"id": "kimi-k3", "note": "الأحدث والأقوى من Kimi"},
            {"id": "kimi-k2.6", "note": "عام وأخف"},
        ],
        "key_url": "https://platform.kimi.ai/console/api-keys", "key_prefix": "sk-", "key_placeholder": "sk-…",
        "free": "رصيد تجريبي عند التسجيل ثم مدفوع",
    },
    "deepseek": {
        "label": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "models": [{"id": "deepseek-chat", "note": "اقتصادي جدًا وجيد بالعربية"}],
        "key_url": "https://platform.deepseek.com/api_keys", "key_prefix": "sk-", "key_placeholder": "sk-…",
        "free": "مدفوع برصيد مسبق — رخيص",
    },
    "grok": {
        "label": "Grok (xAI)", "kind": "openai", "base_url": "https://api.x.ai/v1",
        "default_model": "grok-4",
        "models": [{"id": "grok-4", "note": "نموذج xAI الرئيسي"}],
        "key_url": "https://console.x.ai", "key_prefix": "xai-", "key_placeholder": "xai-…",
        "free": "مدفوع بالاستخدام",
    },
    "qwen": {
        "label": "Qwen (Alibaba)", "kind": "openai",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": [{"id": "qwen-plus", "note": "متوازن"}, {"id": "qwen-max", "note": "الأعلى جودة"}],
        "key_url": "https://modelstudio.console.alibabacloud.com", "key_prefix": "sk-", "key_placeholder": "sk-…",
        "free": "حصة مجانية عند التسجيل ثم مدفوع",
    },
    "gemini": {
        "label": "Google Gemini", "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-flash-latest",
        "models": [
            {"id": "gemini-flash-latest", "note": "سريع وممتاز بالعربية — آخر إصدار Flash تلقائيًا"},
            {"id": "gemini-flash-lite-latest", "note": "الأسرع والأخف"},
            {"id": "gemini-pro-latest", "note": "الأعلى جودة — أبطأ وحدوده المجانية أقل"},
        ],
        "key_url": "https://aistudio.google.com/apikey", "key_prefix": "", "key_placeholder": "AIza… / AQ.…",
        "free": "خطة مجانية من Google AI Studio بحدود في الدقيقة واليوم",
    },
    "cloudflare": {
        "label": "Cloudflare Workers AI", "kind": "openai",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        "default_model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "models": [
            {"id": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "note": "متعدد اللغات وسريع"},
            {"id": "@cf/meta/llama-4-scout-17b-16e-instruct", "note": "أحدث وأخف"},
        ],
        "key_url": "https://dash.cloudflare.com/profile/api-tokens", "key_prefix": "",
        "key_placeholder": "API Token (Workers AI)",
        "free": "10,000 وحدة مجانية يوميًا (Neurons)",
        "extra": [{"field": "cloudflare_account_id", "label": "Account ID",
                   "hint": "من لوحة Cloudflare ← الصفحة الرئيسية للحساب (32 حرفًا)"}],
    },
    "mistral": {
        "label": "Mistral", "kind": "openai", "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "models": [
            {"id": "mistral-small-latest", "note": "سريع واقتصادي — مناسب للمنشورات"},
            {"id": "mistral-medium-latest", "note": "جودة أعلى"},
            {"id": "mistral-large-latest", "note": "الأقوى — أبطأ"},
        ],
        "key_url": "https://console.mistral.ai/api-keys", "key_prefix": "", "key_placeholder": "32-character key",
        "free": "خطة Experiment مجانية بحدود استخدام",
    },
    "openrouter": {
        "label": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/free",
        "models": [
            {"id": "openrouter/free", "note": "يختار نموذجًا مجانيًا يدعم JSON تلقائيًا"},
        ],
        "key_url": "https://openrouter.ai/keys", "key_prefix": "sk-or-", "key_placeholder": "sk-or-v1-…",
        "free": "مجاني بحد يومي للطلبات — أي نموذج ينتهي بـ :free",
    },
    "groq": {
        "label": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-120b",
        "models": [
            {"id": "openai/gpt-oss-120b", "note": "الأفضل للعربية على Groq"},
            {"id": "openai/gpt-oss-20b", "note": "أسرع وأخف"},
            {"id": "qwen/qwen3.8-27b", "note": "تجريبي (Preview)"},
        ],
        "key_url": "https://console.groq.com/keys", "key_prefix": "gsk_", "key_placeholder": "gsk_…",
        "free": "خطة مجانية بحدود في الدقيقة واليوم",
    },
}
ENGINE_ORDER = ("gemini", "claude", "openai", "mistral", "groq", "deepseek", "kimi", "grok", "qwen",
                "cloudflare", "openrouter")   # preference when no primary is chosen

# field -> (is_secret, env fallback attribute on Settings)
FIELDS: dict[str, tuple[bool, str]] = {
    "ai_mode": (False, "ai_mode"),
    "ai_primary": (False, "ai_primary"),
    "ai_ensemble": (False, "ai_ensemble"),
    "mistral_api_key": (True, "mistral_api_key"),
    "mistral_model": (False, "mistral_model"),
    "openrouter_api_key": (True, "openrouter_api_key"),
    "openrouter_model": (False, "openrouter_model"),
    "groq_api_key": (True, "groq_api_key"),
    "groq_model": (False, "groq_model"),
    "claude_api_key": (True, "anthropic_api_key"),
    "claude_model": (False, "claude_model"),
    "openai_api_key": (True, "openai_api_key"),
    "openai_model": (False, "openai_model"),
    "kimi_api_key": (True, "kimi_api_key"),
    "kimi_model": (False, "kimi_model"),
    "deepseek_api_key": (True, "deepseek_api_key"),
    "deepseek_model": (False, "deepseek_model"),
    "grok_api_key": (True, "grok_api_key"),
    "grok_model": (False, "grok_model"),
    "qwen_api_key": (True, "qwen_api_key"),
    "qwen_model": (False, "qwen_model"),
    "gemini_api_key": (True, "gemini_api_key"),
    "gemini_model": (False, "gemini_model"),
    "cloudflare_api_key": (True, "cloudflare_api_key"),
    "cloudflare_account_id": (False, "cloudflare_account_id"),
    "cloudflare_model": (False, "cloudflare_model"),
    "pexels_api_key": (True, "pexels_api_key"),
    "pixabay_api_key": (True, "pixabay_api_key"),
    "buffer_api_key": (True, "buffer_api_key"),
    "meta_access_token": (True, "meta_access_token"),
    "uploadpost_api_key": (True, "uploadpost_api_key"),
}

# Two layers: the platform's keys (shared by every company) and each company's own keys, which win.
# Publishing accounts (Buffer, Meta, upload-post) are always the company's own.
# Engine notes in the other interface languages (the Arabic text is the key)
TEXT_I18N: dict[str, dict[str, str]] = {
    "ممتاز بالعربية وسريع — الأنسب للمنشورات": {"en": "Excellent in Arabic and fast — best for posts", "ms": "Sangat baik dalam bahasa Arab dan pantas — terbaik untuk hantaran", "fr": "Excellent en arabe et rapide — idéal pour les posts"},
    "الأعلى جودة — أبطأ وأغلى": {"en": "Highest quality — slower and pricier", "ms": "Kualiti tertinggi — lebih perlahan dan mahal", "fr": "Qualité maximale — plus lent et plus cher"},
    "مدفوع بالاستخدام (رصيد مسبق)": {"en": "Pay as you go (prepaid credit)", "ms": "Bayar ikut penggunaan (kredit prabayar)", "fr": "Paiement à l’usage (crédit prépayé)"},
    "سريع واقتصادي": {"en": "Fast and economical", "ms": "Pantas dan jimat", "fr": "Rapide et économique"},
    "الأعلى جودة": {"en": "Highest quality", "ms": "Kualiti tertinggi", "fr": "Qualité maximale"},
    "مدفوع بالاستخدام": {"en": "Pay as you go", "ms": "Bayar ikut penggunaan", "fr": "Paiement à l’usage"},
    "الأحدث والأقوى من Kimi": {"en": "Kimi’s newest and strongest", "ms": "Terbaharu dan terkuat daripada Kimi", "fr": "Le plus récent et le plus puissant de Kimi"},
    "عام وأخف": {"en": "General and lighter", "ms": "Umum dan lebih ringan", "fr": "Généraliste et plus léger"},
    "رصيد تجريبي عند التسجيل ثم مدفوع": {"en": "Trial credit at sign-up, then paid", "ms": "Kredit percubaan semasa daftar, kemudian berbayar", "fr": "Crédit d’essai à l’inscription, puis payant"},
    "اقتصادي جدًا وجيد بالعربية": {"en": "Very economical, good in Arabic", "ms": "Sangat jimat, baik dalam bahasa Arab", "fr": "Très économique, bon en arabe"},
    "مدفوع برصيد مسبق — رخيص": {"en": "Prepaid credit — cheap", "ms": "Kredit prabayar — murah", "fr": "Crédit prépayé — bon marché"},
    "نموذج xAI الرئيسي": {"en": "xAI’s main model", "ms": "Model utama xAI", "fr": "Modèle principal de xAI"},
    "متوازن": {"en": "Balanced", "ms": "Seimbang", "fr": "Équilibré"},
    "حصة مجانية عند التسجيل ثم مدفوع": {"en": "Free quota at sign-up, then paid", "ms": "Kuota percuma semasa daftar, kemudian berbayar", "fr": "Quota gratuit à l’inscription, puis payant"},
    "سريع وممتاز بالعربية — آخر إصدار Flash تلقائيًا": {"en": "Fast, excellent in Arabic — always the latest Flash", "ms": "Pantas, sangat baik dalam bahasa Arab — sentiasa Flash terkini", "fr": "Rapide, excellent en arabe — toujours le dernier Flash"},
    "الأسرع والأخف": {"en": "Fastest and lightest", "ms": "Paling pantas dan ringan", "fr": "Le plus rapide et léger"},
    "الأعلى جودة — أبطأ وحدوده المجانية أقل": {"en": "Highest quality — slower, lower free limits", "ms": "Kualiti tertinggi — lebih perlahan, had percuma lebih rendah", "fr": "Qualité maximale — plus lent, limites gratuites plus basses"},
    "خطة مجانية من Google AI Studio بحدود في الدقيقة واليوم": {"en": "Free Google AI Studio plan with per-minute and daily limits", "ms": "Pelan percuma Google AI Studio dengan had per minit dan harian", "fr": "Offre gratuite Google AI Studio avec limites par minute et par jour"},
    "متعدد اللغات وسريع": {"en": "Multilingual and fast", "ms": "Pelbagai bahasa dan pantas", "fr": "Multilingue et rapide"},
    "أحدث وأخف": {"en": "Newer and lighter", "ms": "Lebih baharu dan ringan", "fr": "Plus récent et plus léger"},
    "10,000 وحدة مجانية يوميًا (Neurons)": {"en": "10,000 free units a day (Neurons)", "ms": "10,000 unit percuma sehari (Neurons)", "fr": "10 000 unités gratuites par jour (Neurons)"},
    "سريع واقتصادي — مناسب للمنشورات": {"en": "Fast and economical — good for posts", "ms": "Pantas dan jimat — sesuai untuk hantaran", "fr": "Rapide et économique — adapté aux posts"},
    "جودة أعلى": {"en": "Higher quality", "ms": "Kualiti lebih tinggi", "fr": "Meilleure qualité"},
    "الأقوى — أبطأ": {"en": "Strongest — slower", "ms": "Paling kuat — lebih perlahan", "fr": "Le plus puissant — plus lent"},
    "خطة Experiment مجانية بحدود استخدام": {"en": "Free Experiment plan with usage limits", "ms": "Pelan Experiment percuma dengan had penggunaan", "fr": "Offre Experiment gratuite avec limites"},
    "يختار نموذجًا مجانيًا يدعم JSON تلقائيًا": {"en": "Picks a free JSON-capable model automatically", "ms": "Memilih model percuma yang menyokong JSON secara automatik", "fr": "Choisit automatiquement un modèle gratuit compatible JSON"},
    "مجاني بحد يومي للطلبات — أي نموذج ينتهي بـ :free": {"en": "Free with a daily request limit — any model ending in :free", "ms": "Percuma dengan had permintaan harian — mana-mana model berakhir :free", "fr": "Gratuit avec limite quotidienne — tout modèle finissant par :free"},
    "الأفضل للعربية على Groq": {"en": "Best for Arabic on Groq", "ms": "Terbaik untuk bahasa Arab di Groq", "fr": "Le meilleur pour l’arabe sur Groq"},
    "أسرع وأخف": {"en": "Faster and lighter", "ms": "Lebih pantas dan ringan", "fr": "Plus rapide et léger"},
    "تجريبي (Preview)": {"en": "Preview", "ms": "Pratonton", "fr": "Aperçu"},
    "خطة مجانية بحدود في الدقيقة واليوم": {"en": "Free plan with per-minute and daily limits", "ms": "Pelan percuma dengan had per minit dan harian", "fr": "Offre gratuite avec limites par minute et par jour"},
    "من لوحة Cloudflare ← الصفحة الرئيسية للحساب (32 حرفًا)": {"en": "From the Cloudflare dashboard → account home (32 characters)", "ms": "Dari papan pemuka Cloudflare → laman utama akaun (32 aksara)", "fr": "Depuis le tableau de bord Cloudflare → accueil du compte (32 caractères)"},
}


def tr(text: str) -> dict[str, str]:
    """The text in every interface language."""
    return {"ar": text, **TEXT_I18N.get(text, {"en": text, "ms": text, "fr": text})}


COMPANY_ONLY = {"buffer_api_key", "meta_access_token", "uploadpost_api_key"}
HOME_ORG = 1          # the platform owner's company may also use the server's environment variables
_cache: dict[str, dict[str, str]] = {}


# --------------------------------------------------------------------- storage
def _org() -> int | None:
    from ..db import current_org
    return current_org.get()


def _row_key(scope: str) -> str:
    org = _org()
    return SETTINGS_KEY if scope == "platform" or org is None else f"{SETTINGS_KEY}:org{org}"


def _load(key: str) -> dict[str, str]:
    if key not in _cache:
        try:
            with session_scope() as db:
                row = db.get(AppSetting, key)
                _cache[key] = {k: str(v) for k, v in (row.value or {}).items()} if row else {}
        except Exception:  # noqa: BLE001 - never break a request because of the cache
            return {}
    return _cache[key]


def _clean(values: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in values.items() if k in FIELDS and v}


def _platform() -> dict[str, str]:
    return _clean(_load(SETTINGS_KEY))


def _company() -> dict[str, str]:
    return _clean(_load(_row_key("company"))) if _org() is not None else {}


def _raw_stored() -> dict[str, str]:
    return _load(SETTINGS_KEY)


def _stored() -> dict[str, str]:
    """Values set from the dashboard: the company's own over the platform's."""
    platform = _platform()
    company = _company()
    shared = {k: v for k, v in platform.items()
              if k not in COMPANY_ONLY or _org() in (None, HOME_ORG)}
    return {**shared, **company}


def refresh() -> None:
    _cache.clear()


def _env_value(field: str) -> str:
    if field in COMPANY_ONLY and _org() not in (None, HOME_ORG):
        return ""
    attr = FIELDS[field][1]
    return str(getattr(get_settings(), attr, "") or "") if attr else ""


def _names(value: str) -> list[str]:
    return [n.strip().lower() for n in (value or "").split(",") if n.strip().lower() in ENGINES]


def current() -> dict[str, str]:
    """Effective configuration: dashboard values win, environment variables are the fallback.

    Values that name removed engines (an old AI_PRIMARY=gemini, say) are ignored rather than
    breaking generation."""
    stored = _stored()
    out = {field: stored.get(field) or _env_value(field) for field in FIELDS}
    out["ai_mode"] = out["ai_mode"] if out["ai_mode"] in ("single", "ensemble") else "single"

    primary = (stored.get("ai_primary") or "").lower()
    if not _ready(primary, out):
        primary = (_env_value("ai_primary") or "").lower()
    out["ai_primary"] = primary if _ready(primary, out) else _default_primary(out)

    ensemble = _names(stored.get("ai_ensemble", "")) or _names(_env_value("ai_ensemble"))
    out["ai_ensemble"] = ",".join(ensemble or list(ENGINE_ORDER))
    return out


def _default_primary(values: dict[str, str]) -> str:
    for name in ENGINE_ORDER:
        if _ready(name, values):
            return name
    return ENGINE_ORDER[0]


def source_of(field: str) -> str:
    """dashboard = set by this company (or the platform when no company); platform = shared key."""
    if field not in FIELDS:
        return "unset"
    if _org() is None:
        return "dashboard" if _platform().get(field) else ("environment" if _env_value(field) else "unset")
    if _company().get(field):
        return "dashboard"
    if _stored().get(field):
        return "platform"
    return "environment" if _env_value(field) else "unset"


# --------------------------------------------------------------------- engines
def engine(name: str, values: dict[str, str] | None = None) -> dict[str, str]:
    v = values or current()
    meta = ENGINES[name]
    base_url = meta["base_url"].replace("{account_id}", (v.get("cloudflare_account_id") or "").strip())
    return {"name": name, "label": meta["label"], "kind": meta["kind"], "base_url": base_url,
            "api_key": v.get(f"{name}_api_key", ""),
            "model": v.get(f"{name}_model", "") or meta["default_model"]}


def _ready(name: str, values: dict[str, str]) -> bool:
    if name == "cloudflare" and not (values.get("cloudflare_account_id") or "").strip():
        return False
    return name in ENGINES and bool(values.get(f"{name}_api_key"))


def ready_engines(values: dict[str, str] | None = None) -> list[str]:
    v = values or current()
    return [n for n in ENGINE_ORDER if _ready(n, v)]


def fallback_order(values: dict[str, str] | None = None) -> list[str]:
    """Primary first, then every other ready engine — used when an engine fails."""
    v = values or current()
    primary = v.get("ai_primary", "")
    rest = [n for n in ready_engines(v) if n != primary]
    return ([primary] if _ready(primary, v) else []) + rest


def ensemble_engines(values: dict[str, str] | None = None) -> list[str]:
    """Parallel generation uses every engine that has an API key — nothing else to configure."""
    return ready_engines(values)


def ai_warnings(values: dict[str, str] | None = None) -> list[str]:
    """Settings that cannot work — explained in plain Arabic."""
    v = values or current()
    out: list[str] = []
    if not ready_engines(v):
        out.append("لا يوجد محرّك ذكاء اصطناعي جاهز — أضف مفتاح Gemini أو Mistral أو Groq أو Cloudflare أو OpenRouter")
    if v.get("ai_mode") == "ensemble" and len(ensemble_engines(v)) == 1:
        out.append("وضع التوازي يحتاج مفتاحين على الأقل — يعمل حاليًا بمحرّك واحد")

    mistral_key = v.get("mistral_api_key", "")
    if mistral_key and re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                                    mistral_key):
        out.append("مفتاح Mistral يبدو كمعرّف المفتاح (UUID) لا المفتاح السري نفسه — انسخ المفتاح الذي يظهر "
                   "مرة واحدة عند إنشائه من console.mistral.ai")
    or_key = v.get("openrouter_api_key", "")
    if or_key and not or_key.startswith("sk-or-"):
        out.append("مفاتيح OpenRouter تبدأ عادةً بـ sk-or- — تأكد من نسخ المفتاح كاملًا")
    if v.get("cloudflare_api_key") and not (v.get("cloudflare_account_id") or "").strip():
        out.append("Cloudflare يحتاج Account ID بجانب المفتاح")
    acc = (v.get("cloudflare_account_id") or "").strip()
    if acc and not re.fullmatch(r"[0-9a-fA-F]{32}", acc):
        out.append("Account ID في Cloudflare يتكوّن عادةً من 32 حرفًا (أرقام وحروف a-f)")
    groq_key = v.get("groq_api_key", "")
    if groq_key and not groq_key.startswith("gsk_"):
        out.append("مفاتيح Groq تبدأ عادةً بـ gsk_ — تأكد من نسخ المفتاح كاملًا")
    return out


# --------------------------------------------------------------------- API views
def public_view() -> dict[str, Any]:
    """Safe representation for the dashboard: secrets become a status, never a value."""
    values = current()
    out: dict[str, Any] = {}
    for field, (secret, _env) in FIELDS.items():
        if secret:
            out[field] = {"set": bool(values[field]), "source": source_of(field),
                          "hint": f"…{values[field][-4:]}" if values[field] else ""}
        else:
            out[field] = values[field]
    out["engines"] = {name: {"label": ENGINES[name]["label"], "ready": _ready(name, values),
                             "model": engine(name, values)["model"],
                             "default_model": ENGINES[name]["default_model"],
                             "models": [{**m, "note_i18n": tr(m.get("note", ""))} for m in ENGINES[name]["models"]],
                             "key_url": ENGINES[name]["key_url"],
                             "key_prefix": ENGINES[name]["key_prefix"],
                             "key_placeholder": ENGINES[name]["key_placeholder"],
                             "free": ENGINES[name]["free"], "free_i18n": tr(ENGINES[name]["free"]),
                             "extra": [{**x, "hint_i18n": tr(x.get("hint", ""))} for x in ENGINES[name].get("extra", [])]}
                      for name in ENGINE_ORDER}
    out["ready"] = ready_engines(values)
    out["version"] = VERSION
    out["warnings"] = ai_warnings(values)
    return out


def save(db: Session, values: dict[str, Any], scope: str = "company") -> dict[str, Any]:
    """Update stored credentials. For secrets: "" keeps the current value, None clears it.

    scope="company": the current company's own keys; scope="platform": the shared keys."""
    key = _row_key(scope)
    row = db.get(AppSetting, key)
    data = _clean(dict(row.value or {})) if row else {}
    for field, (secret, _env) in FIELDS.items():
        if field not in values:
            continue
        value = values[field]
        if value is None:
            data.pop(field, None)
            continue
        value = str(value).strip()
        if secret and value == "":
            continue                       # untouched password field
        if field == "ai_primary" and value not in ENGINES:
            continue
        if field == "ai_ensemble":
            value = ",".join(_names(value))
        if value == "":
            data.pop(field, None)
        else:
            data[field] = value
    if row:
        row.value = data
    else:
        db.add(AppSetting(key=key, value=data))
    db.flush()
    _cache[key] = dict(data)
    return public_view()
