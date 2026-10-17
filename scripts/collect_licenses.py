"""复制本机发行包许可；网络许可原文在 assets/licenses 预先保存。"""
from importlib.metadata import distributions
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
output = root/'dist'/'ClassWidget'/'licenses'
output.mkdir(parents=True,exist_ok=True)
selected = ('pyside6','shiboken6','windows-toasts','pywin32','winrt','tzlocal','tzdata','typing_extensions')
for package in distributions():
    name = package.metadata['Name']
    if not name.lower().startswith(selected):
        continue
    folder = output/name
    folder.mkdir(exist_ok=True)
    (folder/'METADATA.txt').write_text(package.read_text('METADATA') or '',encoding='utf-8')
    for file in package.files or []:
        if 'license' in str(file).lower() or 'copying' in str(file).lower():
            source = Path(package.locate_file(file))
            if source.is_file():
                target = folder/str(file).replace('/', '_').replace('\\','_')
                shutil.copyfile(source,target)
python_license = Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():
    shutil.copyfile(python_license,output/'Python-LICENSE.txt')
for source in (root/'assets'/'licenses').glob('*.txt'):
    shutil.copyfile(source,output/source.name)
print('Third-party licenses collected:',output)
