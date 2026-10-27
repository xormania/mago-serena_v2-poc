# Mago owns the PHP workflow

Slice 1 uses the original experimental executable at
`46df50c96d93d0ac3655c116c375574277cf0b30` (`mago 1.58.2`), with PHP 8.5
explicitly selected. The framework overlay installs the SDK from that same
revision. The separate LSP configuration remains `mago.toml`;
[the native PHP configuration](../fixtures/mago/mago.toml) is installed as
`mago-php.toml` in the selected disposable application. No application fixture,
PHPStan baseline or legacy formatter configuration was rewritten.

```sh
./bin/poc up --run understand --no-build
./bin/poc quality --run understand
./bin/poc mago --run understand -- analyze --reporting-format json
./bin/poc mago --run understand -- lint --reporting-format json
./bin/poc mago --run understand -- format --check src/Form/Type/TagsInputType.php
./bin/poc mago --run understand -- format src/Form/Type/TagsInputType.php
./bin/poc mago --run understand -- guard --structural --reporting-format json
./bin/poc mago --run understand -- cst --json --names src/Form/Type/TagsInputType.php
./bin/poc slice1 --run understanding-proof --keep-running
```

`quality` returns the real native exit status: the unchanged Demo has existing
findings and therefore returns **1**. This is distinct from passing calibration
controls. Raw JSON/stdout, stderr, exact invocation, binary/config/Composer/source
hashes, duration and native exit survive under `artifacts/<run>/mago/`.
The launcher accepts an explicit run, works from another directory, and refuses
workspace/config/PHP-target overrides. Formatting and analyzer/linter `--fix`
require explicit existing workspace-relative PHP files. Mixed directory targets,
absolute/parent paths and implicit staged/watch/stdin source selection are
rejected before Mago starts; writing commands accept a conservative set of
known options. Mago is the single formatter for new PHP work; its
constructor/chain layout is configured to preserve the selected Demo service.

## Scope and observations

The service is `App\Form\Type\TagsInputType`, with its `TagRepository`
dependency, `PostType` caller and `TagArrayToStringTransformer` collaborator.
The analyzer uses **all `src/` and `tests/`**, with `vendor/` as declaration
context. Filtering the retained report to the service never removes those
callers or dependencies from analysis. Runtime `var/` output and the historical
`semantic/` calibration fixtures are excluded from these application checks.

The standalone calibration with the original dependency lock enumerated exactly
**46 host PHP files**. Native trace records **9,450 compiled source files**,
matching 46 hosts plus **9,404 installed vendor PHP files**. The native precompiled
builtin prelude is also enabled, but is excluded from that compiled-source
count. The declared framework overlay adds dependency files; each combined run
asserts its own actual host+vendor count. `list-files` lists hosts only, so a
separate dependency hash manifest and analyzer trace are retained. The wiring
observer additionally asks Mago's metadata API for resolved vendor declaration
locations; see [framework integration](SYMFONY-WIRING.md).

The original dependency run reports **35 analyzer findings** and **125 lint
findings**. `TagsInputType` itself has no analyzer diagnostic and one existing
`strict-types` warning at line 1. Caller/collaborator diagnostics remain visible:
`PostType:80` has nullable/stringable argument findings; the transformer has
parameter-name, stringable array, mixed array-value and key-specificity findings.
A successful selected-service control does not certify every contextual finding
as harmless.

[The classified analyzer inventory](evidence/slice1/mago-classified-analyzer.json)
and [lint inventory](evidence/slice1/mago-classified-lint.json) preserve each
code, severity, message and primary file/line. The categories are triage, not
suppression or claims of confirmed Mago defects:

| Existing finding family | Concrete examples | Disposition |
| --- | --- | --- |
| Stringable conversion / source element contracts | `PostRepository:104`, fixtures `:78/:206`, `PostType:80`, transformer `:58`, source extension `:170/:175` | Keep findings. PHP weak scalar coercion and PHPDoc array-element contracts require separate source review; no blanket framework limitation inferred. |
| Nullable lifecycle / repeated getter refinement | `PostType:80`, `CheckRequirementsSubscriber:63`, notification subscriber `:62` | Keep findings. No provider in this slice supplies those runtime invariants. |
| Array/value specificity and dynamic inputs | transformer `:69/:77`, paginator `:127`, Console inputs and tests | Keep findings as unconfirmed contract/refinement concerns. Passing behavior tests do not establish universal inference accuracy. |
| Override names and redundant source | voter `:47`, transformer `:38/:52`, redundant casts/docblocks | Existing API compatibility or cleanup suggestions, outside the bounded service exercise. |
| Reflection/API edge cases | source extension `:102/:115/:141` | Potential false/null/callable edge cases retained; no isolated runtime defect asserted. |
| Lint style / strictness | 46 `strict-types`, 32 `assertion-style`, 17 `literal-named-argument`, other style rules | Existing conventions retained. No whole-Demo style migration. |
| Lint design / security policies | empty constructs, method counts, sensitive parameters and literal test passwords | Contextual review needed; not silently disabled. |

## Installed-tool controls

[The native result](evidence/slice1/mago-result.json) and
[evidence index](evidence/slice1/mago-evidence-index.json) retain actual executions.
Every variant modifies the selected disposable service and restores its exact
bytes in `finally`; no baseline is generated.

| Capability | Healthy / defective / restored observation |
| --- | --- |
| Analyzer | `getParent()` normally returns `TextType::class`. Replacing it with `42` is valid PHP and creates `invalid-return-statement` at line 57. Restoring the source restores the complete original diagnostic multiset. A bogus form parent also changes the service's framework meaning. |
| Linter | Inserting `var_dump($options)` into `buildView()` creates enabled `no-debug-symbols` at line 52. Removal restores the complete original lint multiset. This rule has no automatic fix; removal is explicit. |
| Safe fix | Parenthesizing the `findAll()` assignment creates `no-redundant-parentheses`. Native safe-only lint fixing removes precisely the injected parentheses; the reviewed diff restores the exact healthy source. |
| Formatter | Extra whitespace in the return statement makes read-only `format --check` exit 1 without writing. Native formatting restores the exact source. A second write pass is byte-stable and check exits 0. |
| Behavior | Exact original PHPUnit class/method/dataset/file/line identities pass before and after formatting: 53 tests, 120 assertions. Inspection uses dev; these tests explicitly use test. |
| Guard | A real form must retain its `AbstractType` contract. The scoped structural rule permits the service; removing its parent creates `must-extend` at class line 31. Restoring the parent clears it. No invented application layering rules are claimed. |
| CST | Native lossless tree has no parse errors and exactly preserves source bytes. Bounded native-node checks verify class/inheritance spelling, private readonly promoted `$tags: TagRepository` and four method names. Full method bodies remain in the retained native tree. |
| Routing | The public executable runs from `/tmp`; its file set matches the selected run. Unknown run, workspace override, directory/absolute/parent target mixtures and unscoped fixes fail with exit 3 and no misleading output or source changes. |

## Adoption

| Capability | Actual Mago result / evidence | Legacy tool | Disposition and exact remaining gap |
| --- | --- | --- | --- |
| PHP types/logic | Full-context native reports, calibrated new return diagnostic and exact restoration | PHPStan | **Replacement in the new workflow.** Historical fixture comparison only. Existing findings need source-specific review; no claim of whole-project/plugin parity. |
| PHP lint and safe fixes | Enabled rule inventory, debug-call control, reviewed safe parentheses fix | PHP-CS-Fixer overlapping lint/fixes | **Replacement.** Debug-call removal remains manual because that rule supplies no safe fix. |
| PHP formatting | Selected-file check/fix/idempotence plus unchanged original behavior | PHP-CS-Fixer | **Replacement.** No whole-Demo reformat or universal style parity claim. |
| Source structure | Native CST and applicable Guard contract control | No default predecessor | **Adopted for this bounded question.** No general architecture policy invented. |
| Behavioral/framework validation | PHPUnit and Symfony resource/container/Doctrine checks remain | PHPUnit/native Console | **Retained:** distinct behavior/framework contracts, not competing PHP analyzers. |
| Compiled wiring enrichment | Existing extension off/on graph and invalid-binding controls | No PHPStan fallback | See the exact CLI/LSP boundary in [the framework proof](SYMFONY-WIRING.md). |

`docker/check` keeps Composer and Symfony resource/container/entity validation.
Its optional `--legacy-comparison` adds the original PHPStan/PHP-CS-Fixer checks;
they are absent from the default path. CI runs the original semantic/behavior
acceptance and the separate Mago-first slice. A passing slice means the native
capability controls and framework proof passed, not that the raw original
application diagnostics are empty.
