import socket

class SocketServer:
    def __init__(self) -> None:
        self._host = ''
        self._port = 5001
        self._origin = (self._host, self._port)
        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection:socket.socket|None = None
        self.client = None
        self._listen()

    def _listen(self):
        self._tcp.bind(self._origin)
        self._tcp.listen(1)

    def _accept(self):
        self.connection, self.client = self._tcp.accept()
        print(f'conectado por {self.client}')

    def execute(self):
        if self.connection is not None:
            return self.connection.recv(1024)

        self._accept()
        return None
