# azami/tcpdump — pinned tcpdump runner. Build: docker build -t azami/tcpdump:latest runners/tcpdump
# Capture requires the container to share the host/authorized network namespace; the
# operator supplies --net/--cap at run time only for authorized interfaces.
FROM alpine:3.20
RUN apk add --no-cache tcpdump
