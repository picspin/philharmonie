"""Real Chromium -> HTTP -> compiler -> durable runner smoke (optional Playwright)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright, expect

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hall_e2e_server', REPO / 'concert-hall/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WorkbenchBrowserTests(unittest.TestCase):
    def test_browser_compose_compile_pause_resume_and_real_loop(self):
        with tempfile.TemporaryDirectory(prefix='phil-browser-') as temp:
            base = Path(temp)
            root = base / 'task'
            shutil.copytree(REPO / 'examples/bach-search', root)
            app = module.Workbench(root, base / 'state', demo=True)
            server = module.ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
            server.app = app
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as p:
                    options = {'headless': True}
                    if os.environ.get('PHIL_CHROMIUM'):
                        options['executable_path'] = os.environ['PHIL_CHROMIUM']
                    browser = p.chromium.launch(**options)
                    page = browser.new_page(viewport={'width':1440, 'height':1100})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    expect(page.locator('#task')).to_have_value('Improve sorted search while retaining first-match semantics')
                    page.get_by_label('事件驱动 / EDA').check()
                    self.assertIn('EDA',json.loads(page.locator('#source').input_value())['task']['context']['architecture'])
                    # Make the variation long enough to exercise pause/resume.
                    source = json.loads(page.locator('#source').input_value())
                    source['score']['chapters'][0]['body']['body']['children'][0]['argv'][2] = 'import time;time.sleep(.3);' + source['score']['chapters'][0]['body']['body']['children'][0]['argv'][2]
                    page.locator('details.source > summary').click()
                    expect(page.locator('#source')).to_be_visible()
                    page.locator('#source').fill(json.dumps(source))
                    page.get_by_role('button',name='应用 JSON',exact=True).click()
                    expect(page.locator('#source')).to_have_value(json.dumps(source,ensure_ascii=False,indent=2))
                    page.get_by_role('button',name='编译检查 →').click()
                    expect(page.locator('#compile-result')).to_contain_text('编译通过')
                    expect(page.locator('#start')).to_be_disabled()
                    page.locator('#consent').check()
                    expect(page.locator('#start')).to_be_enabled()
                    # Unapplied JSON changes must not reuse prior consent.
                    page.locator('#source').fill(page.locator('#source').input_value()+'\n')
                    expect(page.locator('#start')).to_be_disabled()
                    expect(page.locator('#consent')).not_to_be_checked()
                    page.get_by_role('button',name='应用 JSON',exact=True).click()
                    page.get_by_role('button',name='编译检查 →').click()
                    expect(page.locator('#compile-result')).to_contain_text('编译通过')
                    page.locator('#consent').check()
                    page.get_by_role('button',name='保存曲谱',exact=True).click()
                    expect(page.locator('#library button')).to_have_count(1)
                    page.locator('#start').click()
                    expect(page.locator('#pause')).to_be_enabled()
                    page.locator('#pause').click()
                    expect(page.locator('#run-state')).to_have_text('paused',timeout=15000)
                    page.locator('#resume').click()
                    expect(page.locator('#run-state')).to_have_text('completed',timeout=20000)
                    expect(page.locator('.decision.keep')).to_have_count(2)
                    expect(page.locator('.decision.crash')).to_have_count(1)
                    expect(page.locator('.decision.discard')).to_have_count(1)
                    history_id = page.locator('#runs').input_value()
                    screenshot_dir = os.environ.get('PHIL_SCREENSHOTS')
                    if screenshot_dir:
                        Path(screenshot_dir).mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(Path(screenshot_dir)/'workbench-desktop.png'),full_page=True)
                    # Changing source invalidates a previously accepted plan.
                    page.locator('#task').fill('A revised task')
                    expect(page.locator('#start')).to_be_disabled()
                    expect(page.locator('#consent')).not_to_be_checked()
                    page.reload()
                    expect(page.locator('#runs')).to_have_value(history_id)
                    expect(page.locator('#run-state')).to_have_text('completed')
                    page.set_viewport_size({'width':390,'height':844})
                    if screenshot_dir:
                        page.screenshot(path=str(Path(screenshot_dir)/'workbench-mobile.png'),full_page=True)
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                    self.assertEqual(errors,[])
                    browser.close()
            finally:
                server.shutdown();server.server_close();thread.join()
                for proc in app.processes.values():
                    proc.wait(timeout=5)
                app.lease.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
