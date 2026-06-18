
# Funes

[![CI/CD](https://github.com/rgrannell1/funes/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/rgrannell1/funes/actions/workflows/ci-cd.yml)

> I have more memories in myself alone than all men have had since the world was a world.

Funes provides a tiny storage-cache layer for repeated computations. Workflows often run through a list of targets repeatedly; this provides two easy patterns for avoiding repeatly running slow steps.

1. **Cached computations**: did we store the result of this function already? If so, return it, if not compute it and store. Supports predicate-based storage, to avoid storing errors, and also supports cache bypass and eviction. Best for expensive lookups or calculations.
2. **Makers**: does the thing exist in the world? If so, return its details; if not, create it. The more general form, which is more useful for external resource creation, that might be modified by other actors.

## Install

```bash
pip install git+https://github.com/rgrannell1/funes.git
```

With `uv`:

```bash
uv add git+https://github.com/rgrannell1/funes.git
```

## Cached Computation

Workflows often perform expensive steps like statistical analysis of a resource, web-fetch of a URL. We'd prefer to avoid repeatedly computing these for the same resource, while allowing for cache-bypasses and invalidations.

```python
import httpx
from funes import SqliteStore, Ok, Err, is_ok


def fetch_page(url: str):
    response = httpx.get(url)
    if response.is_error:
        return Err(response.status_code)   # is_ok policy won't cache failures
    return Ok(response.text)


with SqliteStore(db_path="cache.db", should_store=is_ok) as store:
    page = store.run(fetch_page, "https://rho.ie")   # miss: fetches the URL
    page = store.run(fetch_page, "https://rho.ie")   # hit: returns the cached Ok

# alternatively; inside a zahir/orbis generator program, use yield from instead
# to relay inner effects on
def crawl():
    with SqliteStore(db_path="cache.db", should_store=is_ok) as store:
        page = yield from store(fetch_page, "https://rho.ie")
```

## Maker

`Maker` inspects world-state; if the external resource already exists we return it, if not we create it.

```python
import pydo
from funes import Maker

client = pydo.Client(token=DIGITALOCEAN_TOKEN)


def find_droplet(name: str):
    droplets = client.droplets.list(name=name)["droplets"]
    return droplets[0] if droplets else None


def make_droplet(name: str):
    request = {"name": name, "region": "lon1", "size": "s-1vcpu-1gb", "image": "debian-12"}
    return client.droplets.create(body=request)["droplet"]


maker = Maker(find=find_droplet, make=make_droplet)
droplet = maker.run("web-1")   # the existing droplet, or a freshly created one
```

`find` can be expensive in practice as resource-count grows; but, we can compose layers and use cached-computations to accelerate things (where can accept the use of cached world-state checks).

```python
from functools import partial
from funes import DictStore, Maker


def is_found(droplet):
    return droplet is not None

store = DictStore(should_store=is_found)
cached_find = partial(store, find_droplet, ttl_seconds=300)

maker = Maker(find=cached_find, make=make_droplet)
droplet = maker.run("web-1")
```

## Storage

Supported storage backends:
- `SqliteStore`: SQLite WAL cache
- `DictStore`: in-memory dictionary backed storage

## License

Copyright (c) 2026 Róisín Grannell

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
