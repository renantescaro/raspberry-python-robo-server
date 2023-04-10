import json
import socket


HOST = ''
PORT = 5001
ORIGEM = (HOST, PORT)
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

tcp.bind(ORIGEM)
tcp.listen(1)

while True:
    conexao, cliente = tcp.accept()
    print(f'conectado por {cliente}')

    while True:
        recebido_socket = conexao.recv(1024)
        if not recebido_socket: break

        recebido_utf8 = recebido_socket.decode('utf-8')
        recebido_json = json.loads(recebido_utf8)

        print(recebido_utf8)

    print(f'conexão finalizada com o cliente {cliente}')
    conexao.close
