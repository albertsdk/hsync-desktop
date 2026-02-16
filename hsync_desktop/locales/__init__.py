# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Locale modules for HSYNC Desktop internationalization.

Each language has its own module with a `translations` dictionary.
"""

from hsync_desktop.locales.de import translations as DE
from hsync_desktop.locales.en import translations as EN
from hsync_desktop.locales.es import translations as ES
from hsync_desktop.locales.fr import translations as FR
from hsync_desktop.locales.it import translations as IT

__all__ = ["EN", "IT", "DE", "FR", "ES"]
