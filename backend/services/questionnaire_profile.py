"""Separate self-reported questionnaire answers from visual model evidence."""
import json

OPTIONS = {
    'gender': ['Male', 'Female'], 'age': ['Child (under 13)', 'Teen', '20s', '30s', '40+'],
    'skinType': ['Oily', 'Dry', 'Combination', 'Normal', 'Not sure'],
    'sensitivity': ['Yes', 'No'], 'skinIssues': ['Acne', 'Dark Spots', 'Wrinkles', 'None'],
    'hydration': ['Oily', 'Dry', 'Balanced'], 'pores': ['Large', 'Small', 'Barely Visible'],
    'texture': ['Smooth', 'Rough', 'Uneven'], 'routine': ['Daily', 'Occasionally', 'Rarely', 'Never'],
    'sunExposure': ['Daily', 'Occasionally', 'Rarely'], 'oiliness': ['Yes', 'No'],
    'tightness': ['Yes', 'No'], 'breakouts': ['Often', 'Sometimes', 'Rarely', 'Never'],
    'concern': ['Aging', 'Hydration', 'Brightening', 'None'],
    'products': ['Sensitive', 'Normal', 'Resistant'],
}

def parse_answers(raw):
    if raw is None:
        return None
    if len(raw) > 8192:
        raise ValueError('Questionnaire is too large.')
    try:
        answers = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError('Questionnaire must contain valid JSON.') from None
    if not isinstance(answers, dict) or set(answers) != set(OPTIONS):
        raise ValueError('Please complete all questionnaire questions.')
    for key, value in answers.items():
        if not isinstance(value, str) or value not in OPTIONS[key]:
            raise ValueError(f'Invalid answer for {key}.')
    return answers


def reconcile(answers, visual):
    effective = dict(visual)
    if answers is None:
        return None, effective
    audience = {
        'gender': answers['gender'], 'age_group': answers['age'],
        'source': 'questionnaire',
        'requires_age_review': answers['age'] in ['Child (under 13)', 'Teen'],
    }
    effective['audience'] = audience
    reported = answers['skinType']
    known = reported != 'Not sure'
    conflict = known and not visual.get('uncertainty_flag', True) and reported != visual['predicted_skin_type']
    if not known:
        source = 'image_model'
        label = 'Uncertain' if visual.get('uncertainty_flag', True) else visual['predicted_skin_type']
        message = 'You selected Not sure, so this estimate comes from the image model.'
        if label == 'Uncertain':
            message += ' The image model is also inconclusive; your questionnaire answer did not cause this uncertainty.'
        if label == 'Uncertain':
            # Transparent fallback from reported skin behaviour, not a trained classifier.
            pattern = None
            if answers['oiliness'] == 'Yes' and answers['tightness'] == 'No' and answers['hydration'] == 'Oily':
                pattern = 'Oily'
            elif answers['oiliness'] == 'No' and answers['tightness'] == 'Yes' and answers['hydration'] == 'Dry':
                pattern = 'Dry'
            elif answers['oiliness'] == 'No' and answers['tightness'] == 'No' and answers['hydration'] == 'Balanced':
                pattern = 'Normal'
            if pattern:
                label, source = pattern, 'questionnaire_pattern'
                message = f'Your reported oiliness, tightness and hydration suggest {pattern.lower()} skin. This is a questionnaire-based estimate; the image model remains inconclusive.'
    elif conflict:
        label, source = 'Uncertain', 'disagreement'
        message = 'Your self-reported skin type and the image estimate disagree. Review your answers or retake the photo; type-specific guidance is withheld.'
    else:
        label, source = reported, 'self_reported'
        message = 'Skin type comes from your questionnaire answer, not a diagnosis from the photo.'
        if visual.get('uncertainty_flag', True):
            message += ' The image model is inconclusive.'
    # Do not attach a visual softmax score to a self-reported/effective type.
    effective.update(predicted_skin_type=label, uncertainty_flag=label == 'Uncertain',
                     source=source)
    if source != 'image_model':
        effective.update(confidence=None, confidence_percentage=None, confidence_level='questionnaire', top_two_margin_percentage=None)
    profile = {'self_reported_skin_type': reported, 'skin_type_for_guidance': label,
               'source': source, 'disagreement': conflict, 'message': message,
               'audience': audience,
               'self_reported_sensitivity': answers['sensitivity'] == 'Yes' or answers['products'] == 'Sensitive',
               'self_reported_concern': answers['skinIssues'],
               'note': 'Questionnaire concerns are self-reported and do not change image concern detections.'}
    return profile, effective
