# concurrency + retrieval latency against a fresh local server (dev sandbox; NOT an Android measurement)
import json, time, threading, urllib.request, subprocess, os, sys, statistics, resource
from granth import db, retrieval
con=db.connect('var/granth.sqlite3')
qs=[q["q"] for q in json.load(open("benchmarks/phase5/frozen_test.json",encoding="utf8"))["questions"] if q["book"]=="sci"]
ts=[]
for q in qs:
    t=time.perf_counter(); retrieval.search(con,q,[2],None,k=8); ts.append((time.perf_counter()-t)*1000)
ts.sort(); out={"retrieval_only_ms":{"median":round(statistics.median(ts),2),"p95":round(ts[int(len(ts)*.95)],2),"n":len(ts)}}
out["db_size_bytes"]=os.path.getsize('var/granth.sqlite3')
env=dict(os.environ,GRANTH_DB_PATH="/tmp/perf5.sqlite3"); 
import shutil; shutil.copy('var/granth.sqlite3','/tmp/perf5.sqlite3')
t0=time.perf_counter()
p=subprocess.Popen([sys.executable,"-m","granth","serve","--host","127.0.0.1","--port","8791"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for _ in range(200):
    try: urllib.request.urlopen("http://127.0.0.1:8791/api/health",timeout=1).read(); break
    except Exception: time.sleep(0.05)
out["server_start_s"]=round(time.perf_counter()-t0,2)
def ask(q,lat,err):
    try:
        t=time.perf_counter()
        req=urllib.request.Request("http://127.0.0.1:8791/api/ask",data=json.dumps({"question":q,"edition_id":2}).encode(),headers={"Content-Type":"application/json"})
        r=json.loads(urllib.request.urlopen(req,timeout=30).read()); lat.append((time.perf_counter()-t)*1000)
        if "status" not in r: err.append(str(r)[:80])
    except Exception as e: err.append(repr(e)[:120])
for n in (1,8,32):
    lat,err=[],[]; th=[threading.Thread(target=ask,args=(qs[i%len(qs)],lat,err)) for i in range(n*8)]
    t=time.perf_counter()
    sem=threading.Semaphore(n)
    def run(x):
        with sem: x.run()
    th2=[threading.Thread(target=run,args=(x,)) for x in th]
    [x.start() for x in th2]; [x.join() for x in th2]
    lat.sort()
    out[f"http_concurrency_{n}"]={"requests":len(th),"ok":len(lat),"errors":len(err),"first_error":err[:1],"median_ms":round(statistics.median(lat),1) if lat else None,"p95_ms":round(lat[int(len(lat)*.95)-1],1) if lat else None,"wall_s":round(time.perf_counter()-t,2)}
try:
    rss=int(open(f"/proc/{p.pid}/status").read().split("VmRSS:")[1].split()[0]); out["server_rss_after_load_mb"]=round(rss/1024,1)
except Exception as e: out["server_rss_after_load_mb"]=None
p.terminate()
print(json.dumps(out,indent=1,ensure_ascii=False))
d=json.load(open("benchmarks/results/phase5/phase5_performance.json")); d["phase5_extra"]=out; d["environment"]="development sandbox (Linux container), NOT an Android device"
json.dump(d,open("benchmarks/results/phase5/phase5_performance.json","w"),indent=1,ensure_ascii=False)
