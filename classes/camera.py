from classes.servo_motor import ServoMotor
from classes.settings import Settings

class Camera:
    def __init__(self):
        self.vertical_servo_port = int(Settings.get('PORTA_SERVO_VERTICAL'))
        self.horizontal_servo_port = int(Settings.get('PORTA_SERVO_HORIZONTAL'))

    def move_vertical(self, angulo):
        servo_motor = ServoMotor(port=self.vertical_servo_port)
        servo_motor.set_angle(angulo)

    def move_horizontal(self, angulo):
        servo_motor = ServoMotor(port=self.horizontal_servo_port)
        servo_motor.set_angle(angulo)
