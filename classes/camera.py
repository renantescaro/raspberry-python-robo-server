from classes.servo_motor import ServoMotor

class Camera:
    def __init__(self):
        self.porta_servo_vertical = 18
        self.porta_servo_horizontal = 23

    def mover_vertical(self, angulo):
        servo_motor = ServoMotor(porta=self.porta_servo_vertical)
        servo_motor.definir_angulo(angulo)

    def mover_horizontal(self, angulo):
        servo_motor = ServoMotor(porta=self.porta_servo_horizontal)
        servo_motor.definir_angulo(angulo)
