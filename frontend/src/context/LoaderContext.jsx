// src/context/LoaderContext.jsx

import { createContext, useContext, useState } from "react";
import BeautyverseLoader from "../components/BeautyverseLoader";

const LoaderContext = createContext();

export const useLoader = () => useContext(LoaderContext);

export const LoaderProvider = ({ children }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [onComplete, setOnComplete] = useState(() => () => {});

  const showLoader = (callback) => {
    setIsLoading(true);
    setOnComplete(() => () => {
      setIsLoading(false);
      callback?.();
    });
  };

  return (
    <LoaderContext.Provider value={{ showLoader }}>
      {children}
      {isLoading && <BeautyverseLoader onComplete={onComplete} />}
    </LoaderContext.Provider>
  );
};
