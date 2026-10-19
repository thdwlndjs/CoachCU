"""Local IPC so an unlock-triggered launch reuses the running application."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "PersonalWorkCoach.SingleInstance.v1"


class SingleInstance:
    def __init__(self, on_trigger: Callable[[str], None]) -> None:
        self.on_trigger = on_trigger
        self.server = QLocalServer()
        self.server.newConnection.connect(self._accept_connection)

    @staticmethod
    def notify_existing(trigger: str) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if not socket.waitForConnected(400):
            return False
        socket.write(trigger.encode("utf-8"))
        socket.waitForBytesWritten(400)
        socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        if self.server.listen(SERVER_NAME):
            return True
        QLocalServer.removeServer(SERVER_NAME)
        return self.server.listen(SERVER_NAME)

    def _accept_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda socket=socket: self._read_trigger(socket))
        if socket.bytesAvailable():
            self._read_trigger(socket)

    def _read_trigger(self, socket: QLocalSocket) -> None:
        trigger = bytes(socket.readAll()).decode("utf-8", errors="replace")
        if not trigger:
            return
        socket.disconnectFromServer()
        socket.deleteLater()
        QTimer.singleShot(0, lambda: self.on_trigger(trigger))
