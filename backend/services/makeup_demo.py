"""Demo-only colour sampling and explicit product search preferences."""
from urllib.parse import urlparse

TYPES = ('Not sure', 'Dry', 'Oily', 'Combination', 'Normal')
TONES = ('Not sure', 'Fair', 'Light', 'Medium', 'Tan', 'Deep')

def safe_url(value):
    if not isinstance(value, str): return None
    try:
        parsed = urlparse(value)
        return value if parsed.scheme in ('https', 'http') and parsed.netloc else None
    except ValueError:
        return None

def estimate_tone(image, landmarks):
    import numpy as np
    import cv2
    height, width = image.shape[:2]
    xs = [p.x * width for p in landmarks]
    radius = max(3, int((max(xs) - min(xs)) * .035))
    patches = []
    # Sample both cheek centres; results remain lighting-dependent and editable.
    for index in (205, 425):
        x, y = round(landmarks[index].x * width), round(landmarks[index].y * height)
        patch = image[max(0,y-radius):min(height,y+radius+1), max(0,x-radius):min(width,x+radius+1)]
        if patch.size: patches.append(patch.reshape(-1,3))
    if len(patches) < 2: return {'label': 'Not sure', 'source': 'image_colour_sample', 'hex': None}
    pixels = np.concatenate(patches)
    rgb = np.median(pixels[:, ::-1], axis=0).astype(np.uint8)
    lab = cv2.cvtColor(rgb.reshape(1,1,3), cv2.COLOR_RGB2LAB)[0,0]
    lightness = float(lab[0]) * 100 / 255
    label = next((name for cutoff,name in [(78,'Fair'),(67,'Light'),(54,'Medium'),(40,'Tan')] if lightness >= cutoff), 'Deep')
    return {'label': label, 'hex': '#'+''.join(f'{int(v):02x}' for v in rgb),
            'source':'image_colour_sample', 'note':'Uncalibrated cheek colour estimate. Lighting, makeup and camera processing affect it. Confirm or change before shopping; not an exact foundation match.'}

def product_query(category, skin_type, tone, finish, shade, concerns):
    parts = [category]
    if category in ('foundation', 'concealer'):
        if tone != 'Not sure': parts.append(tone.lower())
        if skin_type != 'Not sure': parts.append(skin_type.lower()+' skin')
        if 'acne' in concerns: parts.append('non comedogenic')
        if finish != 'Any': parts.append(finish.lower())
    else:
        if shade != 'Any': parts.append(shade.lower())
        if finish != 'Any': parts.append(finish.lower())
    return ' '.join(parts) + ' India'

def normalize_products(rows, category):
    result=[];seen=set()
    terms = {'lipstick': ('lipstick','lip color','lip colour'), 'blush':('blush',),
             'foundation':('foundation',), 'concealer':('concealer',)}[category]
    for item in rows:
        if not isinstance(item, dict): continue
        title = str(item.get('title',''))[:300]
        if not any(term in title.lower() for term in terms): continue
        if any(word in title.lower() for word in ('brush','applicator','organizer','holder')): continue
        link = safe_url(item.get('product_link')) or safe_url(item.get('link'))
        if not link or link in seen: continue
        seen.add(link)
        result.append({'title':title,'url':link,'image':safe_url(item.get('thumbnail')),
                       'price':str(item.get('price','Price at retailer'))[:80],
                       'retailer':str(item.get('source','Retailer'))[:100]})
        if len(result)==6:break
    return result
