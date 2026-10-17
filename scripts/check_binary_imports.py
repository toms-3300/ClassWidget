"""调试发行包内 DLL 导入/导出是否匹配，不修改文件。"""
from pathlib import Path
import sys
import pefile

root = Path(sys.argv[1])
files = list(root.rglob('*.dll'))+list(root.rglob('*.pyd'))
lookup = {p.name.lower():p for p in files}
exports = {}
for path in files:
    pe = pefile.PE(str(path),fast_load=True,max_symbol_exports=65536)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT'],pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    for entry in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]):
        target = lookup.get(entry.dll.decode().lower())
        if target is None:
            continue
        if target not in exports:
            target_pe = pefile.PE(str(target),fast_load=True,max_symbol_exports=65536)
            target_pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
            exports[target] = {symbol.name for symbol in getattr(target_pe,'DIRECTORY_ENTRY_EXPORT',type('Empty',(),{'symbols':[]})()).symbols}
        missing = [item.name.decode(errors='replace') for item in entry.imports if item.name and item.name not in exports[target]]
        if missing:
            print(path.name,'requires missing exports from',target.name,missing[:12])
print('Binary import scan complete.')
