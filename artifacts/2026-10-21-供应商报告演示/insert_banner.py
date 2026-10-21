# -*- coding: utf-8 -*-
"""在生成的报告 HTML 顶部插入醒目的「演示数据」横幅（DEMO banner）。"""
import io, os, sys

p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'html-preview', 'index.html')
s = io.open(p, encoding='utf-8').read()

BANNER = ('<div class="demo-banner" style="background:#B70235;color:#fff;text-align:center;'
          'padding:10px 16px;font-size:14px;font-weight:700;letter-spacing:.02em;'
          'position:relative;z-index:9999;">'
          '⚠ 演示数据（DEMO）— 本报告全部数字均为虚构，仅用于验证模板渲染链路，'
          '不代表任何真实供应商的经营情况</div>')

if 'demo-banner' in s:
    print('banner already present, skip')
    sys.exit(0)

i = s.find('<body')
if i < 0:
    print('!! <body not found')
    sys.exit(1)
i = s.find('>', i) + 1
s = s[:i] + '\n' + BANNER + s[i:]
io.open(p, 'w', encoding='utf-8').write(s)
print('banner inserted -> %s' % p)
