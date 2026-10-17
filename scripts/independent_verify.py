"""Independent receipt checker; does NOT import runner.py.

A single later checkpoint can be intrinsically verified without its ancestor,
but full chain-link verification requires --previous and --parent-id.
"""
import argparse, hashlib, json, pathlib, sys


def encode(o):
    return json.dumps(o, separators=(',', ':'), sort_keys=True).encode('utf8')


def hash_json(o):
    return hashlib.sha256(encode(o)).hexdigest()


def verify(fixture, receipt, prior=None, parent_id=None):
    assert fixture['schema'] == 'tude.public-fixtures.v1'
    records = fixture['records']
    assert len(records) == 8
    assert len({r['id'] for r in records}) == 8
    assert receipt['schema'] == 'tude.receipt.v1'
    assert receipt['authority'] == 'READ_ONLY_PUBLIC_RESEARCH'
    assert receipt['fixture_sha256'] == hash_json(fixture)
    assert type(receipt['step']) is int and receipt['step'] >= 1
    assert type(receipt['completed_total']) is int
    assert receipt['completed_total'] == receipt['step'] * 2
    assert isinstance(receipt['run_id'], str) and receipt['run_id'].isdigit()
    assert isinstance(receipt['checks'], list) and len(receipt['checks']) == 2

    step = receipt['step']
    if step == 1:
        assert receipt['parent_run_id'] is None
        assert receipt['previous_receipt_sha256'] is None
    else:
        assert isinstance(receipt['parent_run_id'], str)
        assert receipt['parent_run_id'].isdigit()
        assert receipt['parent_run_id'] != receipt['run_id']
        prev_hash = receipt['previous_receipt_sha256']
        assert isinstance(prev_hash, str) and len(prev_hash) == 64
        assert all(c in '0123456789abcdef' for c in prev_hash)

    if prior is None:
        # For step>1 this is INTRINSIC_ONLY, *not* verified ancestry.
        assert parent_id is None
        scope = 'GENESIS_CHECKED' if step == 1 else 'INTRINSIC_ONLY'
    else:
        assert step > 1
        assert isinstance(parent_id, str) and parent_id.isdigit()
        # Check that the ancestor's own content and claimed parent structure are valid.
        verify(fixture, prior)
        assert prior['fixture_sha256'] == receipt['fixture_sha256']
        assert receipt['step'] == prior['step'] + 1
        assert prior['run_id'] == parent_id
        assert receipt['parent_run_id'] == parent_id
        assert receipt['previous_receipt_sha256'] == hash_json(prior)
        scope = 'PARENT_LINK_VERIFIED'

    expected = []
    for j in range(2):
        r = records[((step - 1) * 2 + j) % 8]
        expected.append({'id': r['id'], 'sha256': hashlib.sha256(r['text'].encode('utf8')).hexdigest()})
    assert receipt['checks'] == expected
    return {
        'result': 'PASS',
        'scope': scope,
        'step': step,
        'run_id': receipt['run_id'],
        'receipt_sha256': hash_json(receipt),
        'parent_run_id': receipt['parent_run_id'],
        'fixture_sha256': hash_json(fixture),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--receipt', required=True)
    p.add_argument('--fixture', default='fixtures/public_cases.json')
    p.add_argument('--previous')
    p.add_argument('--parent-id')
    p.add_argument('--output')
    args = p.parse_args()
    try:
        fixture = json.loads(pathlib.Path(args.fixture).read_text(encoding='utf8'))
        receipt = json.loads(pathlib.Path(args.receipt).read_text(encoding='utf8'))
        previous = json.loads(pathlib.Path(args.previous).read_text(encoding='utf8')) if args.previous else None
        result = verify(fixture, receipt, previous, args.parent_id)
    except (KeyError, ValueError, TypeError, AssertionError, RecursionError) as exc:
        print('HOLD_UNVERIFIED', str(exc))
        sys.exit(1)
    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf8')
    print(result)


if __name__ == '__main__':
    main()
