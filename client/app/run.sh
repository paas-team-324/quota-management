#!/bin/sh

envsubst < /usr/share/nginx/html/env.js > /tmp/env.js
mv -f /tmp/env.js /usr/share/nginx/html/env.js
nginx -c /app/nginx.conf -g 'daemon off;'