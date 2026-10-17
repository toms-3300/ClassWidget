"""只打包已通过自检的发行物，不包含用户数据库、日志或虚拟环境。"""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
bundle = root/'dist'/'ClassWidget'
report = json.loads((root/'.artifacts'/'packaged-window-check.json').read_text(encoding='utf-8'))
if not report.get('passed') or not report.get('tool_window') or not report.get('no_desktop_parent'):
    raise SystemExit('Formal EXE has not passed diagnostics.')
release = root/'release'
release.mkdir(exist_ok=True)
portable = release/'ClassWidget-Windows-x64.zip'
with zipfile.ZipFile(portable,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for file in sorted(bundle.rglob('*')):
        if file.is_file():
            archive.write(file,Path('ClassWidget')/file.relative_to(bundle))
source = release/'ClassWidget-source.zip'
with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for folder in ('app','assets','scripts','tests'):
        for file in sorted((root/folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                archive.write(file,Path('ClassWidget-source')/file.relative_to(root))
    for name in ('main.py','ClassWidget.spec','requirements.txt','requirements-build.txt','requirements-lock.txt','README.md','使用说明.md','THIRD_PARTY_NOTICES.md','测试记录.md','启动课程表.cmd','安装依赖.cmd'):
        archive.write(root/name,Path('ClassWidget-source')/name)
hashes = []
for file in (portable,source):
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    hashes.append(digest+'  '+file.name)
    print(file.name,round(file.stat().st_size/1024/1024,2),'MB',digest)
(release/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
