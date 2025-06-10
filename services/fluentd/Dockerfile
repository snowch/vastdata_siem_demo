FROM fluent/fluentd:v1.16-1
USER root
RUN apk update && apk add ruby-dev --repository=http://dl-cdn.alpinelinux.org/alpine/v3.19/community
RUN fluent-gem install fluent-plugin-kafka
# Remove the problematic baked-in config file
RUN rm -f /fluentd/etc/fluent.conf
USER fluent