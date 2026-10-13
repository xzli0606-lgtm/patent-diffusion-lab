import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from patent_diffusion.demo import make_demo_frames


class LocalUITests(unittest.TestCase):
    def test_upload_compare_report_and_local_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            process=subprocess.Popen([sys.executable,'-m','patent_diffusion','ui','--workdir',tmp,'--port','0'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:
                line=process.stdout.readline()
                base=re.search(r'http://127\.0\.0\.1:\d+',line).group()
                page=urlopen(base).read().decode()
                token=re.search("const token='([^']+)'",page).group(1)
                with self.assertRaises(HTTPError) as err:
                    urlopen(Request(base,headers={'Host':'external.example'}))
                self.assertEqual(err.exception.code,403)
                with self.assertRaises(HTTPError):urlopen(Request(base+'/run',data=b'{}'))
                f,e=make_demo_frames()
                f=f.rename(columns={'docdb_family_id':'family_id','focus_grant_date':'grant_date','wipo35_field_nr':'focal_field'})
                f['group']=f.ai_indicator.map({1:'A',0:'B'})
                e=e.rename(columns={'focus_docdb_family_id':'family_id','citing_docdb_family_id':'citing_family_id','edge_event_date':'event_date','citing_wipo35_mask':'field_mask','citing_wipo35_missing':'classification_missing'})
                paths={}
                for name,frame in [('families',f),('edges',e)]:
                    req=Request(base+'/upload?name='+name+'&ext=csv',data=frame.to_csv(index=False).encode(),headers={'X-Local-Token':token})
                    paths[name]=json.loads(urlopen(req).read())['path']
                paths['config']={'comparison_type':'technology','groups':['A','B'],'group_definition':'Synthetic UI test','cutoff':'2026-06-30','windows':[1]}
                urlopen(Request(base+'/run',data=json.dumps(paths).encode(),headers={'X-Local-Token':token})).close()
                end=time.monotonic()+60
                while time.monotonic()<end:
                    status=json.loads(urlopen(base+'/status').read())
                    if status['status']!='RUNNING':break
                    time.sleep(.2)
                self.assertEqual(status['status'],'COMPLETE',status)
                self.assertIn(b'Matched pairs',urlopen(base+'/report').read())
                self.assertTrue(urlopen(base+'/download').read().startswith(b'PK'))
            finally:
                process.terminate();process.wait(timeout=10);process.stdout.close()


if __name__=='__main__':unittest.main()
