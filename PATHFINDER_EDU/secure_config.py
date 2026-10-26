# -*- coding: utf-8 -*-
"""PATHFINDER EDU: server-only credential management.

Windows: DPAPI encryption scoped to the current Windows user. Encrypted bytes
are persisted to data/.api_credentials.dpapi (NEVER in public website assets).
Non-Windows: environment variables or process memory only (no plaintext file).
Only admin APIs can modify credentials; nothing returns raw key material.
"""
from __future__ import annotations
import ctypes
import json
import os
import re
import threading
import urllib.parse
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE = HERE / 'data' / '.api_credentials.dpapi'
ENV_BY_PROVIDER = {
    'openai': 'OPENAI_API_KEY',
    'neis': 'NEIS_API_KEY',
    'university': 'DATA_GO_KR_API_KEY',
}
DEFAULT_MODEL = 'gpt-4.1-mini'
_lock = threading.RLock()
_memory = {'keys': {}, 'model': DEFAULT_MODEL}
_loaded = False

class CredentialError(Exception):
    pass

class _BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def _crypt(data: bytes, decrypt: bool) -> bytes:
    if os.name != 'nt':
        raise CredentialError('암호화 키의 영구 저장은 Windows DPAPI에서만 지원됩니다.')
    # Windows crypt32 DLL, CurrentUser scope. No machine-wide decryption.
    crypt = ctypes.windll.crypt32
    local_free = ctypes.windll.kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    func = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if decrypt:
        func.argtypes = [ctypes.POINTER(_BLOB), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_BLOB)]
    else:
        func.argtypes = [ctypes.POINTER(_BLOB), wintypes.LPCWSTR, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_BLOB)]
    func.restype = wintypes.BOOL
    buf = ctypes.create_string_buffer(data)
    in_blob = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = _BLOB()
    if decrypt:
        ok = func(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob))
    else:
        ok = func(ctypes.byref(in_blob), 'PATHFINDER EDU API credentials', None, None, None, 0x01, ctypes.byref(out_blob))
    if not ok:
        raise CredentialError('Windows 사용자 암호화 저장소를 사용할 수 없습니다.')
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        local_free(ctypes.cast(out_blob.pbData, ctypes.c_void_p))

def _load():
    global _loaded, _memory
    with _lock:
        if _loaded:
            return
        _loaded = True
        if os.name != 'nt' or not STORE.exists():
            return
        try:
            payload = json.loads(_crypt(STORE.read_bytes(), decrypt=True).decode('utf-8'))
            if isinstance(payload, dict) and isinstance(payload.get('keys'), dict):
                _memory = {'keys': {k: str(v) for k, v in payload['keys'].items()
                                   if k in ENV_BY_PROVIDER and isinstance(v, str)},
                           'model': str(payload.get('model', DEFAULT_MODEL))}
        except (OSError, ValueError, UnicodeError, CredentialError) as exc:
            # Corrupted, wrong OS account, or copied configuration: NEVER silently overwrite.
            raise CredentialError('암호화된 API 설정을 열 수 없습니다. 처음 저장한 Windows 사용자 계정에서 실행하거나 관리자에게 키 재발급을 요청하세요.') from exc

def _persist():
    if os.name != 'nt':
        # Never silently create an unencrypted secret file on Linux/macOS.
        return False
    STORE.parent.mkdir(exist_ok=True)
    encrypted = _crypt(json.dumps(_memory, ensure_ascii=False).encode('utf-8'), decrypt=False)
    temp = STORE.with_suffix('.tmp')
    try:
        with temp.open('wb') as f:
            f.write(encrypted)
        os.chmod(temp, 0o600)
        temp.replace(STORE)
    finally:
        if temp.exists():
            temp.unlink()
    return True

def secret(provider: str) -> str:
    if provider not in ENV_BY_PROVIDER:
        raise ValueError('알 수 없는 API 제공자입니다.')
    _load()
    with _lock:
        # Environment explicitly injected at launch overrides saved Windows key.
        value = os.environ.get(ENV_BY_PROVIDER[provider], '').strip() or _memory['keys'].get(provider, '')
        if provider == 'university':
            # Public data portal shows both encoded and decoded service key versions.
            return urllib.parse.unquote(value)
        return value

def model_name() -> str:
    _load()
    with _lock:
        return os.environ.get('OPENAI_MODEL', '').strip() or _memory['model']

def key_status():
    _load()
    with _lock:
        return {
            provider: {
                'configured': bool(secret(provider)),
                'environmentOverride': bool(os.getenv(env, '').strip()),
                'source': '환경변수' if os.getenv(env, '').strip() else ('Windows 암호화 저장' if os.name == 'nt' and _memory['keys'].get(provider) else ('현재 실행 메모리' if _memory['keys'].get(provider) else '미설정')),
            }
            for provider, env in ENV_BY_PROVIDER.items()
        }

def change(keys=None, delete=None, model=None):
    _load()
    keys = keys or {}
    delete = delete or []
    if not isinstance(keys, dict) or not isinstance(delete, list):
        raise ValueError('키 설정 형식 오류')
    if any(k not in ENV_BY_PROVIDER for k in keys) or any(k not in ENV_BY_PROVIDER for k in delete):
        raise ValueError('등록되지 않은 API 제공자입니다.')
    with _lock:
        proposed = {'keys': dict(_memory['keys']), 'model': _memory['model']}
        for provider, raw in keys.items():
            value = str(raw).strip()
            if not value:  # An empty input means KEEP existing key.
                continue
            if len(value) > 2048 or len(value) < 8 or any(ord(c) < 33 or ord(c) == 127 for c in value):
                raise ValueError('키는 공백·제어문자 없는 8~2048자로 입력하세요.')
            if provider == 'openai' and not value.startswith('sk-'):
                raise ValueError('OpenAI는 sk-로 시작하는 Project Secret Key를 입력하세요. Tracking 설정은 키가 아닙니다.')
            if provider == 'university':
                value = urllib.parse.unquote(value)
            proposed['keys'][provider] = value
        for provider in delete:
            proposed['keys'].pop(provider, None)
        if model is not None:
            value = str(model).strip()
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{2,90}', value):
                raise ValueError('모델 이름 형식이 잘못되었습니다.')
            proposed['model'] = value
        previous = dict(_memory)
        _memory.clear(); _memory.update(proposed)
        try:
            persisted = _persist()
        except Exception:
            _memory.clear(); _memory.update(previous)
            raise
    return {'saved': True, 'persistent': persisted, 'status': key_status(), 'model': model_name(),
            'notice': 'Windows 사용자 DPAPI 암호화 저장 완료' if persisted else 'Windows 외 운영체제: 현재 실행 메모리에만 저장됨. 재실행 시 환경변수를 설정하세요.'}

def reset_for_tests():
    global _loaded
    with _lock:
        _memory.clear(); _memory.update({'keys': {}, 'model': DEFAULT_MODEL}); _loaded = False
