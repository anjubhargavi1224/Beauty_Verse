import unittest
from backend.services.questionnaire_profile import OPTIONS, reconcile
from backend.services.recommendation_engine import RecommendationEngine

class AudienceTests(unittest.TestCase):
    def generate(self, gender='Male', age='20s'):
        answers = {k: v[0] for k, v in OPTIONS.items()}
        answers.update(gender=gender, age=age, skinType='Not sure')
        _, visual = reconcile(answers, {'predicted_skin_type': 'Oily', 'uncertainty_flag': False})
        plan = {'recommended_ingredients': ['example'], 'routine': {'morning': [
            {'category': 'cleanser', 'recommendation': 'gentle cleanser', 'reason': 'routine'}]}}
        return RecommendationEngine().generate(visual, {'concerns': []}, plan)

    def test_explicit_adult_gender_reaches_search(self):
        for gender, term in [('Male', 'for men'), ('Female', 'for women')]:
            result = self.generate(gender)
            self.assertIn(term, result['product_searches'][0]['query'])
            self.assertEqual(result['audience']['source'], 'questionnaire')

    def test_children_and_teens_cannot_receive_adult_plan_searches(self):
        for age in ['Child (under 13)', 'Teen']:
            result = self.generate(age=age)
            self.assertEqual(result['product_searches'], [])
            self.assertEqual(result['recommended_ingredients'], [])
            self.assertEqual(result['routine'], {'morning': [], 'evening': []})
            self.assertEqual(result['product_selection_status'], 'age_review_required')

    def test_missing_audience_does_not_guess_gender(self):
        query = RecommendationEngine().build_query({'category': 'cleanser'}, 'Uncertain', [])
        self.assertNotIn('for men', query)
        self.assertNotIn('for women', query)

if __name__ == '__main__':
    unittest.main()
