FROM nginx:alpine

RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/ssl

COPY openssl.cnf /etc/nginx/ssl/openssl.cnf

RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \
    -out /etc/nginx/ssl/cert.pem \
    -config /etc/nginx/ssl/openssl.cnf

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443
