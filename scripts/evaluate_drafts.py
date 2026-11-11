"""Export 12 synthetic reference cases or explicitly invoke bounded live Gemini evaluation."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import composer
import config
import qc

RUBRIC=('truthful','relevant_proof','correct_audience','natural_voice','useful_subject','single_next_step')


def evaluate(live=False,max_cases=12):
    if not 1<=max_cases<=12: raise ValueError('Choose 1-12 cases')
    if live: config.require_gemini_key()
    fixture=json.loads((ROOT/'tests/fixtures/drafting_evaluation_v1.json').read_text(encoding='utf8'))
    results=[]
    for case in fixture['cases'][:max_cases]:
        started=time.monotonic()
        try:
            if not live: draft=case['reference']
            elif case['kind']=='initial':
                draft=composer.compose_email(case['company'],case['contact'],case['candidate_facts'])
            else:
                draft=composer._generate(json.dumps({'original_subject':case['original_subject'],'original_body':case['original_body'],
                    'company_name':case['company']['name'],'recipient_title':case['contact']['title'],
                    'audience_guidance':composer._audience_guidance(case['contact']),'verified_candidate_facts':case['candidate_facts']}),
                    composer.FollowUpDraft,composer.FOLLOW_UP_SYSTEM_PROMPT)
            subject=case['original_subject'] if case['kind']=='followup' else draft['subject']
            if case['kind']=='followup' and not subject.lower().startswith('re:'): subject='Re: '+subject
            body=composer._body(draft['body'],case['contact'],{'full_name':'Maya Chen','portfolio_url':'https://example.test/portfolio'})
            final_body=body+'\n\nResume: https://example.test/resume.pdf'
            trap_hits=[term for term in case['forbidden'] if term.casefold() in body.casefold()]
            results.append({'id':case['id'],'scenario':case['scenario'],'source_facts':case['candidate_facts'],
                'company_context':case['company'],'recipient':case['contact'],'subject':subject,'body':final_body,
                'research_notes':draft.get('research_notes'),'model':config.GEMINI_MODEL if live else 'curated_reference',
                'prompt_version':composer.PROMPT_VERSION,'calls':draft.get('generation',{}).get('calls',0),
                'duration_seconds':round(time.monotonic()-started,3),'provider_failure':None,
                'pitch_words':len(qc.pitch_text(body).split()),'final_words':len(final_body.split()),
                'writing_suggestions':qc.warnings(subject,body,case['kind']=='followup'),
                'hard_failures':qc.blockers(subject,body)+['Forbidden unsupported claim: '+t for t in trap_hits]})
        except Exception as exc:
            results.append({'id':case['id'],'provider_failure':type(exc).__name__,'calls':getattr(exc,'generation',{}).get('calls'),
                'duration_seconds':round(time.monotonic()-started,3),'hard_failures':['Generation failed']})
    return {'version':fixture['version'],'mode':'live' if live else 'curated_reference','human_review':'pending',
        'rubric':list(RUBRIC),'results':results,'note':'References validate the workflow, not live AI quality. Forbidden-term checks do not establish truthfulness.'}


def score(report,ratings):
    if not isinstance(ratings.get('reviewer'),str) or not ratings['reviewer'].strip(): raise ValueError('A human reviewer identity is required')
    judgments=ratings.get('ratings',[])
    if len(judgments)!=len(report['results']) or len({r['id'] for r in judgments})!=len(judgments): raise ValueError('Rate every output exactly once')
    by_id={r['id']:r for r in judgments};acceptable=0;hard=[]
    for sample in report['results']:
        row=by_id.get(sample['id'])
        if not row or any(type(row.get(k)) is not bool for k in (*RUBRIC,'needs_substantial_rewrite')): raise ValueError('Each rating must contain boolean rubric fields and rewrite decision')
        if sample['hard_failures'] or not row['truthful'] or not row['correct_audience']: hard.append(sample['id'])
        if all(row[k] for k in RUBRIC) and not row['needs_substantial_rewrite'] and not sample['hard_failures']: acceptable+=1
    return {'reviewer':ratings['reviewer'],'acceptable':acceptable,'total':len(judgments),'hard_failures':hard,
        'release_quality_pass':report['mode']=='live' and len(judgments)==12 and acceptable>=10 and not hard,
        'reference_only':report['mode']!='live'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Makes up to three paid model calls per case, plus provider search charges; never sends mail')
    parser.add_argument('--max-cases',type=int,default=12)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,help='Previously exported report to score without new model calls')
    parser.add_argument('--ratings',type=Path,help='Explicit human ratings; never inferred from a clean linter')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a new output filename')
    if args.report and args.live: parser.error('--report cannot be combined with --live')
    report=json.loads(args.report.read_text(encoding='utf8')) if args.report else evaluate(args.live,args.max_cases)
    if args.ratings: report['human_review']=score(report,json.loads(args.ratings.read_text(encoding='utf8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as file: json.dump(report,file,indent=2)
    print(f"Exported {len(report['results'])} cases; mode={report['mode']}; human ratings={'provided' if args.ratings else 'pending'}")

if __name__=='__main__': main()
