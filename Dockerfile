FROM docker.io/library/node:12.4.0-alpine as build

# build ui
WORKDIR /build
COPY client/package.json .
RUN npm install
COPY client/ .
RUN npm run build

FROM docker.io/library/python:3.9-slim

# transfer build
EXPOSE 5000
WORKDIR /app
COPY --from=build /build/build ./ui

# python dependencies
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# run server
COPY server/server.py ./
CMD [ "./server.py" ]