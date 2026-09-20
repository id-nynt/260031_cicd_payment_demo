"""Canonical two-input compiler and self-contained, validated workflow IR.

Agent generation reads only the serialized IR plus the framework policy template.
No source input or project manifest is consulted by generate_agent().
"""
from copy import deepcopy
from pathlib import Path
import math
import re
from urllib.parse import urlparse
import yaml
from model_transform import ModelError, parse_model, project_beliefs


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ModelError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read(path):
    try:
        value = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ModelError(f"Invalid YAML: {error}") from error
    if not isinstance(value, dict):
        raise ModelError("Expected a mapping")
    return value


def keys(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ModelError(f"Expected keys {sorted(allowed)}; required {sorted(required)}")


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ModelError(f"Expected integer in [{minimum}, {maximum}]")
    return value


def atom(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        raise ModelError(f"Invalid entity/environment: {value}")
    return value


def compile_documents(pipeline, goals):
    p, g = deepcopy(pipeline), deepcopy(goals)
    keys(p, {'name','project','workflow_file','execution','jobs','recovery','telemetry'},
         {'name','project','workflow_file','execution','jobs'})
    keys(g, {'goal','telemetry_constraints'}, {'goal'})
    keys(g['goal'], {'achieve(A)','maintain(M)','avoid(V)','duration_unit'}, {'achieve(A)'})
    for field in ('achieve(A)','maintain(M)','avoid(V)'):
        if field in g['goal'] and not isinstance(g['goal'][field],list):
            raise ModelError(f"goal.{field} must be a list")
    for field in ('name','project','workflow_file'):
        if not isinstance(p[field], str) or not p[field].strip():
            raise ModelError(f"Missing {field}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml",p['workflow_file']):
        raise ModelError("workflow_file must be a workflow filename")
    defaults = {'max_retries':0,'observation_attempts':18,'observation_interval_seconds':5,
                'reconciliation_attempts':3,'reconciliation_interval_seconds':5}
    keys(p['execution'], defaults, {'max_retries'})
    execution = defaults | p['execution']
    for key, value in execution.items():
        integer(value, 1 if key.endswith('attempts') else 0, 120 if key.endswith('attempts') else 60)
    jobs, recoveries = p['jobs'], p.get('recovery', {})
    if not isinstance(jobs, dict) or not jobs or not isinstance(recoveries, dict) or set(jobs) & set(recoveries):
        raise ModelError("Normal jobs and recovery actions must be disjoint mappings")
    normalized = {}; aliases = {}; environments = {}; sources = {}
    for name, job in jobs.items():
        atom(name)
        keys(job, {'needs','job_name','environment','observe_before','observe_after'}, {'job_name'})
        needs = job.get('needs', [])
        if isinstance(needs, str): needs = [needs]
        if not isinstance(needs, list) or any(not isinstance(x,str) for x in needs) or len(needs)!=len(set(needs)) or any(x not in jobs for x in needs):
            raise ModelError(f"Invalid normal dependency for {name}")
        job['needs'] = needs
        normalized[name] = {k:v for k,v in job.items() if k not in ('job_name','environment')}
    for name, recovery in recoveries.items():
        atom(name)
        keys(recovery, {'from','on','job_name','environment','release_source','observe_after'},
             {'from','on','job_name','environment','release_source','observe_after'})
        if recovery['from'] not in jobs or recovery['release_source']!='known_good' or recovery['observe_after'] is not True:
            raise ModelError("Recovery must restore a normal job from verified known_good and observe afterwards")
        triggers = recovery['on']
        if not isinstance(triggers,list) or not triggers or any(not isinstance(x,str) for x in triggers) or len(triggers)!=len(set(triggers)):
            raise ModelError("Recovery triggers must be a nonempty unique list")
        normalized[name] = {'recover_from':recovery['from'],'recover_on':triggers,'observe_after':True}
        sources[name] = 'known_good'
    for name, job in (jobs | recoveries).items():
        if not isinstance(job['job_name'],str) or not job['job_name'].strip(): raise ModelError("Missing job_name")
        if 'observe_after' in job and type(job['observe_after']) is not bool: raise ModelError("observe_after must be boolean")
        aliases[name]=job['job_name']
        if 'environment' in job: environments[name]=atom(job['environment'])
    if len(set(aliases.values()))!=len(aliases): raise ModelError("Job display names must be unique")
    model=parse_model({'name':p['name'],'execution':{'max_retries':execution['max_retries']},'jobs':normalized}, {'goal':g['goal']})
    if len({(m.entity,m.property) for m in model.maintenance}) != len(model.maintenance):
        raise ModelError("Duplicate maintenance constraint")
    if len(set(model.achievements)) != len(model.achievements): raise ModelError("Duplicate achievement")
    if any(a.required in recoveries for a in model.avoidance): raise ModelError("Recovery cannot be a normal safety prerequisite")
    # The supported agent chooses one normal sink and cannot make recovery a normal goal.
    model.final_entity
    observed={source for _,source in model.observations}|set(model.observe_after)
    observed.update(item.entity for item in model.maintenance if item.property=='health')
    # Every deployed entity must be verified, including a staging-only campaign.
    post_verified=set(model.observe_after)|{item.entity for item in model.maintenance if item.property=='health'}
    if any(name not in post_verified for name in environments):
        raise ModelError("Every deployed job needs observe_after or a health maintenance goal")
    if observed-set(environments): raise ModelError("Observed entities require environment bindings")
    for source,target in model.recovery:
        if environments.get(source)!=environments.get(target): raise ModelError("Recovery environment differs from source")
    runtime={'project':p['project'],'controller':{'workflow_file':p['workflow_file'],'jobs':aliases,
             'environments':environments,'release_sources':sources,**{k:v for k,v in execution.items() if k!='max_retries'}}}
    telemetry=p.get('telemetry',{})
    if observed:
        keys(telemetry, {'environments','metrics','max_age_seconds'}, {'environments','metrics','max_age_seconds'})
        integer(telemetry['max_age_seconds'],1,300)
        if not isinstance(telemetry['environments'],dict): raise ModelError("Telemetry environments required")
        for name,endpoint in telemetry['environments'].items():
            atom(name); keys(endpoint,{'ready_url','prometheus_url'}, {'ready_url','prometheus_url'})
            for url in endpoint.values():
                if not isinstance(url,str) or urlparse(url).scheme not in ('http','https') or not urlparse(url).netloc:
                    raise ModelError("Invalid telemetry URL")
        if set(environments.values())-set(telemetry['environments']): raise ModelError("Missing telemetry endpoint")
        keys(telemetry['metrics'],{'error_rate_query','latency_p95_ms_query','availability_query','sample_age_seconds_query'},
             {'error_rate_query','latency_p95_ms_query','availability_query','sample_age_seconds_query'})
        if any(not isinstance(q,str) or '{{run_id}}' not in q for q in telemetry['metrics'].values()):
            raise ModelError("Every metric query must correlate {{run_id}}")
        thresholds=g.get('telemetry_constraints',{})
        keys(thresholds,{'error_rate_high_gt','latency_p95_ms_high_gt'}, {'error_rate_high_gt','latency_p95_ms_high_gt'})
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in thresholds.values()): raise ModelError("Invalid thresholds")
        if not 0<=thresholds['error_rate_high_gt']<=1 or thresholds['latency_p95_ms_high_gt']<=0: raise ModelError("Invalid thresholds")
        runtime.update(telemetry);runtime['thresholds']=thresholds
    elif telemetry or g.get('telemetry_constraints'):
        raise ModelError("Telemetry configuration without observed entities")
    workflow={'name':p['name'],'execution':execution,'jobs':jobs,'recovery':recoveries}
    document={'schema_version':1,'workflow':workflow,'goals':g,'runtime':runtime}
    return document,model


def compile_inputs(pipeline, goals):
    return compile_documents(read(pipeline),read(goals))


def load_workflow(path):
    doc=read(path)
    keys(doc,{'schema_version','workflow','goals','runtime'}, {'schema_version','workflow','goals','runtime'})
    if type(doc['schema_version']) is not int or doc['schema_version']!=1: raise ModelError("Unsupported workflow schema")
    w,r=doc['workflow'],doc['runtime']
    keys(w,{'name','execution','jobs','recovery'},{'name','execution','jobs','recovery'})
    if not isinstance(r,dict) or not isinstance(r.get('controller'),dict): raise ModelError("Invalid runtime binding")
    try:
        pipeline={**w,'project':r['project'],'workflow_file':r['controller']['workflow_file']}
        if 'metrics' in r: pipeline['telemetry']={k:r[k] for k in ('environments','metrics','max_age_seconds')}
        expected,model=compile_documents(pipeline,doc['goals'])
    except (KeyError,TypeError) as error:
        raise ModelError("Incomplete workflow model") from error
    if expected!=doc: raise ModelError("Workflow runtime bindings disagree with the normalized model")
    return doc,model


def generate_agent(workflow, template, agent):
    doc,model=load_workflow(workflow)
    policy=doc['workflow']['execution']
    facts=project_beliefs(model).replace('// Generated from 03_workflow_model.yaml; do not edit.',
                                        '// Generated solely from the validated workflow model; do not edit.')
    for key in ('observation_attempts','observation_interval_seconds','reconciliation_attempts','reconciliation_interval_seconds'):
        name={'observation_attempts':'observation_limit','observation_interval_seconds':'observation_interval',
              'reconciliation_attempts':'reconciliation_limit','reconciliation_interval_seconds':'reconciliation_interval'}[key]
        value=policy[key]*(1000 if key.endswith('seconds') else 1)
        facts+=f"{name}({value}).\n"
    if 'thresholds' in doc['runtime']:
        facts+=f"error_rate_limit({doc['runtime']['thresholds']['error_rate_high_gt']}).\n"
        facts+=f"latency_limit({doc['runtime']['thresholds']['latency_p95_ms_high_gt']}).\n"
    Path(agent).write_text(facts+'\n'+Path(template).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    return doc,model
