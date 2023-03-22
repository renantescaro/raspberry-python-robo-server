import sys
import time
import signal
import RPi.GPIO as GPIO
from threading import Thread
from classes.config import Config

class UltraSonico(Thread):
    def __init__(self, **kwargs):
        super(UltraSonico, self).__init__(**kwargs)
        self.PORTA_TRIG = int(Config.get('PORTA_ULTRASSONICO_TRIG'))
        self.PORTA_ECHO = int(Config.get('PORTA_ULTRASSONICO_ECHO'))
        self.distancia = 0
        self.taxa_amostragem = 20.0
        self.velocidade_som = 349.10
        self.distancia_maxima = 4.0
        GPIO.setmode(GPIO.BCM)
        signal.signal(signal.SIGINT, self._manipular_assinatura)
        self.max_delta_t = self.distancia_maxima / self.velocidade_som
        GPIO.setup(self.PORTA_TRIG, GPIO.OUT)
        GPIO.setup(self.PORTA_ECHO, GPIO.IN)
        GPIO.output(self.PORTA_TRIG, False)

    def _limpar_portas(self):
        GPIO.cleanup()

    def _manipular_assinatura(self, signum, instant):
        self._limpar_portas()
        sys.exit()

    def run(self):
        while True:
            GPIO.output(self.PORTA_TRIG, True)
            time.sleep(0.00001)
            GPIO.output(self.PORTA_TRIG, False)

            while GPIO.input(self.PORTA_ECHO) == 0:
                start_t = time.time()

            while GPIO.input(self.PORTA_ECHO) == 1 and time.time() - start_t < self.max_delta_t:
                end_t = time.time()

            distance = -1
            if end_t - start_t < self.max_delta_t:
                delta_t = end_t - start_t
                distance = 100*(0.5 * delta_t * self.velocidade_som)

            time.sleep(1/self.taxa_amostragem)
            self.distancia = round(distance, 2)
