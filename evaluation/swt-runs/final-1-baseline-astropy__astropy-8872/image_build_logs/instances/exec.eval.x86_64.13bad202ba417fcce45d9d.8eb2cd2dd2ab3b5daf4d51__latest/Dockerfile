FROM --platform=linux/x86_64 exec.env.x86_64.13bad202ba417fcce45d9d:latest

COPY ./setup_repo.sh /root/
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
