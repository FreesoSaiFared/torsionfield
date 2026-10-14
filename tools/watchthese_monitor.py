#!/usr/bin/env python3
"""Dated source-drift sensor; never edits third-party claims automatically."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
import json, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'public/watchthese'
OPS=ROOT/'ops/watchthese'
class Reader(HTMLParser):
 def __init__(self): super().__init__(); self.tokens=[]; self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','svg','noscript'): self.skip+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','svg','noscript'): self.skip=max(0,self.skip-1)
 def handle_data(self,data):
  if not self.skip and data.strip(): self.tokens.append(data.strip())
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 tmp.replace(path)
def fetch(url):
 req=Request(url,headers={'User-Agent':'Torsionfield-WatchThese/1.0 editorial research'})
 with urlopen(req,timeout=20) as response:
  if response.status!=200: raise RuntimeError('HTTP '+str(response.status))
  data=response.read(2000001)
 if len(data)>2000000: raise RuntimeError('Source exceeds 2MB bound')
 parser=Reader(); parser.feed(data.decode('utf-8',errors='replace'))
 return ' '.join(' '.join(parser.tokens).split())
def main():
 spec=json.loads((PUB/'sources.json').read_text(encoding='utf-8'))
 assert spec['schema']=='torsionfield-watchthese-sources/1'
 state=OPS/'source-state.json'
 previous=json.loads(state.read_text()) if state.exists() else {}
 now=datetime.now(timezone.utc).isoformat()
 nextstate=dict(previous);observations=[];success=0
 for source in spec['sources']:
  sid=source['id'];prev=previous.get(sid,{})
  obs={'id':sid,'url':source['url'],'checkedAt':now,'status':'unknown'}
  try:
   text=fetch(source['url'])
   digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
   missing=[a for a in source.get('anchors',[]) if a.casefold() not in text.casefold()]
   change='first-observation' if not prev else ('unchanged' if prev['sha256']==digest else 'changed')
   obs.update(status='observed',sha256=digest,change=change,anchorsMissing=missing,needsEditorialReview=bool(missing) or change=='changed')
   nextstate[sid]={'sha256':digest,'lastObserved':now}
   success+=1
  except Exception as err:
   obs.update(status='fetch-failed',change='unavailable',error=str(err)[:180],needsEditorialReview=True)
  observations.append(obs);print(sid,obs['status'],obs.get('change'))
 save(state,nextstate)
 result={'schema':'torsionfield-watchthese-observations/1','generatedAt':now,'caution':'Changes are signals, not factual validation or approval.','sources':observations}
 save(PUB/'observations.json',result)
 save(OPS/'last-run.json',{'successful':success,'total':len(observations),'results':observations})
 return 0 if success==len(observations) else 1
if __name__=='__main__': sys.exit(main())
