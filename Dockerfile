FROM python:3.9.8-slim-buster
WORKDIR /src

RUN mkdir data
COPY bot.py requirements.txt .
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
