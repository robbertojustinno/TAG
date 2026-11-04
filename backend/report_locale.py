"""Translate report captions before inserting any tenant-owned values."""
import json
import re
from functools import lru_cache
from html import escape, unescape
from pathlib import Path

@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('report_translations.json').read_text(encoding='utf-8'))

def report_text(value, language='pt'):
    if language not in ('en','es'): return str(value)
    source=str(value)
    translated=catalog().get(source.strip(),{}).get(language)
    return source.replace(source.strip(),translated,1) if translated else source

def translate_template(source, language='pt'):
    if language not in ('en','es'): return source
    source=source.replace('lang="pt-BR"', 'lang="'+{'en':'en-US','es':'es-ES'}[language]+'"',1)
    def caption(match):
        value=unescape(match[2]);translated=report_text(value,language)
        return match[1]+(escape(translated,quote=False) if translated!=value else match[2])
    return re.sub(r'(^|>)([^<>]*)(?=<|$)',caption,source)
