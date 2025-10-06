import os
import openai

from dotenv import load_dotenv

load_dotenv()

#SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.getcwd(), 'lpg.sqlite')
#SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}'

SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'
SQLALCHEMY_ECHO = True
SQLALCHEMY_TRACK_MODIFICATIONS = True
DEBUG = True
SECRET_KEY = 'abcd'

openai_api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = openai_api_key
