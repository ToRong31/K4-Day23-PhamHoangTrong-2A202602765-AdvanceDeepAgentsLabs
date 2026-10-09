"""Host retrieval tools with bounded retries; no secrets enter the sandbox."""
import json
import os
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, quote_plus
import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()
ARXIV_URL = 'https://export.arxiv.org/api/query'
HF_DAILY_URL = 'https://huggingface.co/api/daily_papers'
HF_SEARCH_URL = 'https://huggingface.co/api/papers/search'
EXA_URL = 'https://mcp.exa.ai/mcp'
_arxiv_lock = threading.Lock()
_last_arxiv = None

class RetryableError(Exception):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after

def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Retry only transient failures; never sleep after the final attempt."""
    if attempts < 1 or base < 0 or cap < 0:
        raise ValueError('invalid retry configuration')
    for attempt in range(attempts):
        try:
            return fn()
        except RetryableError as exc:
            if attempt == attempts - 1:
                raise
            delay = exc.retry_after
            if delay is None:
                delay = base * 2 ** attempt + random.uniform(0, base)
            time.sleep(min(cap, max(0, delay)))

def redact(message):
    text = str(message)
    for name, value in os.environ.items():
        if value and name.endswith(('API_KEY', '_KEY', '_TOKEN', '_SECRET')):
            for variant in {value, quote(value, safe=''), quote_plus(value)}:
                text = text.replace(variant, '[REDACTED]')
    return re.sub(r'(?i)(exaApiKey=)[^&\s]+', r'\1[REDACTED]', text)

def _error(exc):
    return f'ERROR: {type(exc).__name__}: {redact(exc)}'

def _retry_after(value):
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError):
            return None

def _request(method, url, **kwargs):
    try:
        response = httpx.request(method, url, timeout=45, follow_redirects=True, **kwargs)
    except httpx.TransportError as exc:
        raise RetryableError(redact(exc)) from exc
    if response.status_code in {429, 500, 502, 503, 504}:
        raise RetryableError(f'HTTP {response.status_code}', _retry_after(response.headers.get('Retry-After')))
    response.raise_for_status()
    return response

def _compact(value, limit=600):
    return ' '.join(str(value or '').split())[:limit]

def _records(records):
    return json.dumps(records, ensure_ascii=False) if records else 'NO RESULTS'

@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv keywords, newest first. JSON fields: id, url, published, title, summary. Use short queries."""
    try:
        terms = [t for t in re.findall(r'[^\W_]+(?:-[^\W_]+)*', query) if t.upper() not in {'AND', 'OR', 'NOT', 'ALL', 'TI', 'AU', 'ABS'}]
        if not terms:
            return 'NO RESULTS'
        def fetch():
            global _last_arxiv
            with _arxiv_lock:
                if _last_arxiv is not None:
                    time.sleep(max(0, 3 - (time.monotonic() - _last_arxiv)))
                _last_arxiv = time.monotonic()
                return _request('GET', ARXIV_URL, params={'search_query': ' AND '.join(f'all:{t}' for t in terms), 'sortBy': 'submittedDate', 'sortOrder': 'descending', 'max_results': max(1, min(30, max_results)), 'start': 0})
        response = with_retry(fetch, attempts=7, base=3, cap=60)
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        records = []
        for entry in ET.fromstring(response.text).findall('a:entry', ns):
            identifier = re.sub(r'v\d+$', '', entry.findtext('a:id', '', ns).split('/abs/')[-1])
            if not identifier or identifier.endswith('errors'):
                continue
            records.append({'id': identifier, 'url': f'https://arxiv.org/abs/{identifier}', 'published': entry.findtext('a:published', '', ns)[:10], 'title': _compact(entry.findtext('a:title', '', ns)), 'summary': _compact(entry.findtext('a:summary', '', ns))})
        return _records(records)
    except Exception as exc:
        return _error(exc)

def _hf_records(items, search=False):
    if not isinstance(items, list):
        raise ValueError('expected a Hugging Face list')
    records = []
    for item in items:
        paper = item.get('paper', {})
        if not paper.get('id'):
            continue
        identifier = re.sub(r'v\d+$', '', str(paper['id']))
        summary = (paper.get('ai_summary') or item.get('ai_summary')) if search else None
        records.append({'id': identifier, 'url': f'https://huggingface.co/papers/{identifier}', 'published': str(paper.get('publishedAt') or item.get('publishedAt') or '')[:10], 'title': _compact(paper.get('title') or item.get('title')), 'summary': _compact(summary or paper.get('summary') or item.get('summary')), 'upvotes': paper.get('upvotes') or item.get('upvotes') or 0, 'github': paper.get('githubRepo') or item.get('githubRepo') or '', 'stars': paper.get('githubStars') or item.get('githubStars') or 0})
    return records

@tool
def hf_daily_papers(limit: int = 30, date: str = '', keyword: str = '') -> str:
    """Get trending HF papers sorted by upvotes. Optional date YYYY-MM-DD and local keyword filter, not topic search."""
    try:
        params = {'limit': max(1, min(100, limit))}
        if date:
            datetime.strptime(date, '%Y-%m-%d')
            params['date'] = date
        records = _hf_records(with_retry(lambda: _request('GET', HF_DAILY_URL, params=params)).json())
        if keyword:
            records = [r for r in records if keyword.casefold() in (r['title'] + ' ' + r['summary']).casefold()]
        return _records(sorted(records, key=lambda r: r['upvotes'], reverse=True))
    except Exception as exc:
        return _error(exc)

@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search HF papers by topic. JSON includes id, url, published, title, summary, upvotes, github, stars."""
    try:
        if not query.strip():
            return 'NO RESULTS'
        response = with_retry(lambda: _request('GET', HF_SEARCH_URL, params={'q': query, 'limit': max(1, min(50, limit))}))
        return _records(_hf_records(response.json(), search=True))
    except Exception as exc:
        return _error(exc)

def _mcp(name, arguments):
    def fetch():
        key = os.getenv('EXA_API_KEY', '').strip()
        response = _request('POST', EXA_URL, params={'exaApiKey': key} if key else None, headers={'Accept': 'application/json, text/event-stream'}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})
        try:
            payload = response.json()
        except ValueError:
            payload = None
            for event in re.split(r'\r?\n\r?\n', response.text):
                data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
                if data:
                    candidate = json.loads(data)
                    if candidate.get('id') == 1:
                        payload = candidate
            if payload is None:
                raise ValueError('MCP response contains no result event')
        result = payload.get('result', {})
        content = '\n'.join(str(item.get('text', '')) for item in result.get('content', []) if item.get('type') == 'text')
        marker = re.sub(r'[^a-z0-9]', '', json.dumps({'meta': result.get('_meta', {}), 'error': payload.get('error', {})}).lower())
        if any(x in marker for x in ('ratelimitedtrue', 'ratelimitexceeded', 'ratelimittrue', 'toomanyrequests')) or re.search(r'rate.?limit(?:ed| exceeded| reached)|too many requests', content, re.I):
            raise RetryableError('Exa rate limit', retry_after=20)
        if 'error' in payload or result.get('isError'):
            raise RuntimeError(redact(payload.get('error') or content))
        return redact(content.strip()) or 'NO RESULTS'
    return with_retry(fetch, attempts=7, base=3, cap=60)

@tool
def web_search(query: str, objective: str = '', num_results: int = 5) -> str:
    """Search web through Exa; returns text and source URLs. Specify authoritative sources in objective."""
    try:
        if not query.strip():
            return 'NO RESULTS'
        return _mcp('web_search_exa', {'query': query, 'objective': objective or f'Find reliable research sources about {query}', 'numResults': max(1, min(10, num_results))})
    except Exception as exc:
        return _error(exc)

@tool
def web_fetch(url: str) -> str:
    """Fetch one HTTP(S) page through Exa as text capped at 12000 characters, for reading and verification."""
    try:
        if not re.match(r'^https?://\S+$', url):
            raise ValueError('expected an HTTP(S) URL')
        return _mcp('web_fetch_exa', {'urls': [url]})[:12000]
    except Exception as exc:
        return _error(exc)

SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]

if __name__ == '__main__':
    for fn, args in [(arxiv_search, {'query': 'world model', 'max_results': 3}), (hf_daily_papers, {'limit': 20}), (hf_search_papers, {'query': 'world model', 'limit': 3}), (web_search, {'query': 'survey paper on world models', 'num_results': 2}), (web_fetch, {'url': 'https://arxiv.org/abs/1803.10122'})]:
        print(f'== {fn.name}\n{fn.invoke(args)[:400]}\n')
