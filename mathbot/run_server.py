"""Faqat Mini App/API backend'ini ishga tushiruvchi alohida nuqta.

Render'da bu botlardan (main.py, turob/daxshat.py) ALOHIDA "Web Service"
sifatida deploy qilinishi kerak - shundagina Render tashqi HTTPS URL
ajratib, $PORT orqali trafikni shu ilovaga yo'naltiradi.
"""

import logging

from aiohttp import web

from config import WEBAPP_HOST, WEBAPP_PORT
from webapp.server import create_app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(create_app(), host=WEBAPP_HOST, port=WEBAPP_PORT)
