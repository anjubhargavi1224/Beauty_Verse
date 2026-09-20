import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './VirtualTryOn.css';
const API=import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8000';
const LOOKS={makeup:'/effects/MakeupLook.deepar',comparison:'/effects/Split_View_Look.deepar'};
const TYPES=['Not sure','Dry','Oily','Combination','Normal'];
const CONCERNS=['acne','redness','pigmentation','pores','wrinkles'];
const safeURL=x=>typeof x==='string'&&/^https?:\/\//i.test(x)?x:undefined;
async function limited(promise, seconds, cleanup) {
 let expired=false, timer;
 const pending=Promise.resolve(promise).then(value=>{if(expired){cleanup?.(value);throw new Error('Timed out');}return value;});
 try{return await Promise.race([pending,new Promise((_,reject)=>{timer=setTimeout(()=>{expired=true;reject(new Error('Timed out'));},seconds*1000);})]);}
 finally{clearTimeout(timer);}
}
export default function VirtualTryOn(){
 const {state}=useLocation(), initial=state?.skinAnalysis;
 const initialType=initial?.questionnaire_profile?.skin_type_for_guidance||initial?.skin_type?.predicted_skin_type;
 const [profile,setProfile]=useState({skin_type:TYPES.includes(initialType)?initialType:'Not sure',tone:'Not sure',age_group:'',category:'lipstick',shade:'Any',finish:'Any',concerns:initial?.skin_concerns?.detected_concerns||[]});
 const [analysis,setAnalysis]=useState(initial||null),[file,setFile]=useState(null),[photoURL,setPhotoURL]=useState('');
 const [running,setRunning]=useState(false),[mode,setMode]=useState(''),[busy,setBusy]=useState(false),[analyzing,setAnalyzing]=useState(false),[searching,setSearching]=useState(false);
 const [products,setProducts]=useState(null),[look,setLook]=useState('makeup'),[message,setMessage]=useState('Choose a photo or start your camera.'),[error,setError]=useState('');
 const canvas=useRef(null),video=useRef(null),photo=useRef(null),engine=useRef(null),stream=useRef(null),initializing=useRef(false),epoch=useRef(0),analysisRequest=useRef(null),shoppingRequest=useRef(null);
 function dispose(){epoch.current++;stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;if(video.current)video.current.srcObject=null;try{engine.current?.shutdown();}catch{}engine.current=null;}
 useEffect(()=>()=>{dispose();analysisRequest.current?.abort();shoppingRequest.current?.abort();},[]);
 useEffect(()=>()=>{if(photoURL)URL.revokeObjectURL(photoURL);},[photoURL]);
 function stop(){analysisRequest.current?.abort();analysisRequest.current=null;setAnalyzing(false);dispose();setRunning(false);setMode('');setBusy(initializing.current);setMessage('Camera and try-on stopped.');}
 function change(key,value){shoppingRequest.current?.abort();shoppingRequest.current=null;setSearching(false);setProducts(null);setProfile(p=>({...p,[key]:value}));}
 function resetPerson(){analysisRequest.current?.abort();analysisRequest.current=null;shoppingRequest.current?.abort();shoppingRequest.current=null;setAnalyzing(false);setSearching(false);setAnalysis(null);setProducts(null);setProfile(p=>({...p,skin_type:'Not sure',tone:'Not sure',concerns:[]}));}
 function choosePhoto(e){const picked=e.target.files?.[0];if(!picked)return;if(!['image/jpeg','image/png','image/webp'].includes(picked.type)||picked.size>10*1024*1024){setError('Choose a JPG, PNG or WEBP under 10 MB.');return;}stop();resetPerson();setError('');setFile(picked);setPhotoURL(URL.createObjectURL(picked));setMessage('Photo selected. Analyzing automatically; start photo try-on to preview makeup.');}
 async function start(source){
  if(busy||initializing.current)return;const key=import.meta.env.VITE_DEEPAR_LICENSE_KEY;
  if(!key){setError('Add VITE_DEEPAR_LICENSE_KEY to frontend/.env and restart the frontend to enable try-on.');return;}
  if(source==='photo'&&!file){setError('Choose a photo first.');return;}
  dispose();initializing.current=true;const token=epoch.current;setBusy(true);setRunning(false);setError('');setMessage('Loading try-on and face-tracking resources…');
  let stage='camera permission';
  try{
   if(source==='camera'){resetPerson();const media=await limited(navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:960},height:{ideal:720}},audio:false}),25,media=>media.getTracks().forEach(t=>t.stop()));if(token!==epoch.current){media.getTracks().forEach(t=>t.stop());return;}stream.current=media;video.current.srcObject=media;await video.current.play();analyze('camera');}
   stage='SDK download';setMessage('Loading DeepAR SDK…');const deepar=await limited(import('deepar'),30);if(token!==epoch.current)return;
   stage='SDK license / tracking resources';setMessage('Checking Web license and downloading tracking resources…');const instance=await limited(deepar.initialize({licenseKey:key,canvas:canvas.current,additionalOptions:{cameraConfig:{disableDefaultCamera:true}}}),60,instance=>instance.shutdown());
   if(token!==epoch.current){instance.shutdown();return;}engine.current=instance;stage="makeup effect";setMessage("Loading makeup effect…");await limited(instance.switchEffect(LOOKS.makeup),30);if(token!==epoch.current)return;
   if(source==='camera')instance.setVideoElement(video.current,true);else{await photo.current.decode();if(token!==epoch.current)return;instance.processImage(photo.current);}
   setLook('makeup');setMode(source);setRunning(true);setMessage('Preview ready. Use Original to compare.');
  }catch{if(token===epoch.current){dispose();setBusy(false);setError(`Try-on stopped at: ${stage}. Check camera permission, the Web license/domain and internet access. Restart the frontend after changing .env.`);setMessage('Try-on unavailable; analysis and product search still work.');}}
  finally{initializing.current=false;setBusy(false);}
 }
 async function switchLook(value){if(!engine.current||busy)return;setBusy(true);setError('');const token=epoch.current;try{if(value==='original')engine.current.clearEffect();else await limited(engine.current.switchEffect(LOOKS[value]),30);if(token!==epoch.current)return;if(mode==='photo')engine.current.processImage(photo.current);setLook(value);}catch{if(token===epoch.current)setError('Could not load this look. Restart try-on.');}finally{if(token===epoch.current)setBusy(false);}}
 async function analyze(source){
  if(analyzing)return;shoppingRequest.current?.abort();shoppingRequest.current=null;setSearching(false);setError('');let input=file;
  if((source==='camera'||mode==='camera')&&stream.current){const raw=document.createElement('canvas');raw.width=video.current.videoWidth;raw.height=video.current.videoHeight;if(!raw.width){setError('Wait for the camera to start.');return;}raw.getContext('2d').drawImage(video.current,0,0);input=await new Promise(resolve=>raw.toBlob(resolve,'image/jpeg',.95));}
  if(!input){setError('Choose a photo or start the camera first.');return;}
  const controller=new AbortController();analysisRequest.current?.abort();analysisRequest.current=controller;const timer=setTimeout(()=>controller.abort(),60000);setAnalyzing(true);setAnalysis(null);setProducts(null);
  try{const body=new FormData();body.append('image',input,'selfie.jpg');const response=await fetch(`${API}/api/makeup/analyze`,{method:'POST',body,signal:controller.signal});const data=await response.json();if(!response.ok||!data.success)throw new Error(data.message||data.detail||'Analysis failed.');if(analysisRequest.current!==controller)return;setAnalysis(data);setProfile(p=>({...p,skin_type:TYPES.includes(data.skin_type?.predicted_skin_type)?data.skin_type.predicted_skin_type:'Not sure',tone:data.tone?.label||'Not sure',concerns:data.skin_concerns?.detected_concerns||[]}));}
  catch(e){if(analysisRequest.current===controller)setError(e.name==='AbortError'?'Analysis timed out or was cancelled.':e.message);}
  finally{clearTimeout(timer);if(analysisRequest.current===controller)setAnalyzing(false);}
 }
 // A new source triggers one analysis; rescans are explicit to avoid overlapping CPU inference.
 useEffect(()=>{if(file&&!stream.current)analyze();},[file]);
 // Debounce edits; never query the shopping provider on every video frame.
 const shoppingSignature=JSON.stringify([!!analysis,profile.skin_type,profile.tone,profile.age_group,profile.finish,profile.shade,profile.concerns]);
 useEffect(()=>{
  if(!analysis||!profile.age_group)return;
  const timer=setTimeout(()=>search(),600);
  return ()=>{clearTimeout(timer);shoppingRequest.current?.abort();};
 },[shoppingSignature]);
 async function search(){
  if(!profile.age_group){setError('Select your age group before searching.');return;}
  const controller=new AbortController();shoppingRequest.current?.abort();shoppingRequest.current=controller;
  const timer=setTimeout(()=>controller.abort(),70000);setSearching(true);setProducts(null);setError('');
  const categories=['lipstick','blush','foundation','concealer'], results=[];
  async function one(category){
   try{
    const response=await fetch(`${API}/api/makeup/products`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...profile,category}),signal:controller.signal});
    if(!response.ok)throw new Error('Search unavailable');
    const data=await response.json();return {category,...data};
   }catch{return {category,status:'unavailable',products:[],message:'Search unavailable. Retry product search.'};}
  }
  try{
   for(let i=0;i<categories.length;i+=2){
    if(controller.signal.aborted)break;
    results.push(...await Promise.all(categories.slice(i,i+2).map(one)));
    if(shoppingRequest.current===controller)setProducts({groups:[...results]});
   }
  }finally{
   clearTimeout(timer);
   if(shoppingRequest.current===controller){
    setSearching(false);
    if(controller.signal.aborted)setError('Some product searches timed out. Available matches are shown below.');
   }
  }
 }
 async function save(){try{const href=await engine.current.takeScreenshot();const a=document.createElement('a');a.href=href;a.download='beautyverse-makeup.png';a.click();}catch{setError('Could not save preview. Try again after the effect loads.');}}
 const select=(key,title,options)=><label className="bv-field">{title}<select value={profile[key]} disabled={analyzing} onChange={e=>change(key,e.target.value)}>{options.map(v=><option key={v} value={v}>{v||'Choose age group'}</option>)}</select></label>;
 return <main className="bv-makeup"><header><p className="bv-eyebrow">BEAUTYVERSE / MAKEUP STUDIO</p><h1>Your look, your choice.</h1><p>Explore makeup, check your skin profile, and find products that match your preferences.</p><Link to="/skin-analysis">← Back to skincare</Link></header>
 {error&&<p className="bv-error" role="alert">{error}</p>}
 <div className="bv-columns"><section className="bv-panel"><h2>1. Preview your look</h2>
 <div className="bv-controls"><label className="bv-upload">Upload photo<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy||analyzing} onChange={choosePhoto}/></label><button disabled={busy||analyzing} onClick={()=>start('camera')}>Start camera</button><button disabled={!file||busy||analyzing} onClick={()=>start('photo')}>Try on photo</button><button onClick={stop}>Stop</button></div>
 <video ref={video} muted playsInline style={{display:'none'}}/>
 <div className="bv-preview"><canvas ref={canvas} width="640" height="640" style={{display:running||busy?'block':'none'}}/>{photoURL&&<img ref={photo} src={photoURL} alt="Your selected photo" style={{display:!running&&!busy?'block':'none'}}/>}{!photoURL&&!running&&!busy&&<p>Your preview will appear here.<br/>Camera starts only when you choose it.</p>}</div>
 <p aria-live="polite">{message}</p><div className="bv-controls">{[['original','Original'],['makeup','Makeup look'],['comparison','Split comparison']].map(([v,label])=><button key={v} disabled={!running||busy} aria-pressed={look===v} onClick={()=>switchLook(v)}>{label}</button>)}<button disabled={!running||busy} onClick={save}>Save preview</button></div>
 <p className="bv-note">Demo makeup effects by DeepAR. These are preset looks, not exact simulations of the products below. A free license may show a watermark.</p>
 <button className="bv-primary" disabled={analyzing||busy||(!file&&mode!=='camera')} onClick={analyze}>{analyzing?'Analyzing…':'Analyze original photo / camera frame'}</button><p className="bv-note">Analysis sends the original photo or camera frame to your BeautyVerse backend before makeup effects, automatically after upload or camera startup. Use Analyze again to refresh after changing position.</p>
 </section><section className="bv-panel"><h2>2. Your estimated profile</h2>
 {analysis&&<div className="bv-summary"><p>Image skin-type estimate: <strong>{analysis.skin_type?.predicted_skin_type||'Not available'}</strong>{analysis.skin_type?.uncertainty_flag?' (low confidence)':''}</p>{analysis.tone&&<p>Sampled colour: <span className="bv-colour" style={{background:analysis.tone.hex||'transparent'}}/> {analysis.tone.label}. {analysis.tone.note}</p>}<p>Concern signals: {analysis.skin_concerns?.detected_concerns?.join(', ')||'None detected'}. Borderline: {analysis.skin_concerns?.uncertain_concerns?.join(', ')||'None'}.</p></div>}
 <p>Select your age group to automatically find lipstick, blush, foundation and concealer. You can edit these preferences. Image estimates can be wrong, especially under coloured lighting or makeup.</p>
 <div className="bv-fields">{select('skin_type','Skin type for shopping',TYPES)}{select('tone','Skin tone for shopping',['Not sure','Fair','Light','Medium','Tan','Deep'])}{select('age_group','Age group',['','Adult','Under 18'])}</div>
 <fieldset><legend>Concerns you want to consider</legend>{CONCERNS.map(c=><label className="bv-check" key={c}><input type="checkbox" disabled={analyzing} checked={profile.concerns.includes(c)} onChange={e=>change('concerns',e.target.checked?[...profile.concerns,c]:profile.concerns.filter(x=>x!==c))}/>{c}</label>)}</fieldset>
 <p className="bv-note">Edits are your preferences; they do not change recorded model predictions. Cosmetic estimates are not diagnoses.</p>
 <h2>3. Find makeup products</h2><div className="bv-fields">{select('finish','Finish',['Any','Matte','Dewy','Satin'])}{select('shade','Lip / blush colour preference',['Any','Rose','Berry','Nude','Coral','Red'])}</div><button className="bv-primary" disabled={searching||analyzing} onClick={search}>{searching?'Searching…':'Refresh all product matches'}</button><p className="bv-note">Confirm ingredients and the exact shade with the retailer. Under-18 product recommendations are not available in this demo.</p>
 </section></div>
 {products&&<section className="bv-panel"><h2>Product matches</h2><p role="status">Recommendations across all four categories.</p>{products.groups?.map(group=><div key={group.category}><h3>{group.category}</h3><p>{group.message}</p><div className="bv-products">{group.products?.map((p,i)=><article key={p.url||i}>{safeURL(p.image)&&<img src={safeURL(p.image)} alt="" loading="lazy" referrerPolicy="no-referrer"/>}<h3>{p.title}</h3><p>{p.price} · {p.retailer}</p>{safeURL(p.url)&&<a href={safeURL(p.url)} target="_blank" rel="noopener noreferrer">View at retailer ↗</a>}</article>)}</div></div>)}</section>}
 </main>;
}
