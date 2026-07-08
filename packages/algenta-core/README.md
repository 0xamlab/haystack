# algenta-core (deprecated)

`algenta-core` has **graduated into the [`algenta`](https://pypi.org/project/algenta/) distribution**, which
now owns the `algenta` import name and the `algenta` command — plus the bundled in-process runtime.

This package is a compatibility shim: it installs `algenta` and ships no files of its own.

```bash
pip install --upgrade algenta-core   # pulls in `algenta`
# or, going forward, just:
pip install algenta
```

Update your dependency to `algenta` when convenient; `algenta-core` will be retired.
