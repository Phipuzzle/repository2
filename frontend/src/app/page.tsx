import { AppShell } from "../components/layout/AppShell";
import { AuthGate } from "../features/auth/AuthGate";

export default function HomePage() {
  return (
    <AuthGate>
      <AppShell />
    </AuthGate>
  );
}
