"""Rebuild index.html from the page template and the packed mesh data.

    python3 src/make.py
"""
import pathlib
src = pathlib.Path(__file__).parent
page = (src / 'template.html').read_text()
assert '/*__DATA__*/' in page and '/*__BODY__*/' in page
page = page.replace('/*__DATA__*/', (src / 'mesh_data.js').read_text()).replace('/*__BODY__*/', (src / 'body_data.js').read_text())
(src.parent / 'index.html').write_text(page)
print('wrote index.html')
