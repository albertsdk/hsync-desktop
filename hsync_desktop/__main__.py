# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Entry point for running as a module: python -m hsync_desktop."""

import sys

from hsync_desktop.main import main

if __name__ == "__main__":
    sys.exit(main())
