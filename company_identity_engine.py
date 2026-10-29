"""Exact press aliases and explicit coordinated subjects, without fuzzy matching."""
import re

COMPANY_ALIASES = {
    '현대자동차': ('현대차',),
    '삼성중공업': ('삼성重', '삼성중'),
    '한화에어로스페이스': ('한화에어로',),
    '하나금융지주': ('하나금융',),
    '우리금융지주': ('우리금융',),
}
COMPACT_SUBJECTS = {
    '하나·우리금융': ('하나금융지주', '우리금융지주'),
    '우리·하나금융': ('우리금융지주', '하나금융지주'),
}
NEWS_LABEL_PREFIX = r'(?:\[(?:속보|단독|종합|공시|breaking)\]\s*)*'
END = r'(?:\s*[,，:]|(?:은|는|이|가)\s|\s+)'


def joint_subject_end(name, sentence):
    """Return end of the entire shared subject, retaining original evidence text."""
    for compact, names in COMPACT_SUBJECTS.items():
        pattern = re.escape(compact).replace('·', r'\s*[·ㆍ]\s*')
        match = re.match(r'^\s*' + NEWS_LABEL_PREFIX + r'["“\'‘]*' + pattern + END, sentence)
        if name in names and match:
            return match.end()
    lookup = {alias: official for official, aliases in COMPANY_ALIASES.items()
              for alias in (official,) + aliases}
    terms = '|'.join(re.escape(x) for x in sorted(lookup, key=len, reverse=True))
    match = re.match(r'^\s*' + NEWS_LABEL_PREFIX + r'["“\'‘]*(?P<subjects>(?:' + terms + r')(?:\s*[·ㆍ]\s*(?:'
                     + terms + r'))+)' + END, sentence)
    if match:
        parts = re.split(r'\s*[·ㆍ]\s*', match['subjects'])
        if name in [lookup[part] for part in parts]:
            return match.end()
    return None


def has_company_mention(name, text):
    names = (name,) + COMPANY_ALIASES.get(name, ())
    pattern = (r'(?<![가-힣A-Za-z0-9])(?:' + '|'.join(re.escape(n) for n in names)
               + r')(?=(?:은|는|이|가|을|를|와|과|의|에|에게|에서|으로부터|로부터|으로|로|도|만)?'
                 r'(?:[^가-힣A-Za-z0-9]|$))')
    return bool(re.search(pattern, text, re.I)) or any(
        joint_subject_end(name, line) is not None for line in re.split(r'[\n;]', text))
