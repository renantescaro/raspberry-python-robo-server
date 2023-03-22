import RPi.GPIO as GPIO
from classes.config import Config

class Motor:
    def __init__(self):
        self._porta_motor_direita_frente = int(Config.get('PORTA_MOTOR_DIREITA_FRENTE'))
        self._porta_motor_direita_tras = int(Config.get('PORTA_MOTOR_DIREITA_TRAS'))
        self._porta_motor_esquerda_frente = int(Config.get('PORTA_MOTOR_ESQUERDA_FRENTE'))
        self._porta_motor_esquerda_tras = int(Config.get('PORTA_MOTOR_ESQUERDA_TRAS'))

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._porta_motor_direita_frente, GPIO.OUT)
        GPIO.setup(self._porta_motor_direita_tras, GPIO.OUT)
        GPIO.setup(self._porta_motor_esquerda_frente, GPIO.OUT)
        GPIO.setup(self._porta_motor_esquerda_tras, GPIO.OUT)

    def parar(self):
        GPIO.output(self._porta_motor_direita_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.LOW)

    def frente(self):
        GPIO.output(self._porta_motor_direita_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_frente, GPIO.HIGH)
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.HIGH)

    def tras(self):
        GPIO.output(self._porta_motor_direita_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_tras, GPIO.HIGH)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.HIGH)

    def esquerda(self):
        GPIO.output(self._porta_motor_direita_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_tras, GPIO.HIGH)
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.HIGH)


    def direita(self):
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.HIGH)
        GPIO.output(self._porta_motor_direita_frente, GPIO.HIGH)

    def reto(self):
        GPIO.output(self._porta_motor_direita_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_frente, GPIO.LOW)
        GPIO.output(self._porta_motor_direita_tras, GPIO.LOW)
        GPIO.output(self._porta_motor_esquerda_tras, GPIO.LOW)

    def limpar_portas(self):
        GPIO.cleanup()
