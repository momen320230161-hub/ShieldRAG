import base64
import html
import re
import unicodedata
from urllib.parse import unquote

from fastapi import HTTPException

from app.security.decisions import Decision
from app.security.features import normalize
from app.services.gemini import SYSTEM_INSTRUCTION, reject_credentials


PATTERNS=(
 ('instruction_override',r'(?:^|[.!?:]\s*)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|earlier|system)\s+(?:instructions|rules|messages)'),
 ('instruction_override',r'(?:تجاهل|تجاوز|استبدل)\s+(?:كل\s+)?(?:التعليمات|تعليمات|قواعد|سياسة)\s*(?:السابقة|النظام|الامان|الأمان|الحماية)'),
 ('authority_spoofing',r'(?:\[\s*system\s*\]|<\s*system\s*>|system\s+override\s*:|developer\s+(?:message|instruction)\s*:|رسالة المطور\s*:)'),
 ('prompt_extraction',r'(?:reveal|show|print|dump|copy|expose|translate|summarize).{0,60}(?:your|hidden|internal|confidential|actual).{0,45}(?:system\s+prompt|instructions|configuration|credentials|api\s+key)'),
 ('credential_exfiltration',r'(?:print|show|reveal|return|dump|expose).{0,50}(?:backend|service|gemini|supabase|production|private).{0,40}(?:secret|key|password|credential|configuration|environment)'),
 ('prompt_extraction',r'(?:اكشف|اعرض|اطبع|سرب|ترجم).{0,65}(?:السرية|الاسرار|الأسرار|مفتاح|مفاتيح|system prompt|التعليمات الداخلية|تعليماتك الداخلية)'),
 ('role_spoofing',r'(?:bypass|skip|override).{0,45}(?:rls|access\s+controls|role\s+checks|permissions|authenticated\s+role)'),
 ('role_spoofing',r'(?:i am|pretend my role is|treat me as).{0,35}(?:admin|administrator).{0,65}(?:grant|unrestricted|regardless|bypass)'),
 ('instruction_override',r'(?:disable|turn\s+off|skip).{0,30}(?:security\s+(?:agent|checks|controls)|safety\s+(?:checks|validation)|audit\s+logging)'),
 ('instruction_override',r'(?:عطل|عطّل|تجاوز).{0,35}(?:وكيل الحماية|فحوصات الامان|فحوصات الأمان|فحص الصلاحيات|قيود الامان)'),
)


def inspect_rules(text,stage,settings):
    # Preserve exact configured-key checks, including nonstandard test credentials.
    try:
        reject_credentials(text,settings)
        reject_credentials(unicodedata.normalize('NFKC',text),settings)
    except HTTPException:
        return Decision('block','credential_disclosure','protected_credential')
    normalized=normalize(text)
    if stage=='output':
        # Detect substantial verbatim operational prompt fragments, without returning them.
        sentences=[normalize(s) for s in SYSTEM_INSTRUCTION.splitlines() if len(s.strip())>45]
        if any(s in normalized for s in sentences):
            return Decision('block','output_policy_violation','prompt_extraction')
    for reason,pattern in PATTERNS:
        if re.search(pattern,normalized):
            category='indirect_prompt_injection' if stage=='context' else (
                'output_policy_violation' if stage=='output' else 'direct_prompt_injection')
            return Decision('block',category,reason)
    # Bounded one-level canonicalization; never execute decoded text or recurse.
    decoded=[html.unescape(unquote(text))]
    for token in re.findall(r'[A-Za-z0-9+/]{20,}={0,2}',text)[:4]:
        if len(token)>4096:
            continue
        try:
            decoded.append(base64.b64decode(token,validate=True).decode('utf-8'))
        except (ValueError,UnicodeDecodeError):
            continue
    for value in decoded:
        if value==text:
            continue
        try:
            reject_credentials(value,settings)
        except HTTPException:
            return Decision('block','credential_disclosure','protected_credential')
        if any(re.search(pattern,normalize(value)) for _,pattern in PATTERNS):
            return Decision('block','indirect_prompt_injection' if stage=='context' else 'direct_prompt_injection','encoded_instruction')
    return None
