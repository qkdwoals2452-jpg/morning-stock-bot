"""Require the headline itself to report the action being alerted.

Summaries can contain historical deals, biographies and unrelated earnings.
They must not turn a lifestyle/explainer headline into a breaking event.
"""
import html
import re

ACTION = {
    'CAPEX': r'\b(?:invest(?:s|ed)?|to invest|announces? investment|commits? .{0,40}(?:billion|million)|builds?|to build|opens? .{0,30}(?:plant|factory)|expands? .{0,30}(?:plant|factory|capacity))\b|(?:투자|증설|공장.{0,8}(?:신설|건설)).{0,10}(?:결정|확정|착수|발표)|\d[\d,.]*\s*(?:조|억|만).{0,15}(?:투자|증설)',
    'CONTRACT': r'\b(?:signs?|signed|wins?|won|awarded|secures?)\b.{0,70}\b(?:contract|agreement|order|deal)\b|\b(?:supply contract|supply agreement)\b|공급\s*계약|계약\s*체결|수주|.{1,40}(?:에|와|과)\s*.{0,30}공급',
    'M&A': r'\b(?:acquires?|acquired|agrees? to (?:buy|acquire)|completes? .{0,30}(?:acquisition|merger))\b|인수\s*(?:완료|확정|계약)|합병\s*(?:승인|완료)',
    'EARNINGS': r'\b(?:revenue|profit|earnings|income|sales)\b|매출|영업이익|순이익|흑자전환|적자전환',
    'PRODUCTION': r'\b(?:starts?|begins?|commences?)\b.{0,40}\b(?:production|manufacturing|operations)\b|양산\s*(?:시작|개시|착수)|생산\s*(?:시작|개시)|가동\s*(?:시작|개시)',
    'POLICY': r'\b(?:approves?|enacts?|imposes?|announces?|bans?|lifts?)\b.{0,70}\b(?:tariff|ban|rule|policy|sanction|subsid|export)\w*|(?:관세|정책|수출규제|수출\s*규제|보조금).{0,25}(?:발표|확정|승인|시행|인상|인하|철회)',
    'FOMC': r'\b(?:fed|fomc|federal reserve)\b.{0,60}\b(?:raises?|cuts?|holds?|keeps?|leaves?)\b.{0,30}\brates?\b|(?:연준|fomc).{0,30}금리.{0,15}(?:인상|인하|동결)',
}


def headline_action(event):
    title = re.sub(r'\s+', ' ', html.unescape(event.get('event_title', '')).casefold()).strip()
    kind = event.get('event_type')
    if re.search(r'투자의견|목표주가|\bprice target\b', title):
        return False
    if re.search(r'^(?:how|why|what|does|do|is|are|can|could|should)\b|\?|무엇|뜻은|일까', title):
        return False
    if re.search(r'\b(?:stocktwits|stocks? (?:plunges?|surges?|jumps?|falls?|rises?)|st(?:icks?|aying) to .{0,20}strategy|without permission)\b', title):
        return False
    if kind not in ACTION or not re.search(ACTION[kind], title):
        return False
    if kind == 'EARNINGS':
        return bool(re.search(r'\d', title) and re.search(r'\b(?:reports?|posts?|announces?|beats?|misses?|rise|fall|up|down|growth)\b|분기|실적|증가|감소|흑자|적자', title))
    return True
