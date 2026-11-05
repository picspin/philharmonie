"""Install packed plugin into official DSH and exercise the authenticated panel.

DSH_BIN must point at the actual supported CLI. No mocked Cordis/React services.
This smoke covers the global panel; native nonblank-Session header interaction
is still a separate acceptance scenario.
"""
import json
import os
from pathlib import Path
import queue
import re
import signal
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

REPO = Path(__file__).resolve().parents[2]

class OfficialDshBrowserTests(unittest.TestCase):
    def test_packed_bundle_in_official_profile(self):
        binary = os.environ.get('DSH_BIN')
        if not binary:
            self.fail('DSH_BIN must name the actual installed DSH CLI')
        artifacts = Path(os.environ.get('PHIL_SCREENSHOTS', '/tmp/phil-official-shots'))
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='phil-official-') as temp:
            base = Path(temp)
            env = dict(os.environ, DSH_HOME=str(base/'dsh-home'))
            packed = subprocess.run(['npm','--cache',str(base/'npm-cache'),'pack','--ignore-scripts','--json','--pack-destination',str(base)],cwd=REPO,env=env,text=True,capture_output=True,check=True,timeout=60)
            tarball = base/json.loads(packed.stdout)[0]['filename']
            subprocess.run([binary,'--profile','web','--dump-default-config'],env=env,stdout=subprocess.DEVNULL,check=True,timeout=120)
            subprocess.run([binary,'plugin','--profile','web','add','file:'+str(tarball)],env=env,check=True,timeout=240)
            overlay=base/'local.yml'
            overlay.write_text('- id: philharmonie\n  config:\n    state: '+json.dumps(str(base/'hall-state'))+'\n    demo: true\n')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            proc = subprocess.Popen([binary,'--profile','web','--patch',str(overlay),'--port',str(port),'--no-open'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
            lines=queue.Queue();logs=[]
            def consume():
                for line in proc.stdout:
                    lines.put(line)
            reader=threading.Thread(target=consume,daemon=True);reader.start()
            try:
                launch=None;end=time.time()+120
                while time.time()<end:
                    try:line=lines.get(timeout=.2)
                    except queue.Empty:
                        if proc.poll() is not None:break
                        continue
                    logs.append(re.sub(r'token=[^\s]+','token=<redacted>',line))
                    match=re.search(r'dsh web: (http://127\.0\.0\.1:\d+/[^\s]*)',line)
                    if match:launch=match.group(1);break
                self.assertIsNotNone(launch,'official DSH did not announce a launch URL; inspect sanitized startup log')
                parsed=urlsplit(launch);origin=f'{parsed.scheme}://{parsed.netloc}/'
                with sync_playwright() as p:
                    options={'headless':True}
                    if os.environ.get('PHIL_CHROMIUM'):options['executable_path']=os.environ['PHIL_CHROMIUM']
                    browser=p.chromium.launch(**options)
                    context=browser.new_context(viewport={'width':1440,'height':1100})
                    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    try:
                        page.goto(launch,wait_until='domcontentloaded')
                        page.get_by_role('button',name='Concert Hall',exact=True).click(timeout=60000)
                        frame=page.frame_locator('iframe[title="Philharmonie Concert Hall"]')
                        expect(frame.locator('#task')).to_have_value('Improve sorted search while retaining first-match semantics',timeout=30000)
                        frame.locator('#compile').click();expect(frame.locator('#compile-result')).to_contain_text('编译通过')
                        frame.locator('#consent').check();frame.locator('#start').click()
                        expect(frame.locator('#run-state')).to_have_text('completed',timeout=30000)
                        expect(frame.locator('.decision.keep')).to_have_count(2)
                        expect(frame.locator('.decision.crash')).to_have_count(1)
                        expect(frame.locator('.decision.discard')).to_have_count(1)
                        program=json.loads(frame.locator('#source').input_value())
                        # Verify owner-authenticated metadata persistence. This is NOT a
                        # substitute for selecting a real native nonblank Session.
                        response=context.request.post(origin+'api/philharmonie/request',data={'method':'POST','path':'binding','sessionId':'ci-metadata-session','body':{'program':program}})
                        self.assertEqual(response.status,200,response.text())
                        self.assertEqual(response.json()['binding']['program']['task']['id'],program['task']['id'])
                        page.screenshot(path=str(artifacts/'dsh-panel-desktop.png'),full_page=True)
                        page.set_viewport_size({'width':390,'height':844})
                        page.screenshot(path=str(artifacts/'dsh-panel-mobile.png'),full_page=True)
                        anonymous=browser.new_context()
                        denied=anonymous.request.get(origin+'api/philharmonie/frame')
                        self.assertIn(denied.status,(401,403))
                        anonymous.close()
                        self.assertEqual(errors,[])
                    finally:
                        # Preserve diagnostics before Playwright tears the page down.
                        try:
                            page.screenshot(path=str(artifacts/'dsh-last-page.png'),full_page=True)
                            diagnostics=dict(errors=errors,body=page.locator('body').inner_text()[:12000],entries=page.evaluate("(window.__DSH_BOOT__?.entries||[]).map(e=>e.id)"))
                            (artifacts/'browser-diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
                        except Exception as capture_error:
                            (artifacts/'capture-error.txt').write_text(str(capture_error))
                        browser.close()
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                reader.join(timeout=2)
                while not lines.empty():logs.append(re.sub(r'token=[^\s]+','token=<redacted>',lines.get_nowait()))
                (artifacts/'startup-sanitized.log').write_text(''.join(logs))

if __name__=='__main__':unittest.main(verbosity=2)
