import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest
import composer,config

spec=importlib.util.spec_from_file_location('evaluate_drafts',Path(__file__).parents[1]/'scripts/evaluate_drafts.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)

def test_reference_pack_is_complete_truthfully_labeled_and_never_calls_provider(monkeypatch):
    provider=Mock(side_effect=AssertionError('No provider calls in reference mode'))
    monkeypatch.setattr(composer,'_generate',provider)
    report=evaluation.evaluate()
    assert len(report['results'])==12 and len({s['id'] for s in report['results']})==12
    assert report['mode']=='curated_reference' and report['human_review']=='pending'
    assert all(not s['hard_failures'] and s['calls']==0 for s in report['results'])
    assert all(s['final_words']>s['pitch_words'] for s in report['results'])
    provider.assert_not_called()

def test_reference_scores_cannot_claim_live_quality_and_lies_fail_hard():
    report=evaluation.evaluate()
    ratings={'reviewer':'Synthetic test reviewer','ratings':[{'id':s['id'],**dict.fromkeys(evaluation.RUBRIC,True),'needs_substantial_rewrite':False} for s in report['results']]}
    assert not evaluation.score(report,ratings)['release_quality_pass']
    report['mode']='live'
    assert evaluation.score(report,ratings)['release_quality_pass']
    ratings['ratings'][0]['truthful']=False
    assert not evaluation.score(report,ratings)['release_quality_pass']
    assert evaluation.score(report,ratings)['hard_failures']

def test_live_mode_is_bounded_and_requires_configured_key(monkeypatch):
    monkeypatch.setattr(config,'GEMINI_API_KEY','')
    with pytest.raises(ValueError): evaluation.evaluate(live=True)
    with pytest.raises(ValueError): evaluation.evaluate(max_cases=13)

def test_live_failure_records_call_count_without_provider_text(monkeypatch):
    monkeypatch.setattr(config,'GEMINI_API_KEY','synthetic')
    error=RuntimeError('private-provider-text');error.generation={'calls':2}
    monkeypatch.setattr(composer,'compose_email',Mock(side_effect=error))
    report=evaluation.evaluate(live=True,max_cases=1)
    assert report['results'][0]['calls']==2 and report['results'][0]['provider_failure']=='RuntimeError'
    assert 'private-provider-text' not in str(report)
