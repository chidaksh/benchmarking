#!/bin/bash
# Fetch the value from the sidecar by service name and save it.
# Prints diagnostics so a failure shows up in the oracle log.
getent hosts server || echo "DNS: could not resolve 'server'"
python3 - <<'PY'
import urllib.request, sys
url = "http://server:8000/value.txt"
try:
    data = urllib.request.urlopen(url, timeout=10).read().decode()
except Exception as e:
    print(f"FETCH FAILED for {url}: {type(e).__name__}: {e}")
    sys.exit(1)
open("/app/value.txt", "w").write(data)
print(f"FETCHED: {data!r}")
PY
