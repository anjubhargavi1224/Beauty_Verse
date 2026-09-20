from typing import Literal
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from backend.services.face_detection import face_detection_service
from backend.services.skin_regions import skin_region_service
from backend.services.skin_type_classifier import skin_type_classifier_service
from backend.services.skin_concern_classifier import skin_concern_classifier_service
from backend.services.product_search import product_search_service
from backend.services.makeup_demo import estimate_tone, product_query, normalize_products

router = APIRouter(prefix='/api/makeup')

class MakeupSearch(BaseModel):
    category: Literal['lipstick','blush','foundation','concealer']
    skin_type: Literal['Not sure','Dry','Oily','Combination','Normal'] = 'Not sure'
    tone: Literal['Not sure','Fair','Light','Medium','Tan','Deep'] = 'Not sure'
    finish: Literal['Any','Matte','Dewy','Satin'] = 'Any'
    shade: Literal['Any','Rose','Berry','Nude','Coral','Red'] = 'Any'
    age_group: Literal['Adult','Under 18']
    concerns: list[Literal['acne','redness','pigmentation','pores','wrinkles']] = Field(default_factory=list, max_length=5)

def analyze(raw):
    image, faces = face_detection_service.detect(raw)
    if not faces.face_landmarks: return {'success':False,'message':'No face detected. Use an upright, front-facing photo.'}
    landmarks=faces.face_landmarks[0]
    quality=skin_region_service.extract(image,landmarks)['capture_quality']
    if not quality['usable']: return {'success':False,'message':'Use a sharper photo with even lighting.','capture_quality':quality}
    return {'success':True,'capture_quality':quality,'skin_type':skin_type_classifier_service.predict(image,landmarks),
            'skin_concerns':skin_concern_classifier_service.predict(image,landmarks),'tone':estimate_tone(image,landmarks)}

@router.post('/analyze')
async def analyze_makeup(image: UploadFile = File(...)):
    if image.content_type not in ('image/jpeg','image/png','image/webp'):
        raise HTTPException(400,'Choose a JPG, PNG or WEBP image.')
    raw=await image.read(10*1024*1024+1)
    if not raw or len(raw)>10*1024*1024: raise HTTPException(400,'Choose an image smaller than 10 MB.')
    try: return await run_in_threadpool(analyze,raw)
    except Exception: raise HTTPException(422,'Could not analyze this image. Try another clear selfie.') from None

@router.post('/products')
def makeup_products(profile: MakeupSearch):
    if profile.age_group != 'Adult':
        return {'status':'age_review','products':[], 'message':'This demo has no age-verified makeup catalog for under-18s.'}
    if not product_search_service.api_key:
        return {'status':'unavailable','products':[], 'message':'Product search is not configured on the server.'}
    query=product_query(profile.category,profile.skin_type,profile.tone,profile.finish,profile.shade,profile.concerns)
    try:
        products=normalize_products(product_search_service.search_google_shopping(query),profile.category)
    except Exception:
        return {'status':'unavailable','products':[], 'message':'Product search is unavailable. Try again shortly.'}
    return {'status':'completed','query':query,'products':products,
            'message':'Matches to your selected preferences. Confirm ingredients and exact shade with the retailer; the preview is not a simulation of these specific products.' if products else 'No matching listings found. Try a different category or shade.'}
