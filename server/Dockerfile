FROM python:3
EXPOSE 5000
WORKDIR /app

# get python dependencies
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# run server
CMD [ "./server.py" ]