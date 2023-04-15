from classes.data import Data
from classes.camera import Camera
from classes.motor import Motor


class Routine:
    def __init__(self) -> None:
        self._camera = Camera()
        self._motor = Motor()
        self._data = Data()
        self._stopped = True
        self._forwarded = True

    def execute(self, recebido_socket):
        self._data.execute(recebido_socket)

        # motores
        if self._data.engine_front:
            self._motor.go_forward()
            self._stopped = False
        elif self._data.engine_rear:
            self._motor.go_back()
            self._stopped = False
        elif self._stopped == False:
            self._motor.to_stop()
            self._stopped = True

        if self._data.engine_left:
            self._motor.turn_left()
            self._forwarded = False
        elif self._data.engine_right:
            self._motor.turn_right()
            self._forwarded = False
        elif self._forwarded == False:
            self._motor.to_stop()
            self._forwarded = True

        # camera
        if self._data.camera_v != 0:
            self._camera.move_vertical(self._data.camera_v)
        if self._data.camera_h != 0:
            self._camera.move_horizontal(self._data.camera_h)
