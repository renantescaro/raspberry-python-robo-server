import json

class Dados:
    def __init__(self):
        self.camera_v = 0.0
        self.camera_h = 0.0
        self.motor_frente = False
        self.motor_tras = False
        self.motor_esquerda = False
        self.motor_direita = False
        self._grau_seguranca = 5

    def transformar(self, recebido):
        try:
            recebido_utf8 = recebido.decode('utf-8')
            recebido_json = json.loads(recebido_utf8)

            print(recebido_utf8)

            # camera vertical
            if (float(recebido_json['camera-v']) > 0):
                if ((self.camera_v + self._grau_seguranca) < 140):
                    self.camera_v += 5
            elif (float(recebido_json['camera-v']) < 0):
                if ((self.camera_v - self._grau_seguranca) > 0):
                    self.camera_v -= 5

            # camera horizontal
            if (float(recebido_json['camera-h']) < 0):
                if ((self.camera_h + self._grau_seguranca) < 180):
                    self.camera_h += 5
            elif (float(recebido_json['camera-h']) > 0):
                if ((self.camera_h - self._grau_seguranca) > 0):
                    self.camera_h -= 5

            self.motor_frente = bool(recebido_json['motor-frente'])
            self.motor_tras = bool(recebido_json['motor-tras'])
            self.motor_esquerda = bool(recebido_json['motor-esquerda'])
            self.motor_direita = bool(recebido_json['motor-direita'])

        except ValueError as e:
            print(e)
