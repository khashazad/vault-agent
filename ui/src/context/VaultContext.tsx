import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { fetchVaultConfig, setVaultConfig } from "../api/client";

interface VaultContextValue {
  vaultPath: string | null;
  vaultName: string | null;
  isLoading: boolean;
  setVault: (path: string) => Promise<void>;
}

const VaultContext = createContext<VaultContextValue | null>(null);

export function VaultProvider({ children }: { children: ReactNode }) {
  const [vaultPath, setVaultPath] = useState<string | null>(null);
  const [vaultName, setVaultName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchVaultConfig()
      .then((cfg) => {
        setVaultPath(cfg.vault_path);
        setVaultName(cfg.vault_name);
      })
      .catch(() => {
        // Server may be down — leave as null
      })
      .finally(() => setIsLoading(false));
  }, []);

  const setVault = useCallback(async (path: string) => {
    const cfg = await setVaultConfig(path);
    setVaultPath(cfg.vault_path);
    setVaultName(cfg.vault_name);
  }, []);

  return (
    <VaultContext.Provider
      value={{ vaultPath, vaultName, isLoading, setVault }}
    >
      {children}
    </VaultContext.Provider>
  );
}

export function useVault(): VaultContextValue {
  const ctx = useContext(VaultContext);
  if (!ctx) throw new Error("useVault must be used within VaultProvider");
  return ctx;
}
