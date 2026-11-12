#!/usr/bin/env python3
"""Patch build.sh of liyafe1997/kernel_xiaomi_sm8250_mod:
   1) turn '-d KSU_SUSFS_SUS_PATH' into '-e ...' (author disabled it)
   2) optionally do the same for KSU_SUSFS_SUS_SU
   3) comment out the whole AOSP build block (we only need the MIUI image)
Fails loudly if the expected patterns are not found, so a silent no-op
can never produce a kernel without SUS_PATH again.
"""
import os
import sys

p = 'build.sh'
if not os.path.exists(p):
    sys.exit('build.sh not found in workspace root')

s = open(p, encoding='utf-8').read()
report = []

n0 = s.count('-d KSU_SUSFS_SUS_PATH')
s = s.replace('-d KSU_SUSFS_SUS_PATH', '-e KSU_SUSFS_SUS_PATH')
report.append('SUS_PATH -d -> -e : %d occurrence(s)' % n0)
if n0 < 1:
    sys.exit('FATAL: pattern "-d KSU_SUSFS_SUS_PATH" not found in build.sh')

sus_su = os.environ.get('SUS_SU_FLAG', '').strip().lower() in ('1', 'true', 'yes')
if sus_su:
    n1 = s.count('-d KSU_SUSFS_SUS_SU')
    s = s.replace('-d KSU_SUSFS_SUS_SU', '-e KSU_SUSFS_SUS_SU')
    report.append('SUS_SU  -d -> -e : %d occurrence(s)' % n1)

lines = s.split('\n')
out = []
skip = False
nskip = 0
for ln in lines:
    st = ln.strip()
    if st.startswith('echo') and 'Building for AOSP' in st:
        skip = True
    if skip:
        out.append('#' + ln)
        nskip += 1
        if 'End of Building for AOSP' in ln:
            skip = False
        continue
    out.append(ln)

if nskip < 20:
    sys.exit('FATAL: AOSP block markers not found (commented %d lines)' % nskip)

open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
report.append('AOSP block commented: %d lines' % nskip)

txt = open(p, encoding='utf-8').read()
live = [
    l.strip()
    for l in txt.split('\n')
    if 'KSU_SUSFS_SUS_PATH' in l and not l.strip().startswith('#')
]
report.append('live SUS_PATH lines: %d' % len(live))
for l in live:
    report.append('   ' + l)
if not live:
    sys.exit('FATAL: no live SUS_PATH config line after patching')

print('\n'.join(report))
print('PATCH OK')
