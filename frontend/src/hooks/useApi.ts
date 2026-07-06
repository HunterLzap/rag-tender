import { useState, useCallback, useRef } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Generic API call hook providing loading/error state management.
 * Returns the call function plus reactive state.
 */
export function useApi<T, P extends unknown[]>(
  apiFn: (...args: P) => Promise<T>
) {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });
  const mountedRef = useRef(true);

  const execute = useCallback(
    async (...args: P): Promise<T | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await apiFn(...args);
        if (mountedRef.current) {
          setState({ data, loading: false, error: null });
        }
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        if (mountedRef.current) {
          setState({ data: null, loading: false, error: message });
        }
        return null;
      }
    },
    [apiFn]
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}
