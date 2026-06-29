import re, sys
from pathlib import Path

for fpath in sys.argv[1:]:
    f = Path(fpath)
    content = f.read_text()
    
    # Find function wrapper
    func_match = re.search(r'(export const meta = \{[^}]*\})\n\n(export default async function[^\n]*\n)\n', content, re.DOTALL)
    if not func_match:
        continue
    
    meta_block = func_match.group(1)
    func_decl = func_match.group(2)
    
    # Find imports after function declaration
    imports_match = re.search(r'(export default async function[^\n]*\n)\n([^\n]*\n)*(import [^\n]*\n)+', content, re.DOTALL)
    if not imports_match:
        continue
    
    # Extract all imports
    imports = re.findall(r'^import [^\n]*$', content[imports_match.start():], re.MULTILINE)
    if not imports:
        continue
    
    # Remove imports from after function
    for imp in imports:
        content = content.replace('\n' + imp, '', 1)
    
    # Add imports after meta block
    content = content.replace(
        meta_block + '\n\n' + func_decl,
        meta_block + '\n\n' + '\n'.join(imports) + '\n\n' + func_decl
    )
    
    # Ensure closing brace
    if not content.rstrip().endswith('}'):
        content = content.rstrip() + '\n\n}\n'
    
    f.write_text(content)
    print(f"✓ {f.name}")
