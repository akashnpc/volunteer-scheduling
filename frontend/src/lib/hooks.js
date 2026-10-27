"use client";
import { useEffect, useRef, useState } from "react";

/**
 * Run an async loader whenever `deps` change. `reload()` re-runs it.
 * Keeps the previous data on screen while reloading so lists do not flash empty.
 */
export function useLoad(loader, deps) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    loaderRef
      .current()
      .then((data) => !cancelled && setState({ data, error: "", loading: false }))
      .catch((e) => !cancelled && setState((s) => ({ ...s, error: e.message, loading: false })));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}

/** Debounce a fast-changing value (search boxes). */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
