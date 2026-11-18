import base64
import html
import re
import unicodedata
from urllib.parse import unquote

from fastapi import HTTPException

from app.security.decisions import Decision
from app.security.features import normalize
from app.services.gemini import EXTRACTIVE_INSTRUCTION, SYSTEM_INSTRUCTION, reject_credentials


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

OUTPUT_ADOPTION = re.compile(
    r"(?:^|[.!?:]\s*)i\s+(?:will|have)\s+(?:now\s+)?"
    r"(?:ignore|ignored|disregard|disregarded|override|overridden)\s+"
    r"(?:all\s+)?(?:the\s+)?(?:previous|prior|system)\s+(?:instructions|rules|messages)"
)

# The answer route has no account-management capability. Catch affirmative
# first-person claims of changing access, including when copied from a source.
PRIVILEGE_CHANGE_CLAIM = re.compile(
    r"(?:^|[.!?؟]\s+)(?:i\s+(?:have\s+)?(?:grant(?:ed)?|revok(?:e|ed)|"
    r"elevat(?:e|ed)|upgrad(?:e|ed)|promot(?:e|ed)|assign(?:ed)?)\b"
    r"[^.!?؟\n]{0,100}\b(?:access|roles?|permissions?|privileges?|admin(?:istrator)?)\b"
    r"|(?:أنا\s+|لقد\s+)?(?:منحت|سحبت|رفعت|عدلت)\s+[^.!?؟\n]{0,80}"
    r"(?:صلاحيات|صلاحية|امتيازات|admin privileges|administrator role))"
)


ACCEPTED_AUTHORITY = re.compile(
    r"(?:^|[.!?؟]\s+)(?:i\s+(?:have\s+)?(?:accepted|recognized|approved|trusted|relied on)\b"
    r"|(?:أنا\s+|لقد\s+)?(?:قبلت|اعتمدت|وثقت|صدقت)\s+)([^.!?؟\n]{1,180})"
)
AUTHORITY_OBJECT = re.compile(r"\b(?:approval|authorization|permission|consent|certificate|attestation)\b"
                              r"|موافق[ةه]|تفويض|تصريح|شهاد[ةه]|إذن|اذن")
INVALID_AUTHORITY = re.compile(r"\b(?:forged|counterfeit|fabricated|invalid|revoked|expired|falsified)\b"
                               r"|مزور|منتهي|منتهية|مسحوب|باطل|ملغ[ىي]|غير\s+(?:صالح|ساري)")


def inspect_readonly_output(text, *, check_authority=False):
    value = normalize(text)
    if PRIVILEGE_CHANGE_CLAIM.search(value):
        return Decision('block','output_policy_violation','role_spoofing')
    if check_authority:
        for match in ACCEPTED_AUTHORITY.finditer(value):
            clause = match.group(1)
            if AUTHORITY_OBJECT.search(clause) and INVALID_AUTHORITY.search(clause):
                return Decision('block','output_policy_violation','authority_spoofing')
    return None


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
        prompt = SYSTEM_INSTRUCTION + '\n' + EXTRACTIVE_INSTRUCTION
        sentences=[normalize(s) for s in prompt.splitlines() if len(s.strip())>45]
        if any(s in normalized for s in sentences):
            return Decision('block','output_policy_violation','prompt_extraction')
        if OUTPUT_ADOPTION.search(normalized):
            return Decision('block','output_policy_violation','instruction_override')
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
        decoded_text = normalize(value)
        if (any(re.search(pattern,decoded_text) for _,pattern in PATTERNS)
                or (stage=='output' and OUTPUT_ADOPTION.search(decoded_text))):
            category = {'input':'direct_prompt_injection','context':'indirect_prompt_injection',
                        'output':'output_policy_violation'}[stage]
            return Decision('block',category,'encoded_instruction')
    return None
