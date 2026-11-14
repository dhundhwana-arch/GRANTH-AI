import json,sys,glob
A="answered"; R="abstained"; E="either"; C="edition_conflict"
def q(i,cat,lang,book,text,expect,pages=None,must=None,must_not=None,mx=None,group=None,**kw):
    d={"id":i,"cat":cat,"lang":lang,"book":book,"q":text,"expect":expect}
    if pages: d["pages"]=pages
    if must: d["must"]=must
    if must_not: d["must_not"]=must_not
    if mx: d["max_sentences"]=mx
    if group: d["group"]=group
    d.update(kw); return d
BOOKS={"sci":"granth_vigyan_10_2026","sci27":"granth_vigyan_10_2027","soc":"granth_samajik_10_2026","both":["granth_vigyan_10_2026","granth_vigyan_10_2027"]}
EXPECT={"answered":"must answer; lead citation page in 'pages'; every 'must' string in the answer; no 'must_not' string; at most 'max_sentences' sentences when given","abstained":"must refuse","edition_conflict":"must show both editions separately, each with its own value and page","either":"refusal OK; if answered it must satisfy pages/must/must_not"}
def write(path,suite,about,limits,Q,extra=None):
    old=set()
    for f in glob.glob("benchmarks/phase3/*.json")+glob.glob("benchmarks/phase4/*.json")+glob.glob("benchmarks/phase5/*.json")+["benchmarks/questions.json","benchmarks/independent/questions.json"]:
        if f.endswith(path.split("/")[-1]): continue
        def walk(o):
            if isinstance(o,dict):
                for k,v in o.items():
                    if k in("q","question") and isinstance(v,str): old.add(v.strip())
                    else: walk(v)
            elif isinstance(o,list):
                for v in o: walk(v)
        walk(json.load(open(f,encoding="utf8")))
    ids=[x["id"] for x in Q]; assert len(ids)==len(set(ids))
    dup=[x["q"] for x in Q if x["q"] in old]
    doc={"suite":suite,"written":"2026-11-13","about":about,"limitations":limits,"books":BOOKS,"expect_values":EXPECT,
         "overlap_with_earlier_sets":dup,"questions":Q}
    if extra: doc.update(extra)
    json.dump(doc,open(path,"w",encoding="utf8"),ensure_ascii=False,indent=1)
    from collections import Counter
    print(path,len(Q),"dups:",dup, dict(Counter(x["expect"] for x in Q)))
