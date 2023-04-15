import os
from classes.routine import Routine
from classes.socket_server import SocketServer
# from classes.ultra_sonico import UltraSonico

# UltraSonico().start()

os.system('git -C /home/pi/raspberry-python-robo-server/ pull origin master')

socket_server = SocketServer()
routine = Routine()

while True:
    socket_server.accept()

    while True:
        received_socket = socket_server.execute()
        if not received_socket: break
        routine.execute(received_socket)
