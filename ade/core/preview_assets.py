"""Embed brand assets so sandboxed previews do not need session cookies."""
import base64
import re
from html.parser import HTMLParser
from pathlib import Path


MIMES = {'.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.webp': 'image/webp'}


def embed_brand_assets(document: str, src: Path) -> str:
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.output = []

        def handle_starttag(self, tag, attrs):
            raw = self.get_starttag_text()
            attribute = 'href' if tag == 'link' and dict(attrs).get('rel') == 'stylesheet' else 'src' if tag == 'img' else None
            if attribute:
                value = dict(attrs).get(attribute, '') or ''
                relative = Path(value)
                if value.startswith('assets/brand/') and '..' not in relative.parts:
                    path = src / relative
                    mime = MIMES.get(path.suffix.lower())
                    if (mime and path.is_file() and not any(p.is_symlink() for p in (path, *path.parents))
                            and path.resolve().is_relative_to(src.resolve()) and path.stat().st_size <= 30_000_000):
                        data = base64.b64encode(path.read_bytes()).decode('ascii')
                        replacement = f'{attribute}="data:{mime};base64,{data}"'
                        raw = re.sub(r'\b' + attribute + r'\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',
                                     lambda _: replacement, raw, count=1, flags=re.I)
            self.output.append(raw)

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)

        def handle_endtag(self, tag):
            self.output.append(f'</{tag}>')

        def handle_data(self, data):
            self.output.append(data)

        def handle_entityref(self, name):
            self.output.append(f'&{name};')

        def handle_charref(self, name):
            self.output.append(f'&#{name};')

        def handle_comment(self, data):
            self.output.append(f'<!--{data}-->')

        def handle_decl(self, decl):
            self.output.append(f'<!{decl}>')

    parser = Parser()
    parser.feed(document)
    parser.close()
    return ''.join(parser.output)
