"""Structural citation validator; standard library only for sandbox execution."""
import json
import re
import sys
from urllib.parse import urlsplit
REPORT = '/tmp/work/report/report.md'
SOURCES = '/tmp/work/research/sources.json'


def source_identity_problems(entry):
    """Validate discovery family and ID before the lead finishes its work."""
    family = entry.get('source')
    if family is None:
        return []  # Minimal citation fixtures need not carry discovery metadata.
    if family not in {'arxiv', 'hf-daily', 'hf-search', 'web'}:
        return [f"source [{entry.get('n')}] has unknown family {family!r}"]
    base = ('https://arxiv.org/abs/' if family == 'arxiv' else
            'https://huggingface.co/papers/' if family.startswith('hf-') else None)
    if base and entry.get('url') != base + str(entry.get('id', '')):
        return [f"source [{entry.get('n')}] {family} URL does not match id: "
                f"id={entry.get('id')!r}, url={entry.get('url')!r}"]
    return []


def normalize_source_identities(sources):
    """Canonicalize equivalent IDs/URLs only; reject genuinely different papers."""
    if not isinstance(sources, list) or not sources:
        return sources, ['no sources in sources.json']
    normalized, problems = [], []
    for original in sources:
        if not isinstance(original, dict):
            problems.append('source entry must be an object')
            continue
        entry = dict(original)
        family = entry.get('source', '')
        if family in {'arxiv', 'hf-daily', 'hf-search'}:
            host, prefix = ('arxiv.org', '/abs/') if family == 'arxiv' else ('huggingface.co', '/papers/')
            url = urlsplit(str(entry.get('url', '')).strip())
            identifier = str(entry.get('id', '')).strip()
            if identifier.startswith(('http://', 'https://')):
                id_url = urlsplit(identifier)
                if id_url.hostname in {'arxiv.org', 'huggingface.co'}:
                    identifier = id_url.path.removeprefix('/abs/').removeprefix('/papers/').rstrip('/')
            identifier = re.sub(r'v\d+$', '', identifier)
            url_id = re.sub(r'v\d+$', '', url.path[len(prefix):].rstrip('/'))
            if (url.scheme not in {'http', 'https'} or url.netloc != host or
                    not url.path.startswith(prefix) or not identifier or identifier != url_id):
                problems.append(f"source [{entry.get('n')}] {family} identity mismatch: "
                                f"id={entry.get('id')!r}, url={entry.get('url')!r}; verify researcher notes")
            else:
                entry['id'] = identifier
                entry['url'] = f'https://{host}{prefix}{identifier}'
        normalized.append(entry)
    return normalized, problems

def check(report_text, sources):
    """Return problems; [] means every citation resolves consistently."""
    if not isinstance(sources, list) or not sources:
        return ['no sources in sources.json']
    problems, numbers, urls = [], {}, set()
    for entry in sources:
        if not isinstance(entry, dict):
            problems.append('source entry must be an object')
            continue
        n, url = entry.get('n'), entry.get('url')
        problems.extend(source_identity_problems(entry))
        if type(n) is not int or n < 1:
            problems.append('source n must be a positive integer')
        elif n in numbers:
            problems.append(f'duplicate source number [{n}]')
        else:
            numbers[n] = entry
        if not isinstance(url, str) or not re.match(r'^https?://\S+$', url):
            problems.append(f'invalid URL for source [{n}]')
        elif url in urls:
            problems.append(f'duplicate URL: {url}')
        else:
            urls.add(url)
    parts = re.split(r'^## References\s*$', report_text, maxsplit=1, flags=re.M)
    if len(parts) != 2:
        problems.append('missing ## References heading')
    body = re.sub(r'(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', parts[0])
    body = re.sub(r'`[^`\n]*`', '', body)
    body = re.sub(r'\[[^\]\n]*\]\([^\n]*?\)', '', body)
    cited = set()
    for match in re.finditer(r'\[(\d+(?:\s*(?:,|-)\s*\d+)*)\]', body):
        for item in match[1].split(','):
            if '-' in item:
                first, last = map(int, item.split('-'))
                if first > last or last - first > 10000:
                    problems.append(f'invalid citation range [{item}]')
                else:
                    cited.update(range(first, last + 1))
            else:
                cited.add(int(item))
    for n in sorted(cited - numbers.keys()):
        problems.append(f'[{n}] cited but missing from sources.json')
    for n in sorted(numbers.keys() - cited):
        problems.append(f'source [{n}] never cited')
    references = {}
    for line in (parts[1] if len(parts) == 2 else '').splitlines():
        match = re.match(r'^\[(\d+)\]\s+(.+)$', line)
        if not match:
            continue
        n = int(match[1])
        references[n] = references.get(n, 0) + 1
        if n not in numbers:
            problems.append(f'reference [{n}] is not a source')
            continue
        found = re.findall(r'https?://[^\s<>]+', match[2])
        if len(found) != 1 or found[0] != numbers[n].get('url'):
            problems.append(f'reference [{n}] must contain exactly the source URL')
    for n in numbers:
        if references.get(n, 0) != 1:
            problems.append(f'source [{n}] needs exactly one reference line')
    return problems

def main(argv):
    normalize = '--normalize' in argv
    argv = [arg for arg in argv if arg != '--normalize']
    try:
        with open(argv[1] if len(argv) > 1 else REPORT, encoding='utf-8-sig') as f:
            report = f.read()
        with open(argv[2] if len(argv) > 2 else SOURCES, encoding='utf-8-sig') as f:
            sources = json.load(f)
        if normalize:
            sources, problems = normalize_source_identities(sources)
            if problems:
                print('\n'.join(problems))
                return 1
            # Runs alongside the supplied finalizer INSIDE the sandbox.
            from finalize_citations import finalize
            report, sources, problems = finalize(report, sources)
            problems += check(report, sources)
            if problems:
                print('\n'.join(problems))
                return 1
            with open(argv[1] if len(argv) > 1 else REPORT, 'w', encoding='utf-8') as f:
                f.write(report)
            with open(argv[2] if len(argv) > 2 else SOURCES, 'w', encoding='utf-8') as f:
                json.dump(sources, f, ensure_ascii=False, indent=2)
        problems = check(report, sources)
    except (OSError, ValueError) as exc:
        print(f'cannot read inputs: {exc}')
        return 1
    if problems:
        print('\n'.join(problems))
        return 1
    print(f'OK: {len(sources)} sources, all citations resolve')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
