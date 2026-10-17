"""Bounded public-fixture execution; GitHub API only for read-only ancestor discovery."""
import argparse, datetime, hashlib, json, os, pathlib, urllib.request

def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(',',':')).encode()
def sha(o):
    return hashlib.sha256(canonical(o)).hexdigest()
def api(path):
    token=os.environ['GH_TOKEN']
    request=urllib.request.Request('https://api.github.com/'+path,headers={
        'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'tude-research-lab-003'})
    with urllib.request.urlopen(request,timeout=20) as response:
        return json.load(response)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--discover',action='store_true')
    p.add_argument('--produce',action='store_true')
    p.add_argument('--parent-file')
    p.add_argument('--parent-id')
    p.add_argument('--bootstrap',action='store_true')
    a=p.parse_args()
    if a.discover == a.produce:
        raise SystemExit('HOLD_SELECT_ONE_MODE')
    if a.discover:
        repo=os.environ['GITHUB_REPOSITORY']
        current=int(os.environ['GITHUB_RUN_ID'])
        number=int(os.environ['GITHUB_RUN_NUMBER'])
        runs=[]
        for page in range(1,4):
            found=api(f'repos/{repo}/actions/workflows/lab003.yml/runs?per_page=100&page={page}')['workflow_runs']
            runs.extend(found)
            if len(found)<100: break
        older=[r for r in runs if int(r['id'])!=current and r['status']=='completed' and int(r['run_number'])<number]
        older.sort(key=lambda r:int(r['run_number']),reverse=True)
        success=next((r for r in older if r['conclusion']=='success'),None)
        if success:
            aid=api(f'repos/{repo}/actions/runs/{success["id"]}/artifacts?per_page=100')['artifacts']
            valid=[x for x in aid if x['name']=='tude-checkpoint' and not x['expired']]
            if len(valid)!=1:
                raise SystemExit('HOLD_PRIOR_ARTIFACT_MISSING')
            data={'status':'RESUME','parent_run_id':str(success['id']), 'failures_since_parent':sum(r['conclusion']!='success' for r in older if int(r['run_number'])>int(success['run_number']))}
        elif not older and number==1 and os.environ['GITHUB_EVENT_NAME']=='push':
            data={'status':'BOOTSTRAP','parent_run_id':None,'failures_since_parent':0}
        else:
            raise SystemExit('HOLD_NO_TRUSTED_PARENT')
        pathlib.Path('history.json').write_text(json.dumps(data,sort_keys=True)+'\n')
        print(data)
        return
    run=os.environ['GITHUB_RUN_ID']
    if os.environ.get('GITHUB_RUN_ATTEMPT','1')!='1':
        raise SystemExit('HOLD_REPLAYED_RUN_ATTEMPT')
    fixture=json.loads(pathlib.Path('fixtures/public_cases.json').read_text())
    if fixture.get('schema')!='tude.public-fixtures.v1' or len(fixture.get('records',[]))!=8:
        raise SystemExit('HOLD_BAD_FIXTURES')
    record_ids=[r['id'] for r in fixture['records']]
    if len(set(record_ids))!=8: raise SystemExit('HOLD_DUPLICATE_IDS')
    if a.bootstrap:
        if a.parent_file or a.parent_id or os.environ.get('GITHUB_EVENT_NAME')!='push' or os.environ.get('GITHUB_RUN_NUMBER')!='1':
            raise SystemExit('HOLD_UNAUTHORIZED_BOOTSTRAP')
        step=1
        prev_sha=None
        parent_id=None
    else:
        if not a.parent_file or not a.parent_id:
            raise SystemExit('HOLD_MISSING_PARENT')
        previous=json.loads(pathlib.Path(a.parent_file).read_text())
        if previous.get('schema')!='tude.receipt.v1' or previous.get('authority')!='READ_ONLY_PUBLIC_RESEARCH' or previous.get('fixture_sha256')!=sha(fixture) or str(previous.get('run_id'))!=str(a.parent_id):
            raise SystemExit('HOLD_INVALID_PARENT')
        if previous['step']<1 or previous['run_id']==str(run):
            raise SystemExit('HOLD_PARENT_REPLAY')
        step=previous['step']+1
        prev_sha=sha(previous)
        parent_id=str(a.parent_id)
    selected=[fixture['records'][((step-1)*2+j)%8] for j in range(2)]
    output={'schema':'tude.receipt.v1','authority':'READ_ONLY_PUBLIC_RESEARCH','run_id':str(run),
        'step':step,'completed_total':step*2,'parent_run_id':parent_id,
        'previous_receipt_sha256':prev_sha,'fixture_sha256':sha(fixture),
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'checks':[{'id':r['id'],'sha256':hashlib.sha256(r['text'].encode()).hexdigest()} for r in selected]}
    pathlib.Path('evidence').mkdir(exist_ok=True)
    pathlib.Path('evidence/receipt.json').write_text(json.dumps(output,sort_keys=True,indent=2)+'\n')
    print('CANDIDATE_STEP',step)

if __name__=='__main__':
    main()
