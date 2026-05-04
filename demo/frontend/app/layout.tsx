import { Providers } from "./providers";
import { AuthProvider } from "./context/AuthContext";
import { SignalProvider } from "./context/SignalContext";
import { CopilotProvider } from "./context/CopilotContext";
import { UIProvider } from "./hooks/useUI";
import { ProgressProvider } from "./context/ProgressContext";
import { ProgressIndicator } from "./components/ui/ProgressIndicator";
import { ConfigHydrationGate } from "./components/shared/ConfigHydrationGate";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>
          <AuthProvider>
            <SignalProvider>
              <CopilotProvider>
                <UIProvider>
                  <ProgressProvider>
                    <ConfigHydrationGate>
                      {children}
                      <ProgressIndicator />
                    </ConfigHydrationGate>
                  </ProgressProvider>
                </UIProvider>
              </CopilotProvider>
            </SignalProvider>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
