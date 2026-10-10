#!/usr/bin/env python3
"""Source-bound verification candidates; never equate string matches with truth.

Network access is fixed to GitHub raw and two vetted primary domains.
Unknown external URLs are recorded for review and are never fetched/executed.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from watch_hitchhikers import NOTE, PRIMARY, REPO

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / 'public/research/hitchhikers-upstream.json'
OUTPUT = ROOT / 'public/research/evidence-audit.json'
VERSION = 'torsionfield-evidence-audit/1'
METHOD_REVISION = '2026-10-10.r2'
WILLISON = 'https://simonwillison.net/2026/Apr/30/gpt-55-cyber-capabilities/'
MAX_BYTES = 1_000_000

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript') and self.hidden: self.hidden -= 1
    def handle_data(self, text):
        if not self.hidden: self.parts.append(text)

def normalize(s):
    return re.sub(r'\s+', ' ', s).strip().casefold()

def fetch(url, opener=urlopen):
    req = Request(url, headers={'User-Agent':'Torsionfield-EvidenceAudit/1.0'})
    with opener(req, timeout=16) as response:
        if response.geturl() != url:
            raise ValueError('Unexpected redirect while verifying evidence')
        raw = response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise ValueError('Source exceeds 1MB; manual review')
    return raw.decode('utf-8','replace'), hashlib.sha256(raw).hexdigest()

def main_claims(text):
    sections = re.split(r'(?=^### Claim [0-9]+:)', text, flags=re.M)
    result=[]
    for section in sections:
        head=re.search(r'^### Claim (\d+):\s*(.+)',section,re.M)
        if not head: continue
        claim_id=int(head.group(1))
        body=section.split('\n### ',1)[0]
        qmatch=re.search(r'^- \*\*Quote\*\*:\s*[“"](.{12,400}?)[”"]',body,re.M|re.S)
        result.append({'claimId':claim_id,'heading':head.group(2).strip()[:230],
                       'quote':qmatch.group(1).strip() if qmatch else None})
    return result

def build(source_sha, note_text, primary_html, willison_html, note_hash, primary_hash, willison_hash, now):
    p=VisibleText();p.feed(primary_html)
    w=VisibleText();w.feed(willison_html)
    primary_text=normalize(' '.join(p.parts))
    willison_text=normalize(' '.join(w.parts))
    notes=main_claims(note_text)
    extracted=[]
    for claim in notes:
        quote=claim.pop('quote')
        location='not-tested'
        if quote:
            needle=normalize(quote)
            if needle in primary_text: location='primary-text-located'
            elif needle in willison_text: location='linked-commentary-located'
            else: location='quote-not-located'
        extracted.append({**claim,'quoteStatus':location,'reviewStatus':'pending-independent-judgment',
                          'sourceUrl':f'https://github.com/{REPO}/blob/{source_sha}/{NOTE}'})
    anchor_rules={
       'expert-pass-rate':('71.4%', '71.4%'),
       'mythos-comparison':('68.6%', '68.6%'),
       'end-to-end-tlo':('2 of 10 attempts', '2 of 10 attempts'),
       'rust-vm-price':('$1.73', '$1.73'),
    }
    anchors=[]
    for ident,(secondary,original) in anchor_rules.items():
        present_note=secondary in note_text
        present_primary=original.casefold() in primary_text
        anchors.append({'id':ident,'sourceTextHasAnchor':present_note,
                        'primaryTextHasAnchor':present_primary,
                        'status':'literal-match-only' if present_note and present_primary else 'requires-review'})
    one_se=('1 standard error of the mean' in primary_text)
    misleading_ci=bool(re.search(r'95%\s+(?:CI|confidence interval)',note_text,re.I))
    it_caveat=('got stuck on the it sections' in primary_text and
               'failure does not tell us how capable' in primary_text)
    domain_inference=('ics/ot attack requires different domain knowledge' in normalize(note_text))
    checks=[
        {'id':'uncertainty-unit','noteIndicator':'95% CI','primaryIndicator':'1 standard error of the mean',
         'status':'potential-conflict' if misleading_ci and one_se else 'needs-review',
         'primaryEvidenceLocated':one_se,'secondaryInterpretationLocated':misleading_ci},
        {'id':'cooling-tower-interpretation','noteIndicator':'ICS/OT attack requires different domain knowledge',
         'primaryIndicator':'failure does not tell us how capable it would be',
         'status':'potential-conflict' if domain_inference and it_caveat else 'needs-review',
         'primaryEvidenceLocated':it_caveat,'secondaryInterpretationLocated':domain_inference},
    ]
    return {'schema':VERSION,'auditMethodRevision':METHOD_REVISION,'upstreamSha':source_sha,'sourceNote':NOTE,'sourceUrl':f'https://github.com/{REPO}/blob/{source_sha}/{NOTE}',
            'originalPublisher':'UK AI Security Institute','primaryUrl':PRIMARY,
            'commentaryUrl':WILLISON,'checkedAt':now,
            'sourceHashes':{'noteSha256':note_hash,'primarySha256':primary_hash,'commentarySha256':willison_hash},
            'claims':extracted,'literalAnchors':anchors,'interpretationChecks':checks,
            'summary':{'candidateClaims':len(extracted),'locatedQuotes':sum(x['quoteStatus'] in ('primary-text-located','linked-commentary-located') for x in extracted),
                       'potentialConflicts':sum(x['status']=='potential-conflict' for x in checks),
                       'independentlyVerifiedClaims':0},
            'publicationState':'review-required',
            'method':'Literal text checks are mechanical provenance signals, not semantic verification. Independent editorial review required.'}

def run(watch_path=INPUT,output=OUTPUT,clock=None,loader=fetch):
    clock=clock or datetime.now(timezone.utc)
    watch=json.loads(watch_path.read_text(encoding='utf-8'))
    sha=watch['upstreamSha']
    if not re.fullmatch('[a-f0-9]{40}',sha): raise ValueError('Bad upstream SHA')
    if output.exists():
        previous=json.loads(output.read_text(encoding='utf-8'))
        note_changed=(previous.get('upstreamSha')!=sha and any(x.get('path')==NOTE for x in watch.get('changed',[])))
        if previous.get('schema')==VERSION and previous.get('auditMethodRevision')==METHOD_REVISION and not note_changed:
            last=datetime.fromisoformat(previous['checkedAt'])
            if clock-last<timedelta(hours=24):
                print('EVIDENCE_UNCHANGED: SHA and primary recheck window intact')
                return {'status':'unchanged','claims':len(previous['claims'])}
    url=f'https://raw.githubusercontent.com/{REPO}/{sha}/{NOTE}'
    note,nh=loader(url)
    primary,ph=loader(PRIMARY)
    willison,wh=loader(WILLISON)
    report=build(sha,note,primary,willison,nh,ph,wh,clock.isoformat(timespec='seconds'))
    report['otherChangedNotes']=[x['path'] for x in watch.get('changed',[]) if x.get('path','').startswith('source-notes/') and x.get('path')!=NOTE][:12]
    if len(report['claims'])<6 or not all(x['primaryTextHasAnchor'] for x in report['literalAnchors']):
        raise ValueError('Evidence extraction degraded; preserving previous report')
    output.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if output.exists() and output.read_text(encoding='utf-8')==payload:
        return {'status':'unchanged','claims':len(report['claims'])}
    output.write_text(payload,encoding='utf-8')
    print('EVIDENCE_REVIEW_REQUIRED',report['summary'])
    return {'status':'updated','claims':len(report['claims']),'summary':report['summary']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--watch',type=Path,default=INPUT)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    run(watch_path=args.watch,output=args.output)
