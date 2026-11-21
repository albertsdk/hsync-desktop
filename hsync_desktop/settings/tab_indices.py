# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""SettingsDialog tab indices (sync=0, connection=1, general=2, advanced=3).

The connection tab owns both ways of reaching the other devices: its mode
selection decides which half of the page is shown. Advanced is last, after the
app preferences, matching the convention in comparable tools. The live
prefer-primary-role warnings jump to the tab owning the fix on "Yes".
"""

_SYNC_TAB_INDEX = 0
_CONNECTION_TAB_INDEX = 1
_GENERAL_TAB_INDEX = 2
_ADVANCED_TAB_INDEX = 3

# One-line purpose shown at the top of the two broadest tabs, where what each
# owns is not self-evident. General/Advanced stay undescribed: their group
# titles already read as an index.
_TAB_DESCRIPTION_KEYS: dict[int, str] = {
    _SYNC_TAB_INDEX: "settings.sync.description",
    _CONNECTION_TAB_INDEX: "settings.connection.description",
}
