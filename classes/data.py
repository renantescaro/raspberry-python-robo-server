import json

class Data:
    def __init__(self):
        self.camera_v = 0.0
        self.camera_h = 0.0
        self.engine_front = False
        self.engine_rear = False
        self.engine_left = False
        self.engine_right = False
        self._degree_safety = 5

    def execute(self, recebido):
        try:
            received_utf8 = recebido.decode('utf-8')
            received_json = json.loads(received_utf8)

            print(received_json)

            # vertical camera
            if (float(received_json['camera-v']) > 0):
                if ((self.camera_v + self._degree_safety) < 140):
                    self.camera_v += 5
            elif (float(received_json['camera-v']) < 0):
                if ((self.camera_v - self._degree_safety) > 0):
                    self.camera_v -= 5

            # horizontal camera
            if (float(received_json['camera-h']) < 0):
                if ((self.camera_h + self._degree_safety) < 180):
                    self.camera_h += 5
            elif (float(received_json['camera-h']) > 0):
                if ((self.camera_h - self._degree_safety) > 0):
                    self.camera_h -= 5

            self.engine_front = bool(received_json['motor-frente'])
            self.engine_rear = bool(received_json['motor-tras'])
            self.engine_left = bool(received_json['motor-esquerda'])
            self.engine_right = bool(received_json['motor-direita'])

        except ValueError as e:
            print(e)
