"""Install packed plugin into official DSH and exercise the authenticated panel.

DSH_BIN must point at the actual supported CLI. No mocked Cordis/React services.
Covers the global panel and two native nonblank Sessions, using closed offline
recordings persisted through the official provider rather than mocked UI props.
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
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout

REPO = Path(__file__).resolve().parents[2]

def click_with_native_setup(page, target, artifacts, handled):
    """Use supported first-run buttons; never bypass a modal or enter credentials."""
    for _ in range(4):
        try:
            target.click(trial=True,timeout=3000)
            target.click(timeout=5000)
            return
        except PlaywrightTimeout:
            dialog=page.get_by_role('dialog').last
            expect(dialog).to_be_visible()
            title=dialog.get_attribute('aria-label') or ''
            handled.append(title)
            page.screenshot(path=str(artifacts/f'dsh-dialog-{len(handled)}.png'),full_page=True)
            exact_dialog=page.get_by_role('dialog',name=title,exact=True)
            if title in ('Preview Notice','预览版说明'):
                exact_dialog.get_by_role('button',name=re.compile(r'^(Continue|继续)$')).click()
            elif title in ('Add an API key to get started','添加一个 API Key 开始使用'):
                exact_dialog.get_by_role('button',name=re.compile(r'^(Configure later|稍后配置)$')).click()
            else:
                # Only implicit dismissal for other optional native dialogs.
                page.keyboard.press('Escape')
            expect(exact_dialog).not_to_be_visible()
    raise AssertionError('native setup did not settle after four normal interactions')

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
            # The installed profile owns editable settings. Keep its Hall
            # configuration in that profile, not a final CLI override layer.
            profile_patch=Path(env['DSH_HOME'])/'profiles/web/cordis.patch.yml'
            profile_patch.write_text('- id: philharmonie\n  config:\n    state: '+json.dumps(str(base/'hall-state'))+'\n    demo: true\n')
            native_root=base/'native-workspace'
            native_root.mkdir()
            subprocess.run(['node',str(REPO/'dsh-plugin-philharmonie/tests/seed-native-sessions.mjs'),str(Path(env['DSH_HOME'])/'sessions'),str(native_root)],env=dict(env,DSH_BIN=binary),check=True,timeout=60)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            proc = subprocess.Popen([binary,'--profile','web','--port',str(port),'--no-open'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
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
                    page=context.new_page();errors=[];dismissed_dialogs=[];api_errors=[];console_errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.on('console',lambda message:console_errors.append(re.sub(r'token=[^\s]+','token=<redacted>',message.text)) if message.type=='error' else None)
                    def capture_api_error(response):
                        if '/api/' not in urlsplit(response.url).path:return
                        try:
                            payload=response.json()
                            result=payload.get('result',payload) if isinstance(payload,dict) else {}
                            if response.status>=400 or result.get('ok') is False:
                                error=result.get('error',{})
                                api_errors.append(dict(path=urlsplit(response.url).path,status=response.status,code=error.get('code'),message=error.get('message')))
                        except Exception:pass
                    page.on('response',capture_api_error)
                    try:
                        page.goto(launch,wait_until='domcontentloaded')
                        entry=page.get_by_role('button',name='Concert Hall',exact=True)
                        expect(entry).to_be_visible(timeout=60000)
                        click_with_native_setup(page,entry,artifacts,dismissed_dialogs)
                        frame=page.frame_locator('iframe[title="Philharmonie Concert Hall"]')
                        expect(frame.locator('#task')).to_have_value('Improve sorted search while retaining first-match semantics',timeout=30000)
                        click_with_native_setup(page,frame.locator('#compile'),artifacts,dismissed_dialogs)
                        expect(frame.locator('#compile-result')).to_contain_text('编译通过')
                        frame.locator('#consent').check();frame.locator('#start').click()
                        expect(frame.locator('#run-state')).to_have_text('completed',timeout=30000)
                        expect(frame.locator('.decision.keep')).to_have_count(2)
                        expect(frame.locator('.decision.crash')).to_have_count(1)
                        expect(frame.locator('.decision.discard')).to_have_count(1)
                        page.screenshot(path=str(artifacts/'dsh-panel-desktop.png'),full_page=True)
                        page.get_by_role('button',name='返回 DSH 会话',exact=True).click()
                        def open_session(suffix):
                            identity='phil-native-session-'+suffix
                            row=page.locator('[data-row-key="session:'+identity+'"]')
                            if not row.is_visible():
                                for group in page.locator('[data-row-key^="workspace:"][aria-expanded="false"]').all():
                                    group.click()
                            expect(row).to_be_visible(timeout=15000)
                            row.click()
                            expect(row).to_have_attribute('aria-selected','true')
                            header=page.locator('[data-philharmonie-header="'+identity+'"]')
                            expect(header).to_be_visible()
                            return identity,row,header
                        a,row_a,header_a=open_session('a')
                        expect(page.get_by_text('Inspect Bach task alpha.',exact=True)).to_be_visible()
                        expect(header_a).to_contain_text('未关联',timeout=15000)
                        header_a.click()
                        expect(frame.locator('#session-label')).to_contain_text(a)
                        program=json.loads(frame.locator('#source').input_value())
                        program['task']['id']='native-task-a'
                        program['task']['summary']='Native Session alpha Bach loop'
                        frame.locator('details.source > summary').click()
                        frame.locator('#source').fill(json.dumps(program))
                        expect(frame.locator('#bind-session')).to_be_disabled()
                        frame.locator('#apply').click()
                        expect(frame.locator('#task')).to_have_value(program['task']['summary'])
                        frame.locator('#bind-session').click()
                        expect(frame.locator('#session-label')).to_contain_text('当前任务已关联')
                        expect(frame.locator('#runs option')).to_have_count(1)
                        frame.locator('#compile').click()
                        expect(frame.locator('#compile-result')).to_contain_text('编译通过')
                        frame.locator('#consent').check();frame.locator('#start').click()
                        expect(frame.locator('#run-state')).to_have_text('completed',timeout=30000)
                        run_a=frame.locator('#runs').input_value()
                        page.get_by_role('button',name='返回 DSH 会话',exact=True).click()
                        expect(row_a).to_have_attribute('aria-selected','true')
                        expect(page.get_by_text('Inspect Bach task alpha.',exact=True)).to_be_visible()
                        expect(header_a).to_contain_text('completed',timeout=15000)
                        page.screenshot(path=str(artifacts/'dsh-session-header.png'),full_page=True)
                        b,row_b,header_b=open_session('b')
                        expect(header_b).to_contain_text('未关联',timeout=15000)
                        header_b.click()
                        expect(frame.locator('#session-label')).to_contain_text(b)
                        program_b=json.loads(frame.locator('#source').input_value())
                        program_b['task']['id']='native-task-b'
                        program_b['task']['summary']='Native Session beta independent task'
                        frame.locator('details.source > summary').click()
                        frame.locator('#source').fill(json.dumps(program_b));frame.locator('#apply').click()
                        expect(frame.locator('#task')).to_have_value(program_b['task']['summary'])
                        frame.locator('#bind-session').click()
                        expect(frame.locator('#session-label')).to_contain_text('当前任务已关联')
                        expect(frame.locator('#runs option')).to_have_count(1)
                        expect(frame.locator('#run-state')).to_have_text('未启动')
                        expect(frame.locator('#cancel')).to_be_disabled()
                        page.get_by_role('button',name='返回 DSH 会话',exact=True).click()
                        open_session('a')[2].click()
                        expect(frame.locator('#task')).to_have_value(program['task']['summary'])
                        expect(frame.locator('#runs')).to_have_value(run_a)
                        expect(frame.locator('#run-state')).to_have_text('completed')
                        page.reload(wait_until='domcontentloaded')
                        if not page.locator('iframe[title="Philharmonie Concert Hall"]').is_visible():
                            open_session('a')[2].click()
                        expect(frame.locator('#session-label')).to_contain_text(a)
                        expect(frame.locator('#task')).to_have_value(program['task']['summary'])
                        expect(frame.locator('#runs')).to_have_value(run_a)
                        expect(frame.locator('#run-state')).to_have_text('completed')
                        page.screenshot(path=str(artifacts/'dsh-session-restored.png'),full_page=True)
                        page.get_by_role('button',name='全局大厅',exact=True).click()
                        expect(frame.locator('#bind-session')).to_be_disabled()
                        expect(page.locator('[data-philharmonie-session]')).to_have_attribute('data-philharmonie-session','')
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
                            diagnostics=dict(errors=errors,apiErrors=api_errors[-30:],consoleErrors=console_errors[-30:],dismissedDialogs=dismissed_dialogs,body=page.locator('body').inner_text()[:12000],entries=page.evaluate("(window.__DSH_BOOT__?.entries||[]).map(e=>e.id)"))
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
