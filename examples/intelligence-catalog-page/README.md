# ZERO Intelligence Catalog Page Example

This example builds a deterministic static HTML page from the checked
`zero.intelligence.catalog.v1` contract.

```bash
just intelligence-catalog-page-example
```

The page makes the open/commercial boundary inspectable without a hosted
service. It uses no JavaScript, remote assets, secrets, tokens, wallets,
private records, or live trading setup.

To regenerate the checked contract artifact:

```bash
PYTHONPATH="$PWD/engine/src" python3 examples/intelligence-catalog-page/build.py \
  --output contracts/intelligence/catalog.html
```
