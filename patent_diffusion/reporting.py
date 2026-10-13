"""Read fresh result files only; create actuals/tables without reading paper targets."""
import json
import math
from pathlib import Path
import numpy as np
import csv
from .bundles import sha256
from .reproduce import write as dump

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def holm(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [None] * len(values)
    running = 0.0
    for rank,i in enumerate(order):
        running = max(running, min(1.0,(len(values)-rank)*values[i]))
        out[i] = running
    return out

def compile_results(root):
    ROOT=Path(root).resolve()
    actuals, models, table4, s1, refs, third, diagnostics = [], [], [], [], [], [], []
    code = "patent_diffusion/reporting.py"
    def add(key, value, path, method="RECOMPUTED_FROM_REAL_DATA"):
        actuals.append({"actual_key":key,"actual_value":value,"execution_status":method,"source_output":str(Path(path).relative_to(ROOT)),"source_output_sha256":sha256(path),"code":code})
    if (ROOT/'inputs/source_ai_roster.parquet').exists():
        from .lineage import count
        count(ROOT)
    source = ROOT / "outputs/reused_source_counts.json"
    if source.exists():
        for k,v in read(source)["counts"].items(): add("sample."+k,v,source,"COUNTED_FROM_REUSED_PREPROCESSED_RECORDS")
    audit = ROOT / "outputs/window_samples.parquet"
    import pandas as pd
    f=pd.read_parquet(audit)
    add('sample.matched_pairs', f.match_id.nunique(), audit)
    add('sample.matched_families', f.docdb_family_id.nunique(), audit)
    input_edges=ROOT/'inputs/edges.parquet'
    if input_edges.exists():
        import pyarrow.parquet as pq
        add('sample.dated_family_edges',pq.read_metadata(input_edges).num_rows,input_edges)
    wa = ROOT / "outputs/window_audit.json"
    for z in read(wa):
        for k,v in z.items():
            if k!="window": add("window."+z["window"]+"."+k,v,wa)
    for h in ["1Y","3Y","5Y"]:
        p = ROOT / "outputs/model_results" / (h+".json")
        r = read(p)
        for label,z in r["binary"].items():
            flat = {"window":h,"outcome":label,"model":"conditional_logistic","effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"H4/H5 six windows" if label in ["H4","H5"] else "H1/H2/H3 within-window triplet"}
            models.append(flat)
            n = z["pairs_total"]
            for metric,value in [("ai_rate_pct",100*z["raw_rate_ai"]),("nonai_rate_pct",100*z["raw_rate_nonai"]),("difference_pp",100*z["absolute_rate_difference"]),("OR",z["estimate"]),("ci_low",z["ci95_low"]),("ci_high",z["ci95_high"]),("difference_ci_low_pp",z["difference_ci95_pp"][0]),("difference_ci_high_pp",z["difference_ci95_pp"][1])]: add("binary."+h+"."+label+"."+metric,value,p)
            if label in ["H3","H4","H5"]:
                row = {"window":h,"outcome":label,"pairs":n,"ai_count":int(round(n*z["raw_rate_ai"])),"nonai_count":int(round(n*z["raw_rate_nonai"])),"ai_rate_pct":100*z["raw_rate_ai"],"nonai_rate_pct":100*z["raw_rate_nonai"],"difference_pp":100*z["absolute_rate_difference"]}
                table4.append(row)
                for metric in ["ai_count","nonai_count","ai_rate_pct","nonai_rate_pct"]: add("table4."+h+"."+label+"."+metric,row[metric],p)
        for label,z in r["cox"].items():
            models.append({"window":h,"outcome":label,"model":"pair_stratified_Cox_Efron","effect_type":"HR",**z,"p_raw":z["p_two_sided"],"holm_family":"H1/H2/H3 within-window triplet" if label=="H1" else "SUPPORTING_TIMING"})
            for metric,key in [("HR","estimate"),("ci_low","ci95_low"),("ci_high","ci95_high")]: add("cox."+h+"."+label+"."+metric,z[key],p)
        for label,z in r["count"].items(): models.append({"window":h,"outcome":label,"model":"conditional_pair_FE_Poisson","effect_type":"CR",**z,"p_raw":z["p_two_sided"],"holm_family":"SUPPORTING_COUNT"})
        for label,z in r["piecewise"].items():
            for interval in z.get("intervals",[]): models.append({"window":h,"outcome":label,"model":"piecewise_pair_stratified_Cox","effect_type":"HR","interval":interval["interval"],**interval,"log_effect":math.log(interval["estimate"]),"p_raw":interval["p_two_sided"],"holm_family":"SUPPORTING_TIMING"})
        sp = ROOT / "outputs/sensitivity" / (h+".json")
        sr = read(sp)
        for rule,outcomes in sr["variants"].items():
            for label,z in outcomes.items():
                row = {"window":h,"rule":rule,"outcome":label,"pairs":z["pairs_total"],"ai_rate_pct":100*z["raw_rate_ai"],"nonai_rate_pct":100*z["raw_rate_nonai"],"difference_pp":100*z["absolute_rate_difference"],"OR":z["estimate"],"ci_low":z["ci95_low"],"ci_high":z["ci95_high"],"p_raw":z["p_two_sided"]}
                s1.append(row)
                models.append({"window":h,"outcome":label,"model":"sensitivity_"+rule,"effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"SECONDARY_RULE_SENSITIVITY"})
                for metric in ["ai_rate_pct","nonai_rate_pct","difference_pp","OR","ci_low","ci_high"]: add("S1."+rule+"."+h+"."+label+"."+metric,row[metric],sp)
        t = sr["third_family"]
        row = {"window":h,"ai_rate_pct":100*t["raw_rate_ai"],"nonai_rate_pct":100*t["raw_rate_nonai"],"difference_pp":100*t["absolute_rate_difference"],"difference_ci_low_pp":t["difference_ci95_pp"][0],"difference_ci_high_pp":t["difference_ci95_pp"][1],"OR":t["estimate"],"ci_low":t["ci95_low"],"ci_high":t["ci95_high"],"p_raw":t["p_two_sided"]}
        third.append(row)
        models.append({"window":h,"outcome":"H4_third_family","model":"third_distinct_citing_family","effect_type":"OR",**t,"p_raw":t["p_two_sided"],"holm_family":"THIRD_FAMILY_THREE_WINDOWS"})
        for k,v in row.items():
            if k!="window": add("third."+h+"."+k,v,sp)
        for ai,name in [(1,"ai"),(0,"nonai")]:
            d = sr["diagnostics"]["groups"][str(ai)]
            add("diagnostic."+h+"."+name+"_establishment_among_arrivals_pct",d["establishment_among_arrivals_pct"],sp)
            add("diagnostic."+h+"."+name+"_global_wait_median_days",d["global_arrival_to_establishment_days"]["median"],sp)
            for metric,source_key in [("grant_to_arrival_median_days","grant_to_arrival_days"),("remaining_observation_median_days","remaining_observation_days"),("same_field_wait_median_days","same_field_arrival_to_establishment_days")]:add("diagnostic."+h+"."+name+"_"+metric,d[source_key]["median"],sp)
            diagnostics.append({"window":h,"group":name,**d})
        gd=sr["diagnostics"]["groups"]
        add("diagnostic."+h+".conditional_difference_pp",gd["1"]["establishment_among_arrivals_pct"]-gd["0"]["establishment_among_arrivals_pct"],sp)
        ci=sr["diagnostics"]["arrival_conditioned_difference_ci95_pp"]
        add("diagnostic."+h+".conditional_ci_low_pp",ci[0],sp)
        add("diagnostic."+h+".conditional_ci_high_pp",ci[1],sp)
        for kind in ["fixed5_cohort","high_citation_exclusion_top1pct"]:
            for label,z in sr[kind].items():models.append({"window":h,"outcome":label,"model":kind,"effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"SECONDARY_SENSITIVITY"})
        z=sr["fixed5_H1"]
        models.append({"window":h,"outcome":"H1","model":"fixed5_followup_cohort","effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"SECONDARY_SENSITIVITY"})
        for label,bounds in sr["missing_extreme_bounds"].items():
            for bound,z in bounds.items():
                add('missing.'+bound+'.'+h+'.'+label.lower()+'.OR',z['estimate'],sp)
                models.append({"window":h,"outcome":label,"model":"missing_extreme_"+bound,"effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"SECONDARY_MISSINGNESS_BOUND"})
        for kind in ["main","nonai","grant","rebuilt"]:
            selected = ROOT / "outputs/opportunity_reference" / (kind+"_"+h+"_selected.json")
            rp = ROOT / Path(read(selected)["result_path"]) if kind!="rebuilt" else ROOT / "outputs/opportunity_reference" / (kind+"_"+h) / "RESULT.json"
            if not rp.exists():
                rp = ROOT / "outputs/opportunity_reference" / rp.parent.name / "RESULT.json"
            rr = read(rp)
            if kind!="rebuilt":
                aa=rr["audit"]
                add("reference."+kind+"."+h+".supported_pairs",aa["reference_retained_pairs"],rp)
                add("reference."+kind+"."+h+".excluded_pairs",aa["reference_unsupported_pairs"],rp)
            for label,z in rr["outcomes"].items():
                if kind=="rebuilt": row = {"pool":kind,"window":h,"outcome":label,"residual_pp":z["mean_excess_pp"],"ci_low_pp":z["rebuild_pool_ci95_pp"][0],"ci_high_pp":z["rebuild_pool_ci95_pp"][1],"supported_pairs":rr["reference_supported_pairs"],"replicates":rr["replicates"]}
                else: row = {"pool":kind,"window":h,"outcome":label,"observed_pp":z["observed_difference_pp"],"reference_pp":z["reference_difference_pp"],"residual_pp":z["excess_difference_pp"],"ci_low_pp":z["excess_ci95_pp"][0],"ci_high_pp":z["excess_ci95_pp"][1],"mcse_pp":z["mcse_pp"],"p_raw":z["bootstrap_normal_p_two_sided"],"supported_pairs":rr["audit"]["reference_retained_pairs"],"excluded_pairs":rr["audit"]["reference_unsupported_pairs"],"replicates":rr["replicates"]}
                refs.append(row)
                for k,v in row.items():
                    if k not in ["pool","window","outcome"]: add("reference."+kind+"."+h+"."+label+"."+k,v,rp)
    bp=ROOT/"outputs/model_results/benchmark.json"
    b=read(bp)
    models.append({"window":"to_20260630","outcome":"citation_intensity","model":"conditional_pair_FE_Poisson_offset","effect_type":"IRR",**b,"p_raw":b["p_two_sided"],"holm_family":"BENCHMARK"})
    for k,key in [("IRR","estimate"),("ci_low","ci95_low"),("ci_high","ci95_high")]: add("benchmark."+k,b[key],bp)
    labels=read(ROOT/"outputs/sensitivity/ai_label.json")
    for h,scopes in labels["windows"].items():
        for scope in ["ai_ge_090","ai_ge_090_nonai_lt_010"]:
            for label,z in scopes[scope].items():models.append({"window":h,"outcome":label,"model":scope,"effect_type":"OR",**z,"p_raw":z["p_two_sided"],"holm_family":"SECONDARY_AI_LABEL_SENSITIVITY"})
    for h in ["1Y","3Y","5Y"]:
        ix=[i for i,r in enumerate(models) if r["window"]==h and ((r["outcome"] in ["H1","H3"] and r["model"]=="conditional_logistic") or (r["outcome"]=="H1" and r["effect_type"]=="HR" and r["model"]=="pair_stratified_Cox_Efron"))]
        for i,v in zip(ix,holm([models[i]["p_raw"] for i in ix])): models[i]["p_holm"]=v
    ix=[i for i,r in enumerate(models) if r["outcome"] in ["H4","H5"] and r["model"]=="conditional_logistic"]
    for i,v in zip(ix,holm([models[i]["p_raw"] for i in ix])): models[i]["p_holm"]=v
    ix=[i for i,r in enumerate(refs) if r["pool"]=="main" and r["outcome"] in ["H4","H5"]]
    for i,v in zip(ix,holm([refs[i]["p_raw"] for i in ix])): refs[i]["p_holm"]=v
    for i,v in enumerate(holm([r["p_raw"] for r in third])): third[i]["p_holm"]=v
    ix=[i for i,r in enumerate(models) if r["model"]=="third_distinct_citing_family"]
    for i,v in zip(ix,holm([models[i]["p_raw"] for i in ix])):models[i]["p_holm"]=v
    fields=["window","outcome","model","effect_type","interval","estimate","log_effect","se_cluster","ci95_low","ci95_high","p_raw","p_holm","holm_family","pairs_total","pairs_informative","raw_rate_ai","raw_rate_nonai","absolute_rate_difference","difference_ci95_pp","ph_diagnostic"]
    write_csv(ROOT/"outputs/model_results/all_models.csv",models,fields)
    write_csv(ROOT/"outputs/tables/Table4.csv",table4,["window","outcome","pairs","ai_count","nonai_count","ai_rate_pct","nonai_rate_pct","difference_pp"])
    write_csv(ROOT/"outputs/tables/Supplementary_Table_S1.csv",s1,["window","rule","outcome","pairs","ai_rate_pct","nonai_rate_pct","difference_pp","OR","ci_low","ci_high","p_raw"])
    write_csv(ROOT/"outputs/tables/third_family_threshold.csv",third,list(third[0]))
    write_csv(ROOT/"outputs/opportunity_reference/all_reference_results.csv",refs,["pool","window","outcome","observed_pp","reference_pp","residual_pp","ci_low_pp","ci_high_pp","mcse_pp","p_raw","p_holm","supported_pairs","excluded_pairs","replicates"])
    dump(ROOT/"outputs/tables/waiting_time_and_nesting.json",diagnostics)
    dump(ROOT/"outputs/tables/all_models_nested.json",models)
    dump(ROOT/"outputs/tables/all_reference_nested.json",refs)
    write_csv(ROOT/"validation_actual.csv",actuals,["actual_key","actual_value","execution_status","source_output","source_output_sha256","code"])
    # Each scalar in every numerical result remains available in an auditable long table.
    numeric=[]
    def flatten(v,path,source):
        if isinstance(v,dict):
            for k,x in v.items():flatten(x,path+"."+str(k),source)
        elif isinstance(v,list):
            for i,x in enumerate(v):flatten(x,path+"."+str(i),source)
        elif isinstance(v,(int,float)) and not isinstance(v,bool):numeric.append({"source_output":str(source.relative_to(ROOT)),"key":path,"value":v,"sha256":sha256(source)})
    for source in sorted((ROOT/"outputs").rglob("*.json")):
        if "smoke" not in source.parts:flatten(read(source),"",source)
    write_csv(ROOT/"outputs/all_result_scalars.csv",numeric,["source_output","key","value","sha256"])
    print("actuals",len(actuals),"models",len(models),"reference rows",len(refs),flush=True)

def main():
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); compile_results(a.output)

if __name__ == '__main__': main()
