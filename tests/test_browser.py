"""Optional real-Chromium regression, with a temporary DB and no external requests."""
import os, socket, threading, time
from pathlib import Path
import test_stabilization as fixture
from fastapi.staticfiles import StaticFiles
import uvicorn
from playwright.sync_api import sync_playwright

b=fixture.backend
ROOT=Path(__file__).resolve().parents[1]
with b.SessionLocal() as db:
    db.add(b.Equipment(tag='BROWSER-LEGACY',name='Browser regression',photo='test-only'))
    db.commit()
b.app.mount('/ui',StaticFiles(directory=str(ROOT),html=True),name='test-ui')
sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}'
server=uvicorn.Server(uvicorn.Config(b.app,log_level='critical',access_log=False))
thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
thread.start()
try:
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    with sync_playwright() as p:
        executable=os.environ.get('TAGCHECK_BROWSER_EXECUTABLE')
        if not executable:
            candidates=[r'C:\Program Files\Google\Chrome\Application\chrome.exe',r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe']
            executable=next((f for f in candidates if Path(f).exists()),None)
        browser=p.chromium.launch(headless=True,executable_path=executable)
        context=browser.new_context()
        requests=[];errors=[]
        def route(request_route):
            url=request_route.request.url
            if not url.startswith(base):
                request_route.abort();return
            for app,key in [('admin','TAGCHECK_ADMIN_CONFIG'),('viewer','TAGCHECK_VIEWER_CONFIG')]:
                if url.endswith(f'/{app}/config.js'):
                    source=(ROOT/app/'config.js').read_text(encoding='utf-8')
                    # Modify test delivery only; production files stay untouched.
                    import re
                    source=re.sub(r"API_BASE_URL:\s*'[^']*'",f"API_BASE_URL: '{base}'",source)
                    request_route.fulfill(status=200,content_type='application/javascript',body=source);return
            request_route.continue_()
        context.route('**/*',route)
        context.on('request',lambda request:requests.append(request))
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/ui/admin/index.html')
        page.locator('#loginUserInput').fill(fixture.ENV['ADMIN_USERNAME'])
        page.locator('#loginPassInput').fill(fixture.ENV['ADMIN_PASSWORD'])
        page.locator('#loginButton').click()
        page.locator('#pdfButton').wait_for(state='visible')
        assert page.locator('body').inner_text().find('BROWSER-LEGACY')>=0
        with context.expect_page() as popup:
            page.locator('#pdfButton').click()
        pdf_tab=popup.value
        for _ in range(100):
            if any(r.url==base+'/equipment/pdf' and r.method=='POST' for r in requests):break
            page.wait_for_timeout(50)
        sent=[r for r in requests if r.url==base+'/equipment/pdf' and r.method=='POST']
        assert sent,'PDF form did not navigate the new tab'
        assert 'pdf_token=' in sent[-1].post_data
        assert fixture.ENV['ADMIN_TOKEN'] not in sent[-1].post_data
        assert len(context.pages)==2,'PDF opened an extra tab rather than reusing the original popup'
        assert not any('token=' in r.url for r in requests)
        assert not errors,errors
        viewer=context.new_page()
        viewer.goto(base+'/ui/viewer/index.html?tag=BROWSER-LEGACY')
        viewer.wait_for_function("document.body.innerText.includes('BROWSER-LEGACY')")
        assert any('/equipment/tag/BROWSER-LEGACY' in r.url and 'authorization' not in r.headers for r in requests)
        print('Browser: legacy admin login/list, PDF POST in exactly one new tab and anonymous viewer passed.')
        context.close();browser.close()
finally:
    server.should_exit=True;thread.join(timeout=10);sock.close()
    b.engine.dispose();fixture.TMP.cleanup()
