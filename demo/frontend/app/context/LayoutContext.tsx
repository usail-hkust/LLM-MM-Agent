"use client";
import React, { createContext, useContext } from "react";

/**
 * Layout Context
 * Propagates the geometric constraints of the parent container to child atoms.
 */
export type LayoutContextType = {
  /**
   * isFixed:
   * - true: Parent has fixed/defined height (e.g. Workbench/Grid). Child can use height="100%".
   * - false: Parent is auto-height/scrollable (e.g. Focus/Document). Child must use min-height.
   */
  isFixed: boolean;
  
  /**
   * [NEW] contentBottomPadding:
   * Defines how much space should be reserved at the bottom of scrollable areas 
   * to prevent content from being hidden behind floating elements (like the Dock).
   */
  contentBottomPadding?: number;
};

const LayoutContext = createContext<LayoutContextType>({ isFixed: false });

export const useLayoutContext = () => useContext(LayoutContext);

export const LayoutProvider = ({ 
  isFixed, 
  contentBottomPadding, 
  children 
}: { 
  isFixed: boolean; 
  contentBottomPadding?: number; 
  children: React.ReactNode 
}) => {
  return (
    <LayoutContext.Provider value={{ isFixed, contentBottomPadding }}>
      {children}
    </LayoutContext.Provider>
  );
};
