"""Separate literal elemental control from 合中带克 adjudication.

SUP-14 is a classical-text supplement, not an uploaded-page citation. Local
adjudication never establishes full cross-line force or an event outcome.
"""

def review_returning_control(branch, changed_branch, relation, monthly, periods,
        issues, void, month_break, changed_void, changed_break):
    if not relation or relation['element_relation']!='克':return None
    result={'structural_elemental_control':True,'full_effect_certified':False,
        'status':'ELEMENT_CONTROL_RELATION','treat_as_pure_control':True,
        'source_ids':['QA-02','QA-03']}
    if (branch,changed_branch) not in (('子','丑'),('戌','卯'),('申','巳')):return result
    result.update(source_ids=['SUP-14','QA-02'],treat_as_pure_control=False)
    support=[p for p,r in periods.items() if r['element_relation'] in ('生','比和')]
    control=[p for p,r in periods.items() if r['element_relation']=='克']
    result.update(calendar_support=support,calendar_control=control,
        retained_restrictions=[name for name,flag in [('PARENT_VOID',void),('PARENT_MONTH_BREAK',month_break),
            ('CHANGED_VOID',changed_void),('CHANGED_MONTH_BREAK',changed_break)] if flag])
    if issues:result['status']='COMBINED_RELATION_INPUT_UNRESOLVED'
    elif branch=='申':
        if any(r['source']=='寅' for r in periods.values()):
            result['status']='SHEN_SI_YIN_CLASH_AND_PUNISHMENT_REVIEW'
        elif result['retained_restrictions']:
            result['status']='SHEN_SI_COMBINATION_GROWTH_WITH_RESTRICTIONS'
        else:result['status']='SHEN_SI_COMBINATION_GROWTH_LOCAL'
    elif result['retained_restrictions']:
        result['status']='COMBINED_RELATION_RELEASE_PENDING'
    elif support and control:
        result['status']='COMBINED_RELATION_MIXED_SUPPORT_CONTROL'
    elif monthly in ('旺','相') and support:
        result['status']='COMBINATION_DOMINANT_LOCAL'
    elif monthly in ('休','囚','死') and control and not support:
        result['status']='CONTROL_DOMINANT_LOCAL';result['treat_as_pure_control']=True
    else:result['status']='COMBINED_RELATION_DYNAMIC_CONDITIONS_UNRESOLVED'
    return result

def returning_control_requires_review(assessment):
    review=assessment.get('returning_control_review')
    if review:
        return review['status'] not in ('SHEN_SI_COMBINATION_GROWTH_LOCAL','COMBINATION_DOMINANT_LOCAL')
    return any(f['code']=='RETURNING_CONTROL' for f in assessment.get('findings',[]))
