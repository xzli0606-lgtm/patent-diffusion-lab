"""Local browser interface. Inputs/results stay in an explicit local directory."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import zipfile

PAGE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Patent Diffusion Lab</title>
<style>body{font:16px system-ui;background:#f4f7fa;color:#162a40;max-width:1040px;margin:40px auto}section{background:white;padding:25px;border-radius:12px;margin:18px 0}label{display:block;margin:14px 0 5px}input,select,textarea{font:inherit;padding:9px;box-sizing:border-box;width:100%;border:1px solid #b8c9d8;border-radius:5px}button{background:#155d81;color:white;border:0;border-radius:6px;padding:12px 20px;margin-top:16px;cursor:pointer}textarea{font:14px monospace}small{color:#466078}pre{white-space:pre-wrap}a{color:#155d81}</style>
<h1>Patent Diffusion Lab</h1><p>Compare when patent citation paths arrive, recur and expand.<br>比较专利引用历程中的到达、重复引用与后续扩展。</p>
<section><h2>1 · Data / 数据</h2><p>Upload CSV or Parquet tables. Files remain on this computer. 文件仅保存在本机。</p>
<label>Patent families / 专利族</label><input id="families" type="file" accept=".csv,.parquet">
<label>Citation events / 引用事件</label><input id="edges" type="file" accept=".csv,.parquet">
<label>Source manifest / 来源声明</label><input id="source_manifest" type="file" accept=".json">
<label>Classification mapping manifest (optional) / 分类映射记录</label><input id="mapping_manifest" type="file" accept=".json">
<small>One row per focal family; one event per focal/citing-family pair. Preserve missing-classification flags and zero-citation families.</small>
</section><section><h2>2 · Comparison / 比较设置</h2>
<label>Comparison type</label><select id="type"><option value="technology">Technology routes / 技术路线</option><option value="country">Countries / 国家</option><option value="other">Other defined groups / 其他明确组别</option></select>
<label>Group A label (difference = A − B)</label><input id="a" value="Route A"><label>Group B label</label><input id="b" value="Route B">
<label>Group definition and source / 分组定义与来源</label><input id="definition" placeholder="Explain how each patent family was assigned">
<label>Country basis (for country comparisons)</label><select id="country"><option value="applicant">Applicant country</option><option value="inventor">Inventor country</option><option value="priority">Priority country</option><option value="grant_office">Grant office</option></select>
<label>Data cutoff / 数据截止日</label><input id="cutoff" type="date" value="2026-06-30"><label>Complete windows, years / 完整观察窗（年）</label><input id="windows" value="1,3,5">
<label>Grant office scope / 授权局范围</label><input id="offices" value="US">
<label>Calendar block anchor / 日历块锚定年</label><input id="anchor" type="number" value="2019">
<label>Grant cohort anchor / 授权队列锚定年</label><input id="cohort_anchor" type="number" value="2019">
<label>Mode / 模式</label><select id="mode"><option value="smoke">Smoke — diagnostics only / 仅诊断</option><option value="formal">Formal — full precision budget / 正式精度</option></select>
<label>Import configuration / 导入配置</label><input id="import" type="file" accept=".json">
<label>Field mapping and matching / 字段映射与匹配</label>
<small>Map original column names to canonical names. Blank maps assume canonical names. focal_field uses WIPO35 (1–35); field_mask preserves the full set as a 35-bit integer.</small>
<textarea id="mapping" rows="10">{"family_columns": {}, "edge_columns": {}, "matching_columns": ["grant_quarter", "focal_field"]}</textarea>
<p><small>Family fields: family_id, grant_date, focal_field, group.<br>Event fields: family_id, citing_family_id, event_date, field_mask, classification_missing.</small></p>
<p>Inference requires at least 30 effective matching cells. Donor support and method policies are fixed. Formal references may take substantial time. MCSE is simulation error, not sampling uncertainty.</p>
<button id="export">Export configuration / 导出配置</button><button id="run">Validate and compare / 校验并比较</button><button id="cancel" disabled>Cancel / 取消</button></section>
<section><h2>3 · Results / 结果</h2><pre id="status">Ready / 就绪</pre><div id="links"></div><p><small>Observational comparisons. Inspect exclusions, precision and model status. Downloads contain summaries, not raw family/event tables. Summary results also require appropriate permission before public sharing.</small></p></section>
<script>
const token='__TOKEN__';const el=id=>document.getElementById(id);
let configuration;const ready=fetch('/defaults').then(r=>r.json()).then(c=>configuration=c);
function configured(){let c=structuredClone(configuration),m=JSON.parse(el('mapping').value);c.comparison={...c.comparison,type:el('type').value,groups:[el('a').value,el('b').value],group_definition:el('definition').value,country_basis:el('country').value,grant_office_scope:el('offices').value.split(',').map(x=>x.trim()),cutoff:el('cutoff').value,windows_years:el('windows').value.split(',').map(Number)};c.inputs.family_columns=m.family_columns;c.inputs.edge_columns=m.edge_columns;c.matching.columns=m.matching_columns;c.matching.cluster_columns=m.matching_columns;c.reference.calendar_anchor_year=Number(el('anchor').value);c.reference.grant_cohort_anchor_year=Number(el('cohort_anchor').value);c.execution.mode=el('mode').value;return c;}
el('import').onchange=async()=>{await ready;try{configuration=JSON.parse(await el('import').files[0].text());if(configuration.schema_version!=='portable_v1')throw Error('Require portable_v1');let c=configuration.comparison;el('type').value=c.type;el('a').value=c.groups[0];el('b').value=c.groups[1];el('definition').value=c.group_definition;el('country').value=c.country_basis||'applicant';el('offices').value=c.grant_office_scope.join(',');el('cutoff').value=c.cutoff;el('windows').value=c.windows_years.join(',');el('mode').value=configuration.execution.mode;el('anchor').value=configuration.reference.calendar_anchor_year;el('cohort_anchor').value=configuration.reference.grant_cohort_anchor_year;el('mapping').value=JSON.stringify({family_columns:configuration.inputs.family_columns||{},edge_columns:configuration.inputs.edge_columns||{},matching_columns:configuration.matching.columns});}catch(e){el('status').textContent=e.message;}};
el('export').onclick=async()=>{await ready;try{let c=configured();c.inputs.source_manifest='source_manifest.json';let url=URL.createObjectURL(new Blob([JSON.stringify(c,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='comparison.json';a.click();URL.revokeObjectURL(url);}catch(e){el('status').textContent=e.message;}};
async function upload(id,optional=false){const file=el(id).files[0];if(!file){if(optional)return null;throw Error('Select '+id);}const r=await fetch('/upload?name='+id+'&ext='+file.name.split('.').pop(),{method:'POST',headers:{'X-Local-Token':token},body:file});let d=await r.json();if(!r.ok)throw Error(d.error);return d.path;}
el('cancel').onclick=async()=>{await fetch('/cancel',{method:'POST',headers:{'X-Local-Token':token},body:'{}'});};
el('run').onclick=async()=>{await ready;el('run').disabled=true;el('links').textContent='';try{let payload={profile:'portable_v1',families:await upload('families'),edges:await upload('edges'),source_manifest:await upload('source_manifest'),mapping_manifest:await upload('mapping_manifest',true),config:configured()};let r=await fetch('/run',{method:'POST',headers:{'X-Local-Token':token,'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw Error(d.error);el('cancel').disabled=false;let timer=setInterval(async()=>{try{let s=await(await fetch('/status')).json();el('status').textContent=JSON.stringify(s,null,2);if(!['RUNNING','CANCELLING'].includes(s.status)){clearInterval(timer);el('run').disabled=false;el('cancel').disabled=true;if(['COMPLETE','COMPLETED_WITH_LIMITATIONS'].includes(s.status))el('links').innerHTML='<a href="/report" target="_blank">Report / 报告</a> · <a href="/download">Download summaries / 下载汇总</a>';}}catch(e){el('status').textContent=e.message;}},1000);}catch(e){el('status').textContent=e.message;el('run').disabled=false;}};
</script></html>'''


def serve(workdir,port=8765):
    root=Path(workdir).resolve();root.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(32)
    state={'status':'READY'}; uploaded={}; processes={}; lock=threading.Lock()
    def compute_job(folder,payload):
        if payload.get('profile','portable_v1')=='portable_v1':
            from .portable_config import resolve
            payload['config']=resolve(payload['config'])
            payload['config']['inputs']['source_manifest']=payload['source_manifest']
            payload['config']['inputs'].pop('classification_mapping_manifest',None)
            if payload.get('mapping_manifest'):
                payload['config']['inputs']['classification_mapping_manifest']=payload['mapping_manifest']
        config=folder/'config.json';config.write_text(json.dumps(payload['config']),encoding='utf-8')
        with (folder/'run.log').open('w',encoding='utf-8') as log:
            with lock:
                if state.get('cancelled'):
                    state.update(status='CANCELLED',message='Cancelled before analysis started.')
                    return
                process=subprocess.Popen([sys.executable,'-m','patent_diffusion','compare','--profile',payload.get('profile','portable_v1'),'--families',payload['families'],'--edges',payload['edges'],'--config',str(config),'--output',str(folder/'results')],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                processes['active']=process
            process.wait()
        if state.get('cancelled'):
            from .portable_config import write
            write(folder/'cancelled.json',{'status':'CANCELLED','result_is_incomplete':True})
            state.update(status='CANCELLED',message='Cancelled; incomplete outputs are not analysis results.')
            return
        if process.returncode:
            state.update(status='FAILED',message=(folder/'run.log').read_text(encoding='utf-8')[-6000:])
        else:
            with zipfile.ZipFile(folder/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
                for p in (folder/'results').rglob('*'):
                    if p.is_file() and p.suffix!='.parquet':z.write(p,p.relative_to(folder/'results'))
            result_path=folder/'results/results.json'
            status=json.loads(result_path.read_text(encoding='utf-8')).get('status') if result_path.exists() else 'COMPUTED'
            state.update(status='COMPLETED_WITH_LIMITATIONS' if status=='COMPLETED_WITH_LIMITATIONS' else 'COMPLETE',folder=str(folder),message='Inspect exclusions, precision and estimability; completion is not publication acceptance.')
    def job(folder,payload):
        try:
            compute_job(folder,payload)
        except Exception as exc:
            state.update(status='FAILED',message=str(exc))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,data,kind='application/json',code=200):
            if isinstance(data,dict):data=json.dumps(data).encode()
            elif isinstance(data,str):data=data.encode()
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.headers.get('Host','').split(':')[0] not in {'127.0.0.1','localhost'}:
                return self.send({'error':'Local host required'},code=403)
            if self.path=='/':self.send(PAGE.replace('__TOKEN__',token),'text/html; charset=utf-8')
            elif self.path=='/defaults':
                from .portable_config import DEFAULTS
                self.send(DEFAULTS)
            elif self.path=='/status':
                snapshot={k:v for k,v in state.items() if k not in ['folder','cancelled']}
                if state.get('folder') and state['status']=='RUNNING':
                    try:snapshot['progress']=json.loads((Path(state['folder'])/'results/progress.json').read_text(encoding='utf-8'))
                    except (OSError,ValueError):pass
                self.send(snapshot)
            elif self.path in ['/report','/download'] and state['status'] in ['COMPLETE','COMPLETED_WITH_LIMITATIONS']:
                p=Path(state['folder'])/('results/report.html' if self.path=='/report' else 'results.zip')
                self.send(p.read_bytes(),'text/html; charset=utf-8' if self.path=='/report' else 'application/zip')
            else:self.send({'error':'Not found'},code=404)
        def do_POST(self):
            from urllib.parse import urlparse,parse_qs
            if self.headers.get('Host','').split(':')[0] not in {'127.0.0.1','localhost'}:
                return self.send({'error':'Local host required'},code=403)
            if self.headers.get('X-Local-Token')!=token:return self.send({'error':'Invalid local token'},code=403)
            if self.path=='/cancel':
                with lock:
                    if state['status']=='RUNNING':
                        state['cancelled']=True
                        if 'active' in processes and processes['active'].poll() is None: processes['active'].terminate()
                        state.update(status='CANCELLING',message='Waiting for the analysis process to stop.')
                return self.send({'status':state['status']})
            if state['status'] in ['RUNNING','CANCELLING']:return self.send({'error':'An analysis is running'},code=409)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<=0 or size>1024**3:raise ValueError('File/request must be between 1 byte and 1 GiB; use CLI for larger files')
                if self.path.startswith('/upload?'):
                    q=parse_qs(urlparse(self.path).query);name=q['name'][0];ext=q['ext'][0].lower()
                    if not ((name in ['families','edges'] and ext in ['csv','parquet']) or (name in ['source_manifest','mapping_manifest'] and ext=='json')):raise ValueError('Invalid input type')
                    path=root/(secrets.token_hex(8)+'_'+name+'.'+ext)
                    with path.open('xb') as f:
                        remaining=size
                        while remaining:
                            chunk=self.rfile.read(min(8<<20,remaining))
                            if not chunk:raise ValueError('Incomplete upload')
                            f.write(chunk);remaining-=len(chunk)
                    uploaded[str(path)]=True;self.send({'path':str(path)})
                elif self.path=='/run':
                    payload=json.loads(self.rfile.read(size))
                    profile=payload.get('profile','portable_v1')
                    if profile not in ['portable_v1','legacy_v0_2']:raise ValueError('Unknown profile')
                    names=['families','edges']+(['source_manifest'] if profile=='portable_v1' else [])
                    if payload.get('mapping_manifest'): names.append('mapping_manifest')
                    if any(payload.get(k) not in uploaded for k in names):raise ValueError('Use files uploaded in this session')
                    folder=root/('run_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3));folder.mkdir()
                    with lock:
                        if state['status'] in ['RUNNING','CANCELLING']:return self.send({'error':'An analysis is running'},code=409)
                        state.update(status='RUNNING',folder=str(folder),cancelled=False,message='Validating and estimating / 正在校验和估计')
                    threading.Thread(target=job,args=(folder,payload),daemon=True).start();self.send({'status':'RUNNING'})
                else:self.send({'error':'Not found'},code=404)
            except (ValueError,KeyError,OSError) as exc:self.send({'error':str(exc)},code=400)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local interface: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)',flush=True)
    server.serve_forever()


def main():
    p=argparse.ArgumentParser();p.add_argument('--workdir',type=Path,required=True);p.add_argument('--port',type=int,default=8765)
    a=p.parse_args();serve(a.workdir,a.port)
