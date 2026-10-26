# -*- coding: utf-8 -*-
"""Diagnose OpenAI API failures without ever returning secret key material."""
import json
import re
import urllib.error
import urllib.request
from secure_config import secret, model_name

TIPS = {
 'invalid_api_key': 'Secret Key가 올바르지 않거나 폐기됐습니다. OpenAI API Keys에서 새 프로젝트 키를 발급해 등록하세요.',
 'invalid_api_key_format': 'Secret Key 형식이 올바르지 않습니다. sk-로 시작하는 실제 키 전체를 붙여넣으세요.',
 'model_not_found': '선택한 모델명이 존재하지 않거나 현재 프로젝트에서 사용할 수 없습니다. 관리자 화면의 모델명을 확인하세요.',
 'insufficient_quota': 'API 요금제의 크레딧, 조직·프로젝트 지출 한도 또는 사용량 한도를 확인하세요. ChatGPT 구독과 API 비용은 별개입니다.',
 'credit_balance_exhausted': 'API 선불 크레딧이 소진됐습니다. platform.openai.com의 Billing에서 충전 상태를 확인하세요.',
 'project_spend_limit_exceeded': '프로젝트 지출 제한에 도달했습니다. API 프로젝트 Limits를 확인하세요.',
 'organization_spend_limit_exceeded': '조직 지출 제한에 도달했습니다. API 조직 Limits를 확인하세요.',
 'organization_usage_limit_exceeded': '조직의 승인된 API 사용 한도에 도달했습니다. Limits를 확인하세요.',
 'rate_limit_exceeded': 'API 호출 속도 또는 토큰 처리량 한도를 넘었습니다. 요청 간격과 Limits를 확인하세요.',
 'permission_denied': '해당 API 키 또는 프로젝트에 모델/엔드포인트 권한이 없습니다. 프로젝트의 API 키 권한을 확인하세요.',
 'billing_not_active': 'API 결제가 활성화되지 않았을 수 있습니다. API Billing을 확인하세요.',
 'context_length_exceeded': '요청 내용이 모델의 입력 한도를 초과했습니다. 질문을 줄이세요.',
}
STATUS_TIPS = {
 400:'요청 형식 또는 선택한 모델을 확인하세요.',
 401:'API Secret Key가 잘못됐거나 폐기됐을 수 있습니다.',
 403:'API 프로젝트 또는 모델/엔드포인트 권한을 확인하세요.',
 404:'모델명 또는 API 주소를 확인하세요.',
 408:'API 요청 시간이 초과됐습니다.',
 429:'API 크레딧·지출 한도·사용 속도 제한을 확인하세요.',
 500:'OpenAI 서버 일시적 오류입니다. 잠시 후 다시 확인하세요.',
 502:'OpenAI 서버 일시적 오류입니다. 잠시 후 다시 확인하세요.',
 503:'OpenAI 서버 일시적 오류입니다. 잠시 후 다시 확인하세요.',
 504:'OpenAI 서버 응답이 지연됐습니다.',
}

def _safe_code(raw):
    if not isinstance(raw,str):return ''
    return raw if re.fullmatch(r'[A-Za-z0-9_-]{1,90}',raw) else ''

def diagnose_http(exc):
    status=int(exc.code)
    error_code=''
    try:
        raw=exc.read(12000)
        info=json.loads(raw)
        detail=info.get('error',{}) if isinstance(info,dict) else {}
        if isinstance(detail,dict):
            error_code=_safe_code(detail.get('code')) or _safe_code(detail.get('type'))
    except (ValueError,UnicodeError,TypeError,OSError):
        pass
    desc=TIPS.get(error_code,STATUS_TIPS.get(status,'서비스 응답 코드와 인터넷 연결을 확인하세요.'))
    return {'ok':False,'httpStatus':status,'errorCode':error_code or None,
            'message':f'OpenAI HTTP {status}'+(f' [{error_code}]' if error_code else '')+': '+desc}

def diagnose_network(exc):
    if isinstance(exc, TimeoutError):return {'ok':False,'message':'OpenAI 응답 시간이 초과됐습니다. 인터넷 연결·방화벽을 확인하세요.','errorCode':'timeout'}
    if isinstance(exc, urllib.error.URLError):return {'ok':False,'message':'OpenAI 서버 연결 실패: 인터넷, 프록시, SSL 인증서 또는 방화벽을 확인하세요.','errorCode':'network_error'}
    return {'ok':False,'message':'OpenAI 요청 중 예상하지 못한 오류입니다. 관리자에게 서버 오류 기록 확인을 요청하세요.','errorCode':'unknown'}

def extract_text(response):
    if not isinstance(response,dict):return ''
    direct=response.get('output_text','')
    if isinstance(direct,str) and direct.strip():return direct.strip()
    result=[]
    for item in response.get('output',[]) or []:
        if not isinstance(item,dict):continue
        for part in item.get('content',[]) or []:
            if isinstance(part,dict) and part.get('type')=='output_text' and isinstance(part.get('text'),str):
                result.append(part['text'])
    return '\n'.join(result).strip()

def check_real_model():
    """A small real Responses API request to verify both secret and model, not just /models."""
    key=secret('openai')
    if not key:return {'ok':False,'message':'OpenAI Secret Key가 아직 등록되지 않았습니다.','errorCode':'no_key'}
    model=model_name()
    payload={
      'model':model,'instructions':'You are testing an API connection. Reply with the single word OK.',
      'input':'Reply OK.','max_output_tokens':160,'store':False,
    }
    req=urllib.request.Request('https://api.openai.com/v1/responses',
       data=json.dumps(payload).encode('utf-8'),
       headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            info=json.loads(response.read(128000))
        output=extract_text(info)
        if not output:
            reason=(info.get('incomplete_details') or {}).get('reason') if isinstance(info,dict) else None
            return {'ok':False,'errorCode':_safe_code(reason) or 'empty_response',
              'message':'모델 요청은 수락됐지만 텍스트가 반환되지 않았습니다. 출력 토큰 한도와 모델 설정을 확인하세요.'}
        return {'ok':True,'model':model,'message':f'실제 AI 답변 생성 성공 · 모델 {model} · 출력 {len(output)}자. 인증·모델·API 사용량이 모두 확인됐습니다.',
          'usage':info.get('usage') or {}}
    except urllib.error.HTTPError as exc:
        return diagnose_http(exc)
    except (urllib.error.URLError, TimeoutError) as exc:
        return diagnose_network(exc)
    except (ValueError,UnicodeError,TypeError):
        return {'ok':False,'errorCode':'invalid_response','message':'OpenAI 응답을 정상적으로 읽지 못했습니다. 서버/네트워크 상태를 확인하세요.'}
