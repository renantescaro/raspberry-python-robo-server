import os
from dotenv import load_dotenv

class Settings:
    @staticmethod
    def empty_file():
        return os.stat('.env').st_size == 0

    @staticmethod
    def get(hash):
        load_dotenv()
        return os.getenv(str(hash).upper())
