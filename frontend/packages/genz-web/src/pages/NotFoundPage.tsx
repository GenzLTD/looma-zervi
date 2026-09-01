import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-lg px-6 py-24 text-center">
      <h1 className="text-3xl font-semibold text-slate-900">404</h1>
      <p className="mt-4 text-slate-600">Page not found on genz.ltd marketing site.</p>
      <Link to="/" className="mt-8 inline-block text-teal-700 hover:underline">
        Back to home
      </Link>
    </section>
  );
}
