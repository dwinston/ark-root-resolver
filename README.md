
# Run locally

```shell
fastapi dev src/ark_root_resolver/main.py
```

# Test cases

```shell
# No leading '/' (modern ARK)
open "http://127.0.0.1:8000/ark:12148/btv1b8449691v/f29"

# leading '/' (legacy ARK)
open "http://127.0.0.1:8000/ark:/12148/btv1b8449691v/f29"
```

# Docker image

```shell
# Build and run locally
docker build -t ark-root-resolver .
docker run --rm -p 8000:8000 ark-root-resolver

# Pull and run from Docker Hub
docker run --rm -p 8000:8000 dwinston/ark-root-resolver
```