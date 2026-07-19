import { useEffect } from "react";
import { AppShell, Container } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { Outlet, useLocation } from "react-router-dom";
import { Navbar } from "./Navbar";
import { Footer } from "./Footer";

export function AppLayout() {
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure(false);
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [location.pathname]);

  // The map route renders full-bleed (edge-to-edge, no Container/padding, no
  // footer) so it can fill the whole viewport below the navbar. Every other
  // route keeps the contained max-width layout.
  const fullBleed = location.pathname === "/map";

  return (
    <AppShell header={{ height: 60 }} padding={fullBleed ? 0 : "md"}>
      <AppShell.Header style={{ backgroundColor: "#1a1a1a", borderBottom: "1px solid #2b2b2b" }}>
        <Navbar mobileOpened={mobileOpened} onToggleMobile={toggleMobile} onNavigate={closeMobile} />
      </AppShell.Header>

      <AppShell.Main>
        {fullBleed ? (
          <Outlet />
        ) : (
          /* Sticky footer: this wrapper fills the visible area below the 60px
             header (minus the md padding), so the footer sits at the very bottom
             on short pages and content never overflows past it. */
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              minHeight: "calc(100dvh - 92px)",
            }}
          >
            <Container
              size="xl"
              px={{ base: "xs", sm: "md" }}
              style={{ flexGrow: 1, display: "flex", flexDirection: "column", width: "100%" }}
            >
              <Outlet />
            </Container>
            <Footer />
          </div>
        )}
      </AppShell.Main>
    </AppShell>
  );
}
