import React, { useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const PRODUCT_CATEGORY_ORDER = [
  "cleanser",
  "serum",
  "treatment",
  "moisturizer",
  "sunscreen",
];

const SkinAnalysis = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const fileInputRef = useRef(null);
  const resultsRef = useRef(null);

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

    setIsAnalyzing(true);
    setError("");
    setAnalysis(null);

    try {
      const formData = new FormData();
      formData.append("image", selectedFile);

      const response = await fetch(
        `${API_BASE_URL}/api/beautyverse-analysis`,
        {
          method: "POST",
          body: formData,
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
        err.message || "Something went wrong while analysing your skin."
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const removeImage = () => {
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
  const presentation = analysis?.analysis?.presentation;
  const skinTypePresentation = presentation?.skin_type;
  const concernPresentation = presentation?.concerns || [];
  const recommendations = analysis?.recommendations;
  const liveProducts = recommendations?.live_products?.products || [];

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
                Upload one clear selfie. Beautyverse combines facial
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
              {!previewUrl ? (
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
                disabled={!selectedFile || isAnalyzing}
                className={`mt-5 w-full rounded-full py-4 font-semibold transition ${
                  !selectedFile || isAnalyzing
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

      {isAnalyzing && (
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

      {analysis && !isAnalyzing && (
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

            <div className="mt-6 grid md:grid-cols-3 gap-4">
              <SummaryCard
                eyebrow="Skin type"
                title={`${skinTypePresentation?.label || rawSkinType?.predicted_skin_type} pattern`}
                text={
                  skinTypePresentation?.summary ||
                  "Beautyverse selected the highest scoring skin-type class from the current selfie."
                }
              />

              <SummaryCard
                eyebrow="Primary visible concern"
                title={
                  presentation?.confirmed_concerns?.[0] ||
                  "No confirmed concern"
                }
                text={
                  confirmedConcernCount > 0
                    ? "Only confirmed concern signals are allowed to drive targeted recommendations."
                    : "No concern crossed a confirmed detection threshold in this image."
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

                <p className="mt-4 max-w-5xl text-2xl md:text-3xl leading-snug font-medium tracking-tight">
                  {recommendations?.skin_profile}
                </p>

                {recommendations?.skin_goals?.length > 0 && (
                  <div className="mt-8 grid md:grid-cols-3 gap-3">
                    {recommendations.skin_goals.map((goal, index) => (
                      <div
                        key={`${goal}-${index}`}
                        className="rounded-[20px] bg-white/60 p-5"
                      >
                        <span className="text-xs font-semibold text-stone-400">
                          0{index + 1}
                        </span>

                        <p className="mt-3 text-sm leading-relaxed text-stone-700">
                          {goal}
                        </p>
                      </div>
                    ))}
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
                  steps={recommendations?.routine?.morning}
                />

                <RoutineCard
                  title="Evening routine"
                  subtitle="Cleanse & support"
                  symbol="PM"
                  steps={recommendations?.routine?.evening}
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
                    {recommendations.avoid_or_limit.map((item, index) => (
                      <div
                        key={`${item}-${index}`}
                        className="flex gap-4 rounded-[20px] bg-stone-50 p-5"
                      >
                        <div className="h-8 w-8 shrink-0 rounded-full bg-white border border-stone-200 flex items-center justify-center text-sm font-semibold">
                          {index + 1}
                        </div>

                        <p className="text-sm md:text-base leading-relaxed text-stone-600">
                          {item}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {liveProducts.length > 0 && (
              <section className="mt-16">
                <SectionHeading
                  eyebrow="Live product discovery"
                  title="Products matched to your generated routine"
                  description="These products are retrieved live, then filtered and ranked against your skin profile and the requirements of each generated routine step."
                  right={
                    <span className="text-sm text-stone-400">
                      {liveProducts.length} products found
                    </span>
                  }
                />

                <div className="mt-8 space-y-10">
                  {orderedProductGroups.map(({ category, products }) => (
                    <ProductCategorySection
                      key={category}
                      category={category}
                      products={products}
                    />
                  ))}
                </div>

                <div className="mt-8 rounded-[22px] border border-stone-200 bg-white p-5 text-xs leading-relaxed text-stone-500">
                  Prices, ratings, sellers and availability come from live
                  shopping results and can change. Product links are discovery
                  links, not medical treatment recommendations.
                </div>
              </section>
            )}

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

const IngredientCard = ({ ingredient, index }) => (
  <article className="rounded-[26px] border border-stone-200 bg-white p-6">
    <div className="flex items-center justify-between gap-4">
      <span className="h-10 w-10 rounded-full bg-stone-100 flex items-center justify-center text-xs font-semibold text-stone-500">
        {String(index + 1).padStart(2, "0")}
      </span>

      <span className="text-xs uppercase tracking-[0.12em] text-stone-300">
        Ingredient
      </span>
    </div>

    <h4 className="mt-5 text-xl font-semibold">{ingredient.name}</h4>

    <p className="mt-3 text-sm leading-relaxed text-stone-500">
      {ingredient.reason}
    </p>
  </article>
);

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
      {steps?.map((item) => (
        <div
          key={`${item.step}-${item.category}`}
          className="rounded-[22px] bg-stone-50 p-5"
        >
          <div className="flex gap-4">
            <div className="h-9 w-9 shrink-0 rounded-full bg-white border border-stone-200 flex items-center justify-center text-xs font-semibold">
              {String(item.step).padStart(2, "0")}
            </div>

            <div>
              <p className="font-semibold">{item.category}</p>

              <p className="mt-1 text-sm leading-relaxed text-stone-600">
                {item.recommendation}
              </p>

              {item.reason && (
                <p className="mt-3 text-xs leading-relaxed text-stone-400">
                  Why: {item.reason}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  </article>
);

const ProductCategorySection = ({ category, products }) => (
  <div>
    <div className="flex items-center justify-between gap-4 border-b border-stone-200 pb-4">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-stone-400">
          Routine category
        </p>

        <h4 className="mt-1 text-2xl font-semibold capitalize">{category}</h4>
      </div>

      <span className="rounded-full bg-stone-100 px-3 py-1.5 text-xs text-stone-500">
        {products.length} match{products.length === 1 ? "" : "es"}
      </span>
    </div>

    <div className="mt-5 grid md:grid-cols-2 gap-5">
      {products.map((product, index) => (
        <LiveProductCard
          key={`${product.title}-${index}`}
          product={product}
        />
      ))}
    </div>
  </div>
);

const LiveProductCard = ({ product }) => {
  const openProduct = () => {
    if (!product.product_url) return;
    window.open(product.product_url, "_blank", "noopener,noreferrer");
  };

  const openAmazon = (event) => {
    event.stopPropagation();
    if (!product.amazon_url) return;
    window.open(product.amazon_url, "_blank", "noopener,noreferrer");
  };

  const matchedTerms = [
    ...new Set(
      (product.matched_terms || []).map((item) => String(item).trim())
    ),
  ].slice(0, 5);

  return (
    <article className="group overflow-hidden rounded-[28px] border border-stone-200 bg-white transition duration-300 hover:-translate-y-0.5 hover:shadow-[0_18px_60px_rgba(28,25,23,0.08)]">
      <div className="grid sm:grid-cols-[190px_1fr]">
        <button
          type="button"
          onClick={openProduct}
          className="relative min-h-[230px] bg-[#f5f1ed] overflow-hidden"
        >
          {product.image ? (
            <img
              src={product.image}
              alt={product.title}
              loading="lazy"
              className="h-full w-full object-contain p-6 transition duration-500 group-hover:scale-[1.03]"
            />
          ) : (
            <span className="absolute inset-0 flex items-center justify-center text-sm text-stone-400">
              No image
            </span>
          )}

          <span className="absolute left-3 top-3 rounded-full bg-white/90 px-3 py-1.5 text-[11px] font-semibold capitalize backdrop-blur">
            {product.category}
          </span>
        </button>

        <div className="p-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-stone-400">
            {product.source || "Online retailer"}
          </p>

          <button
            type="button"
            onClick={openProduct}
            className="mt-2 text-left"
          >
            <h5 className="text-lg font-semibold leading-snug transition group-hover:text-stone-600">
              {product.title}
            </h5>
          </button>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xl font-semibold">
              {product.price || "View price"}
            </span>

            {product.rating && (
              <span className="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-semibold">
                ★ {product.rating}
                {product.reviews ? ` · ${formatReviews(product.reviews)}` : ""}
              </span>
            )}
          </div>

          {product.routine_requirement && (
            <div className="mt-5 rounded-[18px] bg-stone-50 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">
                Routine match
              </p>

              <p className="mt-2 text-sm leading-relaxed text-stone-600">
                {product.routine_requirement}
              </p>
            </div>
          )}

          {matchedTerms.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {matchedTerms.map((term) => (
                <span
                  key={term}
                  className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-[11px] text-stone-500"
                >
                  {term}
                </span>
              ))}
            </div>
          )}

          <div className="mt-5 flex flex-col sm:flex-row gap-2">
            <button
              type="button"
              onClick={openProduct}
              className="flex-1 rounded-full bg-[#1d1b19] px-4 py-3 text-sm font-semibold text-white transition hover:bg-black"
            >
              View product
            </button>

            {product.amazon_url && (
              <button
                type="button"
                onClick={openAmazon}
                className="rounded-full border border-stone-300 px-4 py-3 text-sm font-semibold transition hover:bg-stone-50"
              >
                Amazon
              </button>
            )}
          </div>
        </div>
      </div>

      {product.why_recommended && (
        <div className="border-t border-stone-100 px-6 py-5">
          <details>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-stone-400">
              Why Beautyverse matched this
            </summary>

            <p className="mt-3 text-sm leading-relaxed text-stone-500">
              {product.why_recommended}
            </p>
          </details>
        </div>
      )}
    </article>
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