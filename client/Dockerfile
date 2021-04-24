FROM node:12.4.0-alpine as build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.16.0-alpine
WORKDIR /app
COPY --from=build /app/build /usr/share/nginx/html
COPY --from=build /app/app . 
RUN chgrp -R 0 /usr/share/nginx/html/env.js && \
    chmod -R g=u /usr/share/nginx/html/env.js
EXPOSE 3200
CMD ["/app/run.sh"]