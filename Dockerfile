FROM python:3.9.8-slim-buster
WORKDIR /src

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir data
COPY bot.py .
COPY data/songs.json data/

CMD ["python", "bot.py"]
