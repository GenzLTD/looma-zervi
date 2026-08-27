import React from "react";
import i18n from "../../i18n";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: string | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error; reset: () => void }>;
}

/**
 * SaaS Error Boundary — captures React render errors with localized fallback UI.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[SaaS ErrorBoundary]", error, errorInfo);
    this.setState({ errorInfo: errorInfo.componentStack || null });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        const Fallback = this.props.fallback;
        return <Fallback error={this.state.error!} reset={this.handleReset} />;
      }

      const isDev = import.meta.env.DEV;
      const brand = i18n.t("brand.name");
      return (
        <div style={styles.container}>
          <div style={styles.card}>
            <div style={styles.icon}>⚠️</div>
            <h2 style={styles.title}>{i18n.t("error.title")}</h2>
            <p style={styles.subtitle}>
              {i18n.t("error.subtitle", { brand })}
            </p>
            {isDev && this.state.error && (
              <details style={styles.details}>
                <summary style={styles.summary}>{i18n.t("error.devInfo")}</summary>
                <pre style={styles.errorMsg}>{this.state.error.toString()}</pre>
                {this.state.errorInfo && (
                  <pre style={styles.errorMsg}>{this.state.errorInfo}</pre>
                )}
              </details>
            )}
            <div style={styles.actions}>
              <button onClick={this.handleReset} style={styles.btnSecondary}>
                {i18n.t("error.retry")}
              </button>
              <button onClick={this.handleReload} style={styles.btnPrimary}>
                {i18n.t("error.reload")}
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--color-bg-page, #F5F6FA)",
    padding: "24px",
  },
  card: {
    background: "var(--color-bg-primary, #FFFFFF)",
    borderRadius: "12px",
    padding: "48px",
    maxWidth: "560px",
    textAlign: "center",
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
  },
  icon: {
    fontSize: "48px",
    marginBottom: "16px",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    color: "var(--color-text-primary, #1A1A2E)",
    marginBottom: "8px",
  },
  subtitle: {
    fontSize: "14px",
    color: "var(--color-text-secondary, #6B6B80)",
    marginBottom: "24px",
    lineHeight: 1.6,
  },
  details: {
    background: "#F8F8FA",
    borderRadius: "8px",
    padding: "12px",
    marginBottom: "24px",
    textAlign: "left",
    maxHeight: "200px",
    overflow: "auto",
  },
  summary: {
    cursor: "pointer",
    fontSize: "13px",
    color: "var(--color-text-secondary, #6B6B80)",
    marginBottom: "8px",
  },
  errorMsg: {
    fontSize: "12px",
    color: "#E74C3C",
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
    margin: 0,
  },
  actions: {
    display: "flex",
    gap: "12px",
    justifyContent: "center",
  },
  btnSecondary: {
    padding: "8px 20px",
    borderRadius: "8px",
    border: "1px solid var(--color-border, #E0E0E8)",
    background: "transparent",
    color: "var(--color-text-primary, #1A1A2E)",
    cursor: "pointer",
    fontSize: "14px",
  },
  btnPrimary: {
    padding: "8px 20px",
    borderRadius: "8px",
    border: "none",
    background: "var(--color-primary, #4A3AFF)",
    color: "#FFFFFF",
    cursor: "pointer",
    fontSize: "14px",
  },
};

export default ErrorBoundary;
