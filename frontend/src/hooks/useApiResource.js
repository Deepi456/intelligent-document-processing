import { useEffect, useState } from "react";

export function useApiResource(loader, dependencies = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let active = true;
    setState({ data: null, loading: true, error: null });
    loader()
      .then((data) => active && setState({ data, loading: false, error: null }))
      .catch((error) => active && setState({ data: null, loading: false, error }));
    return () => { active = false; };
  }, [...dependencies, refreshToken]);

  return { ...state, reload: () => setRefreshToken((value) => value + 1) };
}