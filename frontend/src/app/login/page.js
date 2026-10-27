"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ErrorBanner, Field } from "@/components/ui";

const DEMO = [
  { role: "Coordinator", email: "coordinator@example.com" },
  { role: "Volunteer", email: "alice@example.com" },
];
const DEMO_PASSWORD = "Demo1234!";

function LoginForm() {
  const { user, ready, login, register } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next") || "/";
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (ready && user) router.replace(next.startsWith("/") ? next : "/");
  }, [ready, user, next, router]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    // Free hosting sleeps when idle; tell the user why the first sign-in is slow.
    const timer = setTimeout(() => setSlow(true), 4000);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register(form.name, form.email, form.password);
    } catch (err) {
      setError(err.message);
    } finally {
      clearTimeout(timer);
      setSlow(false);
      setBusy(false);
    }
  }

  return (
    <div className="card auth-card">
      <h1>Volunteer Scheduling</h1>
      <p className="muted">Sign in to see programs and claim shifts.</p>
      <div className="tabs" role="tablist">
        <button type="button" className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>
          Sign in
        </button>
        <button type="button" className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>
          Create volunteer account
        </button>
      </div>
      <ErrorBanner message={error} />
      <form onSubmit={submit}>
        {mode === "register" && (
          <Field label="Name">
            <input value={form.name} onChange={set("name")} required maxLength={120} autoComplete="name" />
          </Field>
        )}
        <Field label="Email">
          <input type="email" value={form.email} onChange={set("email")} required autoComplete="email" />
        </Field>
        <Field label="Password" hint={mode === "register" ? "At least 8 characters" : undefined}>
          <input
            type="password"
            value={form.password}
            onChange={set("password")}
            required
            minLength={mode === "register" ? 8 : undefined}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </Field>
        <button className="primary" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        {slow && (
          <p className="muted">
            The server runs on a free plan and sleeps when idle. Waking it up can take up to a minute.
          </p>
        )}
      </form>
      <div className="demo-box">
        <strong>Demo accounts</strong> (password <code>{DEMO_PASSWORD}</code>)
        <div className="row" style={{ marginTop: "0.5rem" }}>
          {DEMO.map((d) => (
            <button
              key={d.email}
              type="button"
              onClick={() => {
                setMode("login");
                setForm({ ...form, email: d.email, password: DEMO_PASSWORD });
              }}
            >
              Fill in {d.role}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
