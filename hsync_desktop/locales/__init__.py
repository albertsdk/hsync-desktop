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

__all__ = ["DE", "EN", "ES", "FR", "IT"]
