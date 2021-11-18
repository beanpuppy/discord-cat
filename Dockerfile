FROM python:3.9.8-slim-buster
WORKDIR /src

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot.py .
ADD lib lib

RUN mkdir data
COPY data/songs.json data/

CMD ["python", "bot.py"]
