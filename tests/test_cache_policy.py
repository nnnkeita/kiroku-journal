import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CachePolicyTest(unittest.TestCase):
    def test_service_worker_never_serves_api_from_cache_storage(self):
        source = (ROOT / 'static' / 'sw.js').read_text(encoding='utf-8')

        self.assertIn("const CACHE_NAME = 'kiroku-journal-v4'", source)
        self.assertIn("url.pathname.startsWith('/api/')", source)
        self.assertIn("event.respondWith(fetch(request))", source)

    def test_page_reads_bypass_the_http_cache(self):
        source = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')

        self.assertIn("navigator.serviceWorker.register('/static/sw.js?v=4')", source)
        self.assertIn("fetch(`/api/pages/${id}`, { cache: 'no-store' })", source)
        self.assertIn("fetch(`/api/pages/${currentPageId}`, { cache: 'no-store' })", source)

    def test_api_and_service_worker_responses_are_not_cacheable(self):
        source = (ROOT / 'app' / 'flask_app.py').read_text(encoding='utf-8')

        self.assertIn("request.path == '/static/sw.js'", source)
        self.assertIn("request.path.startswith('/api/')", source)
        self.assertIn("response.cache_control.no_store = True", source)


if __name__ == '__main__':
    unittest.main()
