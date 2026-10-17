"""Independent receipt checker; does NOT import runner.py."""
import argparse, hashlib, json, pathlib, sys

def encode(o):
    return json.dumps(o, separators=(',', ':'), sort_keys=True).encode('utf8')
def hash_json(o):
    return hashlib.sha256(encode(o)).hexdigest()
def verify(fixture, receipt, prior=None, parent_id=None):
    assert fixture['schema']=='tude.public-fixtures.v1'
    assert len(fixture['records'])==8
    assert len({r['id'] for r in fixture['records']})==8
    assert receipt['schema']=='tude.receipt.v1'
    assert receipt['authority']=='READ_ONLY_PUBLIC_RESEARCH'
    assert receipt['fixture_sha256']==hash_json(fixture)
    assert isinstance(receipt['step'],int) and receipt['step']>=1
    assert receipt['completed_total']==receipt['step']*2
    assert receipt['run_id'] and str(receipt['run_id'])!=str(parent_id)
    if prior is None:
        assert receipt['step']==1
        assert receipt['parent_run_id'] is None
        assert receipt['previous_receipt_sha256'] is None
    else:
        assert prior['schema']=='tude.receipt.v1'
        assert prior['fixture_sha256']==receipt['fixture_sha256']
        assert prior['authority']=='READ_ONLY_PUBLIC_RESEARCH'
        assert receipt['step']==prior['step']+1
        assert str(prior['run_id'])==str(parent_id)
        assert receipt['parent_run_id']==str(parent_id)
        assert receipt['previous_receipt_sha256']==hash_json(prior)
    records=fixture['records']
    expected=[]
    for j in range(2):
        r=records[((receipt['step']-1)*2+j)%8]
        expected.append({'id':r['id'],'sha256':hashlib.sha256(r['text'].encode('utf8')).hexdigest()})
    assert receipt['checks']==expected
    return {'result':'PASS','step':receipt['step'],'run_id':receipt['run_id'],
            'receipt_sha256':hash_json(receipt),'parent_run_id':receipt['parent_run_id'],
            'fixture_sha256':hash_json(fixture)}
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--receipt',required=True)
    p.add_argument('--fixture',default='fixtures/public_cases.json')
    p.add_argument('--previous')
    p.add_argument('--parent-id')
    p.add_argument('--output')
    args=p.parse_args()
    try:
        fixture=json.loads(pathlib.Path(args.fixture).read_text())
        receipt=json.loads(pathlib.Path(args.receipt).read_text())
        previous=json.loads(pathlib.Path(args.previous).read_text()) if args.previous else None
        result=verify(fixture,receipt,previous,args.parent_id)
    except (KeyError,ValueError,TypeError,AssertionError) as exc:
        print('HOLD_UNVERIFIED',str(exc))
        sys.exit(1)
    if args.output:
        pathlib.Path(args.output).parent.mkdir(exist_ok=True)
        pathlib.Path(args.output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(result)
if __name__=='__main__':
    main()
