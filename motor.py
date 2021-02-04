import RPi.GPIO as GPIO

class Motor:
    def __init__(self):
        self.porta_motor_frente   = 24
        self.porta_motor_tras     = 25
        self.porta_motor_esquerda = 4
        self.porta_motor_direita  = 17
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.porta_motor_frente,GPIO.OUT)
        GPIO.setup(self.porta_motor_tras,GPIO.OUT)
        GPIO.setup(self.porta_motor_esquerda,GPIO.OUT)
        GPIO.setup(self.porta_motor_direita,GPIO.OUT)

    def parar(self):
        GPIO.output(self.porta_motor_frente, GPIO.LOW)
        GPIO.output(self.porta_motor_tras, GPIO.LOW)

    def frente(self):
        GPIO.output(self.porta_motor_tras, GPIO.LOW)
        GPIO.output(self.porta_motor_frente, GPIO.HIGH)

    def tras(self):
        GPIO.output(self.porta_motor_frente, GPIO.LOW)
        GPIO.output(self.porta_motor_tras, GPIO.HIGH)

    def esquerda(self):
        GPIO.output(self.porta_motor_direita, GPIO.LOW)
        GPIO.output(self.porta_motor_esquerda, GPIO.HIGH)
    
    def direita(self):
        GPIO.output(self.porta_motor_esquerda, GPIO.LOW)
        GPIO.output(self.porta_motor_direita, GPIO.HIGH)

    def reto(self):
        GPIO.output(self.porta_motor_esquerda, GPIO.LOW)
        GPIO.output(self.porta_motor_direita, GPIO.LOW)


    def limpar_portas(self):
        GPIO.cleanup()