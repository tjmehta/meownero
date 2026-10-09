FROM scratch
ADD runtime-rootfs-amd64.tar.gz /
COPY monerod railway-peer.py /app/
USER 1000:1000
EXPOSE 19080 8080
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/python3.12", "-B", "/app/railway-peer.py"]
