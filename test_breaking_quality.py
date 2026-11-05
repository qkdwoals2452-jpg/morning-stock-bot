import unittest
from unittest.mock import Mock, patch
from breaking_event_gate import headline_action
from breaking_worker import poll, handoff


class HeadlineTests(unittest.TestCase):
    def test_observed_false_alerts_cannot_borrow_summary_facts(self):
        titles = [
            "How Elon Musk went from Tesla CEO to the 'most powerful civilian, non-governmental actor in history'",
            'Ship With Russian Diesel Signals US Port After Trump-Putin Deal',
            'Indonesia’s Sovereign Fund Sticks to Investment Strategy Amid Market Turmoil',
            'Why Nearly 25% of the Country Is Still Watching Seinfeld',
            'Howard Hughes Holdings Set to Join S&P SmallCap 600',
            'Another AI power stock plunges 11% despite earnings beat',
            'Stocktwits Zero To Sixty: Tesla And SpaceX Form Merger Committees As Profits Drop, While Rivian Buys AI Startup And GM, Ford Advance EV Plans',
            'Bro went from a 700-person village in Slovakia to Google then built an app that makes $2k/day',
            "An OpenAI Model Spent Ethereum Without Permission. Here's What That Means For Crypto Investors.",
            'What Is Meta Platforms (META) Telling Investors With Its Sundial Deal And New Stock?',
            'Does enough capital exist to finance everyone’s ambitious AI spending plans?',
        ]
        for title in titles:
            for kind in ('CAPEX', 'CONTRACT', 'M&A', 'EARNINGS', 'PRODUCTION', 'POLICY', 'FOMC'):
                with self.subTest(title=title, kind=kind):
                    self.assertFalse(headline_action({'event_title': title, 'event_type': kind}))

    def test_observed_investment_advice_is_not_capex(self):
        from event_understanding_engine import understand_event
        titles = [
            "One Wall Street Analyst Says This Stock Is the Best Way to Invest in Anthropic and OpenAI. He's Right.",
            "If I Only Had $500 to Invest Right Now, I'd Buy and Hold This ETF for the Next 25 Years",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assertFalse(headline_action({'event_title': title, 'event_type': 'CAPEX'}))
                self.assertFalse(understand_event({'title': title, 'summary':
                    'Microsoft invests $20 billion in a new data center factory.'})['is_real_event'])
        self.assertTrue(headline_action({'event_title': 'Axon Invests $1.2 Billion in Skydio to Build the Future of Drone as First Responder', 'event_type': 'CAPEX'}))

    def test_actual_actions_remain_eligible(self):
        cases = [('CAPEX', 'Bombardier to Invest $270 Million in U.S. Expansion'),
                 ('CAPEX', "UK to invest £100m in 'world first' AI Biosecurity Lab"),
                 ('CONTRACT', 'LG전자, 독일 쉴링에 상업용 세탁가전 공급…유럽 B2B 공략 가속'),
                 ('CONTRACT', 'Supplier wins $200 million contract with Microsoft'),
                 ('M&A', 'Exclusive: Meta acquires AI data platform Sundial'),
                 ('EARNINGS', '하나·우리금융, 3분기 순이익 1조 돌파'),
                 ('EARNINGS', 'Company reports revenue up 26% in third quarter'),
                 ('PRODUCTION', '기업, 신규 공장 양산 시작'),
                 ('POLICY', 'Government imposes new export ban'),
                 ('FOMC', 'Fed holds interest rates steady')]
        for kind, title in cases:
            with self.subTest(title=title):
                self.assertTrue(headline_action({'event_title': title, 'event_type': kind}))

    def test_wrong_event_type_is_rejected(self):
        self.assertFalse(headline_action({'event_title': 'Meta acquires Sundial', 'event_type': 'CAPEX'}))


class WorkerTests(unittest.TestCase):
    def test_deployment_handoff_only_after_successful_checkpoint(self):
        order, sleep = [], Mock()
        scan = Mock(side_effect=lambda: order.append('saved'))
        def changed():
            self.assertEqual(order, ['saved'])
            return True
        poll(66, scan=scan, clock=lambda: 0, sleep=sleep, should_handoff=changed)
        scan.assert_called_once()
        sleep.assert_not_called()

    def test_failed_poll_cannot_trigger_deployment_handoff(self):
        changed = Mock(return_value=True)
        scan = Mock(side_effect=[None, RuntimeError('checkpoint failed'), None])
        changed.side_effect = [False, True]
        poll(3, scan=scan, clock=lambda: 0, sleep=Mock(), should_handoff=changed)
        self.assertEqual(scan.call_count, 3)
        self.assertEqual(changed.call_count, 2)

    def test_version_check_uses_local_checkout_and_redacts_network_error(self):
        from breaking_worker import deployment_changed
        import subprocess
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch('breaking_worker.subprocess.check_output', side_effect=[b'old', b'new refs/heads/main']):
            self.assertTrue(deployment_changed())
        with patch.dict('os.environ', {'GITHUB_REF': 'refs/heads/main'}), \
                patch('breaking_worker.subprocess.check_output', side_effect=subprocess.TimeoutExpired('git', 10)):
            self.assertFalse(deployment_changed())

    def test_poll_uses_start_to_start_interval_and_does_not_sleep_after_last(self):
        scan, sleep = Mock(), Mock()
        poll(2, scan=scan, clock=Mock(side_effect=[0, 42, 300]), sleep=sleep)
        self.assertEqual(scan.call_count, 2)
        sleep.assert_called_once_with(258)

    def test_failed_scan_does_not_end_monitoring_or_repeat_sends(self):
        scan, sleep = Mock(side_effect=[RuntimeError(), None]), Mock()
        poll(2, scan=scan, clock=Mock(side_effect=[0, 1, 300]), sleep=sleep)
        self.assertEqual(scan.call_count, 2)
        with self.assertRaises(RuntimeError):
            poll(1, scan=Mock(side_effect=RuntimeError()), sleep=sleep)

    def test_slow_scan_never_sleeps_negative(self):
        sleep = Mock()
        poll(2, scan=Mock(), clock=Mock(side_effect=[0, 400, 401]), sleep=sleep)
        sleep.assert_called_once_with(0)

    def test_invalid_cycle_count_does_not_scan(self):
        for cycles in (0, -1, 67):
            with self.assertRaises(ValueError):
                poll(cycles)

    def test_handoff_requires_main_and_ack_without_logging_token(self):
        with patch.dict('os.environ', {'GH_TOKEN': 'test-secret', 'GITHUB_REPOSITORY': 'owner/repo',
                                       'GITHUB_REF': 'refs/heads/main'}):
            with patch('breaking_worker.requests.post', return_value=Mock(status_code=204)) as post:
                handoff()
                self.assertEqual(post.call_args.kwargs['json'], {'ref': 'main'})
            with patch('breaking_worker.requests.post', side_effect=RuntimeError('test-secret')):
                with self.assertRaises(RuntimeError) as error:
                    handoff()
                self.assertNotIn('test-secret', str(error.exception))
