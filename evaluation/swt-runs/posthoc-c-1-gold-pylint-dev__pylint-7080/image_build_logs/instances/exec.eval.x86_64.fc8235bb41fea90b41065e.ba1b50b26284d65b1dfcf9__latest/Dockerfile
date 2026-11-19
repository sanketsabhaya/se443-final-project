FROM --platform=linux/x86_64 exec.env.x86_64.fc8235bb41fea90b41065e:latest

COPY ./setup_repo.sh /root/
RUN /bin/bash /root/setup_repo.sh

WORKDIR /testbed/
