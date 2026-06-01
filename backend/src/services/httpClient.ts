export class ExternalApiError extends Error {
  status?: number;
  provider: string;

  constructor(provider: string, message: string, status?: number) {
    super(message);
    this.name = 'ExternalApiError';
    this.provider = provider;
    this.status = status;
  }
}

export const fetchJson = async <T>(
  provider: string,
  url: string,
  options: RequestInit = {},
  timeoutMs = 12000
): Promise<T> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'User-Agent': 'trip-planner-student-project/1.0',
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      throw new ExternalApiError(provider, `${provider} returned ${response.status}`, response.status);
    }

    return (await response.json()) as T;
  } catch (error: any) {
    if (error instanceof ExternalApiError) {
      throw error;
    }

    const message = error?.name === 'AbortError'
      ? `${provider} request timed out`
      : error?.message || `${provider} request failed`;

    throw new ExternalApiError(provider, message);
  } finally {
    clearTimeout(timeout);
  }
};
