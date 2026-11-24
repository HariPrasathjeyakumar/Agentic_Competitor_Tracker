import sys
from pathlib import Path

title, desc, date = sys.argv[1], sys.argv[2], sys.argv[3]
p = Path("mock_sites/templates/changelog.html")
html = p.read_text(encoding="utf-8")

entry = (f'<article class="entry"><p class="date">{date}</p>'
         f'<h3>{title}</h3><p>{desc}</p></article>\n')

i = html.find("<footer") if "<footer" in html else html.rfind("</body>")
p.write_text(html[:i] + entry + html[i:], encoding="utf-8")
print("Inserted:", title)
