import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, Lock, User, Eye, EyeOff, UserPlus } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function SignupPage() {
  const navigate = useNavigate();
  const { register, isAuthenticated } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    const result = await register(email, fullName, password, confirmPassword);
    setLoading(false);

    if (result === true) {
      navigate("/", { replace: true });
    } else {
      // Show the actual backend error (duplicate email, password policy,
      // etc.) rather than a misleading generic validation message.
      setError(typeof result === "string" ? result : "Registration failed. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f6f3] px-4">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col items-center text-center mb-8">
          <div className="brand-mark mb-4">
            <UserPlus size={18} strokeWidth={2.5} />
          </div>
          <h1 className="font-display text-2xl font-bold text-[#202521] tracking-tight">Atlas</h1>
          <p className="text-[#69716a] text-sm mt-1">Document Intelligence</p>
        </div>

        <div className="panel p-6">
          <h2 className="font-display text-lg font-semibold text-[#202521] mb-1">Create account</h2>
          <p className="text-xs text-[#69716a] mb-6">Enter your details to create a new account</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="field-label mb-2">Full name</label>
              <div className="input-shell">
                <User size={16} />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                  required
                  className="bg-transparent border-0 p-0 text-[#202521]"
                  autoComplete="name"
                />
              </div>
            </div>

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
                  placeholder="At least 6 characters"
                  required
                  minLength={6}
                  className="bg-transparent border-0 p-0 text-[#202521]"
                  autoComplete="new-password"
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

            <div>
              <label className="field-label mb-2">Confirm password</label>
              <div className="input-shell">
                <Lock size={16} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  required
                  className="bg-transparent border-0 p-0 text-[#202521]"
                  autoComplete="new-password"
                />
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
                  <UserPlus size={16} />
                  Create account
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-[#dfe3dd] text-center">
            <p className="text-xs text-[#69716c]">
              Already have an account?{" "}
              <a href="/login" className="text-[#52705a] font-medium hover:underline">
                Sign in
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}