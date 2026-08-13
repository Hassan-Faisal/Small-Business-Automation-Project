import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";

type SignupConfig = { app_id: string; config_id: string };
type SignupResult = { waba_id: string; phone_number_id: string };
type FacebookLoginResponse = { authResponse?: { code?: string } };

declare global {
  interface Window {
    FB?: {
      init: (options: { appId: string; cookie: boolean; xfbml: boolean; version: string }) => void;
      login: (callback: (response: FacebookLoginResponse) => void, options: Record<string, unknown>) => void;
    };
    fbAsyncInit?: () => void;
  }
}

const META_SDK_URL = "https://connect.facebook.net/en_US/sdk.js";

function loadFacebookSdk(config: SignupConfig): Promise<void> {
  if (window.FB) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const previousInit = window.fbAsyncInit;
    window.fbAsyncInit = () => {
      previousInit?.();
      window.FB?.init({ appId: config.app_id, cookie: true, xfbml: true, version: "v21.0" });
      resolve();
    };
    const script = document.createElement("script");
    script.src = META_SDK_URL;
    script.async = true;
    script.defer = true;
    script.onerror = () => reject(new Error("Unable to load Meta signup."));
    document.body.appendChild(script);
  });
}

export function MetaEmbeddedSignup() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const pendingCode = useRef<string | null>(null);
  const pendingResult = useRef<SignupResult | null>(null);


  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== "https://www.facebook.com" && event.origin !== "https://business.facebook.com") return;
      const data = typeof event.data === "string" ? (() => { try { return JSON.parse(event.data); } catch { return null; } })() : event.data;
      if (!data || data.type !== "WA_EMBEDDED_SIGNUP") return;
      if (data.event === "CANCEL") {
        pendingCode.current = null;
        pendingResult.current = null;
        setBusy(false);
        setMessage("Meta signup was cancelled. Your WhatsApp Business app account was not changed.");
        return;
      }
      if (data.event === "ERROR") {
        pendingCode.current = null;
        pendingResult.current = null;
        setBusy(false);
        setMessage("Meta could not complete signup. Your WhatsApp Business app account was not changed.");
        return;
      }
      if (data.event !== "FINISH") return;
      const result = data.data ?? data;
      if (typeof result.waba_id !== "string" || typeof result.phone_number_id !== "string") {
        setBusy(false);
        setMessage("Meta returned an incomplete onboarding result.");
        return;
      }
      pendingResult.current = { waba_id: result.waba_id, phone_number_id: result.phone_number_id };
      if (pendingCode.current) void complete(pendingCode.current, pendingResult.current);
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  });

  async function complete(code: string, result: SignupResult) {
    pendingCode.current = null;
    pendingResult.current = null;
    try {
      await api.post("/admin/meta/embedded-signup/complete", { event: "FINISH", code, ...result });
      setMessage("Coexistence onboarding completed. Keep the WhatsApp Business app open for the QR/access-code step if Meta requests it.");
    } catch {
      setMessage("Meta signup finished, but TiffinAI could not complete the secure server exchange. No token was displayed.");
    } finally {
      setBusy(false);
    }
  }

  async function startSignup() {
    setBusy(true);
    setMessage("");
    try {
      const response = await api.get<SignupConfig>("/admin/meta/embedded-signup/config");
      if (!response.data.app_id || !response.data.config_id) throw new Error("Meta signup is not configured.");
      const signupConfig = response.data;
      await loadFacebookSdk(signupConfig);
      window.FB?.login((response) => {
        const code = response.authResponse?.code;
        if (!code) {
          setBusy(false);
          setMessage("Meta signup did not return an authorization code.");
          return;
        }
        pendingCode.current = code;
        if (pendingResult.current) void complete(code, pendingResult.current);
      }, {
        config_id: signupConfig.config_id,
        response_type: "code",
        override_default_response_type: true,
        extras: {
          setup: {},
          featureType: "whatsapp_business_app_onboarding",
          sessionInfoVersion: "3",
        },
      });
    } catch {
      setBusy(false);
      setMessage("Unable to load Meta signup. Please try again.");
    }
  }

  return (
    <section aria-labelledby="meta-signup-heading" className="mt-8 rounded-2xl border border-teal-100 bg-teal-50 p-5 shadow-sm">
      <h2 id="meta-signup-heading" className="text-base font-bold text-ink">Connect WhatsApp Business app</h2>
      <p className="mt-1 max-w-2xl text-sm text-slate-600">Connect the existing WhatsApp Business app number to Cloud API while keeping the app usable.</p>
      <button type="button" onClick={() => void startSignup()} disabled={busy} className="mt-4 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60">
        {busy ? "Waiting for Meta..." : "Connect with Meta"}
      </button>
      {message && <p role="status" className="mt-3 text-sm text-slate-700">{message}</p>}
    </section>
  );
}
