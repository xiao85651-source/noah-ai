"""Versioned original curricula; seed checkpoints and owner data stay separate."""
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {'seed': ROOT/'training/corpus.jsonl',
            'research-v1': ROOT/'training/datasets/research-v1.jsonl'}

def validate_research(records):
    seen, groups, texts = set(), {}, set()
    for row in records:
        if row.get('split') not in {'train','validation','audit'} or row.get('domain') not in {'biopharma','technology','coding'}:
            raise ValueError('Invalid research split or domain')
        if row.get('language') not in {'zh','en'} or row.get('provenance') != 'project-authored-v1':
            raise ValueError('Research records require authored provenance and a supported language')
        if not all(isinstance(row.get(k),str) and row[k].strip() for k in ['id','group','text']):
            raise ValueError('Missing record identity or content')
        if row['id'] in seen or row['text'].strip() in texts:
            raise ValueError('Duplicate curriculum record')
        if row['group'] in groups and groups[row['group']] != row['split']:
            raise ValueError('A concept group crosses training/evaluation splits')
        if not 32 <= len(row['text'].encode('utf-8')) <= 8192:
            raise ValueError('Invalid record length')
        seen.add(row['id']); texts.add(row['text'].strip()); groups[row['group']]=row['split']
    for split in ['train','validation','audit']:
        if {r['domain'] for r in records if r['split']==split} != {'biopharma','technology','coding'}:
            raise ValueError('Each split must cover all three domains')
    return records

def load_curriculum(profile='seed'):
    if profile not in PROFILES: raise ValueError('Unknown Noah curriculum profile')
    source = PROFILES[profile].read_bytes()
    records = [json.loads(line) for line in source.decode('utf-8').splitlines() if line.strip()]
    if profile != 'seed': validate_research(records)
    return records, hashlib.sha256(source).hexdigest()

def summary(profile):
    records, digest = load_curriculum(profile)
    return {'profile':profile,'sha256':digest,'records':len(records),'expertReviewed':False,
            'splits':dict(Counter(r['split'] for r in records)),
            'domains':dict(Counter(r.get('domain','general') for r in records)),
            'scope':'authored development curriculum; no specialist capability established'}
