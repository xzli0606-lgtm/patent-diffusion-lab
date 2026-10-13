"""Local browser interface. Inputs/results stay in an explicit local directory."""
import argparse
import json
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
<small>One row per focal family; one event per focal/citing-family pair. Preserve missing-classification flags and zero-citation families.</small>
</section><section><h2>2 · Comparison / 比较设置</h2>
<label>Comparison type</label><select id="type"><option value="technology">Technology routes / 技术路线</option><option value="country">Countries / 国家</option><option value="other">Other defined groups / 其他明确组别</option></select>
<label>Group A label (difference = A − B)</label><input id="a" value="Route A"><label>Group B label</label><input id="b" value="Route B">
<label>Group definition and source / 分组定义与来源</label><input id="definition" placeholder="Explain how each patent family was assigned">
<label>Country basis (for country comparisons)</label><select id="country"><option value="applicant">Applicant country</option><option value="inventor">Inventor country</option><option value="priority">Priority country</option><option value="grant_office">Grant office</option></select>
<label>Data cutoff / 数据截止日</label><input id="cutoff" type="date" value="2026-06-30"><label>Complete windows, years / 完整观察窗（年）</label><input id="windows" value="1,3,5">
<label>Field mapping and matching / 字段映射与匹配</label>
<small>Map original column names to canonical names. Blank maps assume canonical names. focal_field uses WIPO35 (1–35); field_mask preserves the full set as a 35-bit integer.</small>
<textarea id="mapping" rows="10">{"family_columns": {}, "edge_columns": {}, "matching_columns": ["grant_quarter", "focal_field"]}</textarea>
<p><small>Family fields: family_id, grant_date, focal_field, group.<br>Event fields: family_id, citing_family_id, event_date, field_mask, classification_missing.</small></p>
<button id="run">Validate and compare / 校验并比较</button></section>
<section><h2>3 · Results / 结果</h2><pre id="status">Ready / 就绪</pre><div id="links"></div><p><small>Comparisons are observational. Complete-pair and classification exclusions are reported per window. The full paper reference analyses run through the separate reproduce command.</small></p></section>
<script>
const token='__TOKEN__';const el=id=>document.getElementById(id);
async function upload(id){const file=el(id).files[0];if(!file)throw Error('Select '+id+' file');const response=await fetch('/upload?name='+id+'&ext='+file.name.split('.').pop(),{method:'POST',headers:{'X-Local-Token':token},body:file});const data=await response.json();if(!response.ok)throw Error(data.error);return data.path;}
el('run').onclick=async()=>{el('run').disabled=true;el('links').textContent='';try{el('status').textContent='Uploading / 正在读取文件';const families=await upload('families'),edges=await upload('edges');const config={...JSON.parse(el('mapping').value),comparison_type:el('type').value,groups:[el('a').value,el('b').value],group_definition:el('definition').value,country_basis:el('country').value,cutoff:el('cutoff').value,windows:el('windows').value.split(',').map(Number)};const r=await fetch('/run',{method:'POST',headers:{'X-Local-Token':token,'Content-Type':'application/json'},body:JSON.stringify({families,edges,config})});const d=await r.json();if(!r.ok)throw Error(d.error);const timer=setInterval(async()=>{const s=await(await fetch('/status')).json();el('status').textContent=s.status+(s.message?'\n'+s.message:'');if(s.status!=='RUNNING'){clearInterval(timer);el('run').disabled=false;if(s.status==='COMPLETE')el('links').innerHTML='<a href="/report" target="_blank">View report / 查看报告</a> · <a href="/download">Download results / 下载结果</a>'; }},1500);}catch(e){el('status').textContent=e.message;el('run').disabled=false;}};
</script></html>'''


def serve(workdir,port=8765):
    root=Path(workdir).resolve();root.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(32)
    state={'status':'READY'}; uploaded={}
    def compute_job(folder,payload):
        config=folder/'config.json';config.write_text(json.dumps(payload['config']),encoding='utf-8')
        with (folder/'run.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-m','patent_diffusion','compare','--families',payload['families'],'--edges',payload['edges'],'--config',str(config),'--output',str(folder/'results')],stdout=log,stderr=log)
        if result.returncode:
            state.update(status='FAILED',message=(folder/'run.log').read_text(encoding='utf-8')[-6000:])
        else:
            with zipfile.ZipFile(folder/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
                for p in (folder/'results').rglob('*'):
                    if p.is_file():z.write(p,p.relative_to(folder/'results'))
            state.update(status='COMPLETE',folder=str(folder),message='Results computed. Inspect sample exclusions and model estimability in the report.')
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
            elif self.path=='/status':self.send({k:v for k,v in state.items() if k!='folder'})
            elif self.path in ['/report','/download'] and state['status']=='COMPLETE':
                p=Path(state['folder'])/('results/report.html' if self.path=='/report' else 'results.zip')
                self.send(p.read_bytes(),'text/html; charset=utf-8' if self.path=='/report' else 'application/zip')
            else:self.send({'error':'Not found'},code=404)
        def do_POST(self):
            from urllib.parse import urlparse,parse_qs
            if self.headers.get('Host','').split(':')[0] not in {'127.0.0.1','localhost'}:
                return self.send({'error':'Local host required'},code=403)
            if self.headers.get('X-Local-Token')!=token:return self.send({'error':'Invalid local token'},code=403)
            if state['status']=='RUNNING':return self.send({'error':'An analysis is running'},code=409)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<=0 or size>1024**3:raise ValueError('File/request must be between 1 byte and 1 GiB; use CLI for larger files')
                if self.path.startswith('/upload?'):
                    q=parse_qs(urlparse(self.path).query);name=q['name'][0];ext=q['ext'][0].lower()
                    if name not in ['families','edges'] or ext not in ['csv','parquet']:raise ValueError('Invalid table type')
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
                    if any(payload.get(k) not in uploaded for k in ['families','edges']):raise ValueError('Use files uploaded in this session')
                    folder=root/('run_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3));folder.mkdir()
                    state.update(status='RUNNING',message='Validating and estimating / 正在校验和估计')
                    threading.Thread(target=job,args=(folder,payload),daemon=True).start();self.send({'status':'RUNNING'})
                else:self.send({'error':'Not found'},code=404)
            except (ValueError,KeyError,OSError) as exc:self.send({'error':str(exc)},code=400)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Local interface: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)',flush=True)
    server.serve_forever()


def main():
    p=argparse.ArgumentParser();p.add_argument('--workdir',type=Path,required=True);p.add_argument('--port',type=int,default=8765)
    a=p.parse_args();serve(a.workdir,a.port)
