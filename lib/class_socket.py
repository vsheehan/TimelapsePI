# classes/class_socket.py
from sys import getsizeof


class SocketManager:
    _socketio = None

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Use classmethods only — do not instantiate SocketManager")

    @classmethod
    def set_socketio(cls, socketio):
        """
        Set the global SocketIO instance.
        Should be called once in app.py after SocketIO is initialized.
        """
        cls._socketio = socketio

    @classmethod
    def get_socketio(cls):
        """
        Retrieve the global SocketIO instance.
        Raises an error if not initialized.
        """
        if cls._socketio is None:
            raise RuntimeError("SocketIO not initialized — call set_socketio() first.")
        return cls._socketio

    @classmethod
    def emit(cls, event, data):
        """
        Shortcut to emit a socket event via the global SocketIO instance.
        """
        size = getsizeof(data)
        from lib.class_logging import Logger
        Logger.debug(f"Emitting socket event: {event} (size: {size} bytes)", category="socket")
        cls.get_socketio().emit(event, data)