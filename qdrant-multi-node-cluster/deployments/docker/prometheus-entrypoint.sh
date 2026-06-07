#!/bin/sh

if [ -n "$QDRANT_API_KEY" ]; then
    echo -n "$QDRANT_API_KEY" > /etc/prometheus/qdrant_api_key
    echo "API key file created"
else
    echo "WARNING: QDRANT_API_KEY not set, metrics may not be accessible"
    touch /etc/prometheus/qdrant_api_key
fi

exec /bin/prometheus "$@"

