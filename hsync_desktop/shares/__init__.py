# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Named shares: a folder + p2p/server target + the sync parameters.

A *share* bundles the local folder, the p2p/server mode and every sync/mode
setting under one name. The store keeps a list of named shares and writes the
active one into the flat ``QSettings`` keys ("the active projection"), so the
engine argument builder and every reader stay unchanged.
"""

from hsync_desktop.shares.model import Share
from hsync_desktop.shares.store import BOOK_KEY, ShareStore, sort_key

__all__ = ["BOOK_KEY", "Share", "ShareStore", "sort_key"]
