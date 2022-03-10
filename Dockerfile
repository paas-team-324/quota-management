FROM docker.io/library/node:14.18 as build

# build ui
WORKDIR /build
COPY client/package.json .
RUN npm install
COPY client/ .
RUN npm run build

FROM docker.io/library/python:3.9-slim

# set-up backend
EXPOSE 5000
WORKDIR /app
ENV PATH="/app/bin:${PATH}"
RUN mkdir /usr/local/share/ca-certificates/extra ./bin && \
    ln -s /var/run/secrets/kubernetes.io/serviceaccount/ca.crt /usr/local/share/ca-certificates/extra/local-cluster-ca.crt && \
    chgrp -R 0 /etc/ssl/certs/ && \
    chmod -R g=u /etc/ssl/certs/
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY bin/ server/server.py bin/

# transfer ui build
COPY --from=build /build/build ./ui

# run server
CMD [ "docker-entrypoint.sh" ]