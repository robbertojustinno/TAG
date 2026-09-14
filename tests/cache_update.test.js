const fs = require('fs'), vm = require('vm'), assert = require('assert');

(async () => {
  for (const app of ['admin', 'viewer']) {
    const handlers = {}, deleted = [], calls = [], writes = [];
    let offline = false, response, claimed = false;
    const cache = {
      match: async (key) => key === './index.html' ? { offline: true } : undefined,
      put: async (...args) => writes.push(args), addAll: async () => {}
    };
    const context = { URL, Request, Response, Headers,
      self: { location: { origin: 'https://test.invalid' },
        addEventListener: (name, fn) => handlers[name] = fn,
        clients: { claim: async () => { claimed = true; } } },
      caches: { keys: async () => [`tagcheck-${app}-old`, 'unrelated-cache'],
        delete: async (key) => deleted.push(key), open: async () => cache },
      fetch: async (request, options) => {
        calls.push(options);
        if (offline) throw new Error('offline');
        return new Response('new release');
      }
    };
    vm.runInNewContext(fs.readFileSync(`${app}/sw.js`, 'utf8'), context);
    let activation;
    handlers.activate({ waitUntil: (p) => activation = p });
    await activation;
    assert.deepEqual(deleted, [`tagcheck-${app}-old`]);
    assert(claimed);
    const pending = [];
    const request = { method: 'GET', mode: 'navigate',
      url: 'https://test.invalid/?tag=QR-123', headers: new Headers() };
    const event = { request, respondWith: (p) => response = p, waitUntil: (p) => pending.push(p) };
    handlers.fetch(event);
    assert.equal(await (await response).text(), 'new release');
    assert.equal(calls.at(-1).cache, 'no-store');
    await Promise.all(pending);
    if (app === 'viewer') {
      assert.equal(writes.length, 1);
      offline = true;
      handlers.fetch(event);
      assert.deepEqual(await response, { offline: true });
      request.mode = 'cors'; request.url = 'https://test.invalid/missing.js';
      handlers.fetch(event);
      assert.equal((await response).type, 'error');
    }
  }
  console.log('Cache activation, isolation, fresh HTML and offline QR navigation passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
