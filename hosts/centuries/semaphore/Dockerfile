FROM semaphoreui/semaphore:latest

USER root

# Installeer de benodigde Python libraries voor NetBox integration
RUN apk add --no-cache python3 py3-pip && \
    pip install --upgrade --break-system-packages pytz pynetbox requests

# Switch terug naar de semaphore user voor security
USER semaphore
