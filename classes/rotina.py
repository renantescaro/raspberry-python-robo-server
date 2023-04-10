from classes.dados import Dados
from classes.camera import Camera
from classes.motor import Motor


class Rotina:
    def __init__(self) -> None:
        self._camera = Camera()
        self._motor = Motor()
        self._dados = Dados()
        self._parado = True
        self._reto = True

    def executar(self, recebido_socket):
        self._dados.transformar(recebido_socket)

        # motores
        if self._dados.motor_frente:
            self._motor.frente()
            self._parado = False
        elif self._dados.motor_tras:
            self._motor.tras()
            self._parado = False
        elif self._parado == False:
            self._motor.parar()
            self._parado = True

        if self._dados.motor_esquerda:
            self._motor.esquerda()
            self._reto = False
        elif self._dados.motor_direita:
            self._motor.direita()
            self._reto = False
        elif self._reto == False:
            self._motor.reto()
            self._reto = True

        # camera
        if self._dados.camera_v != 0:
            self._camera.mover_vertical(self._dados.camera_v)
        if self._dados.camera_h != 0:
            self._camera.mover_horizontal(self._dados.camera_h)
