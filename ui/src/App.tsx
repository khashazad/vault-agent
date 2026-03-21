import { RouterProvider } from "react-router";
import { router } from "./router";
import { VaultProvider } from "./context/VaultContext";

export default function App() {
  return (
    <VaultProvider>
      <RouterProvider router={router} />
    </VaultProvider>
  );
}
