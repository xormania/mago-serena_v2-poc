# Selected service: TagsInputType

The slice explains the existing `App\Form\Type\TagsInputType` form service,
its `TagRepository` dependency and `PostType` caller. Source identities remain
the original adapted Demo fixture. The exact Mago LSP source is
`46df50c96d93d0ac3655c116c375574277cf0b30` (version string `1.58.2`);
Serena is `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3`.

## What the source and semantic tools establish

The actual MCP → Serena REPL → Mago queries returned these declarations and
references. Source locations in this explanation are **one-based**; retained
LSP/reference positions are zero-based.

| Fact | Source location | Actual observation |
| --- | --- | --- |
| `TagsInputType` extends Symfony `AbstractType` | `app/src/Form/Type/TagsInputType.php:31` | Class body from `find_symbol`; vendor parent declaration from `find_declaration`; direct LSP type hierarchy returns `Symfony\Component\Form\AbstractType` |
| Constructor declares readonly `TagRepository $tags` | `app/src/Form/Type/TagsInputType.php:34` | Body plus dependency definition resolves `app/src/Repository/TagRepository.php:29`; hover retains `@template-extends ServiceEntityRepository<Tag>` |
| `PostType` selects this form type for its `tags` field | `app/src/Form/PostType.php:69` | Exact two references: import at line 16 and class reference at line 69; reverse definition returns the selected class |
| `buildForm` transforms collection → array → string | `app/src/Form/Type/TagsInputType.php:45` | Returned source body constructs `CollectionToArrayTransformer`, then `TagArrayToStringTransformer($this->tags)` |
| `buildView` supplies repository tags to view variables | `app/src/Form/Type/TagsInputType.php:52` | `find_declaration` resolves inherited `findAll` to `vendor/doctrine/orm/src/EntityRepository.php:94`; direct outgoing call hierarchy confirms that source call |
| Parent field type is Symfony `TextType` | `app/src/Form/Type/TagsInputType.php:55` | Returned `getParent(): string` body returns `TextType::class` |

The inherited declaration hover is generic `list<T>` information. It is not a
claim that a declaration-hover request resolves every call-site generic, nor
that an analysis query executes Doctrine. Symfony service IDs and effective
constructor bindings require the compiled-container evidence described in
[the wiring integration](SYMFONY-WIRING.md). A source type declaration alone
does not prove which service the container injects.

## Capability boundaries

`include_info=True` on the existing `s.lsp.find_symbol` and
`s.lsp.find_declaration` methods already requests Mago hover. For example,
`TagsInputType/buildView` returns a signature containing
`array<string, mixed> $options`. An earlier capability table overlooked that
facade option. No adapter modification is needed for this capability.
`include_body=True` supersedes `include_info` in this Serena revision, so the
proof uses separate requests.

| Capability | Server | Serena path demonstrated |
| --- | --- | --- |
| Class/method bodies and source locations | Advertised and returned | Existing `find_symbol` |
| Dependency and inherited vendor definitions | Advertised and returned | Existing `find_declaration` |
| Exact caller/reference context | Advertised and returned | Existing `find_referencing_symbols` |
| Declaration hover/signature information | Advertised and returned | Existing `include_info=True` option |
| Type and outgoing call hierarchy | Advertised and returned | Direct LSP probe; no dedicated REPL facade method in this revision |
| Promoted `$tags` property as its own document symbol | Not returned in this probe | Constructor/class body still exposes its declaration; no property-symbol claim |
| Compiled-wiring extension results in LSP | Separate propagation probe | See recorded server-propagation result; CLI contribution is not inferred to reach Serena |

The [propagation control](evidence/slice1/semantic-propagation-result.json)
uses the same declared extension configuration and coherent binary/SDK source.
A wrapper writes a marker immediately before executing the original worker
command. CLI analysis starts the worker, runs the final-graph observer, and
reports the package's `analysis-attestation` with `complete: true` and 34 source
files. The configured LSP returns normal service symbols but creates neither
the worker-start marker nor observer output. This isolates **server
propagation**, rather than Composer compatibility or Serena exposure. Existing
native PHP findings still give the CLI exit 1; the control does not call that
application clean. The pinned LSP builds its native plugin registry in
`src/language_server/workspace/loading.rs:89` without the external-host
initialization used by the CLI. See the [unpublished reproduction draft](upstream/mago-lsp-extension-hosts.md).

The healthy selected-file LSP diagnostic was the pre-existing `strict-types`
warning at file start. The proof preserves it rather than claiming a clean
application or suppressing it. PHP checks and disposable defect controls are
separate from semantic navigation.

## Reproduction and evidence

For a running selected workspace:

```sh
.venv/bin/python tests/integration/service_semantics.py --run <run-id>
.venv/bin/python tests/integration/service_semantics.py --run <run-id> --extension-propagation
```

The second command requires the prepared framework overlay. The host launcher
is absolute and starts from `/tmp`; wrong-run routing must return exit 3,
actionable stderr and no stdout. Each invocation retains a unique attempt under
`artifacts/<run-id>/service-semantics/` with raw MCP calls, direct LSP frames,
capabilities, actual results and source hashes. Semantic inspection must leave
the three selected application files unchanged.

The local agent also made **adaptive live REPL calls** through
`bin/serena-mcp --run semantic-slice`, inspecting returned declarations and then
following dependency, caller and inherited-method results. Its separate
[raw transcript](evidence/slice1/semantic-agent-mcp.jsonl) includes the missing
promoted-property query and original warning. The
[deterministic replay](evidence/slice1/semantic-replay-mcp.jsonl) independently
asserts the selected facts; [direct frames](evidence/slice1/semantic-direct-lsp.jsonl)
prove the hierarchy responses. The
[evidence index](evidence/slice1/semantic-evidence-index.json) records hashes and
original artifact paths. Neither this read-only investigation nor replay is a
new autonomous code-development benchmark. Historical semantic-rename evidence
and the original full-sync/stale-span findings retain their existing attribution.
