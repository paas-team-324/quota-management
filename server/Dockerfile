FROM python:3

# general
EXPOSE 5000
WORKDIR /app

# python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# run server
COPY server.py ./
CMD [ "./server.py" ]