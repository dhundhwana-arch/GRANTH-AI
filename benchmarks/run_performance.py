"""Phase 4 performance measurements on the demo corpus (run: PYTHONPATH=. python benchmarks/run_performance.py).
Measured on the development sandbox, NOT on an Android device."""
import time,subprocess,sys,json,tempfile,resource,statistics,os
from pathlib import Path
t=time.perf_counter(); import granth; from granth import db,answer,retrieval; from granth.__main__ import seed_samples; imp=time.perf_counter()-t
con=db.connect(Path(tempfile.mkdtemp())/"p.sqlite3"); t=time.perf_counter(); seed_samples(con); seed=time.perf_counter()-t
ed={r["slug"]:r["id"] for r in con.execute("SELECT slug,id FROM textbook_editions")}; e=ed["granth_vigyan_10_2026"]
qs=[q["q"] for q in json.load(open("benchmarks/phase4/frozen_test.json"))["questions"] if q["book"]=="sci"]
t=time.perf_counter(); retrieval.get_index(con); idx=time.perf_counter()-t
def run(cache):
    out=[]
    for q in qs:
        t=time.perf_counter(); r=answer.ask(con,q,{"edition_id":e},use_cache=cache); out.append((time.perf_counter()-t)*1000)
    return out
cold=run(False); fill=run(True); warm=run(True)
h0=con.execute("SELECT COUNT(*) FROM usage_events WHERE kind='cache_hit'").fetchone()[0]
for q in qs: answer.ask(con,q,{"edition_id":e},use_cache=True)
hits=con.execute("SELECT COUNT(*) FROM usage_events WHERE kind='cache_hit'").fetchone()[0]-h0
p=lambda a,x: round(sorted(a)[min(len(a)-1,int(len(a)*x))],1)
res={"python_import_s":round(imp,3),"seed_4_books_s":round(seed,2),"index_build_s":round(idx,3),"questions":len(qs),
 "ask_no_cache_ms":{"median":round(statistics.median(cold),1),"p95":p(cold,.95),"max":round(max(cold),1)},
 "ask_cached_ms":{"median":round(statistics.median(warm),1),"p95":p(warm,.95)},
 "cache_hits_on_repeat":f"{hits}/{len(qs)}","peak_rss_mb":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1)}
# large book: replicate chunks x200
n0=con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0]
cols=[r[1] for r in con.execute("PRAGMA table_info(text_chunks)") if r[1]!="id"]
t=time.perf_counter()
for i in range(100): con.execute(f"INSERT INTO text_chunks({','.join(cols)}) SELECT {','.join(cols)} FROM text_chunks WHERE id<=?",(n0,))
con.commit(); n1=con.execute("SELECT COUNT(*) FROM text_chunks").fetchone()[0]
try:
    retrieval._indexes.clear()
except Exception as ex: res["large_note"]="index cache not cleared: "+str(ex)
t=time.perf_counter(); retrieval.get_index(con); big_idx=time.perf_counter()-t
big=[]
for q in qs[:15]:
    t=time.perf_counter(); answer.ask(con,q,{"edition_id":e},use_cache=False); big.append((time.perf_counter()-t)*1000)
res["large_synthetic"]={"chunks_before":n0,"chunks_after":n1,"index_build_s":round(big_idx,2),"ask_median_ms":round(statistics.median(big),1),"ask_max_ms":round(max(big),1),"peak_rss_mb":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1)}
print(json.dumps(res,indent=1))
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "benchmarks/results/phase5/phase5_performance.json"   # phase 4 result file is kept unchanged
res["engine_version"] = __import__("granth").ENGINE_VERSION
json.dump(res,open(OUT,"w"),indent=1)
