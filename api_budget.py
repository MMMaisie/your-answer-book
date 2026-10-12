"""Conservative CNY reservation using official peak rates checked 2026-10-10."""
import json
from decimal import Decimal
from types import SimpleNamespace
RATES={'deepseek-v4-pro':(Decimal('9'),Decimal('27')),'deepseek-flash':(Decimal('2'),Decimal('8'))}
PRICE_SOURCE='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
class BudgetReached(Exception):pass
class CostClient:
 def __init__(self,client,budget='5',spent='0',limit=24):
  self.client=client;self.budget=Decimal(str(budget));self.spent=Decimal(str(spent));self.calls=0;self.limit=limit;self.events=[]
  if self.budget<=0 or self.spent<0:raise ValueError('invalid budget')
  self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
 def create(self,**kw):
  model=kw['model']
  if model not in RATES:raise ValueError('unknown model pricing; no API request sent')
  ir,orr=RATES[model]
  # UTF-8 byte count is a deliberately large token upper estimate, plus framing.
  inputs=len(json.dumps(kw['messages'],ensure_ascii=False).encode('utf-8'))+256*len(kw['messages'])+1024
  outputs=kw.get('max_tokens')
  if not isinstance(outputs,int) or outputs<1:raise ValueError('explicit output cap required')
  reserve=(Decimal(inputs)*ir+Decimal(outputs)*orr)/Decimal(1000000)
  if self.calls>=self.limit or self.spent+reserve>self.budget:raise BudgetReached('next request reservation exceeds remaining budget')
  self.calls+=1;self.spent+=reserve
  event=dict(request=self.calls,model=model,reserved_cny=str(reserve),accounted_cny=str(reserve),usage_status='UNKNOWN_RESERVED_MAXIMUM');self.events.append(event)
  response=self.client.chat.completions.create(**kw)
  usage=getattr(response,'usage',None)
  if usage:
   pt=getattr(usage,'prompt_tokens',None);ct=getattr(usage,'completion_tokens',None)
   if isinstance(pt,int) and isinstance(ct,int) and pt>=0 and ct>=0:
    cost=(Decimal(pt)*ir+Decimal(ct)*orr)/Decimal(1000000)
    self.spent+=cost-reserve;event.update(accounted_cny=str(cost),usage_status='USAGE_PEAK_RATE_UPPER_ESTIMATE',prompt_tokens=pt,completion_tokens=ct)
    if cost>reserve:event['reservation_exceeded']=True
  return response
 def close(self):
  if hasattr(self.client,'close'):self.client.close()
 def report(self):
  return dict(cap_cny=str(self.budget),accounted_upper_estimate_cny=str(self.spent),requests=self.calls,price_source=PRICE_SOURCE,price_checked='2026-10-10',pricing_policy='Peak rates; cache discounts ignored. Unknown usage retains full reservation. Provider billing is authoritative.',events=self.events)
