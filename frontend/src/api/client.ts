import createFetchClient from 'openapi-fetch';
import type { paths } from './schema';

let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

export const getAccessToken = () => accessToken;

export const apiClient = createFetchClient<paths>({
  baseUrl: '',
});

apiClient.use({
  async onRequest(req) {
    if (accessToken) {
      req.headers.set('Authorization', `Bearer ${accessToken}`);
    }
    return req;
  },
  async onResponse(res) {
    if (!res.ok) {
      const cloned = res.clone();
      try {
        const errorBody = (await cloned.json()) as { error?: { message?: string } };
        if (errorBody && errorBody.error) {
          throw new Error(errorBody.error.message || 'API request failed');
        }
      } catch (e: unknown) {
        if (e instanceof Error) throw e;
      }
    }
    return res;
  },
});
