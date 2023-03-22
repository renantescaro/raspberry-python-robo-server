import socket
import os
from classes.dados import Dados
from classes.camera import Camera
from classes.motor import Motor
# from classes.ultra_sonico import UltraSonico

HOST = ''
PORT = 5001
ORIGEM = (HOST, PORT)
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
camera = Camera()
motor = Motor()
dados = Dados()

tcp.bind(ORIGEM)
tcp.listen(1)

# UltraSonico().start()

os.system('git pull origin master')

while True:
    con, cliente = tcp.accept()
    print(f'conectado por {cliente}')

    parado = True
    reto = True
    while True:
        recebido_socket = con.recv(1024)
        if not recebido_socket: break

        # json para objeto
        dados.transformar(recebido_socket)

        # motores
        if dados.motor_frente:
            motor.frente()
            parado = False
        elif dados.motor_tras:
            motor.tras()
            parado = False
        elif parado == False:
            motor.parar()
            parado = True

        if dados.motor_esquerda:
            motor.esquerda()
            reto = False
        elif dados.motor_direita:
            motor.direita()
            reto = False
        elif reto == False:
            motor.reto()
            reto = True

        # camera
        if dados.camera_v != 0:
            camera.mover_vertical(dados.camera_v)
        if dados.camera_h != 0:
            camera.mover_horizontal(dados.camera_h)

    print(f'conexão finalizada com o cliente {cliente}')
    con.close
