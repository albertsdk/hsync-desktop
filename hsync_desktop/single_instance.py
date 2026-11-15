# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Single instance management for HSYNC Desktop.

Ensures only one instance of the application runs at a time.
If a second instance is launched, it signals the first instance
to bring its window to the foreground and then exits.
"""

from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    """Manages single instance enforcement using local sockets.

    Uses QLocalServer/QLocalSocket for cross-platform IPC.
    The first instance creates a server; subsequent instances
    connect as clients to signal the existing instance.
    """

    # Emitted when another instance tries to start
    activate_requested = Signal()

    # Base identifier; the effective name is per user (see ``_server_name``).
    _SERVER_NAME = "hsync-desktop-single-instance"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server: QLocalServer | None = None

    @classmethod
    def _server_name(cls) -> str:
        """Return the per-user server name.

        Windows named pipes are machine-global and macOS/Linux sockets share
        ``/tmp``: with one fixed name, a second logged-in user would reach the
        first user's instance (or fail to listen) and exit silently.
        """
        try:
            user = getpass.getuser()
        except (KeyError, OSError):
            user = ""
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in user)
        return f"{cls._SERVER_NAME}-{safe}" if safe else cls._SERVER_NAME

    def try_start(self) -> bool:
        """Try to become the primary instance.

        Returns:
            True if this is the primary instance (server started successfully).
            False if another instance is already running (we signaled it).
        """
        # First, try to connect to an existing instance
        socket = QLocalSocket(self)
        socket.connectToServer(self._server_name())

        if socket.waitForConnected(500):
            # Another instance is running - send activation message
            socket.write(b"activate")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return False

        # No existing instance - become the primary
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)

        # Remove stale socket file (Linux/macOS)
        QLocalServer.removeServer(self._server_name())

        # Failure here shouldn't happen normally.
        return bool(self._server.listen(self._server_name()))

    def _on_new_connection(self) -> None:
        """Handle incoming connection from another instance."""
        if self._server is None:
            return

        socket = self._server.nextPendingConnection()
        if socket is None:
            return

        # Wait for the message
        if socket.waitForReadyRead(1000):
            data = socket.readAll().data()
            if data == b"activate":
                self.activate_requested.emit()

        socket.disconnectFromServer()
        socket.deleteLater()
