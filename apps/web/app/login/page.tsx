"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, FileText, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { useDemoMode } from "@/lib/demo";

const DEMO_EMAIL = "service@demo.local";
const DEMO_PASSWORD = "demo-password";

export default function LoginPage() {
  const router = useRouter();
  const demo = useDemoMode();
  // null until the person edits a field, so demo mode can pre-fill the engineer account.
  const [email, setEmail] = useState<string | null>(null);
  const [password, setPassword] = useState<string | null>(null);
  const emailValue = email ?? (demo ? DEMO_EMAIL : "");
  const passwordValue = password ?? (demo ? DEMO_PASSWORD : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email: emailValue, password: passwordValue }) });
      router.replace("/work");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  function selectAccount(value: string) {
    setEmail(value);
    setPassword(DEMO_PASSWORD);
  }

  return (
    <div className="login-page">
      <section className="login-context">
        <div className="brand-row">
          <div className="brand-mark">S</div>
          <div><div className="brand-name">Service Desk</div><div className="brand-org">Service case support</div></div>
        </div>
        <div>
          <h1>Do the work with the evidence in view.</h1>
          <p>Investigate service cases across permitted company knowledge and operational data, prepare a usable brief, then move approved follow-up into the system of record.</p>
          <div className="context-preview" aria-hidden="true">
            <div className="context-preview-head"><span>Northstar Foods / PX-400</span><span>Escalation</span></div>
            <div className="context-preview-body">
              <div className="preview-brief">
                <strong>Repeated E-217 stops after firmware 4.8</strong>
                <div className="preview-line"/><div className="preview-line"/><div className="preview-line short"/>
                <div style={{ height: 12 }}/>
                <div className="preview-line"/><div className="preview-line short"/>
              </div>
              <div className="preview-sources">
                <div className="preview-source"><FileText size={13}/> Service bulletin</div>
                <div className="preview-source"><FileText size={13}/> Maintenance agreement</div>
                <div className="preview-source"><Wrench size={13}/> 3 service cases</div>
              </div>
            </div>
          </div>
        </div>
        <small style={{ color: "#707780" }}>{demo ? "Local demo data. No external account is required." : ""}</small>
      </section>

      <section className="login-form-side">
        <form className="login-card" onSubmit={submit}>
          <h2>Sign in to Service Desk</h2>
          <p>{demo ? "Use one of the seeded accounts to run the demo." : "Use the account your administrator created for you."}</p>
          <div className="login-fields">
            <div className="field"><label>Email</label><input className="input" value={emailValue} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></div>
            <div className="field"><label>Password</label><input className="input" type="password" value={passwordValue} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
            {error && <div className="error-box">{error}</div>}
            <button className="button primary" disabled={busy} style={{ width: "100%" }}>
              {busy ? "Signing in…" : <>Continue <ArrowRight size={15}/></>}
            </button>
          </div>
          {demo && (
            <div className="demo-accounts">
              <span>Demo accounts</span>
              <button type="button" className="demo-account" onClick={() => selectAccount(DEMO_EMAIL)}><strong>Maya Chen</strong><span>Service engineer</span></button>
              <button type="button" className="demo-account" onClick={() => selectAccount("manager@demo.local")}><strong>Luis Martin</strong><span>Approver</span></button>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}
