import os
from classes.rotina import Rotina
from classes.socket_server import SocketServer
# from classes.ultra_sonico import UltraSonico

# UltraSonico().start()

os.system('git -C /home/pi/raspberry-python-robo-server/ pull origin master')

socket_server = SocketServer()
rotina = Rotina()


while True:
    received_socket = socket_server.execute()

    if not received_socket: break

    rotina.executar(received_socket)
