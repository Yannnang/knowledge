# -*- coding: utf-8 -*-
"""生成演示用 data.json —— 全部数字为虚构（DEMO），仅用于验证 supplier-report 模板渲染链路。

复用 skill 的 window.py 计算真实窗口结构（2026 年度 YTD），series/total/dim 填假数据，
字段结构与 fetch_data.py 的产出完全一致，供 build_report.py 直接消费。
"""
import io, json, os, sys

SKILL_TOOLS = r"C:\Users\nydia.yang\.claude\skills\supplier-report-彭于晏版\tools"
sys.path.insert(0, SKILL_TOOLS)
import window as W  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

WIN = {"type": "annual", "year": 2026, "mode": "ytd"}
SECTIONS = ["exec", "year", "dest", "quality", "dispute", "adr", "supply", "qps", "finding"]
RATE = 7.1  # 虚构汇率 CNY/USD

W_ = W.resolve(WIN)
months = ['%04d-%02d' % p for p in W_['trend']]
months_prev = ['%04d-%02d' % p for p in W_['trend_prev']]
n = len(months)


def div(a, b, scale=1.0, nd=2):
    return [round(x / y * scale, nd) if (x is not None and y) else None
            for x, y in zip(a, b)]


def mom(a, nd=1):
    o = [None]
    for i in range(1, len(a)):
        o.append(round((a[i] - a[i - 1]) / a[i - 1] * 100, nd)
                 if (a[i] is not None and a[i - 1]) else None)
    return o


# ── 虚构月度序列（长度 = n，2026-01..2026-09；prev = 2025 同月）──
bks      = [4200, 3850, 4600, 5050, 5600, 6300, 7050, 6600, 5950]
bks_prev = [3600, 3300, 3900, 4300, 4700, 5200, 5800, 5500, 5000]
ttv      = [1386.0, 1232.0, 1518.0, 1717.0, 1960.0, 2268.0, 2608.5, 2376.0, 2082.5]   # 万元
ttv_prev = [1080.0, 957.0, 1170.0, 1333.0, 1504.0, 1716.0, 1972.0, 1815.0, 1600.0]
assert len(bks) == len(bks_prev) == len(ttv) == len(ttv_prev) == n

failRate      = [2.8, 3.1, 2.6, 2.4, 2.2, 2.0, 1.9, 2.1, 2.3]
failRate_prev = [3.5, 3.8, 3.3, 3.1, 2.9, 2.8, 2.6, 2.7, 3.0]
acc           = [96.2, 96.8, 97.1, 97.4, 97.0, 96.6, 97.2, 97.5, 97.8]

dis      = [42, 38, 45, 40, 36, 33, 30, 32, 35]
dis_prev = [55, 52, 58, 54, 50, 47, 44, 46, 49]
disRate      = div(dis, bks, 100)
disRate_prev = div(dis_prev, bks_prev, 100)

adr      = [680, 660, 700, 720, 750, 790, 830, 810, 760]
adr_prev = [610, 600, 630, 650, 670, 700, 730, 710, 680]
adr_usd      = [round(x / RATE, 2) for x in adr]
adr_usd_prev = [round(x / RATE, 2) for x in adr_prev]
los      = [1.8, 1.75, 1.85, 1.9, 2.0, 2.1, 2.2, 2.15, 2.0]
los_prev = [1.7, 1.7, 1.75, 1.8, 1.85, 1.9, 2.0, 1.95, 1.9]
lt       = [28.0, 30.0, 27.0, 25.0, 24.0, 22.0, 21.0, 23.0, 26.0]
lt_prev  = [32.0, 33.0, 31.0, 30.0, 29.0, 28.0, 26.0, 27.0, 29.0]

htl      = [620, 590, 650, 680, 720, 760, 810, 790, 750]
htl_prev = [520, 500, 540, 570, 600, 630, 670, 650, 620]
sup_all    = [18200, 18400, 18600, 18800, 19000, 19200, 19500, 19600, 19800]
sup_ok     = [12100, 12300, 12500, 12600, 12800, 13000, 13200, 13300, 13500]
sup_priced = [4300, 4400, 4600, 4700, 4900, 5100, 5300, 5400, 5600]

qps      = [420.0, 435.0, 448.0, 460.0, 472.0, 485.0, 498.0, 490.0, 476.0]
qps_prev = [350.0, 360.0, 372.0, 380.0, 390.0, 402.0, 415.0, 408.0, 396.0]
vol      = [1100.0, 1150.0, 1230.0, 1310.0, 1400.0, 1520.0, 1640.0, 1580.0, 1460.0]  # 万次/月

ttv_usd      = [round(x / RATE, 1) for x in ttv]
ttv_usd_prev = [round(x / RATE, 1) for x in ttv_prev]

# ── 汇总（与序列严格自洽）──
T = {}
T['ttv'] = round(sum(ttv) * 1e4)
T['ttv_prev'] = round(sum(ttv_prev) * 1e4)
T['ttv_usd'] = round(T['ttv'] / RATE)
T['ttv_usd_prev'] = round(T['ttv_prev'] / RATE)
T['bks'] = sum(bks)
T['bks_prev'] = sum(bks_prev)
T['aov'] = round(T['ttv'] / T['bks'])
T['aov_prev'] = round(T['ttv_prev'] / T['bks_prev'])
T['aov_usd'] = round(T['ttv_usd'] / T['bks'])
T['aov_usd_prev'] = round(T['ttv_usd_prev'] / T['bks_prev'])
T['htl'] = 1450          # 累计有产酒店（去重口径，虚构）
T['htl_prev'] = 1180
fail_n = [round(r / 100 * b) for r, b in zip(failRate, bks)]
fail_n_prev = [round(r / 100 * b) for r, b in zip(failRate_prev, bks_prev)]
T['fail'] = sum(fail_n)
T['failRate'] = round(sum(fail_n) / sum(bks) * 100, 2)
T['failRate_prev'] = round(sum(fail_n_prev) / sum(bks_prev) * 100, 2)
T['dis'] = sum(dis)
T['dis_prev'] = sum(dis_prev)
T['disRate'] = round(T['dis'] / T['bks'] * 100, 2)
T['disRate_prev'] = round(T['dis_prev'] / T['bks_prev'] * 100, 2)
T['adr'] = round(sum(adr) / len(adr))
T['adr_prev'] = round(sum(adr_prev) / len(adr_prev))
T['adr_usd'] = round(sum(adr_usd) / len(adr_usd), 2)
T['adr_usd_prev'] = round(sum(adr_usd_prev) / len(adr_usd_prev), 2)
T['qps'] = round(sum(qps) / len(qps), 1)
T['qps_min'] = min(qps)
T['qps_max'] = max(qps)
T['vol'] = sum(vol)
T['all'] = sup_all[-1]
T['ok'] = sup_ok[-1]
T['priced'] = sup_priced[-1]
T['htl_latest'] = htl[-1]

# ── 维度（虚构目的地/区域，Top10 与总量数量级自洽）──
dest = [
    ["泰国", 3250.0, 2380.0, 9400],
    ["日本", 2860.0, 2350.0, 7600],
    ["马来西亚", 1980.0, 1420.0, 5900],
    ["新加坡", 1520.0, 1180.0, 4100],
    ["印度尼西亚", 1310.0, 940.0, 3900],
    ["韩国", 1180.0, 1020.0, 3300],
    ["越南", 980.0, 690.0, 3100],
    ["阿联酋", 760.0, 520.0, 1800],
    ["沙特阿拉伯", 640.0, 0, 1300],
    ["土耳其", 510.0, 380.0, 1400],
]
reg = [
    ["东南亚", 9040.0, 6610.0],
    ["东北亚", 4040.0, 3370.0],
    ["中东", 1910.0, 900.0],
    ["其他", 2158.0, 2267.0],
]

D = {
    "meta": {
        "supplier_id": "999999",
        "supplier_name": "演示供应商（DEMO·虚构数据）",
        "window": WIN,
        "label": W_['label'],
        "months": months,
        "focus": ['%04d-%02d' % p for p in W_['focus']],
        "sections": SECTIONS,
        "main": ['%04d-%02d' % W_['main'][0], '%04d-%02d' % W_['main'][1]],
        "prev": ['%04d-%02d' % W_['main_prev'][0], '%04d-%02d' % W_['main_prev'][1]],
        "last": None,
        "currency": "CNY",
        "lang": "zh",
    },
    "series": {
        "ttv": ttv, "ttv_prev": ttv_prev,
        "ttv_usd": ttv_usd, "ttv_usd_prev": ttv_usd_prev,
        "bks": bks, "bks_prev": bks_prev,
        "failRate": failRate, "failRate_prev": failRate_prev, "acc": acc,
        "dis": dis, "dis_prev": dis_prev, "disRate": disRate, "disRate_prev": disRate_prev,
        "adr": adr, "adr_prev": adr_prev, "adr_usd": adr_usd, "adr_usd_prev": adr_usd_prev,
        "los": los, "los_prev": los_prev, "lt": lt, "lt_prev": lt_prev,
        "htl": htl, "htl_prev": htl_prev,
        "all": sup_all, "ok": sup_ok, "priced": sup_priced,
        "qps": qps, "qps_prev": qps_prev, "vol": vol,
        "qpsMom": mom(qps), "volMom": mom(vol),
    },
    "total": T,
    "dim": {"dest": dest, "reg": reg},
    "flags": {"acc_empty": False, "sup_missing": [], "qps_prev_empty": False},
    "acct": None,
}

out = os.path.join(HERE, 'data.json')
io.open(out, 'w', encoding='utf-8').write(json.dumps(D, ensure_ascii=False, indent=1))
print('written %s' % out)
print('窗口: %s · months=%s..%s (%d) · label=%s' % (WIN, months[0], months[-1], n, W_['label']))
print('TTV: %s vs prev %s (虚构)' % (T['ttv'], T['ttv_prev']))
