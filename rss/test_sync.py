import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
import sync


def snapshot(source='cnbc', date='Wed, 04 Nov 2026 00:30:00 GMT'):
    domain = {'cnbc': 'www.cnbc.com', 'barrons': 'www.barrons.com',
              'electrek': 'electrek.co', 'eletricvehicles': 'eletric-vehicles.com'}[source]
    url = 'https://' + domain + '/article'
    return (f'<rss><channel><lastBuildDate>{date}</lastBuildDate><item>'
            f'<title>中文 A &amp; B 🚀</title><link>{url}</link><guid>{url}</guid>'
            '<pubDate>Wed, 04 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>').encode()


class Response:
    headers = {'Content-Type': 'application/rss+xml; charset=utf-8'}
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return self.data[:size]


class PublisherTests(unittest.TestCase):
    def test_valid_unicode_and_canonical_self_link(self):
        for source in ('cnbc', 'barrons', 'electrek', 'eletricvehicles'):
            root = ET.fromstring(sync.normalize(snapshot(source), source))
            self.assertEqual(root.findtext('./channel/item/title'), '中文 A & B 🚀')
            self.assertEqual(root.find('./channel/{%s}link' % sync.ATOM).get('href'), sync.PUBLIC + source + '.xml')

    def test_reject_corrupt_and_semantically_invalid_feeds(self):
        data = snapshot()
        for bad in (b'<html><body>Error & retry</body></html>', data.replace(b'A &amp;', b'A &'),
                    data.replace(b'<title>', b'<title>\x01'),
                    data.replace(b'www.cnbc.com', b'evil.example'),
                    data.replace(b'<guid>', b'<guid>other'),
                    data.replace(b'Wed, 04 Nov 2026 00:30:00 GMT', b'bad date'),
                    data.replace(b'</item>', b'</item>' + data.split(b'<item>')[1].split(b'</channel>')[0]).replace(b'</item><title>', b'</item><item><title>')):
            with self.subTest(bad=bad[:80]), self.assertRaises((ValueError, ET.ParseError)):
                sync.normalize(bad, 'cnbc')

    def test_html_diagnostic_does_not_include_page_contents(self):
        diagnostic = sync.response_diagnostic(b'<!DOCTYPE html><html>private account token</html>', 'text/html')
        self.assertEqual(diagnostic['kind'], 'html-error-page')
        self.assertNotIn('private', str(diagnostic))

    def run_main(self, directory, responder):
        with patch.object(sync, '__file__', str(Path(directory) / 'sync.py')), \
             patch.object(sync.urllib.request, 'urlopen', side_effect=responder), \
             patch.object(sync.time, 'sleep'), \
             patch.dict(sync.os.environ, {'RSS_SYNC_STATUS_FILE': str(Path(directory) / 'status.json')}):
            sync.main()

    def test_transient_html_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def responder(url, timeout):
                source = url.split('=')[-1]; calls.append(source)
                return Response(b'<html>Error & retry</html>' if len(calls) == 1 else snapshot(source))
            self.run_main(directory, responder)
            self.assertEqual(calls.count('cnbc'), 2)
            self.assertTrue((Path(directory) / 'cnbc.xml').exists())

    def test_permanent_failure_keeps_old_feed_and_publishes_healthy_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cnbc.xml'; path.write_bytes(snapshot())
            def responder(url, timeout):
                source = url.split('=')[-1]
                return Response(b'<html>Error & retry</html>' if source == 'cnbc' else snapshot(source))
            with self.assertRaises(SystemExit): self.run_main(directory, responder)
            self.assertEqual(path.read_bytes(), snapshot())
            self.assertTrue((Path(directory) / 'barrons.xml').exists())

    def test_stale_response_never_overwrites_newer_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cnbc.xml'; path.write_bytes(snapshot())
            def responder(url, timeout):
                source = url.split('=')[-1]
                return Response(snapshot(source, 'Tue, 03 Nov 2026 00:30:00 GMT'))
            with self.assertRaises(SystemExit): self.run_main(directory, responder)
            self.assertEqual(path.read_bytes(), snapshot())


if __name__ == '__main__': unittest.main()
