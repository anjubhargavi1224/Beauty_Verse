import unittest
from backend.services.questionnaire_profile import OPTIONS, reconcile
from backend.services.prediction_presenter import prediction_presenter
from backend.services.makeup_demo import product_query, normalize_products

class DemoTests(unittest.TestCase):
    def test_questionnaire_fallback_is_not_visual_confidence(self):
        answers={k:v[0] for k,v in OPTIONS.items()}
        answers.update(skinType='Not sure',oiliness='No',tightness='Yes',hydration='Dry')
        visual={'predicted_skin_type':'Combination','uncertainty_flag':True,'confidence_level':'uncertain','confidence_percentage':45}
        profile,effective=reconcile(answers,visual)
        shown=prediction_presenter.build(effective,{'concerns':[]})
        self.assertEqual(effective['predicted_skin_type'],'Dry')
        self.assertEqual(profile['source'],'questionnaire_pattern')
        self.assertIsNone(effective['confidence_percentage'])
        self.assertEqual(shown['skin_type']['label'],'Dry')
        self.assertIn('questionnaire',shown['summary'])
        self.assertTrue(visual['uncertainty_flag'])
    def test_inconsistent_answers_do_not_force_skin_type(self):
        answers={k:v[0] for k,v in OPTIONS.items()}
        answers.update(skinType='Not sure',oiliness='Yes',tightness='Yes',hydration='Dry')
        _,effective=reconcile(answers,{'predicted_skin_type':'Combination','uncertainty_flag':True})
        self.assertTrue(effective['uncertainty_flag'])
    def test_product_results_reject_unsafe_links_accessories_and_duplicates(self):
        rows=[{'title':'Lipstick','link':'javascript:alert(1)'},
              {'title':'Lipstick brush','link':'https://example.com/brush'},
              {'title':'Rose lipstick','product_link':'https://example.com/lip','thumbnail':'data:x'},
              {'title':'Rose lipstick','link':'https://example.com/lip'},
              {'title':'Face cleanser','link':'https://example.com/cleanser'}]
        result=normalize_products(rows,'lipstick')
        self.assertEqual(len(result),1)
        self.assertIsNone(result[0]['image'])
    def test_concerns_do_not_turn_lipstick_into_acne_treatment(self):
        query=product_query('lipstick','Oily','Deep','Matte','Berry',['acne','redness'])
        self.assertEqual(query,'lipstick berry matte India')
        base=product_query('foundation','Oily','Deep','Matte','Berry',['acne'])
        self.assertIn('non comedogenic',base)
        self.assertNotIn('berry',base)

if __name__=='__main__':unittest.main()
