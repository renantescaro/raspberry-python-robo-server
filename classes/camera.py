from classes.servo_motor import ServoMotor
from classes.config import Config

class Camera:
    def __init__(self):
        self.porta_servo_vertical = Config.get('PORTA_SERVO_VERTICAL')
        self.porta_servo_horizontal = Config.get('PORTA_SERVO_HORIZONTAL')

    def mover_vertical(self, angulo):
        servo_motor = ServoMotor(porta=self.porta_servo_vertical)
        servo_motor.definir_angulo(angulo)

    def mover_horizontal(self, angulo):
        servo_motor = ServoMotor(porta=self.porta_servo_horizontal)
        servo_motor.definir_angulo(angulo)
