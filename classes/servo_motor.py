import RPi.GPIO as gpio
import time

class ServoMotor:
    def __init__(self, porta):
        self.servo_pin = porta
        self.deg_0_pulse   = 0.5 
        self.deg_180_pulse = 2.5
        self.f = 50.0
        self.period = 1000 / self.f
        self.k      = 100 / self.period
        self.deg_0_duty = self.deg_0_pulse * self.k
        self.pulse_range = self.deg_180_pulse - self.deg_0_pulse
        self.duty_range = self.pulse_range * self.k
        gpio.setmode(gpio.BCM)
        gpio.setwarnings(False)
        gpio.setup(self.servo_pin, gpio.OUT)
        self.pwm = gpio.PWM(self.servo_pin, self.f)
        self.pwm.start(0)


    def set_angulo(self, angulo):
        try:
            self._set_angulo_convertido(angulo)
            time.sleep(0.025)
        finally:
            pass


    def _set_angulo_convertido(self, angulo):
        duty = self.deg_0_duty + (float(angulo)/180.0) * self.duty_range
        self.pwm.ChangeDutyCycle(duty)