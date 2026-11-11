"""Conservative SMTP rejection categories; retain codes, never provider text."""
import re


def rejection(code,text,stage='recipient'):
    text=text.decode('ascii',errors='ignore') if isinstance(text,bytes) else str(text)
    found=re.search(r'(?<![\d.])([245]\.[0-7]\.\d{1,3})(?![\d.])',text[:4096])
    enhanced=found[1] if found else None
    invalid=stage=='recipient' and code>=500 and enhanced=='5.1.1'
    if stage=='authentication': category='authentication'
    elif code<500 or (enhanced and enhanced.startswith('4.')): category='temporary_limit'
    elif invalid: category='invalid_mailbox'
    elif enhanced and enhanced.startswith('5.7.'): category='policy_rejection'
    else: category='message_rejected'
    return {'smtp_code':int(code),'enhanced_status':enhanced,'category':category,
        'suppress':invalid,'pause':not invalid,
        'error_code':f"smtp:{stage}:{int(code)}:{enhanced or 'unknown'}:{category}"}
