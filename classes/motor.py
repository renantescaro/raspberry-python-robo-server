import RPi.GPIO as GPIO
from classes.settings import Settings

class Motor:
    def __init__(self):
        self._port_motor_right_front = int(Settings.get('PORTA_MOTOR_DIREITA_FRENTE'))
        self._port_motor_right_rear = int(Settings.get('PORTA_MOTOR_DIREITA_TRAS'))
        self._port_motor_left_front = int(Settings.get('PORTA_MOTOR_ESQUERDA_FRENTE'))
        self._port_motor_left_rear = int(Settings.get('PORTA_MOTOR_ESQUERDA_TRAS'))

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._port_motor_right_front, GPIO.OUT)
        GPIO.setup(self._port_motor_right_rear, GPIO.OUT)
        GPIO.setup(self._port_motor_left_front, GPIO.OUT)
        GPIO.setup(self._port_motor_left_rear, GPIO.OUT)

    def to_stop(self):
        GPIO.output(self._port_motor_right_front, GPIO.LOW)
        GPIO.output(self._port_motor_right_rear, GPIO.LOW)
        GPIO.output(self._port_motor_left_front, GPIO.LOW)
        GPIO.output(self._port_motor_left_rear, GPIO.LOW)

    def go_forward(self):
        GPIO.output(self._port_motor_right_rear, GPIO.LOW)
        GPIO.output(self._port_motor_left_rear, GPIO.LOW)
        GPIO.output(self._port_motor_right_front, GPIO.HIGH)
        GPIO.output(self._port_motor_left_front, GPIO.HIGH)

    def go_back(self):
        GPIO.output(self._port_motor_right_front, GPIO.LOW)
        GPIO.output(self._port_motor_left_front, GPIO.LOW)
        GPIO.output(self._port_motor_right_rear, GPIO.HIGH)
        GPIO.output(self._port_motor_left_rear, GPIO.HIGH)

    def turn_left(self):
        GPIO.output(self._port_motor_right_front, GPIO.LOW)
        GPIO.output(self._port_motor_left_rear, GPIO.LOW)
        GPIO.output(self._port_motor_right_rear, GPIO.HIGH)
        GPIO.output(self._port_motor_left_front, GPIO.HIGH)

    def turn_right(self):
        GPIO.output(self._port_motor_left_front, GPIO.LOW)
        GPIO.output(self._port_motor_right_rear, GPIO.LOW)
        GPIO.output(self._port_motor_left_rear, GPIO.HIGH)
        GPIO.output(self._port_motor_right_front, GPIO.HIGH)

    def clean_pins(self):
        GPIO.cleanup()
