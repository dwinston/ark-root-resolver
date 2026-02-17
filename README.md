
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