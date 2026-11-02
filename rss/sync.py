"""Publish validated snapshots; never replace a feed with an error response."""
from pathlib import Path
import time
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://script.google.com/macros/s/AKfycbxaLGEbhl2dvFJFN8lCBlA2my7WmgxtbRUcQdfYpMVOHfLqNOvHEeskgC4wkJqgZb-0Hg/exec'
PUBLIC = 'https://wsb511.github.io/rss/'
ATOM = 'http://www.w3.org/2005/Atom'
ET.register_namespace('atom', ATOM)

def normalize(data, source):
    root = ET.fromstring(data)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('Not RSS')
    items = channel.findall('item')
    domain = {'cnbc': 'www.cnbc.com', 'barrons': 'www.barrons.com', 'electrek': 'electrek.co', 'eletricvehicles': 'eletric-vehicles.com', 'fttechnology': 'www.ft.com'}[source]
    if not items or any(not (i.findtext('link') or '').startswith('https://' + domain + '/') for i in items):
        raise ValueError('Missing items or wrong source')
    for old in channel.findall('{' + ATOM + '}link'):
        channel.remove(old)
    ET.SubElement(channel, '{' + ATOM + '}link', {'href': PUBLIC + source + '.xml', 'rel': 'self', 'type': 'application/rss+xml'})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'

def main():
    failed = []
    for source in ('cnbc', 'barrons', 'electrek', 'eletricvehicles', 'fttechnology'):
        for attempt in range(3):
            try:
                with urllib.request.urlopen(BASE + '?source=' + source, timeout=60) as r:
                    data = r.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError('Unexpected response size')
                output = normalize(data, source)
                path = Path(__file__).parent / (source + '.xml')
                if not path.exists() or path.read_bytes() != output:
                    temp = path.with_suffix('.tmp')
                    temp.write_bytes(output)
                    temp.replace(path)
                print(source + ': valid RSS snapshot')
                break
            except Exception as error:
                print(source, 'attempt', attempt + 1, str(error))
                if attempt == 2:
                    failed.append(source)
                else:
                    time.sleep(3)
    if failed:
        raise SystemExit('Old snapshots retained for: ' + ', '.join(failed))

if __name__ == '__main__':
    main()
