# Standalone Demo fixture

Source: official Symfony Demo at
`8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`. PHP >=8.4 is required; the PoC
uses PHP 8.5.12, Composer 2.9.1, SQLite and the unchanged upstream composer.lock.
No framework upgrade is part of this fixture. PHP needs intl, mbstring,
pdo_sqlite, zip and the ordinary XML/DOM extensions used by PHPUnit.

Copy `app/` to a writable, disposable directory. From that directory run
`/path/to/this/repository/docker/setup`, then `php vendor/bin/phpunit`.
The setup script has no Serena or Mago dependency. It copies `.env.local.demo`
to `.env.local`, installs locked Composer dependencies without auto-scripts, and
runs the application's cache/assets/importmap/Sass steps explicitly. This avoids
the upstream auto-script's destructive rename of the tracked seed environment
file. Network access is needed for Composer, importmap packages and the locked
Sass binary download. Do not run reset in the checked-in `app/` directory.

Reset removes only `data/database.sqlite` and `data/database_test.sqlite` in the
disposable directory. `doctrine:schema:create` opens each fresh SQLite database;
`doctrine:fixtures:load --no-interaction` loads it for dev and test. DBAL 4's
database:create/drop commands do not support SQLite here. `.env.test` supplies
the actual test database path. Original PHPUnit configuration and assertions
are retained. Random fixture contents are not exact-value test oracles.

The only source adaptation is the comment timestamp line in AppFixtures:
`now +` becomes `now -`. The original immediate new-comment failure was observed
on PHP 8.4.25 and saved in [the baseline log](evidence/timestamp-baseline-php84.txt).
Fresh fixture comments could otherwise sort ahead of a newly submitted comment.
No assertion was relaxed. The application checksums and approved adaptation
hashes live in `fixtures/upstream.sha256.json` and `fixtures/adaptations.json`.

Named scenarios are Demo repository-method rename, interface-family rename,
Calculator body edit and non-BMP/CRLF position accuracy. Controlled sources are
under `fixtures/semantic/`; these are copied into disposable apps only.
`tests/integration/verifier.py` independently defines expected changed files,
exact replacement counts and source positions. Fixture source and expectations
can be reused without an agent orchestrator. Protocol probes, adapter setup and
MCP transcript assertions belong to this integration. Outputs stay outside
fixture sources. Consumers can reuse these fixture and verification contracts independently;
see [Contributing](CONTRIBUTING.md) for maintaining their provenance.

The application verifier captures the **whole post-setup application**, including
vendor, root PHPUnit/Composer configuration, lockfiles, tests, public entrypoints,
unknown files, directories and symlink targets, plus permission bits. Its narrow
exclusions are defined in `tests/integration/verifier.py`; runtime caches and the
two known SQLite databases/sidecars are mutable, while `.serena/project.yml` is
covered. Baselines are host-owned outside the editable app and read-only at
`/trusted/application.json`. A correct two-file rename accompanied by any other
covered change is rejected.

Before edits, PHPUnit's trusted `--list-tests-xml` inventory is checked against
the original fixture's public test methods/source hashes and sealed outside the
app. JUnit must name exactly those class/method/dataset/file/line identities, use
the original `phpunit.dist.xml`, contain no skips/failures, and execute assertions
in every test. Aggregate counts and exit status are supporting evidence. Fast
controls deliberately weaken root configuration, change tests/dependencies,
replace paths with symlinks, change modes, add/delete files and forge incomplete
or same-total suite records; each is rejected alongside healthy controls.
