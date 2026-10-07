# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Internationalization (i18n) module for HSYNC Desktop.

Provides translation support with auto-detection of system language.
Supported languages: English, Italian, German, French, Spanish.
"""

from __future__ import annotations

import locale
from collections.abc import Callable

from PySide6.QtCore import QSettings

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG

# Callbacks to notify when language changes
_language_change_callbacks: list[Callable[[], None]] = []

# Language codes
P2PG_EN = "en"
P2PG_IT = "it"
P2PG_DE = "de"
P2PG_FR = "fr"
P2PG_ES = "es"

SUPPORTED_LANGUAGES = {
    P2PG_EN: "English",
    P2PG_IT: "Italiano",
    P2PG_DE: "Deutsch",
    P2PG_FR: "Français",
    P2PG_ES: "Español",
}

_current_lang: str = P2PG_EN
_translations: dict[str, dict[str, str]] = {}


def _detect_system_language() -> str:
    """Detect system language and return matching supported language code."""
    try:
        lang_code = locale.getlocale()[0] or ""
        lang_prefix = lang_code[:2].lower()
        if lang_prefix in SUPPORTED_LANGUAGES:
            return lang_prefix
    except Exception:
        pass
    return P2PG_EN


def init_language() -> None:
    """Initialize language from saved settings or system detection."""
    global _current_lang
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    saved = s.value("appearance/language", "", str)
    if saved and saved in SUPPORTED_LANGUAGES:
        _current_lang = str(saved)
    else:
        _current_lang = _detect_system_language()


def set_language(lang: str) -> None:
    """Set the current language and notify all registered callbacks."""
    global _current_lang
    if lang in SUPPORTED_LANGUAGES and lang != _current_lang:
        _current_lang = lang
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.setValue("appearance/language", lang)
        # Notify all registered callbacks
        for callback in _language_change_callbacks:
            try:
                callback()
            except Exception:
                pass  # Don't let one callback break others


def get_language() -> str:
    """Get the current language code."""
    return _current_lang


def register_language_callback(callback: Callable[[], None]) -> None:
    """Register a callback to be called when the language changes."""
    if callback not in _language_change_callbacks:
        _language_change_callbacks.append(callback)


def unregister_language_callback(callback: Callable[[], None]) -> None:
    """Unregister a previously registered language-change callback."""
    try:
        _language_change_callbacks.remove(callback)
    except ValueError:
        pass


def tr(key: str) -> str:
    """Translate a key to the current language. Falls back to English."""
    lang_dict = _translations.get(_current_lang, {})
    result = lang_dict.get(key)
    if result is not None:
        return result
    # Fallback to English
    en_dict = _translations.get(P2PG_EN, {})
    return en_dict.get(key, key)


# ─── Load translations from locale modules ──────────────────────────────────

from hsync_desktop.locales import DE, EN, ES, FR, IT

_translations = {
    P2PG_EN: EN,
    P2PG_IT: IT,
    P2PG_DE: DE,
    P2PG_FR: FR,
    P2PG_ES: ES,
}
