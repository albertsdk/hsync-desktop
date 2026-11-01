# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Internationalization (i18n) module for HSYNC Desktop.

Provides translation support with auto-detection of system language.
Supported languages: English, Italian, German, French, Spanish, Portuguese
(Brazil), Chinese (Simplified), Russian, Dutch, Polish, Japanese.
"""

from __future__ import annotations

import locale
import os
from collections.abc import Callable

from PySide6.QtCore import QLocale, QSettings

from hsync_desktop.config import SETTINGS_APP, SETTINGS_ORG

# Callbacks to notify when language changes
_language_change_callbacks: list[Callable[[], None]] = []

# Language codes
P2PG_EN = "en"
P2PG_IT = "it"
P2PG_DE = "de"
P2PG_FR = "fr"
P2PG_ES = "es"
P2PG_PT = "pt"
P2PG_ZH = "zh"
P2PG_RU = "ru"
P2PG_NL = "nl"
P2PG_PL = "pl"
P2PG_JA = "ja"

# Sentinel stored in ``appearance/language`` meaning "follow the system
# locale" (the default). It is not a language code.
AUTO_LANGUAGE = "auto"

# Supported languages, keyed by code. Listed alphabetically by their endonym so
# the settings combo (which iterates this mapping) reads in alphabetical order.
# Each name is the language's own endonym and is never translated.
SUPPORTED_LANGUAGES = {
    P2PG_DE: "Deutsch",
    P2PG_EN: "English",
    P2PG_ES: "Español",
    P2PG_FR: "Français",
    P2PG_IT: "Italiano",
    P2PG_NL: "Nederlands",
    P2PG_PL: "Polski",
    P2PG_PT: "Português (Brasil)",
    P2PG_RU: "Русский",
    P2PG_ZH: "中文（简体）",
    P2PG_JA: "日本語",
}

_current_lang: str = P2PG_EN
_translations: dict[str, dict[str, str]] = {}

# Locale variables that speak for the *interface* language. glibc precedence is
# ``LC_ALL`` > ``LC_MESSAGES`` > ``LANG`` (``LANGUAGE`` is GNU gettext's list).
# When at least one is present the process was told its locale — including an
# explicit ``C``, which must stay English — so the machine-wide configuration
# below is not consulted.
_LANGUAGE_ENV_VARS = ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")

# Machine-wide locale configuration, read only when the process carries no
# locale variable at all (a stripped environment: ``sudo``, a service, a
# container, a launcher that drops the environment). systemd keeps it in
# ``/etc/locale.conf``, Debian/Ubuntu in ``/etc/default/locale``; both are
# ``KEY=value`` files.
_SYSTEM_LOCALE_FILES = ("/etc/locale.conf", "/etc/default/locale")
_SYSTEM_LOCALE_KEYS = ("LC_ALL", "LC_MESSAGES", "LANG")


def _language_from_locale(name: str) -> str | None:
    """The supported language code of a POSIX locale name, if any.

    ``it``, ``it_IT``, ``it_IT.UTF-8`` and ``it_IT@euro`` all resolve to ``it``.
    """
    language = name[:2].lower()
    return language if language in SUPPORTED_LANGUAGES else None


def _read_locale_entries(path: str) -> dict[str, str]:
    """The ``KEY=value`` pairs of one machine-wide locale file (empty if unreadable)."""

    entries: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                key, separator, value = line.partition("=")
                if separator:
                    entries[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return entries


def _system_wide_locale() -> str | None:
    """The interface language configured machine-wide, if any.

    Consulted only when the process environment carries no locale variable: the
    session locale is missing (``sudo``, a service, a container, a launcher that
    drops the environment) while the machine still has its own default. Within a
    file the glibc precedence applies, so ``LC_ALL`` decides when it is set.
    """
    for path in _SYSTEM_LOCALE_FILES:
        entries = _read_locale_entries(path)
        for key in _SYSTEM_LOCALE_KEYS:
            value = entries.get(key, "")
            if value:
                return _language_from_locale(value)
    return None


def _detect_system_language() -> str:
    """Detect the OS language and return a matching supported language code.

    ``QLocale.system()`` is the primary source: unlike Python's ``locale``, it
    resolves the desktop locale even when the C library reports ``("C",
    "UTF-8")`` (e.g. ``LANG=it`` or ``it_IT@euro`` on glibc) and it reads the
    OS locale directly on Windows/macOS. It needs no ``QApplication``. The
    ``locale`` module is the fallback, the machine-wide configuration the
    fallback for a process started without any locale variable, and English the
    last resort.
    """
    if not any(os.environ.get(name) for name in _LANGUAGE_ENV_VARS):
        machine_wide = _system_wide_locale()
        if machine_wide is not None:
            return machine_wide
    try:
        name = QLocale.system().name()
        if name and name != "C":
            language = _language_from_locale(name)
            if language is not None:
                return language
    except Exception:
        pass
    try:
        lang_code = locale.getlocale()[0] or ""
        language = _language_from_locale(lang_code)
        if language is not None:
            return language
    except Exception:
        pass
    return P2PG_EN


def init_language() -> None:
    """Initialize the language from the saved preference or the system locale.

    The stored value is either :data:`AUTO_LANGUAGE` (the default: follow the
    system locale), a supported code, or an unsupported/absent value (which also
    follows the system locale).
    """
    global _current_lang
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    saved = str(s.value("appearance/language", AUTO_LANGUAGE, str))
    if saved in SUPPORTED_LANGUAGES:
        _current_lang = saved
    else:
        _current_lang = _detect_system_language()


def set_language(lang: str) -> None:
    """Persist the language preference and notify the registered callbacks.

    :data:`AUTO_LANGUAGE` keeps following the system locale; the preference is
    stored as-is so it stays dynamic on later launches. Callbacks fire only when
    the effective language actually changes.
    """
    global _current_lang
    if lang != AUTO_LANGUAGE and lang not in SUPPORTED_LANGUAGES:
        return
    resolved = _detect_system_language() if lang == AUTO_LANGUAGE else lang
    QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("appearance/language", lang)
    if resolved == _current_lang:
        return
    _current_lang = resolved
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

from hsync_desktop.locales import DE, EN, ES, FR, IT, JA, NL, PL, PT, RU, ZH

_translations = {
    P2PG_EN: EN,
    P2PG_IT: IT,
    P2PG_DE: DE,
    P2PG_FR: FR,
    P2PG_ES: ES,
    P2PG_PT: PT,
    P2PG_ZH: ZH,
    P2PG_RU: RU,
    P2PG_NL: NL,
    P2PG_PL: PL,
    P2PG_JA: JA,
}
