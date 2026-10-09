"""Offline regression tests: python -m unittest discover -s tests -v."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import httpx
import tools
import research
from check_citations import check, normalize_source_identities, main as citation_main
from langchain_core.messages import AIMessage

class CitationTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'n': 1, 'url': 'https://example.org/one'}, {'n': 2, 'url': 'https://example.org/two'}]
        self.refs = '\n## References\n[1] One. web. https://example.org/one (unknown)\n[2] Two. web. https://example.org/two (unknown)\n'

    def test_valid_group_and_range(self):
        for body in ('Evidence [1][2]', 'Evidence [1, 2]', 'Evidence [1-2]'):
            self.assertEqual(check(body + self.refs, self.sources), [])

    def test_references_are_not_body_citations(self):
        self.assertTrue(any('never cited' in p for p in check(self.refs, self.sources)))

    def test_missing_source(self):
        self.assertTrue(any('missing from' in p for p in check('[1][2][3]' + self.refs, self.sources)))

    def test_duplicate_reference_and_wrong_url(self):
        self.assertTrue(check('[1][2]' + self.refs + '[1] Again https://example.org/wrong\n', self.sources))

    def test_bundled_urls(self):
        self.assertTrue(check('[1][2]' + self.refs.replace('One. web.', 'One. https://extra.org web.'), self.sources))

    def test_code_and_links_ignored(self):
        for body in ('`[1][2]`', '[1](https://example.org/one) [2](https://example.org/two)', '```python\n[1][2]\n```'):
            self.assertTrue(any('never cited' in p for p in check(body + self.refs, self.sources)))

    def test_empty_invalid_duplicate_sources(self):
        for sources in ([], [{}], [self.sources[0], self.sources[0]], [{'n': True, 'url': 'file:///x'}]):
            self.assertTrue(check('[1]' + self.refs, sources))

class IdentityTests(unittest.TestCase):
    def test_equivalent_hf_ids(self):
        for identifier in ('2501.00001v2', 'https://huggingface.co/papers/2501.00001',
                           'https://arxiv.org/abs/2501.00001v3', ' 2501.00001 '):
            sources, problems = normalize_source_identities([{'n': 1, 'source': 'hf-search',
                'id': identifier, 'url': 'https://huggingface.co/papers/2501.00001/'}])
            self.assertEqual(problems, [])
            self.assertEqual(sources[0]['id'], '2501.00001')
            self.assertEqual(sources[0]['url'], 'https://huggingface.co/papers/2501.00001')

    def test_different_paper_or_wrong_family_rejected(self):
        for url in ('https://huggingface.co/papers/2501.99999', 'https://arxiv.org/abs/2501.00001',
                    'https://huggingface.co.evil.org/papers/2501.00001'):
            original = [{'n': 7, 'source': 'hf-daily', 'id': '2501.00001', 'url': url}]
            _, problems = normalize_source_identities(original)
            self.assertTrue(problems)
            self.assertIn('source [7]', problems[0])
            self.assertEqual(original[0]['url'], url)

    def test_validator_reports_identity_before_export(self):
        sources = [{'n': 1, 'source': 'hf-search', 'id': '2501.99999',
                    'url': 'https://huggingface.co/papers/2501.00001'}]
        report = '[1]\n## References\n[1] Paper. hf-search. https://huggingface.co/papers/2501.00001 (unknown)'
        self.assertTrue(any('URL does not match id' in p for p in check(report, sources)))

    @patch('builtins.print')
    def test_normalize_cli_rebuilds_references_and_rejects_mismatch(self, output):
        with tempfile.TemporaryDirectory() as tmp:
            report, source = Path(tmp) / 'report.md', Path(tmp) / 'sources.json'
            url = 'https://huggingface.co/papers/2501.00001/'
            report.write_text(f'[1]\n## References\n[1] Paper {url} (unknown)', encoding='utf-8')
            source.write_text(json.dumps([{'n': 1, 'id': '2501.00001v2', 'source': 'hf-search',
                                         'url': url, 'title': 'Paper'}]), encoding='utf-8')
            self.assertEqual(citation_main(['check', str(report), str(source), '--normalize']), 0)
            normalized = json.loads(source.read_text())
            self.assertEqual(check(report.read_text(), normalized), [])
            self.assertEqual(normalized[0]['id'], '2501.00001')
            self.assertNotIn('2501.00001/', report.read_text())
            normalized[0]['id'] = '2501.99999'
            source.write_text(json.dumps(normalized), encoding='utf-8')
            before = report.read_bytes(), source.read_bytes()
            self.assertEqual(citation_main(['check', str(report), str(source), '--normalize']), 1)
            self.assertEqual(before, (report.read_bytes(), source.read_bytes()))


class RetryTests(unittest.TestCase):
    @patch('tools.time.sleep')
    @patch('tools.random.uniform', return_value=0.25)
    def test_backoff_and_final_attempt(self, jitter, sleep):
        fn = Mock(side_effect=tools.RetryableError('temporary'))
        with self.assertRaises(tools.RetryableError):
            tools.with_retry(fn, attempts=3, base=1, cap=2)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.25, 2])
        self.assertEqual(fn.call_count, 3)

    @patch('tools.time.sleep')
    def test_retry_after_and_success(self, sleep):
        fn = Mock(side_effect=[tools.RetryableError('wait', 7), 'done'])
        self.assertEqual(tools.with_retry(fn), 'done')
        sleep.assert_called_once_with(7)

    @patch('tools.time.sleep')
    def test_programming_error_not_retried(self, sleep):
        fn = Mock(side_effect=ValueError('bad'))
        with self.assertRaises(ValueError):
            tools.with_retry(fn)
        self.assertEqual(fn.call_count, 1)
        sleep.assert_not_called()

    @patch('tools.httpx.request')
    def test_status_and_transport(self, request):
        request.return_value = httpx.Response(429, headers={'Retry-After': '4'}, request=httpx.Request('GET', 'https://example.org'))
        with self.assertRaises(tools.RetryableError) as context:
            tools._request('GET', 'https://example.org')
        self.assertEqual(context.exception.retry_after, 4)
        request.side_effect = httpx.ConnectError('offline')
        with self.assertRaises(tools.RetryableError):
            tools._request('GET', 'https://example.org')

class ToolTests(unittest.TestCase):
    @patch('tools._request')
    def test_empty_query_no_network(self, request):
        self.assertEqual(tools.arxiv_search.invoke({'query': '" : AND OR'}), 'NO RESULTS')
        request.assert_not_called()

    @patch('tools.time.sleep')
    @patch('tools._request')
    def test_arxiv_normalization_and_throttle(self, request, sleep):
        request.return_value = Mock(text='<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2501.00001v2</id><title> A\n paper </title><published>2025-01-02T00:00:00Z</published><summary>Evidence</summary></entry></feed>')
        with patch('tools._last_arxiv', None):
            result = json.loads(tools.arxiv_search.invoke({'query': 'all:"world" AND model'}))
            tools.arxiv_search.invoke({'query': 'world'})
        self.assertEqual(result[0]['url'], 'https://arxiv.org/abs/2501.00001')
        self.assertEqual(result[0]['title'], 'A paper')
        self.assertEqual(request.call_args_list[0].kwargs['params']['search_query'], 'all:world AND all:model')
        self.assertTrue(any(c.args[0] > 0 for c in sleep.call_args_list))

    def test_hf_normalization(self):
        result = tools._hf_records([{'paper': {'id': '2501.00001', 'summary': 'long', 'ai_summary': 'short', 'upvotes': 3}}, {'paper': {}}], search=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['summary'], 'short')

    @patch('tools._request', side_effect=ValueError('broken API'))
    def test_tool_errors_are_strings(self, request):
        for fn, args in [(tools.arxiv_search, {'query': 'world'}), (tools.hf_daily_papers, {}), (tools.hf_search_papers, {'query': 'world'}), (tools.web_search, {'query': 'world'}), (tools.web_fetch, {'url': 'https://example.org'})]:
            with patch('tools._last_arxiv', None):
                self.assertTrue(fn.invoke(args).startswith('ERROR:'))

    @patch('tools.time.sleep')
    @patch('tools._request')
    def test_mcp_sse_and_http200_throttling(self, request, sleep):
        limited = Mock()
        limited.json.return_value = {'id': 1, 'result': {'_meta': {'rateLimited': True}, 'content': []}}
        okay = Mock(text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"evidence"}]}}\n\n')
        okay.json.side_effect = ValueError('SSE')
        request.side_effect = [limited, okay]
        self.assertEqual(tools._mcp('web_search_exa', {}), 'evidence')
        sleep.assert_called_once_with(20)

    @patch.dict(os.environ, {'EXA_API_KEY': 'dummy secret/value'})
    def test_redact_encoded_secret(self):
        self.assertNotIn('dummy', tools.redact('dummy secret/value dummy%20secret%2Fvalue dummy+secret%2Fvalue'))

class OutputTests(unittest.TestCase):
    def artifacts(self):
        sources = [{'n': i, 'id': str(i), 'title': f'Paper {i}', 'date': 'unknown', 'source': family, 'url': url} for i, family, url in [(1, 'arxiv', 'https://arxiv.org/abs/1'), (2, 'hf-search', 'https://huggingface.co/papers/2'), (3, 'web', 'https://example.org/3')]]
        report = '[1][2][3]\n## References\n' + '\n'.join(f"[{s['n']}] {s['title']}. {s['source']}. {s['url']} (unknown)" for s in sources)
        return {research.REPORT_PATH: report.encode(), research.SOURCES_PATH: json.dumps(sources).encode()}

    def messages(self):
        return [AIMessage(content='', tool_calls=[{'name': 'task', 'args': {}, 'id': str(i)} for i in range(3)], usage_metadata={'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15})]

    def test_safe_slug(self):
        for topic in ('../../x', '', 'a' * 200, '../..', '\\windows\\name'):
            slug = research.slugify(topic)
            self.assertTrue(slug)
            self.assertLessEqual(len(slug), 60)
            self.assertNotRegex(slug, r'[./\\]')

    def test_summary(self):
        meta = research.summarize(self.messages(), 1.234, 'test')
        self.assertEqual(meta['subagent_calls'], 3)
        self.assertEqual(meta['tokens']['input'], 10)

    @patch('research.download')
    def test_export_preserves_sandbox_bytes(self, download):
        download.return_value = self.artifacts()
        with tempfile.TemporaryDirectory() as tmp:
            path = research.save_outputs(None, 'topic', self.messages(), 1, 'test', tmp)
            self.assertEqual(path.read_bytes(), download.return_value[research.REPORT_PATH])
            self.assertEqual(len(list(Path(tmp).iterdir())), 3)

    @patch('research.download')
    def test_failed_run_writes_nothing(self, download):
        for artifacts in ({}, {research.REPORT_PATH: b' ', research.SOURCES_PATH: b'[]'}, {research.REPORT_PATH: b'[1]', research.SOURCES_PATH: b'broken'}):
            download.return_value = artifacts
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RuntimeError):
                    research.save_outputs(None, 'topic', [], 1, 'test', tmp)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    @patch('research.download')
    def test_rejects_missing_families(self, download):
        artifacts = self.artifacts()
        sources = json.loads(artifacts[research.SOURCES_PATH])
        for source in sources:
            source['source'] = 'web'
        artifacts[research.SOURCES_PATH] = json.dumps(sources).encode()
        download.return_value = artifacts
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                research.save_outputs(None, 'topic', self.messages(), 1, 'test', tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    @patch('research.download')
    def test_rollback_on_export_failure(self, download):
        download.return_value = self.artifacts()
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path(tmp) / 'topic.sources.json'
            previous.write_bytes(b'previous')
            replace = os.replace
            count = 0
            def fail_second(src, dst):
                nonlocal count
                count += 1
                if count == 2:
                    raise OSError('disk error')
                return replace(src, dst)
            with patch('research.os.replace', side_effect=fail_second):
                with self.assertRaises(OSError):
                    research.save_outputs(None, 'topic', self.messages(), 1, 'test', tmp)
            self.assertEqual(previous.read_bytes(), b'previous')
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

if __name__ == '__main__':
    unittest.main()
