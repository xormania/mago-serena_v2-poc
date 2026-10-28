# Minimal native external-analyzer reproduction

This fixture uses the real Mago PHP SDK. Its explicit regression plugin adds one
`Body` dependency from `Repro\Service::__construct` to `Repro\Concrete`; native
PHP supplies the separate `Repro\Port` signature dependency. The plugin is test
input, not a Symfony analyzer or a claim that this edge follows from PHP alone.
Its after-analysis observer reads Mago's final graph without adding more edges.

Use experimental base `46df50c96d93d0ac3655c116c375574277cf0b30` and its exact
Composer SDK `1.58.2`/MANA `2.1`. PHP with the SDK's installed Composer dependencies
is required. The script uses Python's standard library and the repository's
`tests/integration/lsp_client.py` plus `trace.py`; no adapter or Serena is involved.

From the repository root, compare separately built binaries:

```sh
python3 docs/upstream/lsp-extensions-repro/reproduce.py \
  --binary /path/to/unpatched/mago --autoload /path/to/vendor/autoload.php \
  --evidence /absolute/new/baseline-evidence
python3 docs/upstream/lsp-extensions-repro/reproduce.py --candidate \
  --binary /path/to/candidate/mago --autoload /path/to/vendor/autoload.php \
  --evidence /absolute/new/candidate-evidence
```

`MAGO_REPRO_AUTOLOAD` can supply the autoloader instead. If copied outside the
repository, pass `--helpers /path/to/tests/integration` and keep `Example.php`,
`worker.php` and `reproduce.py` together. The PoC image provides the helpers at
`/opt/poc/tests/integration` and its prepared app autoloader at
`/app/vendor/autoload.php`.

Both modes require real CLI worker startup and the final CLI Body edge. Baseline
mode requires working native LSP symbols with no worker startup/observer.
Candidate mode requires the native `mago/symbolReferences` response to include
the edge with the extension on and omit it with the extension disabled. It also
checks that disabled mode starts no worker. Complete bounded protocol frames,
configuration, CLI report, observer graph and result are retained. An unexpected
outcome fails; exit 0 for baseline means the omission was reproduced.

All source/config generation occurs in a temporary directory removed on exit.
The evidence directory must be new. These tiny controls do not establish Symfony
metadata freshness, incremental lifecycle, Serena propagation or adaptive-agent
success; the dedicated PoC proof covers those separately.
