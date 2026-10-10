#!/usr/bin/env python3
"""Identify new feed entries requiring a first-party title and relevance explanation.

This is only a candidate queue: nothing can publish without a reviewed entry.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
FEED=ROOT/'public/research-feed.json'
EDIT=ROOT/'public/research/editorial.json'

def candidates(feed, editorial):
    approved=editorial.get('entries', {})
    results=[]
    for item in feed.get('items', []):
        link=item.get('url','')
        parsed=urlparse(link)
        if parsed.scheme!='https' or not parsed.hostname: continue
        entry=approved.get(link)
        if entry and entry.get('editorialStatus')=='reviewed' and entry.get('headline') and entry.get('relevance') and entry.get('sourceTitleAtReview')==item.get('title'):
            continue
        results.append({'source':item.get('source','External research'),
                        'sourceTitle':item.get('title','')[:250], 'url':link,
                        'reason':'source-updated' if entry else 'new-source',
                        'editorialStatus':'needs-first-party-interpretation'})
    return results

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    parser.add_argument('--github-issue',action='store_true')
    args=parser.parse_args()
    feed=json.loads(FEED.read_text())
    editorial=json.loads(EDIT.read_text())
    rows=candidates(feed, editorial)
    digest=hashlib.sha256('\n'.join(sorted(r['url']+' '+r['sourceTitle'] for r in rows)).encode()).hexdigest()[:12]
    report={'schema':'torsionfield-editorial-backlog/1','digest':digest,
            'reviewNeeded':len(rows),'items':rows}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('EDITORIAL_REVIEW_QUEUE',len(rows),'digest',digest)
    if not args.github_issue or not rows:
        return
    import subprocess
    # Stable digest makes re-running the schedule idempotent.
    repo='FreesoSaiFared/torsionfield'
    title='Editorial review '+digest+' — '+str(len(rows))+' unreviewed research entries'
    previous=json.loads(subprocess.check_output(
        ['gh','issue','list','-R',repo,'--state','all','--search','Editorial review '+digest+' in:title','--json','title'],text=True))
    if any(digest in x['title'] for x in previous): return
    body='New or changed article titles need a plain-language Torsionfield headline and a source-grounded relevance explanation.\n\n'
    for row in rows[:18]:
        body+=('- '+row['source']+': '+row['sourceTitle']+'\n  '+row['url']+'\n')
    body+='\n**Publication gate:** add a reviewed entry to public/research/editorial.json. Unreviewed articles must not appear as first-party interpretations. Do not treat generated suggestions as verified facts.\n'
    subprocess.run(['gh','issue','create','-R',repo,'--title',title,'--body',body],check=True)
if __name__=='__main__':main()
