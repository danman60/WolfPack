"""Read-only deployment validation before isolated QA browser writes."""
import json,re,subprocess,urllib.request
from pathlib import Path
from urllib.parse import urlparse


def validate_target(url, expected_sha=None):
    if url=='http://127.0.0.1:3218/rotation':
        return {'environment':'local','url':url}
    parsed=urlparse(url)
    if not (parsed.scheme=='https' and not parsed.port and not parsed.username and parsed.path=='/rotation' and not parsed.query and not parsed.fragment and re.fullmatch(r'wolf-pack-[a-z0-9]{9}-danman60s-projects\.vercel\.app',parsed.hostname or '')):
        raise ValueError('An explicit immutable WolfPack Preview URL is required; production aliases are forbidden.')
    if not expected_sha or not re.fullmatch(r'[0-9a-f]{40}',expected_sha):
        raise ValueError('Preview QA requires the exact expected Git commit SHA.')
    auth=json.loads((Path.home()/'.local/share/com.vercel.cli/auth.json').read_text())
    request=urllib.request.Request('https://api.vercel.com/v13/deployments/'+parsed.hostname,headers={'Authorization':'Bearer '+auth['token']})
    with urllib.request.urlopen(request,timeout=30) as response:deployment=json.load(response)
    expected_project=json.loads((Path(__file__).resolve().parents[2]/'.vercel/project.json').read_text())['projectId']
    project=deployment.get('projectId') or (deployment.get('project') or {}).get('id')
    sha=(deployment.get('meta') or {}).get('githubCommitSha') or (deployment.get('gitSource') or {}).get('sha')
    if project!=expected_project or deployment.get('name')!='wolf-pack' or deployment.get('url')!=parsed.hostname or deployment.get('target') not in (None,'preview') or deployment.get('readyState')!='READY' or sha!=expected_sha:
        raise ValueError('Live deployment metadata does not match the authorized READY Preview and Git commit.')
    cli=json.loads(subprocess.run(['vercel','inspect','https://'+parsed.hostname,'--format=json'],capture_output=True,text=True,check=True,cwd=Path(__file__).resolve().parents[2]).stdout)
    if cli.get('id')!=deployment['id'] or cli.get('target')!='preview' or cli.get('readyState')!='READY':
        raise ValueError('Vercel CLI must independently classify this deployment as READY Preview.')
    return {'cliTarget':cli['target'],'environment':'Preview','deploymentId':deployment['id'],'projectId':project,'url':url,'gitSha':sha,'apiTarget':deployment.get('target'),'readyState':deployment['readyState']}


def protect_context(context, url, protection_file):
    if protection_file is None:return {}
    if url.startswith('http://127.0.0.1:'):raise ValueError('Protection credentials are only for the verified Preview deployment.')
    key=Path(protection_file).read_text().strip()
    if len(key)<16:raise ValueError('Invalid deployment protection credential file.')
    origin=url.removesuffix('/rotation')
    # Scope the deployment-only credential to this exact origin, never third-party resources.
    def route(request):
        headers={**request.request.headers,'x-vercel-protection-bypass':key}
        request.continue_(headers=headers)
    context.route(origin+'/**',route)
    return {'x-vercel-protection-bypass':key}
