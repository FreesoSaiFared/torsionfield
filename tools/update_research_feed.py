#!/usr/bin/env python3
"""Generate an attributed, validated research RSS snapshot; retain the old one on total failure."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import xml.etree.ElementTree as ET

SOURCES = [
 ('Trail of Bits','https://blog.trailofbits.com/index.xml','blog.trailofbits.com'),
 ('SpecterOps','https://specterops.io/blog/feed/','specterops.io'),
 ('SentinelLABS','https://www.sentinelone.com/labs/feed/','www.sentinelone.com'),
 ('Unit 42','https://unit42.paloaltonetworks.com/feed/','unit42.paloaltonetworks.com'),
 ('Cloudflare','https://blog.cloudflare.com/rss/','blog.cloudflare.com'),
 ('watchTowr Labs','https://labs.watchtowr.com/rss/','labs.watchtowr.com'),
 ('PortSwigger Research','https://portswigger.net/research/rss','portswigger.net')]
OUT = Path(__file__).resolve().parent.parent/'public'/'research-feed.json'
def retrieve(name, feed, hostname):
 req=Request(feed,headers={'User-Agent':'Torsionfield-ResearchRadar/1.0','Accept':'application/rss+xml,application/xml'})
 with urlopen(req,timeout=14) as response: raw=response.read(3000001)
 if len(raw)>3000000: raise ValueError('oversized feed')
 root=ET.fromstring(raw)
 items=[]
 for entry in root.findall('./channel/item'):
  title=(entry.findtext('title') or '').strip()[:300]
  link=(entry.findtext('link') or '').strip()
  parsed=urlparse(link)
  if parsed.scheme!='https' or parsed.hostname!=hostname or not title: continue
  date=entry.findtext('pubDate') or ''
  try: date=parsedate_to_datetime(date).astimezone(timezone.utc).isoformat()
  except (TypeError,ValueError,IndexError): date=None
  items.append({'source':name,'title':title,'url':link,'date':date})
  if len(items)>=5: break
 return items

def main():
 existing={}
 if OUT.exists():
  try:
   for item in json.loads(OUT.read_text(encoding='utf-8')).get('items',[]):
    if item.get('source'): existing.setdefault(item['source'],[]).append(item)
    elif item.get('url','').startswith('https://blog.trailofbits.com/'):
     existing.setdefault('Trail of Bits',[]).append({**item,'source':'Trail of Bits'})
  except (OSError,ValueError,TypeError): pass
 all_items=[]; stats={}
 for name,feed,hostname in SOURCES:
  try:
   items=retrieve(name,feed,hostname)
   if not items: raise ValueError('feed had zero valid articles')
   stats[name]='live';all_items.extend(items)
  except Exception as exc:
   stats[name]='cached' if existing.get(name) else 'unavailable'
   all_items.extend(existing.get(name,[])[:5]); print(name,stats[name],str(exc)[:90])
 if not all_items: raise RuntimeError('No valid items: preserving existing snapshot')
 all_items.sort(key=lambda item:item.get('date') or '',reverse=True)
 payload={'sources':[{'name':n,'feed':f,'status':stats[n]} for n,f,_ in SOURCES],'updatedAt':datetime.now(timezone.utc).isoformat(),'items':all_items}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('verified',len(all_items),'items from',sum(v!='unavailable' for v in stats.values()),'sources')
if __name__=='__main__': main()
