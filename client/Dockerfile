FROM docker.io/library/node:12.4.0-alpine as build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM docker.io/nginxinc/nginx-unprivileged:1.20
WORKDIR /app
COPY --from=build /app/build /usr/share/nginx/html
COPY --from=build /app/app .
USER root
RUN chgrp -R 0 /usr/share/nginx/html && \
    chmod -R g=u /usr/share/nginx/html
EXPOSE 3200
CMD ["/app/run.sh"]