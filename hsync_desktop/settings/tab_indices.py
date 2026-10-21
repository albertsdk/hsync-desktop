# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""SettingsDialog tab indices (sync=0, p2p=1, server=2, general=3, advanced=4).

Advanced is last, after the app preferences, matching the convention in
comparable tools. The live prefer-primary-role warnings jump to the tab owning
the fix on "Yes".
"""

_SYNC_TAB_INDEX = 0
_P2P_TAB_INDEX = 1
_SERVER_TAB_INDEX = 2
_GENERAL_TAB_INDEX = 3
_ADVANCED_TAB_INDEX = 4

# One-line purpose shown at the top of the mode tabs, where the choice between
# p2p and server is not self-evident. General/Advanced stay undescribed: their
# group titles already read as an index.
_TAB_DESCRIPTION_KEYS: dict[int, str] = {
    _SYNC_TAB_INDEX: "settings.sync.description",
    _P2P_TAB_INDEX: "settings.p2p.description",
    _SERVER_TAB_INDEX: "settings.server_mode.description",
}
