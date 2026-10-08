import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, Lock, Eye, EyeOff, LogIn } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    navigate("/", { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const success = await login(email, password);
    setLoading(false);

    if (success) {
      navigate("/", { replace: true });
    } else {
      setError("Invalid email or password");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f6f3] px-4">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="brand-mark mb-4">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </div>
          <h1 className="font-display text-2xl font-bold text-[#202521] tracking-tight">Atlas</h1>
          <p className="text-[#69716a] text-sm mt-1">Document Intelligence</p>
        </div>

        <div className="panel p-6">
          <h2 className="font-display text-lg font-semibold text-[#202521] mb-1">Sign in</h2>
          <p className="text-xs text-[#69716a] mb-6">Enter your credentials to access the workspace</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="field-label mb-2">Email</label>
              <div className="input-shell">
                <Mail size={16} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="bg-transparent border-0 p-0 text-[#202521]"
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <label className="field-label mb-2">Password</label>
              <div className="input-shell">
                <Lock size={16} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="bg-transparent border-0 p-0 text-[#202521]"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="ml-auto text-[#69716a] hover:text-[#202521]"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="button-primary w-full py-3"
              disabled={loading}
            >
              {loading ? (
                <span className="loading-spinner" />
              ) : (
                <>
                  <LogIn size={16} />
                  Sign In
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-[#dfe3dd] text-center">
            <p className="text-xs text-[#69716c]">
              Don't have an account?{" "}
              <a href="/signup" className="text-[#52705a] font-medium hover:underline">
                Sign up
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

