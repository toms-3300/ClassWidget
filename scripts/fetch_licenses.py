"""一次性获取上游许可原文；构建本身使用本地缓存。"""
from pathlib import Path
from urllib.request import urlopen

folder = Path(__file__).resolve().parents[1]/'assets'/'licenses'
folder.mkdir(parents=True,exist_ok=True)
sources = {
    'LGPL-3.0-only.txt':'https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/LGPL-3.0-only.txt',
    'GPL-3.0-only.txt':'https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/GPL-3.0-only.txt',
    'PyWinRT-MIT.txt':'https://raw.githubusercontent.com/pywinrt/pywinrt/main/LICENSE',
}
for name,url in sources.items():
    with urlopen(url,timeout=30) as response:
        (folder/name).write_bytes(response.read())
print('Upstream license texts cached.')
