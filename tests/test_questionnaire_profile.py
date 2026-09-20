import json
import unittest
from backend.services.questionnaire_profile import OPTIONS, parse_answers, reconcile

class QuestionnaireTests(unittest.TestCase):
    def answers(self, **changes):
        result = {key: values[0] for key, values in OPTIONS.items()}
        result.update(changes)
        return result
    def visual(self, label='Oily', uncertain=False):
        return dict(predicted_skin_type=label, uncertainty_flag=uncertain, confidence_percentage=80)
    def test_unrelated_yes_does_not_make_type_oily(self):
        a = self.answers(skinType='Dry', sensitivity='Yes', oiliness='No')
        profile, effective = reconcile(a, self.visual('Dry'))
        self.assertEqual(effective['predicted_skin_type'], 'Dry')
        self.assertTrue(profile['self_reported_sensitivity'])
        self.assertIsNone(effective['confidence_percentage'])
    def test_disagreement_withholds_type(self):
        profile, effective = reconcile(self.answers(skinType='Dry'), self.visual())
        self.assertTrue(profile['disagreement'])
        self.assertTrue(effective['uncertainty_flag'])
        self.assertEqual(effective['predicted_skin_type'], 'Uncertain')
    def test_uncertain_visual_preserves_self_report_not_its_score(self):
        original = self.visual('Combination', True)
        profile, effective = reconcile(self.answers(skinType='Dry'), original)
        self.assertEqual(effective['predicted_skin_type'], 'Dry')
        self.assertEqual(profile['source'], 'self_reported')
        self.assertIsNone(effective['confidence_percentage'])
        self.assertEqual(original['predicted_skin_type'], 'Combination')
    def test_unknown_uses_confident_image_estimate(self):
        original = self.visual()
        profile, effective = reconcile(self.answers(skinType='Not sure'), original)
        self.assertEqual(effective['predicted_skin_type'], 'Oily')
        self.assertFalse(effective['uncertainty_flag'])
        self.assertEqual(effective['confidence_percentage'], 80)
        self.assertEqual(profile['source'], 'image_model')
        self.assertFalse(profile['disagreement'])
        self.assertNotIn('source', original)
    def test_unknown_preserves_image_uncertainty(self):
        original = self.visual('Combination', True)
        profile, effective = reconcile(self.answers(skinType='Not sure'), original)
        self.assertTrue(effective['uncertainty_flag'])
        self.assertEqual(effective['predicted_skin_type'], 'Uncertain')
        self.assertEqual(profile['source'], 'image_model')
        self.assertEqual(original['predicted_skin_type'], 'Combination')
    def test_no_questionnaire_preserves_upload_contract(self):
        original = self.visual()
        profile, effective = reconcile(None, original)
        self.assertIsNone(profile)
        self.assertEqual(effective, original)
    def test_invalid_incomplete_or_extra_answers_rejected(self):
        for raw in ['bad', '[]', '{}', json.dumps(self.answers(skinType='fake')), json.dumps(dict(self.answers(), extra='text'))]:
            with self.assertRaises(ValueError): parse_answers(raw)
        self.assertEqual(parse_answers(json.dumps(self.answers())), self.answers())
        self.assertIsNone(parse_answers(None))

if __name__ == '__main__': unittest.main()
