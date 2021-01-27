import socket
from dados import Dados
from camera import Camera
from motor import Motor

HOST   = ''
PORT   = 5001
tcp    = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ORIGEM = (HOST, PORT)
camera = Camera()
motor  = Motor()
dados  = Dados()

tcp.bind(ORIGEM)
tcp.listen(1)

while True:
    con, cliente = tcp.accept()
    print('conectado por '+ str(cliente))

    while True:
        recebido_socket = con.recv(1024)
        if not recebido_socket: break

        # json para objeto
        dados.transformar(recebido_socket)

        # motores
        if dados.motor_frente:
            motor.frente()
        elif dados.motor_tras:
            motor.tras()
        else:
            motor.parar()

        if dados.motor_esquerda:
            motor.esquerda()
        elif dados.motor_direita:
            motor.direita()
        else:
            motor.reto()

        # camera
        if dados.camera_v != 0:
            camera.mover_vertical(dados.camera_v)
        if dados.camera_h != 0:
            camera.mover_horizontal(dados.camera_h)


    print('conexão finalizada com o cliente '+str(cliente))
    con.close