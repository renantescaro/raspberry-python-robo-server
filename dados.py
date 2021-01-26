import json

class Dados:
    def __init__(self):
        self.camera_v = float(0.0)
        self.camera_h = float(0.0)

    def transformar(self, recebido):
        recebido_utf8 = recebido.decode('utf-8')
        recebido_json = json.loads(recebido_utf8)
        self.camera_v = float(recebido_json['camera-v'])
        self.camera_h = float(recebido_json['camera-h'])