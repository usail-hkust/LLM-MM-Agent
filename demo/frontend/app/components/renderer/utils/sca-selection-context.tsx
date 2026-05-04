"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

interface ScaSelectionContextValue {
  ignoreSelection: boolean;
  markUserSelected: () => void;
}

const ScaSelectionContext = createContext<ScaSelectionContextValue | null>(null);

export function ScaSelectionProvider({
  scaKey,
  hasOptions,
  isReadOnly,
  children,
}: {
  scaKey: string;
  hasOptions: boolean;
  isReadOnly: boolean;
  children: React.ReactNode;
}) {
  const [hasUserSelected, setHasUserSelected] = useState(false);

  useEffect(() => {
    setHasUserSelected(false);
  }, [scaKey]);

  const value = useMemo(
    () => ({
      ignoreSelection: hasOptions && !hasUserSelected && !isReadOnly,
      markUserSelected: () => setHasUserSelected(true),
    }),
    [hasOptions, hasUserSelected, isReadOnly],
  );

  return (
    <ScaSelectionContext.Provider value={value}>
      {children}
    </ScaSelectionContext.Provider>
  );
}

export function useScaSelectionContext() {
  return useContext(ScaSelectionContext);
}
