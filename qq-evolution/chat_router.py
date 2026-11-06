"""Loopback-only chat provider routing with five-minute recovery probes."""
import json,time,threading,urllib.request,os,subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

class RoutePool:
 def __init__(self,routes,request,clock=time.time,on_switch=None,initial_state=None,on_state=None):
  self.routes=routes;self.request=request;self.clock=clock;self.on_switch=on_switch;self.on_state=on_state
  self.available=[True]*len(routes);self.checked=[0]*len(routes)
  state=initial_state if isinstance(initial_state,dict) else {}
  active=state.get('active')
  self.last_probe=clock();self.active=active if any(r['name']==active for r in routes) else None
  self.last_success=state.get('lastSuccess');self.last_switch=state.get('lastSwitch');self.lock=threading.Lock()
 def health(self):
  with self.lock:
   active_model=next((r.get('model') for r in self.routes if r['name']==self.active),None)
   return {'active':self.active,'activeModel':active_model,'lastSuccess':self.last_success,'lastSwitch':self.last_switch,'lastProbe':self.last_probe,'routes':[{'name':r['name'],'model':r.get('model'),'available':self.available[i],'checkedAt':self.checked[i]} for i,r in enumerate(self.routes)]}
 def mark(self,index,ok):
  with self.lock:self.available[index]=ok;self.checked[index]=self.clock()
 @staticmethod
 def valid(body,content_type):
  if 'event-stream' in content_type:
   chunks=[]
   for line in body.decode('utf-8').splitlines():
    if line.startswith('data: ') and line[6:]!='[DONE]':chunks.append(json.loads(line[6:]))
   if any(x.get('error') for x in chunks):return False
   return any(c.get('delta',{}).get('content') or c.get('delta',{}).get('tool_calls') for x in chunks for c in x.get('choices',[]))
  data=json.loads(body)
  choice=(data.get('choices') or [{}])[0]
  message=choice.get('message') or {}
  return choice.get('finish_reason') not in ('error','cancelled','length') and bool(message.get('content') or message.get('tool_calls'))
 def chat(self,payload):
  with self.lock:indices=[i for i,ok in enumerate(self.available) if ok]
  for i in indices:
   try:
    body,ctype=self.request(self.routes[i],payload)
    if not self.valid(body,ctype):raise ValueError('invalid completion')
    self.mark(i,True)
    with self.lock:
     previous=self.active;current=self.routes[i]['name'];self.active=current;self.last_success=self.clock()
     if previous!=current:self.last_switch=self.last_success
    if previous is not None and previous!=current and self.on_switch:
     try:self.on_switch(previous,current)
     except Exception:pass
    if self.on_state:
     try:self.on_state(self.health())
     except Exception:pass
    return body,ctype
   except Exception:self.mark(i,False)
  raise RuntimeError('no healthy chat route; recovery probe pending')
 def probe_due(self,force=False):
  now=self.clock()
  with self.lock:
   if not force and now-self.last_probe<300:return False
   self.last_probe=now
  for i,route in enumerate(self.routes):
   try:
    body,ctype=self.request(route,{'messages':[{'role':'user','content':'Health check. Reply OK only. Do not use tools.'}],'max_tokens':32,'stream':False})
    self.mark(i,self.valid(body,ctype))
   except Exception:self.mark(i,False)
  return True

def main():
 config=json.loads(Path('/home/hermes/.hermes/chat-routing.json').read_text())
 state_path=Path('/home/hermes/.hermes/chat-router-state.json')
 try:initial_state=json.loads(state_path.read_text())
 except (OSError,json.JSONDecodeError):initial_state={}
 def save_state(state):
  state_path.parent.mkdir(parents=True,exist_ok=True)
  temp=state_path.with_name('.'+state_path.name+'.'+str(os.getpid())+'.tmp')
  temp.write_text(json.dumps({key:state.get(key) for key in ('active','activeModel','lastSuccess','lastSwitch')}),encoding='utf-8')
  os.chmod(temp,0o600);os.replace(temp,state_path)
 labels={'gemini':'Gemini','grok':'Grok','deepseek-relay':'中转站 DeepSeek','deepseek':'官方 DeepSeek'}
 def notify_switch(previous,current):
  old=labels.get(previous,previous or '启动');new=labels.get(current,current)
  switched_at=time.strftime('%m月%d日 %H:%M:%S')
  content=f'江生的聊天线路已从{old}切换到{new}（{switched_at}），回复服务正在继续运行。我会每五分钟检查优先级，线路恢复后自动切回。'
  event='route-switch-'+str(time.time_ns())
  def publish():
   try:
    proc=subprocess.Popen(['/home/hermes/.hermes/tools/node-26.12.1-linux-x64/bin/node','/home/hermes/qq-qzone-post.mjs','--publish-update',event],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:proc.communicate(content.encode(),timeout=100)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
   except Exception:pass
  threading.Thread(target=publish,daemon=True).start()
 def request(route,payload):
  data={**payload,'model':route['model']}
  if route['name']=='deepseek':data['thinking']={'type':'disabled'}
  req=urllib.request.Request(route['base'].rstrip('/')+'/chat/completions',data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+route['key'],'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=25) as r:return r.read(8*1024*1024),r.headers.get('Content-Type','application/json')
 pool=RoutePool(config['routes'],request,on_switch=notify_switch,initial_state=initial_state,on_state=save_state)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def send(self,code,body,ctype='application/json'):
   self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  def do_GET(self):
   if self.path=='/health':self.send(200,json.dumps(pool.health()).encode())
   elif self.path=='/v1/models':self.send(200,json.dumps({'object':'list','data':[{'id':'qq-chat','object':'model'}]}).encode())
   else:self.send(404,b'{}')
  def do_POST(self):
   if self.headers.get('Authorization')!='Bearer '+config['localKey']:self.send(401,b'{}');return
   if self.path!='/v1/chat/completions':self.send(404,b'{}');return
   try:
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=8*1024*1024:raise ValueError('invalid request size')
    payload=json.loads(self.rfile.read(size));body,ctype=pool.chat(payload);self.send(200,body,ctype)
   except Exception:self.send(503,b'{"error":{"message":"chat providers unavailable","type":"upstream_error"}}')
 def probes():
  pool.probe_due(force=True)
  while True:time.sleep(5);pool.probe_due()
 threading.Thread(target=probes,daemon=True).start()
 ThreadingHTTPServer(('127.0.0.1',8650),Handler).serve_forever()

if __name__=='__main__':main()
