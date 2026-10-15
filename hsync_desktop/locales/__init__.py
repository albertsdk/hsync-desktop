# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Locale modules for HSYNC Desktop internationalization.

Each language has its own module with a `translations` dictionary.
"""

from hsync_desktop.locales.de import translations as DE
from hsync_desktop.locales.en import translations as EN
from hsync_desktop.locales.es import translations as ES
from hsync_desktop.locales.fr import translations as FR
from hsync_desktop.locales.it import translations as IT
from hsync_desktop.locales.ja import translations as JA
from hsync_desktop.locales.nl import translations as NL
from hsync_desktop.locales.pl import translations as PL
from hsync_desktop.locales.pt import translations as PT
from hsync_desktop.locales.ru import translations as RU
from hsync_desktop.locales.zh import translations as ZH

__all__ = ["DE", "EN", "ES", "FR", "IT", "JA", "NL", "PL", "PT", "RU", "ZH"]
