import { useEffect, useRef, useState } from "react";

export default function LiveCamera({ apiBaseUrl, onCapture, disabled, questionnaire }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const sessionRef = useRef(0);
  const timerRef = useRef(null);
  const requestRef = useRef(null);
  const latestRef = useRef(null);
  const historyRef = useRef([]);
  const [active, setActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState("Start the camera to check your skin live.");
  const [stableResult, setStableResult] = useState(null);

  function releaseCamera() {
    sessionRef.current += 1;
    clearTimeout(timerRef.current);
    requestRef.current?.abort();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    latestRef.current = null;
    historyRef.current = [];
  }

  useEffect(() => () => releaseCamera(), []);

  function stop() {
    releaseCamera();
    setActive(false);
    setStarting(false);
    setStableResult(null);
    setMessage("Camera stopped.");
  }

  async function scan(session) {
    if (session !== sessionRef.current) return;
    const video = videoRef.current;
    let timeout;
    try {
      if (!video?.videoWidth || video.readyState < 2) {
        throw new Error("Waiting for the camera. Keep your face in view.");
      }
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.95));
      if (session !== sessionRef.current) return;
      if (!blob) throw new Error("Could not capture this frame. Please try again.");

      const controller = new AbortController();
      requestRef.current = controller;
      timeout = setTimeout(() => controller.abort(), 30000);
      const form = new FormData();
      form.append("image", blob, "live-selfie.jpg");
      if (questionnaire) form.append("questionnaire", JSON.stringify(questionnaire));
      const response = await fetch(`${apiBaseUrl}/api/beautyverse-analysis?preview_only=true`, {
        method: "POST", body: form, signal: controller.signal,
      });
      const data = await response.json();
      if (session !== sessionRef.current) return;
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Live analysis is unavailable.");
      if (!data.success) {
        throw new Error(data.reason === "no_face_detected"
          ? "Keep one face in view, looking straight at the camera."
          : data.message || "Use even lighting and hold the camera steady.");
      }

      const result = data.analysis;
      const signature = JSON.stringify([
        result.presentation.skin_type.label,
        result.skin_concerns.concerns.map(({ id, status }) => [id, status]),
      ]);
      historyRef.current = [...historyRef.current, signature].slice(-3);
      const stable = historyRef.current.length === 3 && historyRef.current.every((item) => item === signature);
      if (stable) {
        latestRef.current = blob;
        setStableResult({ ...result.presentation, questionnaire_profile: result.questionnaire_profile });
        setMessage("Results agree across three frames. Consistency does not guarantee accuracy.");
      } else {
        latestRef.current = null;
        setStableResult(null);
        setMessage("Checking consistency across frames. Hold still in even lighting.");
      }
    } catch (error) {
      if (session !== sessionRef.current) return;
      latestRef.current = null;
      historyRef.current = [];
      setStableResult(null);
      setMessage(error.name === "AbortError" ? "Analysis timed out. Retrying…" : error.message);
    } finally {
      clearTimeout(timeout);
      if (session === sessionRef.current) {
        // Schedule after completion: never overlap inference requests.
        timerRef.current = setTimeout(() => scan(session), 2000);
      }
    }
  }

  async function start() {
    releaseCamera();
    const session = sessionRef.current;
    setStarting(true);
    setMessage("Allow camera access when prompted.");
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera access requires HTTPS or localhost and a supported browser. You can upload a photo instead.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      if (session !== sessionRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      stream.getVideoTracks()[0].onended = () => {
        if (session === sessionRef.current) stop();
      };
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      if (session !== sessionRef.current) return;
      setActive(true);
      setStarting(false);
      setMessage("Checking your face and image quality…");
      scan(session);
    } catch (error) {
      if (session !== sessionRef.current) return;
      releaseCamera();
      setActive(false);
      setStarting(false);
      setMessage(error.name === "NotAllowedError"
        ? "Camera permission was denied. Allow access in your browser or upload a photo."
        : error.message || "Camera unavailable. Try uploading a photo.");
    }
  }

  function capture() {
    const blob = latestRef.current;
    if (!blob) return;
    stop();
    onCapture(new File([blob], "camera-selfie.jpg", { type: "image/jpeg" }));
  }

  return (
    <div className="rounded-[26px] bg-stone-50 p-5">
      <video ref={videoRef} autoPlay muted playsInline aria-label="Live camera preview"
        className={`w-full rounded-2xl bg-stone-200 ${active || starting ? "" : "hidden"}`}
        style={{ transform: "scaleX(-1)" }} />
      <p className="my-4 text-sm text-stone-600">
        Starting the camera sends sampled frames to Beautyverse for live analysis.
        Use a bare face, even lighting and no filters. Makeup and lighting can affect results.
      </p>
      <p role="status" className="my-4 text-sm font-medium">{message}</p>
      {stableResult && <div className="my-4 rounded-2xl bg-white p-4">
        <p className="text-sm">Live image estimate</p>
        <h3 className="font-semibold">{stableResult.skin_type.headline}</h3>
        {stableResult.questionnaire_profile && <p className="mt-2 text-sm">
          Skin type for guidance: {stableResult.questionnaire_profile.skin_type_for_guidance}. {stableResult.questionnaire_profile.message}
        </p>}
        <ul className="mt-2 text-sm space-y-2">
          {stableResult.concerns.map((concern) => <li key={concern.id}>
            {concern.name}: {concern.display_status}
          </li>)}
        </ul>
      </div>}
      <div className="flex flex-wrap gap-3">
        {!active && !starting && <button type="button" disabled={disabled} onClick={start}
          className="rounded-full bg-stone-900 text-white px-5 py-3 disabled:opacity-50">Start live camera</button>}
        {(active || starting) && <button type="button" onClick={stop}
          className="rounded-full border border-stone-400 px-5 py-3">Stop camera</button>}
        {active && <button type="button" disabled={!stableResult || disabled} onClick={capture}
          className="rounded-full bg-stone-900 text-white px-5 py-3 disabled:opacity-50">Use this frame for my report</button>}
      </div>
    </div>
  );
}
