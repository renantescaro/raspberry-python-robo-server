import socket
from dados import Dados
from camera import Camera

HOST = ''
PORT = 5001
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ORIGEM = (HOST, PORT)
camera = Camera()
dados  = Dados()

tcp.bind(ORIGEM)
tcp.listen(1)

while True:
    con, cliente = tcp.accept()
    print('conectado por '+ str(cliente))

    while True:
        mensagem = con.recv(1024)
        if not mensagem: break

        dados.transformar(mensagem)
        camera.mover_vertical(dados.camera_v)
        camera.mover_horizontal(dados.camera_h)
    print('conexão finalizada com o cliente '+str(cliente))
    con.close