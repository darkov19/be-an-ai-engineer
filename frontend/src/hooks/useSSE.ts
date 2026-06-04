import { useEffect, useRef } from 'react';

interface SSEHandlers {
  onOpen?: () => void;
  onStarted?: (payload: unknown) => void;
  onLog?: (payload: unknown) => void;
  onCompleted?: (payload: unknown) => void;
  onFailed?: (payload: unknown) => void;
  onError?: () => void;
  timeoutMs?: number;
}

const parsePayload = (event: MessageEvent) => {
  try {
    return JSON.parse(event.data);
  } catch {
    return event.data;
  }
};

export const useSSE = (
  url: string | null,
  enabled: boolean,
  handlers: SSEHandlers
) => {
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!enabled || !url) {
      return;
    }

    let closedByHook = false;
    const es = new EventSource(url);
    const timeoutId = handlersRef.current.timeoutMs
      ? window.setTimeout(() => {
          closedByHook = true;
          es.close();
          handlersRef.current.onError?.();
        }, handlersRef.current.timeoutMs)
      : null;

    const clearConnectionTimeout = () => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };

    es.onopen = () => {
      clearConnectionTimeout();
      handlersRef.current.onOpen?.();
    };

    es.addEventListener('task.started', (event) => {
      clearConnectionTimeout();
      handlersRef.current.onStarted?.(parsePayload(event));
    });

    es.addEventListener('task.log', (event) => {
      handlersRef.current.onLog?.(parsePayload(event));
    });

    es.addEventListener('task.completed', (event) => {
      closedByHook = true;
      handlersRef.current.onCompleted?.(parsePayload(event));
      es.close();
    });

    es.addEventListener('task.failed', (event) => {
      closedByHook = true;
      handlersRef.current.onFailed?.(parsePayload(event));
      es.close();
    });

    es.onerror = () => {
      clearConnectionTimeout();
      if (!closedByHook) {
        closedByHook = true;
        handlersRef.current.onError?.();
      }
      es.close();
    };

    return () => {
      closedByHook = true;
      clearConnectionTimeout();
      es.close();
    };
  }, [enabled, url]);
};
