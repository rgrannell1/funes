
# Funes

> I have more memories in myself alone than all men have had since the world was a world.

Funes provides a tiny storage-cache layer for repeated computations. Workflows often run through a list of targets repeatedly; this provides an easy pattern for avoiding repeatly running slow steps.

This library ships with a result-type implementation; `should_store` allows selective caching based on a predicate of the value, for example `is_ok`. It also supports cache bypass and eviction.

Supported storage backends:
- `SqliteStore`: SQLite WAL cache
- `DictStore`: in-memory dictionary backed storage

```python
from funes import SqliteStore, Ok, is_ok


def fetch_user(user_id: int):
    return Ok({"id": user_id, "name": "Ireneo"})


with SqliteStore(db_path="cache.db", should_store=is_ok) as store:
    result = store.run(fetch_user, 42)   # miss: runs fetch_user
    result = store.run(fetch_user, 42)   # hit: returns cached Ok

# alternatively; inside a zahir/orbis generator program, use yield from instead
# to relay inner effects on
def my_job():
    with SqliteStore(db_path="cache.db", should_store=is_ok) as store:
        result = yield from store(fetch_user, 42)
```

## License

Copyright (c) 2026 Róisín Grannell

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.