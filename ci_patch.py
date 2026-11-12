#!/usr/bin/env python3
"""Patch the kernel tree before building an elish (sm8250, 4.19) MIUI kernel.

What it does, in order:

  1. build.sh : '-d KSU_SUSFS_SUS_PATH'   -> '-e KSU_SUSFS_SUS_PATH'
  2. build.sh : '-d KSU_SUSFS_SUS_SU'     -> '-e ...'   (only if SUS_SU_FLAG)
  3. build.sh : comment out the whole AOSP build block (MIUI image only)
  4. build.sh : disable the '-perf' -> '-<date>-<sha>-perf' localversion sed
  5. defconfig: pin CONFIG_LOCALVERSION so /proc/version matches the stock ROM
  6. Makefile : SUBLEVEL 325 -> 157
  7. scripts/setlocalversion: emit nothing (drops the git suffix and the
     dirty-tree '+' marker that would otherwise trail the release string)

Goal: uname -r and /proc/version both read
    4.19.157-perf-gf8cf95f4dc15
which is exactly what the stock Android 13 elish kernel reports, so the
'uname vs /proc/version mismatch' tell disappears.

Every step fails loudly: a silent no-op can never ship a kernel again.
"""
import os
import re
import sys

STOCK_LOCAL_VERSION = '-perf-gf8cf95f4dc15'
STOCK_SUBLEVEL = '157'


def die(msg):
    sys.exit('FATAL: ' + msg)


DEV = os.environ.get('DEV', 'elish').strip() or 'elish'
report = []

# ---------------------------------------------------------------- build.sh --
p = 'build.sh'
if not os.path.exists(p):
    die('build.sh not found')
s = open(p, encoding='utf-8').read()

n0 = s.count('-d KSU_SUSFS_SUS_PATH')
s = s.replace('-d KSU_SUSFS_SUS_PATH', '-e KSU_SUSFS_SUS_PATH')
report.append('SUS_PATH -d -> -e : %d occurrence(s)' % n0)
if n0 < 1:
    die('pattern "-d KSU_SUSFS_SUS_PATH" not found in build.sh')

if os.environ.get('SUS_SU_FLAG', '').strip().lower() in ('1', 'true', 'yes'):
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
    die('AOSP block markers not found (commented %d lines)' % nskip)
report.append('AOSP block commented: %d lines' % nskip)
s = '\n'.join(out)

# 4) kill the date/hash localversion rewrite
SED_OLD = 'sed -i "s/${local_version_str}/${local_version_date_str}/g"'
if SED_OLD not in s:
    die('localversion sed line not found in build.sh')
s = s.replace(SED_OLD, '# [ci_patch] disabled -> ' + SED_OLD)
report.append('date/hash localversion sed disabled')

open(p, 'w', encoding='utf-8', newline='\n').write(s)

# re-verify SUS_PATH is still live after all edits
live = [l.strip() for l in s.split('\n')
        if 'KSU_SUSFS_SUS_PATH' in l and not l.strip().startswith('#')]
if not live:
    die('no live SUS_PATH config line after patching')
report.append('live SUS_PATH lines: %d' % len(live))
for l in live:
    report.append('   ' + l)

# --------------------------------------------------------------- defconfig --
dc = 'arch/arm64/configs/%s_defconfig' % DEV
if not os.path.exists(dc):
    die('defconfig not found: ' + dc)
d = open(dc, encoding='utf-8').read()
d2, n = re.subn(r'^CONFIG_LOCALVERSION=.*$',
                'CONFIG_LOCALVERSION="%s"' % STOCK_LOCAL_VERSION,
                d, flags=re.M)
if n != 1:
    die('CONFIG_LOCALVERSION occurrences in %s: %d' % (dc, n))
open(dc, 'w', encoding='utf-8', newline='\n').write(d2)
report.append('%s CONFIG_LOCALVERSION="%s"' % (dc, STOCK_LOCAL_VERSION))

# ---------------------------------------------------------------- Makefile --
mk = open('Makefile', encoding='utf-8').read()
mk2, n = re.subn(r'^SUBLEVEL = \d+$', 'SUBLEVEL = ' + STOCK_SUBLEVEL, mk, flags=re.M)
if n != 1:
    die('SUBLEVEL occurrences in Makefile: %d' % n)
open('Makefile', 'w', encoding='utf-8', newline='\n').write(mk2)
report.append('Makefile SUBLEVEL = %s' % STOCK_SUBLEVEL)

# -------------------------------------------------------- setlocalversion ---
slv = 'scripts/setlocalversion'
if not os.path.exists(slv):
    die('scripts/setlocalversion not found')
open(slv, 'w', encoding='utf-8', newline='\n').write(
    '#!/bin/sh\n'
    '# [ci_patch] suppress git suffix and the dirty-tree "+" marker\n'
    'exit 0\n')
os.chmod(slv, 0o755)
report.append('scripts/setlocalversion -> exit 0')

print('\n'.join(report))
print('target release string: 4.19.%s%s' % (STOCK_SUBLEVEL, STOCK_LOCAL_VERSION))
print('PATCH OK')
