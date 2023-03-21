import os
from dotenv import load_dotenv

class Config:
    @staticmethod
    def arquivo_vazio():
        return os.stat('.env').st_size == 0

    @staticmethod
    def get(hash):
        load_dotenv()
        return os.getenv(str(hash).upper())
