import { useLocation, Link } from "react-router-dom";
import React, { useEffect, useMemo, useRef, useState } from "react";
import LiveCamera from "./LiveCamera";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const PRODUCT_CATEGORY_ORDER = [
  "cleanser",
  "serum",
  "treatment",
  "moisturizer",
  "sunscreen",
];

const categoryDefaultImages = {
  cleanser: "/products/product01.jpg",
  serum: "/products/product04.jpg",
  treatment: "/products/product05.jpg",
  moisturizer: "/products/product07.jpg",
  sunscreen: "/products/product10.jpg",
  toner: "/products/product03.jpg",
  mask: "/products/product12.jpg",
  eye: "/products/product11.jpg",
};

const getCategoryDefaultImage = (cat) => {
  if (!cat) return "/products/product01.jpg";
  const c = String(cat).toLowerCase();
  for (const [key, path] of Object.entries(categoryDefaultImages)) {
    if (c.includes(key)) return path;
  }
  return "/products/product01.jpg";
};

const SkinAnalysis = () => {
  const location = useLocation();
  const [useQuestionnaire, setUseQuestionnaire] = useState(true);
  const questionnaire = useQuestionnaire ? location.state?.questionnaire : null;
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [inputMode, setInputMode] = useState("upload");

  const fileInputRef = useRef(null);
  const resultsRef = useRef(null);
  const analysisRequest = useRef(null);
  const [analysisStage, setAnalysisStage] = useState("");
  useEffect(() => () => analysisRequest.current?.abort(), []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const resetAnalysis = () => {
    setAnalysis(null);
    setError("");
  };

  const handleFile = (file) => {
    if (isAnalyzing) return;
    resetAnalysis();
    if (!file) return;

    const allowedTypes = [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "image/webp",
    ];

    if (!allowedTypes.includes(file.type)) {
      setError("Please choose a JPG, JPEG, PNG, or WEBP image.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("Please choose an image smaller than 10 MB.");
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);

    const nextPreview = URL.createObjectURL(file);
    setSelectedFile(file);
    setPreviewUrl(nextPreview);
    setInputMode("upload");
  };

  const handleFileInput = (event) => {
    handleFile(event.target.files?.[0]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    handleFile(event.dataTransfer.files?.[0]);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const analyzeSkin = async () => {
    if (!selectedFile) {
      setError(
        "Please upload a clear selfie before starting the analysis."
      );
      return;
    }

    analysisRequest.current?.abort();
    const controller = new AbortController();
    analysisRequest.current = controller;
    let timer = setTimeout(() => controller.abort(), 60000);
    setAnalysisStage("Analyzing skin pattern, visible concerns, and personalizing recommendations…");
    setIsAnalyzing(true);
    setError("");
    setAnalysis(null);

    try {
      const formData = new FormData();
      formData.append("image", selectedFile);
      if (questionnaire) formData.append("questionnaire", JSON.stringify(questionnaire));

      const response = await fetch(
        `${API_BASE_URL}/api/beautyverse-analysis`,
        {
          method: "POST",
          body: formData,
          signal: controller.signal,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Beautyverse could not analyze the image."
        );
      }

      if (!data.success) {
        if (data.reason === "no_face_detected") {
          throw new Error(
            "We couldn't detect a face. Try a clear, front-facing selfie."
          );
        }

        if (data.reason === "image_quality") {
          const quality = data.capture_quality;

          if (quality?.focus_status === "possibly_blurry") {
            throw new Error(
              "The photo appears slightly blurry. Retake it while keeping the camera steady."
            );
          }

          if (
            quality?.lighting_status === "too_dark" ||
            quality?.lighting_status === "underexposed"
          ) {
            throw new Error(
              "The image is too dark. Try again in brighter, even lighting."
            );
          }

          if (
            quality?.lighting_status === "too_bright" ||
            quality?.lighting_status === "overexposed"
          ) {
            throw new Error(
              "The image is overexposed. Try softer, more even lighting."
            );
          }

          throw new Error(
            "This photo isn't suitable for analysis. Try a clearer selfie in even lighting."
          );
        }

        throw new Error(
          data.message || "Beautyverse could not analyze this image."
        );
      }

      setAnalysis(data);

      window.setTimeout(() => {
        resultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 150);
    } catch (err) {
      console.error("Beautyverse analysis error:", err);
      setError(
        err.name === "AbortError"
          ? "This request took too long. Check that the backend server is running and try again."
          : err.message || "Something went wrong while analysing your skin."
      );
    } finally {
      clearTimeout(timer);
      setAnalysisStage("");
      setIsAnalyzing(false);
    }
  };

  const removeImage = () => {
    setUseQuestionnaire(false);
    if (previewUrl) URL.revokeObjectURL(previewUrl);

    setSelectedFile(null);
    setPreviewUrl("");
    setAnalysis(null);
    setError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const captureQuality = analysis?.analysis?.capture_quality;
  const rawSkinType = analysis?.analysis?.skin_type;
  const rawSkinTone = analysis?.analysis?.skin_tone;
  const presentation = analysis?.analysis?.presentation;
  const skinTypePresentation = presentation?.skin_type;
  const skinTonePresentation = presentation?.skin_tone || rawSkinTone;
  const concernPresentation = presentation?.concerns || [];
  const regionalSummary = analysis?.analysis?.regional_summary;
  const recommendations = analysis?.recommendations || analysis?.analysis?.recommendations || {};
  const rawLive = recommendations?.live_products || analysis?.live_products;
  const liveProducts = Array.isArray(rawLive)
    ? rawLive
    : Array.isArray(rawLive?.products)
    ? rawLive.products
    : [];

  useEffect(() => {
    if (analysis) {
      console.log("[BeautyVerse] live_products count:", liveProducts?.length);
    }
  }, [analysis, liveProducts]);

  const detectedSkinTypeLabel = skinTypePresentation?.label || rawSkinType?.predicted_skin_type || "Balanced";
  const skinTypeConfidence = rawSkinType?.confidence_percentage ? `${rawSkinType.confidence_percentage}%` : null;
  const toneLabel = skinTonePresentation?.shade_description || rawSkinTone?.complexion || rawSkinTone?.fitzpatrick_scale || null;
  const undertoneLabel = skinTonePresentation?.undertone || rawSkinTone?.undertone || null;

  const regionalFinding = useMemo(() => {
    if (!regionalSummary) return null;
    const parts = [];
    if (regionalSummary.tzone_shine_index != null) {
      const shine = Math.round(Number(regionalSummary.tzone_shine_index) * 100);
      parts.push(`T-Zone Shine: ${shine}%`);
    }
    if (regionalSummary.average_erythema_index != null) {
      parts.push(`Erythema Index: ${Number(regionalSummary.average_erythema_index).toFixed(1)}`);
    } else if (regionalSummary.average_texture_roughness != null) {
      parts.push(`Texture Roughness: ${Math.round(Number(regionalSummary.average_texture_roughness) * 100)}%`);
    }
    return parts.length ? parts.join(" • ") : null;
  }, [regionalSummary]);

  const primaryConcernsList = useMemo(() => {
    const raw = concernPresentation?.primary_concerns || concernPresentation || [];
    return raw
      .map((c) => (typeof c === "object" && c !== null ? (c.label || c.title || c.concern || "") : String(c || "")))
      .filter(Boolean)
      .slice(0, 4);
  }, [concernPresentation]);

  const profileSummaryText = useMemo(() => {
    if (recommendations?.skin_profile && typeof recommendations.skin_profile === "string" && recommendations.skin_profile.trim().length > 15) {
      return recommendations.skin_profile;
    }
    const parts = [];
    if (detectedSkinTypeLabel) {
      parts.push(`Skin Type: ${detectedSkinTypeLabel}${skinTypeConfidence ? ` (${skinTypeConfidence} confidence)` : ""}`);
    }
    if (toneLabel) {
      parts.push(`Complexion: ${toneLabel}${undertoneLabel ? ` with ${undertoneLabel} undertones` : ""}`);
    }
    if (primaryConcernsList?.length) {
      parts.push(`Target Concerns: ${primaryConcernsList.join(", ")}`);
    }
    if (regionalFinding) {
      parts.push(`Regional Findings: ${regionalFinding}`);
    }
    return parts.length
      ? parts.join(". ") + "."
      : `${detectedSkinTypeLabel} skin profile analyzed for personalized cosmetic care.`;
  }, [recommendations?.skin_profile, detectedSkinTypeLabel, skinTypeConfidence, toneLabel, undertoneLabel, primaryConcernsList, regionalFinding]);

  const skinGoalsList = useMemo(() => {
    if (recommendations?.skin_goals?.length) {
      return recommendations.skin_goals;
    }
    if (primaryConcernsList?.length) {
      return primaryConcernsList.map((c) => `Target and soothe ${c} while protecting skin barrier integrity`);
    }
    return [
      `Maintain optimal hydration and barrier protection for ${detectedSkinTypeLabel} skin`,
      "Enhance cellular turnover with gentle daily antioxidant care",
      "Shield against environmental oxidative stressors and UV exposure",
    ];
  }, [recommendations?.skin_goals, primaryConcernsList, detectedSkinTypeLabel]);

  const safeMorningSteps = useMemo(() => {
    const r = recommendations?.routine?.morning || analysis?.routine?.morning;
    if (Array.isArray(r) && r.length > 0) return r;
    const st = detectedSkinTypeLabel.toLowerCase();
    return [
      {
        step: 1,
        category: "Cleanser",
        recommendation: st.includes("oil") || st.includes("comb") ? "Low-pH balancing gel cleanser" : "Gentle hydrating cream-to-foam cleanser",
        reason: "Gently lifts overnight sebum and metabolic residue without disrupting natural barrier lipids.",
      },
      {
        step: 2,
        category: "Serum",
        recommendation: "Antioxidant protective barrier serum",
        reason: "Defends against daytime environmental oxidants and enhances skin radiance.",
      },
      {
        step: 3,
        category: "Moisturizer",
        recommendation: st.includes("oil") ? "Oil-free light water gel" : "Ceramide-rich nourishing lotion",
        reason: "Locks in essential hydration and maintains barrier elasticity throughout the day.",
      },
      {
        step: 4,
        category: "Sunscreen",
        recommendation: "Broad-Spectrum SPF 50+ PA++++",
        reason: "Provides broad-spectrum UV shielding against hyperpigmentation and photo-damage.",
      },
    ];
  }, [recommendations?.routine?.morning, analysis?.routine?.morning, detectedSkinTypeLabel]);

  const safeEveningSteps = useMemo(() => {
    const r = recommendations?.routine?.evening || analysis?.routine?.evening;
    if (Array.isArray(r) && r.length > 0) return r;
    return [
      {
        step: 1,
        category: "Cleanser",
        recommendation: "Gentle purifying double-cleanse face wash",
        reason: "Thoroughly removes daytime sunscreen, pollutants, and sebum build-up.",
      },
      {
        step: 2,
        category: "Treatment",
        recommendation: "Restorative overnight corrective treatment",
        reason: "Accelerates overnight cellular repair, targeting active concerns during the resting phase.",
      },
      {
        step: 3,
        category: "Moisturizer",
        recommendation: "Overnight barrier recovery cream with ceramides and peptides",
        reason: "Supports overnight lipid synthesis and prevents trans-epidermal water loss.",
      },
    ];
  }, [recommendations?.routine?.evening, analysis?.routine?.evening]);

  const discoveryCards = useMemo(() => {
    if (recommendations?.product_searches?.length) {
      return recommendations.product_searches.map((s, idx) => {
        const cat = s.display_category || s.category || "Skincare Step";
        return {
          ...s,
          display_category: cat,
          category: s.category || s.display_category || "Skincare",
          routine_requirement: s.routine_requirement || s.query || "Formulation tailored to your routine step.",
          routine_reason: s.routine_reason || s.reason || "Supports targeted barrier protection and active concern treatment.",
          target_actives: s.desired_ingredients || s.target_actives || s.actives || [],
          used_in: s.used_in || [],
          step: s.step || idx + 1,
          image_url: s.image_url || s.thumbnail || getCategoryDefaultImage(cat),
          amazon_search_url: s.amazon_search_url || `https://www.amazon.in/s?k=${encodeURIComponent(s.query || s.category)}`,
          nykaa_search_url: s.nykaa_search_url || `https://www.nykaa.com/search/result/?q=${encodeURIComponent(s.query || s.category)}`,
        };
      });
    }
    const combined = [
      ...safeMorningSteps.map((m) => ({ ...m, used_in: ["Morning"] })),
      ...safeEveningSteps.map((e) => ({ ...e, used_in: ["Evening"] })),
    ];
    return combined.map((step, idx) => {
      const cat = step.category || step.title || step.step || "Skincare";
      const query = `${cat} for ${detectedSkinTypeLabel} skin`.trim();
      return {
        step: step.step || idx + 1,
        category: cat,
        display_category: cat,
        used_in: step.used_in || [],
        query: query,
        routine_requirement: step.recommendation || step.description || "Formulation tailored for your routine step.",
        routine_reason: step.reason || "Selected to maintain skin balance and target identified concerns.",
        target_actives: Array.isArray(step.actives) ? step.actives : (step.target_actives || []),
        image_url: step.image_url || step.thumbnail || getCategoryDefaultImage(cat),
        amazon_search_url: `https://www.amazon.in/s?k=${encodeURIComponent(query)}`,
        nykaa_search_url: `https://www.nykaa.com/search/result/?q=${encodeURIComponent(query)}`,
      };
    });
  }, [recommendations?.product_searches, safeMorningSteps, safeEveningSteps, detectedSkinTypeLabel]);

  const productMessage = recommendations?.product_selection_status === "age_review_required"
    ? "Automatic product selection is paused for this child or teen because age suitability has not been verified."
    : recommendations?.plan_status === "temporarily_unavailable"
      ? "The routine generator is unavailable, so it could not prepare product searches."
      : recommendations?.live_products?.status === "unavailable"
        ? "Product search is unavailable. Your image analysis completed, but shopping results could not be retrieved."
        : !recommendations?.product_searches?.length
          ? "No product searches were generated for this analysis."
          : "No products survived the current search and matching filters.";

  const downloadDiagnostics = () => {
    // Explicit fields only: no image bytes, API keys, or provider error URLs.
    const report = {
      schema_version: 1,
      analysis: {
        capture_quality: captureQuality,
        skin_type: rawSkinType,
        skin_tone: rawSkinTone,
        skin_concerns: analysis?.analysis?.skin_concerns,
        regional_summary: regionalSummary,
        questionnaire_profile: analysis?.analysis?.questionnaire_profile,
      },
      recommendations: {
        plan_status: recommendations?.plan_status,
        product_selection_status: recommendations?.product_selection_status,
        search_count: recommendations?.product_searches?.length || 0,
        shopping_status: recommendations?.live_products?.status,
        product_count: liveProducts.length,
        filtered_counts: recommendations?.live_products?.filter_summary,
        search_failures: recommendations?.live_products?.search_failures,
        error_type: recommendations?.live_products?.error_type,
      },
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `beautyverse-diagnostics-${Date.now()}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const groupedProducts = useMemo(() => {
    const groups = {};

    liveProducts.forEach((product) => {
      const category = (product.category || "other").toLowerCase();
      if (!groups[category]) groups[category] = [];
      groups[category].push(product);
    });

    return groups;
  }, [liveProducts]);

  const orderedProductGroups = useMemo(() => {
    const categories = Object.keys(groupedProducts);

    categories.sort((a, b) => {
      const aIndex = PRODUCT_CATEGORY_ORDER.indexOf(a);
      const bIndex = PRODUCT_CATEGORY_ORDER.indexOf(b);
      return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
    });

    return categories.map((category) => ({
      category,
      products: groupedProducts[category],
    }));
  }, [groupedProducts]);

  const confirmedConcernCount =
    presentation?.confirmed_concerns?.length || 0;

  const recheckCount =
    presentation?.needs_recheck?.length || 0;

  return (
    <main className="min-h-screen bg-[#f7f4f1] text-[#1d1b19]">
      <section className="px-5 sm:px-6 md:px-10 lg:px-16 pt-10 md:pt-16 pb-8">
        <div className="max-w-7xl mx-auto">
          <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
            <span className="h-2 w-2 rounded-full bg-[#8c6f66]" />
            Beautyverse AI
          </div>

          <div className="mt-7 grid lg:grid-cols-[1fr_0.72fr] gap-8 lg:items-end">
            <div>
              <h1 className="max-w-4xl text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-semibold tracking-[-0.045em] leading-[0.98]">
                A smarter look at
                <span className="block text-stone-400">your skin.</span>
              </h1>
            </div>

            <div className="lg:pb-2">
              <p className="max-w-xl text-base md:text-lg text-stone-600 leading-relaxed">
                Upload a selfie or use live camera analysis. Beautyverse combines facial
                localisation, image-quality checks, trained skin-analysis
                models and dynamic skincare planning to build a cosmetic skin
                profile and routine.
              </p>

              <p className="mt-4 text-xs leading-relaxed text-stone-400">
                Cosmetic skincare guidance only. Beautyverse does not diagnose
                medical skin conditions.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 sm:px-6 md:px-10 lg:px-16 pb-16">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-[1.08fr_0.92fr] gap-6">
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              className="rounded-[32px] bg-white border border-stone-200 p-5 md:p-7 shadow-[0_20px_70px_rgba(28,25,23,0.05)]"
            >
              <div className="mb-5 rounded-2xl bg-stone-50 p-4 text-sm">
                {questionnaire ? <>
                  <p>Questionnaire attached. Self-reported skin type: <strong>{questionnaire.skinType}</strong>.</p>
                  <p>Use these answers only for the person in the photo. No visual concerns are confirmed by this questionnaire.</p>
                  <button type="button" disabled={isAnalyzing} className="mt-2 underline"
                    onClick={() => { setUseQuestionnaire(false); resetAnalysis(); }}>Remove questionnaire</button>
                </> : <p><Link className="underline" to="/questionnaire">Complete the existing questionnaire</Link> to include your answers. You can also analyze a photo without it.</p>}
              </div>
              <div className="mb-5 flex gap-3" aria-label="Choose image source">
                <button type="button" disabled={isAnalyzing} aria-pressed={inputMode === "upload"}
                  onClick={() => setInputMode("upload")}
                  className={`rounded-full px-5 py-3 ${inputMode === "upload" ? "bg-stone-900 text-white" : "bg-stone-100"}`}>Upload photo</button>
                <button type="button" disabled={isAnalyzing} aria-pressed={inputMode === "camera"}
                  onClick={() => { resetAnalysis(); setInputMode("camera"); }}
                  className={`rounded-full px-5 py-3 ${inputMode === "camera" ? "bg-stone-900 text-white" : "bg-stone-100"}`}>Live camera</button>
              </div>
              {inputMode === "camera" ? (
                <LiveCamera key={JSON.stringify(questionnaire || null)} apiBaseUrl={API_BASE_URL} onCapture={handleFile} disabled={isAnalyzing} questionnaire={questionnaire} />
              ) : !previewUrl ? (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full min-h-[500px] rounded-[26px] border border-dashed border-stone-300 bg-[#fbfaf9] px-6 flex flex-col items-center justify-center text-center transition hover:border-stone-500 hover:bg-white"
                >
                  <div className="h-16 w-16 rounded-full bg-[#1d1b19] text-white flex items-center justify-center text-3xl font-light">
                    +
                  </div>

                  <p className="mt-7 text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
                    Start your analysis
                  </p>

                  <h2 className="mt-3 text-2xl md:text-3xl font-semibold tracking-tight">
                    Upload a clear selfie
                  </h2>

                  <p className="mt-3 max-w-md text-stone-500 leading-relaxed">
                    Face the camera directly, use even lighting and avoid heavy
                    shadows or strong beauty filters.
                  </p>

                  <div className="mt-8 flex flex-wrap justify-center gap-2 text-xs text-stone-500">
                    <span className="rounded-full bg-stone-100 px-3 py-2">
                      JPG / PNG / WEBP
                    </span>
                    <span className="rounded-full bg-stone-100 px-3 py-2">
                      Up to 10 MB
                    </span>
                  </div>
                </button>
              ) : (
                <div className="relative min-h-[500px] overflow-hidden rounded-[26px] bg-stone-100">
                  <img
                    src={previewUrl}
                    alt="Selected selfie"
                    className="absolute inset-0 h-full w-full object-cover"
                  />

                  <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-black/10" />

                  <div className="absolute left-5 top-5 rounded-full bg-white/90 backdrop-blur px-4 py-2 text-xs font-semibold">
                    Selfie ready
                  </div>

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="absolute right-5 top-5 rounded-full bg-white/90 backdrop-blur px-4 py-2 text-xs font-semibold transition hover:bg-white"
                  >
                    Change photo
                  </button>

                  <div className="absolute inset-x-5 bottom-5 rounded-[20px] border border-white/20 bg-black/35 p-4 text-white backdrop-blur-md">
                    <p className="text-sm font-semibold">
                      Ready for Beautyverse analysis
                    </p>

                    <p className="mt-1 text-xs text-white/70">
                      Your image is sent only when you select Analyze My Skin.
                    </p>
                  </div>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleFileInput}
              />

              {error && (
                <div className="mt-5 rounded-[20px] border border-red-100 bg-red-50 px-5 py-4">
                  <p className="font-semibold text-red-800">
                    We couldn't complete the analysis
                  </p>

                  <p className="mt-1 text-sm leading-relaxed text-red-600">
                    {error}
                  </p>
                </div>
              )}

              <button
                type="button"
                onClick={analyzeSkin}
                disabled={!selectedFile || isAnalyzing || inputMode === "camera"}
                className={`mt-5 w-full rounded-full py-4 font-semibold transition ${
                  !selectedFile || isAnalyzing || inputMode === "camera"
                    ? "cursor-not-allowed bg-stone-200 text-stone-400"
                    : "bg-[#1d1b19] text-white hover:bg-black"
                }`}
              >
                {isAnalyzing
                  ? "Building your skin profile..."
                  : "Analyze My Skin"}
              </button>
            </div>

            <aside className="rounded-[32px] bg-[#dfd5ce] p-7 md:p-10">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                What happens next
              </p>

              <h2 className="mt-4 max-w-lg text-3xl md:text-4xl font-semibold tracking-tight">
                From selfie to a personalized cosmetic routine.
              </h2>

              <div className="mt-10 space-y-3">
                <MethodStep
                  number="01"
                  title="Face & quality check"
                  text="MediaPipe locates facial landmarks while Beautyverse checks lighting, contrast and focus."
                />

                <MethodStep
                  number="02"
                  title="Skin pattern analysis"
                  text="EfficientNet models estimate cosmetic skin type and visible concern signals."
                />

                <MethodStep
                  number="03"
                  title="Prediction interpretation"
                  text="Borderline results are separated from confirmed signals instead of being treated as certain."
                />

                <MethodStep
                  number="04"
                  title="Dynamic skincare plan"
                  text="The current predictions are converted into goals, ingredients and morning/evening routine guidance."
                />

                <MethodStep
                  number="05"
                  title="Live product discovery"
                  text="Products are retrieved live and filtered against your generated routine and current prediction profile."
                />
              </div>
            </aside>
          </div>
        </div>
      </section>

      {isAnalyzing && <p role="status" className="max-w-7xl mx-auto px-6 py-4">{analysisStage}</p>}
      {analysis?.success && <div className="max-w-7xl mx-auto px-6 py-4"><Link className="text-purple-700 underline font-semibold" to="/virtual-try-on" state={{ skinAnalysis: analysis.analysis }}>Continue to makeup & virtual try-on</Link></div>}
      {analysis?.analysis?.questionnaire_profile && (
        <section className="mx-auto mb-8 max-w-7xl rounded-2xl border border-stone-200 bg-white p-6" aria-label="Questionnaire and image comparison">
          <h2 className="text-xl font-semibold">Skin type for guidance: {analysis.analysis.questionnaire_profile.skin_type_for_guidance}</h2>
          <p className="mt-2">Self-reported: {analysis.analysis.questionnaire_profile.self_reported_skin_type}</p>
          <p className="mt-2">{analysis.analysis.questionnaire_profile.message}</p>
          <p className="mt-2 text-sm">{analysis.analysis.questionnaire_profile.note}</p>
          {analysis.analysis.questionnaire_profile.audience && <p className="mt-2 text-sm">
            Product audience (from questionnaire): {analysis.analysis.questionnaire_profile.audience.gender}, {analysis.analysis.questionnaire_profile.audience.age_group}.
            {analysis.analysis.questionnaire_profile.audience.requires_age_review
              ? " Automatic product recommendations are withheld until age suitability can be verified for this child or teen."
              : " Product searches use this audience; retailer results still need suitability checks."}
          </p>}
        </section>
      )}
      {isAnalyzing && !analysis && (
        <section className="px-5 sm:px-6 md:px-10 lg:px-16 pb-16">
          <div className="max-w-7xl mx-auto">
            <div className="rounded-[32px] border border-stone-200 bg-white p-8 md:p-12">
              <div className="mx-auto max-w-xl text-center">
                <div className="mx-auto h-12 w-12 rounded-full border-[3px] border-stone-200 border-t-[#1d1b19] animate-spin" />

                <h2 className="mt-6 text-2xl font-semibold">
                  Building your Beautyverse report
                </h2>

                <p className="mt-3 text-stone-500 leading-relaxed">
                  Checking image quality, running skin-pattern models,
                  generating your routine and finding live product matches.
                </p>
              </div>

              <div className="mt-9 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  "Face & quality",
                  "Skin type",
                  "Visible concerns",
                  "Routine & products",
                ].map((item, index) => (
                  <div
                    key={item}
                    className="rounded-2xl bg-stone-50 px-4 py-4 text-sm text-stone-600"
                  >
                    <span className="mr-2 text-stone-400">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {analysis && (
        <section
          ref={resultsRef}
          className="px-5 sm:px-6 md:px-10 lg:px-16 pb-24 scroll-mt-8"
        >
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5 pb-8">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-400">
                  Your Beautyverse Report
                </p>

                <h2 className="mt-3 text-4xl md:text-5xl font-semibold tracking-tight">
                  Your skin profile
                </h2>
              </div>

              <div className="flex flex-wrap gap-2">
                <ReportPill>
                  {confirmedConcernCount} confirmed concern
                  {confirmedConcernCount === 1 ? "" : "s"}
                </ReportPill>

                <ReportPill>
                  {recheckCount} result{recheckCount === 1 ? "" : "s"} to recheck
                </ReportPill>

                <ReportPill>
                  {liveProducts.length} live product
                  {liveProducts.length === 1 ? "" : "s"}
                </ReportPill>
              </div>
            </div>

            <div className="grid xl:grid-cols-[0.72fr_1.28fr] gap-6">
              <div className="relative min-h-[520px] overflow-hidden rounded-[32px] bg-stone-200">
                {previewUrl && (
                  <img
                    src={previewUrl}
                    alt="Analyzed selfie"
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                )}

                <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/5 to-transparent" />

                <div className="absolute inset-x-6 bottom-6 text-white">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/65">
                    Analyzed image
                  </p>

                  <p className="mt-2 text-sm text-white/80">
                    Capture quality:{" "}
                    <span className="font-semibold text-white capitalize">
                      {captureQuality?.usable ? "Passed" : "Review"}
                    </span>
                  </p>
                </div>
              </div>

              <div className="rounded-[32px] bg-[#1d1b19] p-7 md:p-10 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/45">
                  Primary skin pattern
                </p>

                <div className="mt-5 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                  <div>
                    <h3 className="text-4xl sm:text-5xl md:text-6xl font-semibold tracking-tight">
                      {skinTypePresentation?.label ||
                        rawSkinType?.predicted_skin_type}
                    </h3>

                    <p className="mt-3 text-white/60">
                      {skinTypePresentation?.preference_label ||
                        rawSkinType?.confidence_level}
                    </p>
                  </div>

                  <div className="md:text-right">
                    <p className="text-3xl font-semibold">
                      {skinTypePresentation?.model_score_percentage ??
                        rawSkinType?.confidence_percentage}
                      %
                    </p>

                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-white/40">
                      Model score
                    </p>
                  </div>
                </div>

                <p className="mt-8 max-w-3xl text-base md:text-lg leading-relaxed text-white/75">
                  {presentation?.summary ||
                    skinTypePresentation?.summary ||
                    recommendations?.skin_profile}
                </p>

                <div className="mt-8 rounded-[24px] border border-white/10 bg-white/[0.06] p-5">
                  <p className="text-sm leading-relaxed text-white/65">
                    {skinTypePresentation?.score_note ||
                      "Model scores describe prediction strength and are not clinical measurements."}
                  </p>
                </div>

                <div className="mt-9 grid sm:grid-cols-2 gap-x-8 gap-y-5">
                  {rawSkinType?.probabilities?.map((item) => (
                    <ProbabilityBar
                      key={item.skin_type}
                      label={item.skin_type}
                      percentage={item.percentage}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 grid md:grid-cols-2 xl:grid-cols-4 gap-4">
              <SummaryCard
                eyebrow="Skin type"
                title={`${skinTypePresentation?.label || rawSkinType?.predicted_skin_type} pattern`}
                text={
                  skinTypePresentation?.summary ||
                  "Beautyverse selected the highest scoring skin-type class from the current selfie."
                }
              />

              <SkinToneCard tone={skinTonePresentation} />

              <SummaryCard
                eyebrow="Primary visible concern"
                title={
                  presentation?.confirmed_concerns?.[0] ||
                  "Balanced skin"
                }
                text={
                  confirmedConcernCount > 0
                    ? `Observed ${confirmedConcernCount} area${confirmedConcernCount > 1 ? "s" : ""} of focus: ${presentation?.confirmed_concerns?.join(", ")}.`
                    : "No strong visual concern crossed the calibrated detection threshold in this image."
                }
              />

              <SummaryCard
                eyebrow="Capture quality"
                title={captureQuality?.usable ? "Analysis-ready" : "Review image"}
                text={`Lighting: ${formatStatus(
                  captureQuality?.lighting_status
                )}. Focus: ${formatStatus(captureQuality?.focus_status)}.`}
              />
            </div>

            {regionalSummary && (
              <RegionalObservationsCard summary={regionalSummary} />
            )}

            {concernPresentation.length > 0 && (
              <section className="mt-14">
                <SectionHeading
                  eyebrow="Visible concern analysis"
                  title="What the model saw"
                  description="Beautyverse separates confirmed, borderline and below-threshold signals. Borderline results are shown for transparency but do not drive targeted product recommendations."
                />

                <div className="mt-7 grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
                  {concernPresentation.map((concern) => (
                    <PresentedConcernCard
                      key={concern.id}
                      concern={concern}
                    />
                  ))}
                </div>

                {recheckCount > 0 && (
                  <div className="mt-4 rounded-[24px] border border-[#e8d8a7] bg-[#fff8e5] p-5 md:p-6">
                    <div className="flex gap-4">
                      <div className="h-10 w-10 shrink-0 rounded-full bg-white flex items-center justify-center font-semibold text-[#8c6f25]">
                        ?
                      </div>

                      <div>
                        <p className="font-semibold text-[#604d1f]">
                          Some results would benefit from another selfie
                        </p>

                        <p className="mt-1 text-sm leading-relaxed text-[#806b35]">
                          {presentation?.needs_recheck?.join(", ")} are close to
                          their decision thresholds. Beautyverse keeps them out
                          of targeted recommendation logic.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </section>
            )}

            <section className="mt-14">
              <SectionHeading
                eyebrow="AI-personalized strategy"
                title="Your skincare plan"
                description="The routine below is generated from your current skin-type pattern and confirmed concern signals rather than from a fixed routine template."
              />

              <div className="mt-7 rounded-[32px] bg-[#dfd5ce] p-7 md:p-10">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">
                  Profile summary
                </p>

                <p className="mt-4 max-w-5xl text-2xl md:text-3xl leading-snug font-medium tracking-tight text-stone-900">
                  {profileSummaryText}
                </p>

                {/* Actual Profile Attributes from Backend Analysis */}
                <div className="mt-6 flex flex-wrap gap-2.5">
                  <div className="rounded-full bg-white/80 border border-stone-300/60 px-4 py-1.5 text-xs font-semibold text-stone-800 shadow-2xs">
                    <span className="text-stone-500 font-medium">Skin Type: </span>
                    <span className="capitalize">{detectedSkinTypeLabel}</span> {skinTypeConfidence && <span className="text-stone-500 font-normal">({skinTypeConfidence})</span>}
                  </div>
                  {toneLabel && (
                    <div className="rounded-full bg-white/80 border border-stone-300/60 px-4 py-1.5 text-xs font-semibold text-stone-800 shadow-2xs">
                      <span className="text-stone-500 font-medium">Tone: </span>
                      <span>{toneLabel}</span>{undertoneLabel ? <span className="text-stone-500 font-normal"> • {undertoneLabel}</span> : null}
                    </div>
                  )}
                  {primaryConcernsList.length > 0 && (
                    <div className="rounded-full bg-white/80 border border-stone-300/60 px-4 py-1.5 text-xs font-semibold text-stone-800 shadow-2xs">
                      <span className="text-stone-500 font-medium">Detected Concerns: </span>
                      <span>{primaryConcernsList.join(", ")}</span>
                    </div>
                  )}
                  {regionalFinding && (
                    <div className="rounded-full bg-white/80 border border-stone-300/60 px-4 py-1.5 text-xs font-semibold text-stone-800 shadow-2xs">
                      <span className="text-stone-500 font-medium">Regional Findings: </span>
                      <span>{regionalFinding}</span>
                    </div>
                  )}
                </div>

                {skinGoalsList?.length > 0 && (
                  <div className="mt-8 grid md:grid-cols-3 gap-3">
                    {skinGoalsList.map((goal, index) => {
                      const goalText =
                        typeof goal === "object" && goal !== null
                          ? (goal.goal || goal.text || goal.description || goal.name || "")
                          : String(goal || "");

                      if (!goalText) return null;

                      return (
                        <div
                          key={`goal-${index}`}
                          className="rounded-[20px] bg-white/60 p-5 shadow-2xs"
                        >
                          <span className="text-xs font-semibold text-stone-400">
                            0{index + 1}
                          </span>

                          <p className="mt-3 text-sm leading-relaxed text-stone-700 font-medium">
                            {goalText}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>

            {recommendations?.recommended_ingredients?.length > 0 && (
              <section className="mt-10">
                <SectionHeading
                  eyebrow="Ingredient direction"
                  title="Ingredients Beautyverse prioritized"
                  description="These are cosmetic ingredient directions generated for this analysis, not prescriptions."
                />

                <div className="mt-7 grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
                  {recommendations.recommended_ingredients.map(
                    (ingredient, index) => (
                      <IngredientCard
                        key={`${ingredient.name}-${index}`}
                        ingredient={ingredient}
                        index={index}
                      />
                    )
                  )}
                </div>
              </section>
            )}

            <section className="mt-14">
              <SectionHeading
                eyebrow="Daily routine"
                title="Morning and evening"
                description="Each step includes the reason it was included in your generated plan."
              />

              <div className="mt-7 grid lg:grid-cols-2 gap-6">
                <RoutineCard
                  title="Morning routine"
                  subtitle="Protect & balance"
                  symbol="AM"
                  steps={safeMorningSteps}
                />

                <RoutineCard
                  title="Evening routine"
                  subtitle="Cleanse & support"
                  symbol="PM"
                  steps={safeEveningSteps}
                />
              </div>
            </section>

            {recommendations?.avoid_or_limit?.length > 0 && (
              <section className="mt-10 rounded-[32px] border border-stone-200 bg-white p-7 md:p-9">
                <div className="grid lg:grid-cols-[0.55fr_1fr] gap-7">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
                      Keep in mind
                    </p>

                    <h3 className="mt-3 text-3xl font-semibold tracking-tight">
                      Things to avoid or limit
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {recommendations.avoid_or_limit.map((entry, index) => {
                      const itemTitle =
                        typeof entry === "object" && entry !== null
                          ? (entry.item || entry.name || entry.title || "")
                          : String(entry || "");
                      const itemReason =
                        typeof entry === "object" && entry !== null
                          ? (entry.reason || entry.rationale || entry.evidence || "")
                          : "";

                      if (!itemTitle && !itemReason) return null;

                      return (
                        <div
                          key={`avoid-${index}-${itemTitle.slice(0, 24)}`}
                          className="flex gap-4 rounded-[20px] bg-stone-50 p-5"
                        >
                          <div className="h-8 w-8 shrink-0 rounded-full bg-white border border-stone-200 flex items-center justify-center text-sm font-semibold text-stone-700">
                            {index + 1}
                          </div>

                          <div className="min-w-0 flex-1">
                            <p className="text-sm md:text-base font-semibold leading-snug text-stone-800">
                              {itemTitle}
                            </p>
                            {itemReason && (
                              <p className="mt-1.5 text-xs md:text-sm leading-relaxed text-stone-600">
                                {itemReason}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>
            )}

            {/* PRODUCT RECOMMENDATIONS SECTION */}
            <section className="mt-16" id="product-recommendations-section">
              <SectionHeading
                eyebrow="Product Recommendations"
                title="Personalized Product Recommendations"
                description={
                  liveProducts.length > 0
                    ? "These products are retrieved live, then filtered and ranked against your skin profile and the requirements of each generated routine step."
                    : "Curated formulations and active ingredients aligned to your skin analysis. Explore matching verified products via direct retailer discovery."
                }
                right={
                  <span className="text-sm font-medium text-stone-500">
                    {liveProducts.length > 0
                      ? `${liveProducts.length} live product${liveProducts.length === 1 ? "" : "s"} found`
                      : `${discoveryCards.length} routine recommendations`}
                  </span>
                }
              />

              {liveProducts.length > 0 ? (
                /* STATE 1 & STATE 3: LIVE PRODUCTS (Flip cards with images or category placeholders) */
                <div className="mt-8 space-y-10">
                  {orderedProductGroups.map(({ category, products }) => (
                    <ProductCategorySection
                      key={category}
                      category={category}
                      products={products}
                    />
                  ))}

                  <div className="mt-8 rounded-[22px] border border-stone-200 bg-white p-5 text-xs leading-relaxed text-stone-500">
                    Prices, ratings, sellers and availability come from live
                    shopping results and can change. Product links are discovery
                    links, not medical treatment recommendations.
                  </div>
                </div>
              ) : (
                /* STATE 2: PERSONALIZED RECOMMENDATION DISCOVERY CARDS */
                <div className="mt-8 space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {discoveryCards.map((step, sIdx) => (
                      <RecommendationDiscoveryCard
                        key={`discovery-${sIdx}-${step.category || "step"}`}
                        step={step}
                        stepIndex={sIdx}
                        detectedSkinType={detectedSkinTypeLabel}
                        concernsList={primaryConcernsList}
                        regionalFinding={regionalFinding}
                      />
                    ))}
                  </div>

                  <div className="rounded-[22px] border border-stone-200 bg-white p-5 text-xs leading-relaxed text-stone-500">
                    Recommendations are formulated from your skin analysis profile. Direct search links search for matched formulations and active ingredients on Amazon India and Nykaa.
                  </div>
                </div>
              )}

              <div className="mt-6 flex items-center justify-between">
                <button
                  type="button"
                  onClick={downloadDiagnostics}
                  className="rounded-xl border border-stone-300 bg-white px-5 py-2.5 text-xs font-semibold text-stone-700 hover:bg-stone-50 transition"
                >
                  Download analysis diagnostics
                </button>
              </div>
            </section>


            <section className="mt-14 border-t border-stone-200 pt-8">
              <div className="grid md:grid-cols-[1fr_auto] gap-6 md:items-end">
                <div className="max-w-3xl">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-400">
                    Important
                  </p>

                  <p className="mt-3 text-sm leading-relaxed text-stone-500">
                    {recommendations?.safety?.disclaimer ||
                      presentation?.disclaimer ||
                      "Beautyverse provides cosmetic skincare guidance and does not diagnose medical skin conditions."}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={removeImage}
                  className="rounded-full bg-[#1d1b19] px-7 py-3.5 font-semibold text-white transition hover:bg-black"
                >
                  Analyze another selfie
                </button>
              </div>
            </section>
          </div>
        </section>
      )}
    </main>
  );
};

const MethodStep = ({ number, title, text }) => (
  <div className="rounded-[22px] border border-black/[0.06] bg-white/35 p-5">
    <div className="flex gap-4">
      <div className="h-10 w-10 shrink-0 rounded-full bg-[#1d1b19] text-white flex items-center justify-center text-xs font-semibold">
        {number}
      </div>

      <div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-stone-600">{text}</p>
      </div>
    </div>
  </div>
);

const ReportPill = ({ children }) => (
  <span className="rounded-full border border-stone-200 bg-white px-4 py-2 text-xs font-medium text-stone-600">
    {children}
  </span>
);

const SectionHeading = ({ eyebrow, title, description, right = null }) => (
  <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5">
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-400">
        {eyebrow}
      </p>

      <h3 className="mt-2 text-3xl md:text-4xl font-semibold tracking-tight">
        {title}
      </h3>

      {description && (
        <p className="mt-3 max-w-3xl text-sm md:text-base leading-relaxed text-stone-500">
          {description}
        </p>
      )}
    </div>

    {right}
  </div>
);

const SummaryCard = ({ eyebrow, title, text }) => (
  <div className="rounded-[24px] border border-stone-200 bg-white p-6">
    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-400">
      {eyebrow}
    </p>

    <h3 className="mt-3 text-xl font-semibold">{title}</h3>

    <p className="mt-2 text-sm leading-relaxed text-stone-500">{text}</p>
  </div>
);

const SkinToneCard = ({ tone }) => (
  <div className="rounded-[24px] border border-stone-200 bg-white p-6">
    <div className="flex items-center justify-between gap-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-400">
        Skin tone & complexion
      </p>
      {tone?.representative_hex && (
        <span
          className="h-6 w-6 rounded-full border border-stone-300 shadow-sm"
          style={{ backgroundColor: tone.representative_hex }}
          title={`Representative tone: ${tone.representative_hex}`}
        />
      )}
    </div>

    <h3 className="mt-3 text-xl font-semibold">
      {tone?.complexion || "Medium"}{" "}
      <span className="text-sm font-normal text-stone-500">
        ({tone?.undertone || "Neutral"} undertone)
      </span>
    </h3>

    <p className="mt-2 text-sm leading-relaxed text-stone-500">
      {tone?.fitzpatrick_scale || "Type III"} ·{" "}
      {tone?.undertone_description || "Calibrated optical tone assessment."}
    </p>

    {tone?.uv_sensitivity && (
      <div className="mt-3 rounded-xl bg-stone-50 p-2.5 text-xs text-stone-600">
        <span className="font-semibold text-stone-700">UV Profile:</span>{" "}
        {tone.uv_sensitivity}
      </div>
    )}
  </div>
);

const RegionalObservationsCard = ({ summary }) => (
  <div className="mt-6 rounded-[28px] border border-stone-200 bg-white p-6 md:p-8">
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-stone-100 pb-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-400">
          Facial Regional Analysis
        </p>
        <h4 className="mt-1 text-xl font-semibold">Zone-by-zone optical breakdown</h4>
      </div>
      <span className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-600">
        Multi-signal calibrated
      </span>
    </div>

    <div className="mt-6 grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
      <div className="rounded-2xl bg-stone-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">T-Zone (Forehead & Nose)</p>
        <p className="mt-2 text-lg font-semibold text-stone-800">
          {summary?.tzone_shine_index > 0.32
            ? "Elevated shine"
            : summary?.tzone_shine_index > 0.20
            ? "Balanced shine"
            : "Low sebum / matte"}
        </p>
        <p className="mt-1 text-xs text-stone-500">Sebum index: {summary?.tzone_shine_index ?? "—"}</p>
      </div>

      <div className="rounded-2xl bg-stone-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">U-Zone (Cheeks & Chin)</p>
        <p className="mt-2 text-lg font-semibold text-stone-800">
          {summary?.uzone_shine_index > 0.28
            ? "Dewy / oily"
            : summary?.uzone_shine_index > 0.15
            ? "Normal / hydrated"
            : "Dry / matte"}
        </p>
        <p className="mt-1 text-xs text-stone-500">Sebum index: {summary?.uzone_shine_index ?? "—"}</p>
      </div>

      <div className="rounded-2xl bg-stone-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">Regional Divergence</p>
        <p className="mt-2 text-lg font-semibold text-stone-800">
          {summary?.shine_divergence > 0.10 ? "Combination pattern" : "Uniform distribution"}
        </p>
        <p className="mt-1 text-xs text-stone-500">Δ shine: {summary?.shine_divergence ?? "—"}</p>
      </div>

      <div className="rounded-2xl bg-stone-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-stone-400">Skin Texture & Calm</p>
        <p className="mt-2 text-lg font-semibold text-stone-800">
          {summary?.average_texture_roughness > 0.35 ? "Texture observed" : "Smooth micro-surface"}
        </p>
        <p className="mt-1 text-xs text-stone-500">Erythema avg: {summary?.average_erythema_index ?? "—"}</p>
      </div>
    </div>
  </div>
);

const ProbabilityBar = ({ label, percentage }) => (
  <div>
    <div className="mb-2 flex items-center justify-between gap-4 text-sm">
      <span className="text-white/75">{label}</span>
      <span className="font-medium text-white">{percentage}%</span>
    </div>

    <div className="h-2 overflow-hidden rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-white transition-all duration-700"
        style={{
          width: `${Math.max(Number(percentage) || 0, 1)}%`,
        }}
      />
    </div>
  </div>
);

const PresentedConcernCard = ({ concern }) => {
  const config = {
    confirmed: {
      symbol: "✓",
      card: "border-[#c8ded1] bg-[#f2f8f4]",
      icon: "bg-[#dcecdf] text-[#356346]",
      badgeClass: "bg-white text-[#356346]",
    },
    review: {
      symbol: "?",
      card: "border-[#eadcae] bg-[#fff9e9]",
      icon: "bg-[#f7e8b9] text-[#7a6324]",
      badgeClass: "bg-white text-[#7a6324]",
    },
    none: {
      symbol: "○",
      card: "border-stone-200 bg-white",
      icon: "bg-stone-100 text-stone-500",
      badgeClass: "bg-stone-100 text-stone-500",
    },
  };

  const style = config[concern.priority] || config.none;

  return (
    <article className={`rounded-[26px] border p-6 ${style.card}`}>
      <div className="flex items-start justify-between gap-4">
        <div
          className={`h-11 w-11 rounded-full flex items-center justify-center font-semibold ${style.icon}`}
        >
          {style.symbol}
        </div>

        <span
          className={`rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${style.badgeClass}`}
        >
          {concern.display_status}
        </span>
      </div>

      <h4 className="mt-5 text-xl font-semibold">{concern.name}</h4>

      <p className="mt-1 text-xs font-medium uppercase tracking-[0.12em] text-stone-400">
        {concern.signal_label}
      </p>

      <p className="mt-4 text-sm leading-relaxed text-stone-600">
        {concern.message}
      </p>

      <div className="mt-5 rounded-[18px] bg-white/70 p-4">
        <div className="flex items-center justify-between gap-4 text-xs">
          <span className="text-stone-500">Model score</span>
          <span className="font-semibold">
            {concern.model_score_percentage}%
          </span>
        </div>

        <div className="mt-2 flex items-center justify-between gap-4 text-xs">
          <span className="text-stone-500">Decision threshold</span>
          <span className="font-semibold">{concern.threshold_percentage}%</span>
        </div>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-stone-400">
        {concern.score_note}
      </p>
    </article>
  );
};

const IngredientCard = ({ ingredient, index }) => {
  const name =
    typeof ingredient === "object" && ingredient !== null
      ? (ingredient.name || ingredient.item || ingredient.title || "")
      : String(ingredient || "");
  const reason =
    typeof ingredient === "object" && ingredient !== null
      ? (ingredient.reason || ingredient.rationale || ingredient.description || "")
      : "";

  return (
    <article className="rounded-[26px] border border-stone-200 bg-white p-6">
      <div className="flex items-center justify-between gap-4">
        <span className="h-10 w-10 rounded-full bg-stone-100 flex items-center justify-center text-xs font-semibold text-stone-500">
          {String(index + 1).padStart(2, "0")}
        </span>

        <span className="text-xs uppercase tracking-[0.12em] text-stone-300">
          Ingredient
        </span>
      </div>

      <h4 className="mt-5 text-xl font-semibold">{name}</h4>

      {reason && (
        <p className="mt-3 text-sm leading-relaxed text-stone-500">
          {reason}
        </p>
      )}
    </article>
  );
};

const RoutineCard = ({ title, subtitle, symbol, steps = [] }) => (
  <article className="rounded-[32px] border border-stone-200 bg-white p-7 md:p-8">
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-400">
          {subtitle}
        </p>

        <h3 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h3>
      </div>

      <div className="h-12 w-12 rounded-full bg-[#1d1b19] text-white flex items-center justify-center text-xs font-semibold tracking-wider">
        {symbol}
      </div>
    </div>

    <div className="mt-8 space-y-3">
      {steps?.map((item, idx) => {
        const stepNum = typeof item === "object" && item !== null ? (item.step ?? idx + 1) : idx + 1;
        const category = typeof item === "object" && item !== null ? (item.category || "Step") : "Step";
        const recommendation =
          typeof item === "object" && item !== null
            ? (typeof item.recommendation === "object" && item.recommendation !== null
                ? (item.recommendation.item || item.recommendation.name || item.recommendation.text || "")
                : String(item.recommendation || item.title || ""))
            : String(item || "");
        const reason =
          typeof item === "object" && item !== null
            ? (typeof item.reason === "object" && item.reason !== null
                ? (item.reason.reason || item.reason.rationale || item.reason.text || "")
                : (item.reason || ""))
            : "";
        const rawActives =
          typeof item === "object" && item !== null
            ? (Array.isArray(item.actives) ? item.actives : Array.isArray(item.target_actives) ? item.target_actives : Array.isArray(item.desired_ingredients) ? item.desired_ingredients : [])
            : [];
        const actives = rawActives.map((a) => (typeof a === "object" && a !== null ? (a.name || a.active || a.item || "") : String(a || ""))).filter(Boolean);
        const instructions =
          typeof item === "object" && item !== null
            ? (item.instructions || item.how_to_use || "")
            : "";
        const warnings =
          typeof item === "object" && item !== null
            ? (item.warnings || item.avoid || item.caution || "")
            : "";

        return (
          <div
            key={`step-${stepNum}-${category}-${idx}`}
            className="rounded-[22px] bg-stone-50 p-5 border border-stone-100/80"
          >
            <div className="flex gap-4">
              <div className="h-9 w-9 shrink-0 rounded-full bg-white border border-stone-200 flex items-center justify-center text-xs font-semibold text-stone-800 shadow-2xs">
                {String(stepNum).padStart(2, "0")}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-stone-900 capitalize text-sm md:text-base">{category}</span>
                </div>

                <p className="mt-1 text-sm leading-relaxed text-stone-700 font-medium">
                  {recommendation}
                </p>

                {actives.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {actives.map((act, aIdx) => (
                      <span
                        key={`act-${aIdx}`}
                        className="rounded-full bg-emerald-50 border border-emerald-200/70 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-800"
                      >
                        {act}
                      </span>
                    ))}
                  </div>
                )}

                {instructions && (
                  <p className="mt-2 text-xs leading-relaxed text-stone-500">
                    <span className="font-semibold text-stone-700">Instructions: </span>
                    {instructions}
                  </p>
                )}

                {reason && (
                  <p className="mt-2 text-xs leading-relaxed text-stone-500">
                    <span className="font-semibold text-stone-600">Why: </span>
                    {reason}
                  </p>
                )}

                {warnings && (
                  <p className="mt-1.5 text-xs leading-relaxed text-amber-700">
                    <span className="font-semibold">Note: </span>
                    {warnings}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  </article>
);

const ProductCategorySection = ({ category, products }) => (
  <div>
    <div className="flex items-center justify-between gap-4 border-b border-stone-200 pb-4">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-stone-400 font-semibold">
          Routine category
        </p>

        <h4 className="mt-1 text-2xl font-semibold capitalize text-stone-900">{category}</h4>
      </div>

      <span className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-semibold text-stone-600">
        {products.length} match{products.length === 1 ? "" : "es"}
      </span>
    </div>

    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {(products || []).filter(Boolean).map((product, index) => (
        <FlipProductCard
          key={`${product?.title || product?.name || product?.product_name || "product"}-${index}`}
          product={product}
        />
      ))}
    </div>
  </div>
);

const getCategoryIcon = (cat) => {
  const c = String(cat || "").toLowerCase();
  if (c.includes("sunscreen") || c.includes("spf")) {
    return (
      <svg className="w-8 h-8 text-amber-500/90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
      </svg>
    );
  }
  if (c.includes("serum") || c.includes("ampoule")) {
    return (
      <svg className="w-8 h-8 text-rose-400/90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    );
  }
  if (c.includes("cleanser") || c.includes("wash")) {
    return (
      <svg className="w-8 h-8 text-teal-400/90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-.778.099-1.533.284-2.253" />
      </svg>
    );
  }
  if (c.includes("treatment")) {
    return (
      <svg className="w-8 h-8 text-indigo-400/90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693l-1.57-.393m15.6 0a9.006 9.006 0 01-1.5 5.7M4.2 15.3a9.006 9.006 0 001.5 5.7m13.8 0H4.5" />
      </svg>
    );
  }
  return (
    <svg className="w-8 h-8 text-sky-400/90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
    </svg>
  );
};

const ProductCardPlaceholder = ({ category }) => {
  const fallbackImg = getCategoryDefaultImage(category);
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#f8f5f1] p-3 text-center select-none overflow-hidden">
      <img
        src={fallbackImg}
        alt={category || "Product"}
        className="h-full w-full object-contain p-2 drop-shadow-xs transition-transform duration-500 hover:scale-105"
      />
    </div>
  );
};

const RecommendationDiscoveryCard = ({
  step,
  stepIndex,
  detectedSkinType,
  concernsList,
  regionalFinding,
}) => {
  const category = step.display_category || step.category || "Skincare Step";
  const requirement = step.routine_requirement || "";
  const targetActives = step.target_actives || [];
  const amazonUrl = step.amazon_search_url || null;
  const nykaaUrl = step.nykaa_search_url || null;
  const cardImage = step.image_url || step.thumbnail || getCategoryDefaultImage(category);

  return (
    <article className="rounded-[28px] border border-stone-200/90 bg-white p-6 flex flex-col justify-between shadow-[0_4px_24px_rgba(28,25,23,0.04)] hover:shadow-[0_16px_48px_rgba(28,25,23,0.08)] hover:border-stone-300 transition-all duration-300">
      <div>
        {/* Top Product Image */}
        <div className="relative h-48 w-full rounded-2xl bg-[#f5f1ed] overflow-hidden flex items-center justify-center mb-5 shrink-0 border border-stone-100">
          <span className="absolute left-3 top-3 z-10 rounded-full bg-white/95 px-3 py-1 text-[11px] font-semibold capitalize text-stone-700 shadow-xs backdrop-blur">
            {step.used_in?.length ? `${step.used_in.join(" & ")} • Step ${stepIndex + 1}` : `Routine Step ${stepIndex + 1}`}
          </span>
          <span className="absolute right-3 top-3 z-10 rounded-full bg-stone-900/75 px-2.5 py-0.5 text-[10px] font-medium text-stone-100 backdrop-blur">
            Recommended
          </span>
          <img
            src={cardImage}
            alt={category}
            loading="lazy"
            className="h-full w-full object-contain p-3 transition-transform duration-500 hover:scale-105"
          />
        </div>

        {/* Step pill & icon */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5f1ed] border border-stone-200/60 shadow-2xs shrink-0">
              {getCategoryIcon(category)}
            </div>
            <div>
              <p className="text-xs font-semibold text-stone-400 capitalize">
                {category}
              </p>
            </div>
          </div>
          <span className="rounded-full bg-stone-100 px-3 py-1 text-[11px] font-semibold text-stone-600">
            Discovery
          </span>
        </div>

        {/* Title and Recommended for your analysis */}
        <div className="mt-3">
          <h4 className="text-xl font-bold text-stone-900 leading-snug">
            {category}
          </h4>
          <p className="mt-0.5 text-xs font-semibold text-rose-600/90">
            Recommended for your analysis
          </p>
        </div>

        {/* Analysis findings / Profile alignment */}
        <div className="mt-4 space-y-2 rounded-2xl bg-[#faf8f5] p-4 border border-stone-200/60">
          {detectedSkinType && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-stone-400 font-medium">Skin Type Relevance:</span>
              <span className="font-semibold text-stone-800 capitalize">{detectedSkinType}</span>
            </div>
          )}
          {concernsList?.length > 0 && (
            <div className="pt-2 border-t border-stone-200/50">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-stone-400 block mb-1">
                Concern Relevance:
              </span>
              <div className="flex flex-wrap gap-1">
                {concernsList.map((concern) => (
                  <span
                    key={concern}
                    className="rounded-md bg-white border border-stone-200/80 px-2.5 py-0.5 text-[10px] font-medium text-stone-700 shadow-2xs"
                  >
                    {concern}
                  </span>
                ))}
              </div>
            </div>
          )}
          {regionalFinding && (
            <div className="pt-2 border-t border-stone-200/50 text-[11px] text-stone-500">
              <span className="text-stone-400 font-medium">Regional Finding: </span>
              <span className="font-semibold text-stone-700">{regionalFinding}</span>
            </div>
          )}
        </div>

        {/* Why it is recommended */}
        {step.routine_reason && (
          <div className="mt-3.5 rounded-xl bg-stone-50 p-3.5 border border-stone-200/60">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block mb-1">
              Why it is recommended
            </span>
            <p className="text-xs leading-relaxed text-stone-700">
              {step.routine_reason}
            </p>
          </div>
        )}

        {/* Formulation requirement */}
        {requirement && (
          <div className="mt-3.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 block">
              Formulation requirement
            </span>
            <p className="mt-1 text-xs leading-relaxed text-stone-600">
              {requirement}
            </p>
          </div>
        )}

        {/* Target active ingredients */}
        {targetActives.length > 0 && (
          <div className="mt-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400 block mb-1.5">
              Target active ingredients
            </span>
            <div className="flex flex-wrap gap-1.5">
              {targetActives.map((act) => (
                <span
                  key={act}
                  className="rounded-full bg-emerald-50 border border-emerald-200/70 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-800"
                >
                  {act}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Retailer Links */}
      <div className="mt-6 pt-4 border-t border-stone-100 flex flex-col gap-2">
        {amazonUrl && (
          <a
            href={amazonUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-center text-xs font-semibold text-stone-800 shadow-2xs hover:bg-stone-50 transition"
          >
            <span>Search on Amazon India</span>
            <span>↗</span>
          </a>
        )}
        {nykaaUrl && (
          <a
            href={nykaaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 rounded-xl border border-[#fc2779]/30 bg-[#fc2779]/5 px-4 py-2.5 text-center text-xs font-semibold text-[#fc2779] shadow-2xs hover:bg-[#fc2779]/10 transition"
          >
            <span>Search on Nykaa</span>
            <span>↗</span>
          </a>
        )}
      </div>
    </article>
  );
};

const FlipProductCard = ({ product }) => {
  if (!product || typeof product !== "object") return null;

  const [isFlipped, setIsFlipped] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  const title =
    product.product_name ||
    product.name ||
    product.title ||
    "Recommended Skincare Product";
  const brand = product.brand || null;
  const category = product.category || "Skincare";
  const price = product.price || null;
  const rating = product.rating || null;
  const reviews = product.reviews_count || product.reviews || null;
  const catDefaultImg = getCategoryDefaultImage(category);
  const imageUrl =
    product.image_url ||
    product.image ||
    product.thumbnail ||
    catDefaultImg;
  const productUrl = product.product_url || product.link || null;
  const amazonUrl = product.amazon_url || null;
  const nykaaUrl = product.nykaa_url || null;
  const retailer = product.retailer || product.source || "Online retailer";
  const description = product.description || product.snippet || null;
  const recommendationReason =
    product.recommendation_reason ||
    product.why_recommended ||
    "Formulated to align with your personal skin profile and routine targets.";
  const routineRequirement =
    typeof product.routine_requirement === "object" && product.routine_requirement !== null
      ? (product.routine_requirement.recommendation || product.routine_requirement.reason || product.routine_requirement.item || "")
      : (product.routine_requirement ? String(product.routine_requirement) : "");

  const matchedTerms = [
    ...new Set(
      (product.matched_terms || []).map((item) =>
        typeof item === "object" && item !== null
          ? (item.term || item.name || item.item || "").trim()
          : String(item || "").trim()
      )
    ),
  ].filter(Boolean).slice(0, 5);

  const handleFlip = (e) => {
    if (e && e.stopPropagation) {
      e.stopPropagation();
    }
    setIsFlipped((prev) => !prev);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleFlip(e);
    }
  };

  const openUrl = (url, e) => {
    if (e && e.stopPropagation) {
      e.stopPropagation();
    }
    if (!url) return;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div
      className="perspective-1000 w-full min-h-[520px] h-[520px] focus:outline-none select-none"
      tabIndex={0}
      role="region"
      aria-label={`Product card for ${title}. ${isFlipped ? "Showing recommendation rationale" : "Showing product overview"}`}
      onKeyDown={handleKeyDown}
    >
      <div
        className={`relative h-full w-full transition-transform duration-500 ease-out transform-style-preserve-3d ${
          isFlipped ? "rotate-y-180" : ""
        }`}
      >
        {/* ================= FRONT OF CARD ================= */}
        <article
          onClick={handleFlip}
          className={`absolute inset-0 h-full w-full backface-hidden rounded-[28px] border border-stone-200/90 bg-white p-6 flex flex-col justify-between shadow-[0_4px_24px_rgba(28,25,23,0.04)] hover:shadow-[0_16px_48px_rgba(28,25,23,0.08)] hover:border-stone-300 transition-all duration-300 cursor-pointer overflow-hidden ${
            isFlipped ? "pointer-events-none opacity-0 invisible z-0" : "pointer-events-auto opacity-100 visible z-10"
          }`}
        >
          {/* Top image area */}
          <div className="relative h-60 w-full rounded-2xl bg-[#f5f1ed] overflow-hidden flex items-center justify-center shrink-0">
            {/* Category badge */}
            <span className="absolute left-3 top-3 z-10 rounded-full bg-white/95 px-3 py-1 text-[11px] font-semibold capitalize text-stone-700 shadow-xs backdrop-blur">
              {category}
            </span>

            {/* Retailer badge */}
            <span className="absolute right-3 top-3 z-10 rounded-full bg-stone-900/75 px-2.5 py-0.5 text-[10px] font-medium text-stone-100 backdrop-blur">
              {retailer}
            </span>

            {/* Image with skeleton loader and placeholder fallback */}
            {imageUrl && !imageError ? (
              <>
                {!imageLoaded && (
                  <div className="absolute inset-0 animate-pulse bg-stone-200/70 flex items-center justify-center">
                    <span className="text-xs text-stone-400">Loading product image…</span>
                  </div>
                )}
                <img
                  src={imageUrl}
                  alt={title}
                  referrerPolicy="no-referrer"
                  loading="lazy"
                  onLoad={() => setImageLoaded(true)}
                  onError={() => {
                    setImageLoaded(false);
                    setImageError(true);
                  }}
                  className={`h-full w-full object-contain p-4 transition-all duration-500 ${
                    imageLoaded ? "opacity-100" : "opacity-0"
                  }`}
                />
              </>
            ) : (
              <ProductCardPlaceholder category={category} />
            )}
          </div>

          {/* Middle details area */}
          <div className="mt-4 flex-1 flex flex-col justify-between overflow-hidden">
            <div>
              {brand && (
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-rose-500 truncate">
                  {brand}
                </p>
              )}
              <h5
                className="mt-1 text-base font-semibold leading-snug text-stone-900 line-clamp-2"
                title={title}
              >
                {title}
              </h5>
            </div>

            <div className="mt-3 flex items-center justify-between gap-2 border-t border-stone-100 pt-3">
              <div>
                {price ? (
                  <span className="text-lg font-bold text-stone-900">{price}</span>
                ) : (
                  <span className="text-xs text-stone-400">Check merchant price</span>
                )}
              </div>

              {rating && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 border border-amber-200/60">
                  <span>★</span>
                  <span>{rating}</span>
                  {reviews ? <span className="text-[10px] text-amber-600/80">({formatReviews(reviews)})</span> : null}
                </span>
              )}
            </div>
          </div>

          {/* Bottom Flip Affordance */}
          <div className="mt-4 pt-3 border-t border-stone-100">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleFlip(e);
              }}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-stone-900 hover:bg-black text-white py-3 text-xs font-bold tracking-wider transition-all shadow-xs cursor-pointer active:scale-[0.98]"
            >
              <span>↻</span>
              <span>TAP TO SEE WHY</span>
            </button>
          </div>
        </article>

        {/* ================= BACK OF CARD ================= */}
        <article
          className={`absolute inset-0 h-full w-full backface-hidden rotate-y-180 rounded-[28px] border border-stone-200/90 bg-[#faf8f5] p-6 flex flex-col justify-between shadow-[0_16px_48px_rgba(28,25,23,0.1)] overflow-y-auto ${
            isFlipped ? "pointer-events-auto opacity-100 visible z-10" : "pointer-events-none opacity-0 invisible z-0"
          }`}
        >
          {/* Back Header */}
          <div className="flex items-center justify-between border-b border-stone-200/80 pb-3">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-stone-400">
                Recommendation Rationale
              </span>
              <p className="text-xs font-semibold capitalize text-stone-700">
                {category} • {retailer}
              </p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleFlip(e);
              }}
              className="rounded-full bg-white hover:bg-stone-100 py-1.5 px-3 text-stone-600 border border-stone-200 shadow-2xs transition-colors text-xs flex items-center gap-1 font-medium cursor-pointer"
              aria-label="Flip back to front"
            >
              <span>↺</span>
              <span>Front</span>
            </button>
          </div>

          {/* Rationale & verified snippet content */}
          <div className="mt-3 flex-1 space-y-3 overflow-y-auto pr-1">
            {/* Why we recommended this */}
            <div className="rounded-2xl bg-white p-4 border border-stone-200/80 shadow-2xs">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <h6 className="text-[11px] font-bold uppercase tracking-wider text-stone-700">
                  Why we recommended this
                </h6>
              </div>
              <p className="text-xs leading-relaxed text-stone-600">
                {recommendationReason}
              </p>
            </div>

            {/* Routine step target */}
            {routineRequirement && (
              <div className="rounded-xl bg-stone-100/70 p-3 border border-stone-200/50">
                <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">
                  Routine step target
                </span>
                <p className="mt-1 text-xs text-stone-600 leading-snug">
                  {routineRequirement}
                </p>
              </div>
            )}

            {/* About this product (verified snippet only) */}
            {description && (
              <div className="rounded-xl bg-white/70 p-3 border border-stone-200/50">
                <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">
                  About this product
                </span>
                <p className="mt-1 text-xs text-stone-500 leading-relaxed italic">
                  "{description}"
                </p>
              </div>
            )}

            {/* Matched active signals */}
            {matchedTerms.length > 0 && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-stone-400">
                  Matched Active Signals
                </span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {matchedTerms.map((term) => (
                    <span
                      key={term}
                      className="rounded-full bg-white border border-stone-200 px-2.5 py-1 text-[10px] font-medium text-stone-600 shadow-2xs"
                    >
                      {term}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Action buttons & Flip Back affordance */}
          <div className="mt-4 pt-3 border-t border-stone-200/80 space-y-2">
            <div className="flex flex-col sm:flex-row gap-2">
              {productUrl && (
                <button
                  type="button"
                  onClick={(e) => openUrl(productUrl, e)}
                  className="flex-1 rounded-full bg-[#1d1b19] px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-black text-center shadow-xs"
                >
                  View Product ↗
                </button>
              )}

              {amazonUrl && (
                <button
                  type="button"
                  onClick={(e) => openUrl(amazonUrl, e)}
                  className={`rounded-full border border-stone-300 bg-white px-3 py-2.5 text-xs font-semibold text-stone-700 transition hover:bg-stone-50 text-center ${
                    !productUrl ? "flex-1" : ""
                  }`}
                >
                  Amazon India ↗
                </button>
              )}

              {nykaaUrl && (
                <button
                  type="button"
                  onClick={(e) => openUrl(nykaaUrl, e)}
                  className={`rounded-full border border-[#fc2779]/30 bg-[#fc2779]/5 px-3 py-2.5 text-xs font-semibold text-[#fc2779] transition hover:bg-[#fc2779]/10 text-center ${
                    !productUrl && !amazonUrl ? "flex-1" : ""
                  }`}
                >
                  Nykaa ↗
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleFlip(e);
              }}
              className="w-full text-center py-2 text-xs font-semibold text-stone-600 hover:text-stone-900 transition-colors cursor-pointer"
            >
              ← Back to product
            </button>
          </div>
        </article>
      </div>
    </div>
  );
};

const formatStatus = (value) => {
  if (!value) return "Unavailable";

  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

const formatReviews = (value) => {
  const number = Number(value);

  if (!Number.isFinite(number)) return value;

  if (number >= 1000000) {
    return `${(number / 1000000).toFixed(1)}M`;
  }

  if (number >= 1000) {
    return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`;
  }

  return String(number);
};

export default SkinAnalysis;
