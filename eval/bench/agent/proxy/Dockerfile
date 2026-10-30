# SPDX-License-Identifier: MIT OR Apache-2.0
# Pośrednik HTTP(S) z listą dozwolonych hostów. Kontener agenta jest tylko w sieci wewnętrznej
# (--internal), więc jedyną drogą na zewnątrz jest ten pośrednik.
FROM alpine:3.20
RUN apk add --no-cache tinyproxy
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY dozwolone /etc/tinyproxy/dozwolone
EXPOSE 8888
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
