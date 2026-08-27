import { ReactNode } from "react";
import { SiteFooter, SiteHeader } from "./SiteChrome";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      {children}
      <SiteFooter />
    </>
  );
}
