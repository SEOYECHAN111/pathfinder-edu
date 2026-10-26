"""Offline API diagnostics regression tests; do not require a real key."""
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api_diagnostics
import ai_suite


class APIDiagnostics(unittest.TestCase):
    def fake_response(self, text='OK', usage=None):
        doc = {'output':[{'type':'message','content':[{'type':'output_text','text':text}]}],
               'usage':usage or {'input_tokens':12,'output_tokens':3},'status':'completed'}
        resp = MagicMock()
        resp.__enter__.return_value.read.return_value=json.dumps(doc).encode('utf-8')
        return resp

    def fake_error(self, code, err_code):
        body=json.dumps({'error':{'type':err_code,'code':err_code,'message':'Sensitive user input'}}).encode()
        return urllib.error.HTTPError('https://api.openai.com/v1/responses',code,'failure',{},io.BytesIO(body))

    def test_real_model_test_uses_responses_and_selected_model(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-fake_testing','OPENAI_MODEL':'gpt-4.1-mini'}):
            with patch('api_diagnostics.urllib.request.urlopen',return_value=self.fake_response('OK')) as urlopen:
                output=api_diagnostics.check_real_model()
                self.assertTrue(output['ok'])
                req=urlopen.call_args.args[0]
                self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
                self.assertEqual(json.loads(req.data)['model'],'gpt-4.1-mini')
                self.assertFalse(json.loads(req.data)['store'])
                self.assertEqual(output['usage']['input_tokens'],12)

    def test_errors_are_actionable_without_secrets(self):
        cases=[(401,'invalid_api_key','Secret Key'),(403,'permission_denied','권한'),
               (404,'model_not_found','모델'),(429,'insufficient_quota','크레딧'),
               (429,'rate_limit_exceeded','한도')]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-dont-leak','OPENAI_MODEL':'gpt-4.1-mini'}):
            for status,code,expect in cases:
                with self.subTest(status=status,code=code):
                    with patch('api_diagnostics.urllib.request.urlopen',side_effect=self.fake_error(status,code)):
                        result=api_diagnostics.check_real_model()
                        self.assertFalse(result['ok'])
                        self.assertEqual(result['httpStatus'],status)
                        self.assertEqual(result['errorCode'],code)
                        self.assertIn(expect,result['message'])
                        self.assertNotIn('sk-proj-dont-leak',json.dumps(result))
                        self.assertNotIn('Sensitive user input',json.dumps(result))

    def test_student_ai_reports_real_429_cause(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-dont-leak','OPENAI_MODEL':'gpt-4.1-mini'}):
            with patch('ai_suite.urllib.request.urlopen',side_effect=self.fake_error(429,'credit_balance_exhausted')):
                with self.assertRaisesRegex(RuntimeError,'크레딧이 소진'):
                    ai_suite.call_openai('comprehensive',{})

    def test_incomplete_response_actionable(self):
        incomplete={'status':'incomplete','incomplete_details':{'reason':'max_output_tokens'},'output':[]}
        obj=MagicMock()
        obj.__enter__.return_value.read.return_value=json.dumps(incomplete).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-fake','OPENAI_MODEL':'gpt-4.1-mini'}):
            with patch('ai_suite.urllib.request.urlopen',return_value=obj):
                with self.assertRaisesRegex(RuntimeError,'출력 토큰 한도'):
                    ai_suite.call_openai('comprehensive',{})

    def test_university_service_error_not_false_success(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'response':{'header':{'resultCode':'30','resultMsg':'SERVICE_KEY_IS_NOT_REGISTERED'},'body':{}}}).encode()
        with patch.dict(os.environ,{'DATA_GO_KR_API_KEY':'some-fake-data-key'}):
            with patch('ai_suite.urllib.request.urlopen',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'인증·서비스 호출 오류'):
                    ai_suite.university_lookup('전남대학교')

if __name__=='__main__':unittest.main()
