# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""Tests for hsync_desktop.single_instance module."""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import QByteArray


class TestSingleInstance:
    """Test SingleInstance class."""

    def test_server_name_constant(self):
        """Test that server name constant is defined."""
        from hsync_desktop.single_instance import SingleInstance

        assert hasattr(SingleInstance, "_SERVER_NAME")
        assert SingleInstance._SERVER_NAME == "hsync-desktop-single-instance"

    def test_activate_requested_signal_exists(self):
        """Test that activate_requested signal exists."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        assert hasattr(instance, "activate_requested")

    def test_init_with_parent(self):
        """Test initialization with parent QObject."""
        from PySide6.QtCore import QObject

        from hsync_desktop.single_instance import SingleInstance

        parent = QObject()
        instance = SingleInstance(parent)
        assert instance.parent() == parent

    def test_init_sets_server_to_none(self):
        """Test initialization sets _server to None."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        assert instance._server is None

    @patch("hsync_desktop.single_instance.QLocalSocket")
    @patch("hsync_desktop.single_instance.QLocalServer")
    def test_try_start_another_instance_running(self, mock_server_class, mock_socket_class):
        """Test try_start when another instance is already running."""
        from hsync_desktop.single_instance import SingleInstance

        # Setup mock socket to succeed connection (existing instance)
        mock_socket = MagicMock()
        mock_socket.waitForConnected.return_value = True
        mock_socket_class.return_value = mock_socket

        instance = SingleInstance()

        result = instance.try_start()

        assert result is False
        mock_socket.write.assert_called_once_with(b"activate")

    @patch("hsync_desktop.single_instance.QLocalSocket")
    @patch("hsync_desktop.single_instance.QLocalServer")
    def test_try_start_server_fails_to_listen(self, mock_server_class, mock_socket_class):
        """Test try_start when server fails to listen."""
        from hsync_desktop.single_instance import SingleInstance

        # Setup mock socket to fail connection
        mock_socket = MagicMock()
        mock_socket.waitForConnected.return_value = False
        mock_socket_class.return_value = mock_socket

        # Setup mock server to fail listening
        mock_server = MagicMock()
        mock_server.listen.return_value = False
        mock_server_class.return_value = mock_server

        instance = SingleInstance()

        result = instance.try_start()

        assert result is False

    @patch("hsync_desktop.single_instance.QLocalSocket")
    @patch("hsync_desktop.single_instance.QLocalServer")
    def test_try_start_removes_stale_server(self, mock_server_class, mock_socket_class):
        """Test try_start calls removeServer to clean up stale socket files."""
        from hsync_desktop.single_instance import SingleInstance

        # Setup mock socket to fail connection (no existing instance)
        mock_socket = MagicMock()
        mock_socket.waitForConnected.return_value = False
        mock_socket_class.return_value = mock_socket

        # Setup mock server
        mock_server = MagicMock()
        mock_server.listen.return_value = True
        mock_server_class.return_value = mock_server

        instance = SingleInstance()
        instance.try_start()

        # Check removeServer was called
        mock_server_class.removeServer.assert_called_once()


class TestSingleInstanceSignals:
    """Test signal connections for SingleInstance."""

    def test_activate_requested_can_connect(self):
        """Test that activate_requested signal can be connected to."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        callback_called = []

        def callback():
            callback_called.append(True)

        instance.activate_requested.connect(callback)

        # Emit the signal
        instance.activate_requested.emit()

        assert len(callback_called) == 1

    def test_activate_requested_can_disconnect(self):
        """Test that activate_requested signal can be disconnected."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        callback_called = []

        def callback():
            callback_called.append(True)

        instance.activate_requested.connect(callback)
        instance.activate_requested.disconnect(callback)

        # Emit the signal
        instance.activate_requested.emit()

        assert len(callback_called) == 0


class TestOnNewConnection:
    """Test _on_new_connection method."""

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_emits_signal(self, mock_socket_class):
        """Test _on_new_connection emits activate_requested on valid message."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = MagicMock()

        # Setup mock socket - need to return QByteArray for readAll()
        mock_socket = MagicMock()
        mock_socket.waitForReadyRead.return_value = True
        qba = QByteArray(b"activate")
        mock_socket.readAll.return_value = qba
        instance._server.nextPendingConnection.return_value = mock_socket

        callback_called = []
        instance.activate_requested.connect(lambda: callback_called.append(True))

        instance._on_new_connection()

        assert len(callback_called) == 1

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_ignores_non_activate(self, mock_socket_class):
        """Test _on_new_connection ignores non-activate messages."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = MagicMock()

        # Setup mock socket with non-activate message
        mock_socket = MagicMock()
        mock_socket.waitForReadyRead.return_value = True
        qba = QByteArray(b"other")
        mock_socket.readAll.return_value = qba
        instance._server.nextPendingConnection.return_value = mock_socket

        callback_called = []
        instance.activate_requested.connect(lambda: callback_called.append(True))

        instance._on_new_connection()

        assert len(callback_called) == 0

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_server_none(self, mock_socket_class):
        """Test _on_new_connection returns early when server is None."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = None

        # Should not raise
        instance._on_new_connection()

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_no_pending_connection(self, mock_socket_class):
        """Test _on_new_connection handles None pending connection."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = MagicMock()
        instance._server.nextPendingConnection.return_value = None

        # Should not raise
        instance._on_new_connection()

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_socket_disconnects(self, mock_socket_class):
        """Test _on_new_connection disconnects socket after processing."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = MagicMock()

        # Setup mock socket
        mock_socket = MagicMock()
        mock_socket.waitForReadyRead.return_value = True
        qba = QByteArray(b"activate")
        mock_socket.readAll.return_value = qba
        instance._server.nextPendingConnection.return_value = mock_socket

        instance._on_new_connection()

        mock_socket.disconnectFromServer.assert_called_once()
        mock_socket.deleteLater.assert_called_once()

    @patch("hsync_desktop.single_instance.QLocalSocket")
    def test_on_new_connection_no_data_to_read(self, mock_socket_class):
        """Test _on_new_connection when no data is available to read."""
        from hsync_desktop.single_instance import SingleInstance

        instance = SingleInstance()
        instance._server = MagicMock()

        # Setup mock socket - waitForReadyRead returns False
        mock_socket = MagicMock()
        mock_socket.waitForReadyRead.return_value = False
        instance._server.nextPendingConnection.return_value = mock_socket

        callback_called = []
        instance.activate_requested.connect(lambda: callback_called.append(True))

        # Should not raise and not emit signal
        instance._on_new_connection()

        assert len(callback_called) == 0
