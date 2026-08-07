# Homeclaw for Home Assistant

This repository is the public, code-only distribution of the Homeclaw Home
Assistant custom integration. Homeclaw itself and all household data remain on
the local network.

## Install with HACS

1. In HACS, add `https://github.com/astyrrian1/homeclaw-ha` as a custom
   **Integration** repository.
2. Download Homeclaw and restart Home Assistant.
3. Add or reload the Homeclaw integration in **Settings → Devices & services**.

The integration talks only to the Homeclaw API URL configured in Home
Assistant. It does not contain inference models, household configuration,
credentials, or a cloud fallback.

## Release contract

The integration version is declared in
`custom_components/homeclaw/manifest.json`. Repository contract tests run with:

```sh
python3 -m unittest discover -s tests -v
```
