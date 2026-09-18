# azami/nmap — pinned Nmap runner. Build: docker build -t azami/nmap:latest runners/nmap
FROM alpine:3.20
RUN apk add --no-cache nmap nmap-scripts
# No ENTRYPOINT: the DockerRunner pins --entrypoint nmap and passes args.
