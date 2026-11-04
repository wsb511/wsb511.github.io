"""Publish validated snapshots; never replace a feed with an error response."""
from pathlib import Path
from datetime import timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://script.google.com/macros/s/AKfycbxaLGEbhl2dvFJFN8lCBlA2my7WmgxtbRUcQdfYpMVOHfLqNOvHEeskgC4wkJqgZb-0Hg/exec'
PUBLIC = 'https://raw.githubusercontent.com/wsb511/wsb511.github.io/main/rss/'
ATOM = 'http://www.w3.org/2005/Atom'
ET.register_namespace('atom', ATOM)

def feed_date(root):
    value = root.findtext('./channel/lastBuildDate')
    if not value:
        raise ValueError('Missing lastBuildDate')
    date = parsedate_to_datetime(value)
    if date.tzinfo is None:
        raise ValueError('lastBuildDate must include timezone')
    return date.astimezone(timezone.utc)

def response_diagnostic(data, content_type):
    # Never log full Google error pages: they may contain account/session URLs.
    kind = 'html-error-page' if b'<html' in data[:1024].lower() or b'<!doctype html' in data[:1024].lower() else 'non-rss-response'
    return {'kind': kind, 'content_type': content_type, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}

def normalize(data, source):
    root = ET.fromstring(data)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('Not RSS')
    items = channel.findall('item')
    domain = {'cnbc': 'www.cnbc.com', 'barrons': 'www.barrons.com', 'electrek': 'electrek.co', 'eletricvehicles': 'eletric-vehicles.com'}[source]
    if not items or any(not ((i.findtext('link') or '').startswith('https://' + domain + '/')) for i in items):
        raise ValueError('Missing items or wrong source')
    feed_date(root)
    urls = set()
    for item in items:
        link = item.findtext('link')
        if link in urls or not (item.findtext('title') or '').strip() or item.findtext('guid') != link:
            raise ValueError('Duplicate URL, empty title or inconsistent GUID')
        urls.add(link)
        date = parsedate_to_datetime(item.findtext('pubDate') or '')
        if date.tzinfo is None:
            raise ValueError('pubDate must include timezone')
    for old in channel.findall('{' + ATOM + '}link'):
        channel.remove(old)
    ET.SubElement(channel, '{' + ATOM + '}link', {'href': PUBLIC + source + '.xml', 'rel': 'self', 'type': 'application/rss+xml'})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'

def main():
    failed = []
    for source in ('cnbc', 'barrons', 'electrek', 'eletricvehicles'):
        for attempt in range(3):
            data, content_type = b'', 'unknown'
            try:
                with urllib.request.urlopen(BASE + '?source=' + source, timeout=60) as r:
                    content_type = r.headers.get('Content-Type', 'unknown')
                    data = r.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError('Unexpected response size')
                output = normalize(data, source)
                path = Path(__file__).parent / (source + '.xml')
                if path.exists():
                    # An older cached response must never roll a feed backwards.
                    previous = ET.fromstring(path.read_bytes())
                    if feed_date(ET.fromstring(output)) < feed_date(previous):
                        raise ValueError('Stale upstream snapshot; newer public feed retained')
                if not path.exists() or path.read_bytes() != output:
                    temp = path.with_suffix('.tmp')
                    temp.write_bytes(output)
                    temp.replace(path)
                upstream_date = ET.fromstring(output).findtext('./channel/lastBuildDate') or 'missing'
                print(source + ': valid RSS snapshot; upstream lastBuildDate=' + upstream_date)
                break
            except Exception as error:
                print(source, 'attempt', attempt + 1, str(error))
                if data:
                    diagnostic = response_diagnostic(data, content_type)
                    if isinstance(error, ET.ParseError):
                        diagnostic['parse_position'] = error.position
                        if diagnostic['kind'] != 'html-error-page':
                            lines = data.decode('utf-8', errors='replace').splitlines()
                            line, column = error.position
                            if line <= len(lines) and column < len(lines[line - 1]):
                                diagnostic['codepoint'] = 'U+%04X' % ord(lines[line - 1][column])
                    print(source, 'response diagnostic', json.dumps(diagnostic, sort_keys=True))
                if attempt == 2:
                    failed.append(source)
                else:
                    # The web app shares a lock with collectors (up to 60s).
                    # Space attempts out instead of repeating the same transient page.
                    time.sleep((10, 30)[attempt])
    status_path = os.environ.get('RSS_SYNC_STATUS_FILE')
    if status_path:
        Path(status_path).write_text(json.dumps({'failed': failed}), encoding='utf-8')
    if failed:
        raise SystemExit('Old snapshots retained for: ' + ', '.join(failed))

if __name__ == '__main__':
    main()

