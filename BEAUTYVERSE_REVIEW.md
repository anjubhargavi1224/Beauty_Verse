# BeautyVerse: initial accuracy review and camera update

Reviewed main at `17be28e5c316b68bbec14989f8b69016e53f7d29`.

## What the repository establishes

- `ml/results/dataset_report.json`: skin type uses 35 training, 7 validation and 8 test examples per class (140/28/32 total). Raw augmented image counts are not independent sample counts. The processed classes are balanced, so there is no evidence here that Combination is a hardcoded fallback or a majority class.
- `ml/results/skin_type_metrics.json`: saved test accuracy is 87.5% on 32 images. This does not establish accuracy on users' selfies.
- `ml/results/skin_concern_metrics.json`: 500 reviewed images split 357/77/66; some concern labels are unknown and masked. Saved wrinkle test precision is 67.74%, recall 91.30%, based on 45 known test labels. These figures use the training evaluator's threshold policy, not the app's extra uncertainty margin.
- Saved wrinkle threshold is 0.21; runtime declares detection at threshold + 0.08, so 0.29 if the checkpoint uses the same saved threshold. The app loads thresholds from the checkpoint, not the standalone JSON. No checkpoint inference or deserialization was performed during this review.
- Skin-type normalization and evaluation transforms match between training and serving. The training pipeline loads source images directly, while serving applies a MediaPipe face crop first. Source images might already be cropped; inspect them and compare full-image versus production-crop evaluation before changing preprocessing.
- Both concern and skin-type classifiers use whole-face classification, not lesion localization. Nothing in these classifiers explicitly distinguishes makeup from redness. Existing quality checks measure brightness, clipped pixels and focus; passing them does not establish that color is trustworthy or makeup is absent.
- The skin-type classifier already flags weak separation as uncertain, but presentation still showed the winning class. Recommendation generation also consumed that class.
- Raw dataset images, selfie evaluation labels and failure-example photos are absent from this checkout. The root requirements.txt is empty. Use the existing working Python environment for inference; reproducible dependency pinning remains outstanding.

## Changes in this patch

- Upload photo / Live camera choice in the skin analysis page.
- Live camera starts only on an explicit button click, requests video without audio, samples frames, and sends one request at a time. The next request starts two seconds after the previous one completes. This is sampled live analysis, not video-rate inference.
- Same API quality checks and models for upload and live frames. `preview_only=true` skips AI planning and product search. Three matching classifications are required before showing a stable result; temporal agreement is not an accuracy guarantee.
- Stop, mode switch and component unmount release the camera, cancel pending requests and invalidate late results. Permission denial and request timeout have messages. HTTPS or localhost is needed for browser camera access.
- The user can select the actual analyzed frame and then request a full report using Analyze My Skin.
- Uncertain skin types display as uncertain and are passed to the planner and recommendation engine as Uncertain. Raw model scores remain available. Concern detections are presented as possible concerns.
- A production-preprocessing evaluator measures class collapse, false positives, uncertainty, rejected input coverage, and optional lighting/makeup/skin-tone strata. It does not make AI or shopping requests.
- Three image filename imports corrected to match uppercase filenames so the frontend builds on Linux.

Model weights and detection thresholds are unchanged. These are workflow/reporting improvements, not a trained replacement model or a measured accuracy improvement. Makeup/redness confusion and confidently incorrect classifications remain unresolved.

## Apply on Windows PowerShell

Save beautyverse-improvements.patch in Downloads. From the Beauty_Verse repository:

```powershell
git status --short
git apply --check "$env:USERPROFILE\Downloads\beautyverse-improvements.patch"
git apply "$env:USERPROFILE\Downloads\beautyverse-improvements.patch"
python -m unittest discover -s tests -v
```

If the check fails, do not force the patch: local changes or a different repository revision may overlap. The check does not modify files. Keep existing work intact and share the error to adapt the changes.

Restart the existing backend and frontend, then visit `/skin-analysis`. The frontend build command from `frontend` is `npm run build`.

## Evaluate the actual model

Create a CSV next to your consented evaluation images:

```csv
image_path,skin_type,acne,pigmentation,redness,pores,wrinkles,lighting,makeup,skin_tone
photos/example.jpg,Normal,0,0,0,,0,daylight,no,
```

The row is a format example only. Supply independently verified labels: 1 means present, 0 absent, blank unknown. Skin types must be Combination, Dry, Normal or Oily; blank is allowed. Do not infer ground truth from the model's predictions. Relative paths resolve beside the CSV.

From the repository root, in the working Python environment:

```powershell
python -m ml.evaluation.evaluate_selfies --manifest selfies.csv --output ml/results/selfie_evaluation.json
```

The output contains per-image predictions and quality failures. Review total analysis coverage, skin-type prediction counts, accuracy when decided, and per-concern false positives/recall together. Poor inputs and abstentions must not disappear from the assessment.

## Next model work requires data

Start with failure examples, the training data/annotations and their provenance, and predictions from the evaluator. Include clean negative examples (no fine lines, no acne), bare-face and makeup examples, lighting changes, and a range of skin tones and cameras. A small debugging set can expose errors but cannot validate deployment accuracy.

1. Compare existing training inputs against the production face crops and reproduce the repeated Combination predictions.
2. Audit labels, duplicates, source-family and person overlap across splits.
3. Build an independent selfie validation set and a locked test set. Keep images from the same person/source family in the same split.
4. Retrain with consistent preprocessing and representative negative examples; evaluate local skin-region/lesion methods if whole-face resolution loses relevant details.
5. Choose per-concern operating thresholds using validation precision/recall and sample support. Evaluate the exact runtime uncertainty policy on the untouched test set. Do not raise the wrinkle threshold solely to hide examples.
6. Recheck performance by lighting, makeup and skin tone, including input rejection and uncertainty coverage. Decide whether makeup should trigger a retake or an explicit user-provided condition; do not claim reliable makeup detection without validation.

## Verification

- Frontend production build passes. Existing CSS import-order, stale Browserslist and bundle-size warnings remain.
- Three focused Python reporting/evaluation tests pass; backend and evaluator compile.
- Camera interaction tests could not run: no browser binary was installed and its download timed out. Test permission denial, start/stop, mode switching and frame capture on your browser before deploying.
- Model inference/retraining and new accuracy measurements were not run: the ML dependencies and labeled image dataset are not available in this environment.
