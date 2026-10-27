These inputs support deterministic fast tests, without Docker or credentials.

`original-suite-list.xml` is actual PHPUnit 11.5.55 `--list-tests-xml` output
from the pinned, unchanged Symfony Demo tests. The Docker invocation was
`php vendor/bin/phpunit --list-tests-xml /evidence/expected-tests.xml` at `/app`.
Fast tests bind its classes/methods to the checked-in fixture and construct
synthetic JUnit controls to exercise rejection. Acceptance generates its own
trusted inventory before edits and checks actual JUnit execution evidence.

`reviewed_verifier.py` is the unmodified verifier from
`41729d30d23459de1ba53023051eb55894fb33b9`, SHA-256
`1fcf44c55403872c3dac71c6a5bbdaa596e7e2f2cd3f807c31271a244856e282`.
It is deliberately defective test input, never the acceptance verifier. A test
executes its original implementation to demonstrate the root-configuration hole,
then requires the repaired verifier to reject the identical application change.
