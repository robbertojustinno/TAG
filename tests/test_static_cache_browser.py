"""Static-only browser checks; no backend or deployment is required."""
import functools
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    release = 'one'

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith('/admin/release.'):
            is_js = self.path.startswith('/admin/release.js')
            content = (f'window.release = "{self.release}";' if is_js else
                       f'<p>{self.release}</p><script src="release.js"></script>')
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript' if is_js else 'text/html')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(content.encode())
            return
        super().do_GET()


class StaticCacheBrowserTests(unittest.TestCase):
    def test_windows_browsers(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                for channel in ['msedge', 'chrome']:
                    with self.subTest(channel=channel):
                        browser = p.chromium.launch(channel=channel)
                        try:
                            context = browser.new_context()
                            page = context.new_page()
                            page.goto(base + '/admin/index.html', wait_until='load')
                            page.evaluate('navigator.serviceWorker.ready')
                            page.wait_for_function('navigator.serviceWorker.controller !== null')
                            # Exercise the shared rule with every Admin select label.
                            page.evaluate('''() => {
                              document.body.innerHTML = ['Perfil','Usuário','Empresa','Papel','Unidade']
                                .map(label => `<label>${label}<select class="input"><option>Supervisor</option>
                                  <option>Operador</option><option>Somente leitura</option></select></label>`).join('');
                            }''')
                            for select in page.locator('select').all():
                                select.click()
                                for option in select.locator('option').all():
                                    self.assertEqual(option.evaluate('(e) => getComputedStyle(e).color'), 'rgb(17, 24, 39)')
                                    self.assertEqual(option.evaluate('(e) => getComputedStyle(e).backgroundColor'), 'rgb(255, 255, 255)')
                                page.keyboard.press('Escape')
                                self.assertNotEqual(select.evaluate('(e) => getComputedStyle(e).color'), 'rgb(17, 24, 39)')
                            Handler.release = 'one'
                            page.goto(base + '/admin/release.html')
                            self.assertEqual(page.evaluate('window.release'), 'one')
                            Handler.release = 'two'
                            page.reload()
                            self.assertEqual(page.locator('p').inner_text(), 'two')
                            self.assertEqual(page.evaluate('window.release'), 'two')
                            page.goto(base + '/viewer/index.html')
                            page.evaluate('navigator.serviceWorker.ready')
                            page.wait_for_function('navigator.serviceWorker.controller !== null')
                            context.set_offline(True)
                            page.goto(base + '/viewer/?tag=QR-123')
                            self.assertEqual(page.title(), 'TagCheck Viewer V7')
                            self.assertTrue(page.evaluate("typeof searchByTag === 'function'"))
                            print(f'{channel}: select contrast, normal reload HTML/JS, Viewer offline QR shell passed')
                        finally:
                            browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
