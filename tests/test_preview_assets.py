import base64
from ade.core.preview_assets import embed_brand_assets


def test_brand_assets_embedded_without_changing_script(tmp_path):
    brand = tmp_path / 'assets' / 'brand'
    brand.mkdir(parents=True)
    (brand / 'theme.css').write_text('body{color:red}')
    (brand / 'logo.png').write_bytes(b'png-test')
    page = '''<!DOCTYPE html><link rel="stylesheet" href="assets/brand/theme.css"><img src="assets/brand/logo.png"><script>if(a<2){a++}</script>'''
    result = embed_brand_assets(page, tmp_path)
    assert 'data:text/css;base64,' + base64.b64encode(b'body{color:red}').decode() in result
    assert 'data:image/png;base64,' in result
    assert '<script>if(a<2){a++}</script>' in result


def test_no_external_or_symlink_embedding(tmp_path):
    brand = tmp_path / 'assets' / 'brand'
    brand.mkdir(parents=True)
    (tmp_path / 'secret.css').write_text('secret')
    (brand / 'link.css').symlink_to(tmp_path / 'secret.css')
    page = '<link rel="stylesheet" href="assets/brand/link.css"><img src="https://example.org/a.png">'
    assert embed_brand_assets(page, tmp_path) == page
