# ductape

> The duct tape your data pipeline deserves.

**ductape** is a universal schema adapter generator. It reads versioned C struct headers
and generates compilable C++ converter classes that handle all version combinations
automatically — using a hub-and-spoke pattern that scales linearly, not quadratically.

You write config. It writes converters.

## Quick start

```bash
pip install -e .
ductape generate --config variants/reference_project/config.yaml --output build/
```

## Documentation

- [Architecture specification](ARCHITECTURE_FINAL_v3.md)
- [Build phases](docs/build-phases.md)

## Status

Under construction.
