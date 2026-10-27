"""Small, independent assertions for the installed Mate/Console inspection slice."""
import json
from pathlib import Path

from evidence import digest
from verifier import snapshot

SERVICE = r'App\Form\Type\TagsInputType'
DEPENDENCY = r'App\Repository\TagRepository'
CONTEXT = 'inspection-dev'


def payload(raw):
    value = json.loads(raw)
    assert isinstance(value, dict) and isinstance(value.get('untrusted_data'), dict), 'Missing Mate data envelope'
    return value['untrusted_data']


def compare(mate_raw, console_raw, dependency_raw, *, requested=SERVICE):
    """Console JSON has no ID: its separately retained exact argv supplies identity.

    This case has a direct service reference, no alias or inlining. Compare the
    reference at position zero; Mate additionally resolves its PHP parameter name.
    Expectations are pinned to existing Demo source, not copied from Mate output.
    """
    mate, console, dependency = payload(mate_raw), json.loads(console_raw), json.loads(dependency_raw)
    assert requested == SERVICE and mate.get('id') == SERVICE, 'Wrong or missing service identity'
    assert mate.get('context') == CONTEXT, 'Wrong metadata context'
    assert mate.get('class') == console.get('class') == SERVICE, 'Wrong or missing implementation class'
    ma, ca = mate.get('arguments'), console.get('arguments')
    assert isinstance(ma, list) and len(ma) == 1 and isinstance(ca, list) and len(ca) == 1, 'Expected one constructor argument'
    assert ma[0].get('name') == 'tags' and ma[0].get('type') == ca[0].get('type') == 'service', 'Wrong argument binding'
    assert ma[0].get('value') == ca[0].get('id') == DEPENDENCY, 'Wrong resolved dependency'
    assert dependency.get('class') == DEPENDENCY, 'Native dependency service does not resolve to the expected class'
    assert mate.get('autowired') is True and console.get('autowire') is True
    return {'status': 'pass', 'service_id': requested, 'class': SERVICE,
            'constructor_parameter': 'tags', 'dependency_id': DEPENDENCY,
            'dependency_class': dependency['class'], 'context': CONTEXT,
            'normalization': 'Direct reference at constructor position 0; no alias or inlining in this fixture.'}


def classify_search(raw):
    result = payload(raw)
    if result.get('count') == 0 and result.get('services') in ([], {}) and result.get('truncated') is False:
        return 'not_found'
    assert isinstance(result.get('services'), dict) and result.get('count', 0) > 0, 'Incomplete search response'
    return 'found'


def application_state(app):
    # Reuse the complete existing manifest, including installed dependency bytes,
    # root configuration and relevant modes. No new verifier exclusions.
    return snapshot(app)


def metadata_hashes(app):
    import hashlib
    app = Path(app)
    paths = sorted((app/'var/cache/dev').glob('*DebugContainer.xml'))
    assert len(paths) == 1 and paths[0].is_file() and not paths[0].is_symlink(), 'Dev metadata absent or ambiguous; run mate-prepare'
    return {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def validate_preparation(record, data, state, xml):
    assert record.get('run_id') == data['run_id'] and record.get('workspace') == data['app'], 'Preparation belongs to another workspace'
    assert record.get('environment') == 'dev' and record.get('context') == CONTEXT, 'Wrong preparation environment'
    assert record.get('application_sha256') == digest(state), 'Application/dependencies changed; run mate-prepare explicitly'
    assert record.get('metadata') == xml and xml, 'Metadata changed; run mate-prepare explicitly'
    assert record.get('preparation_exit') == 0 and record.get('preparation_id'), 'Incomplete preparation'
