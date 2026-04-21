import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthKitProvider } from '@workos-inc/authkit-react';
import { AppInsightsContext } from '@microsoft/applicationinsights-react-js';
import App from './App.tsx';
import { loadAppInsights, reactPlugin } from './lib/appInsights.ts';
import './index.css';

loadAppInsights();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000, // 2 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const workosClientId = import.meta.env.VITE_WORKOS_CLIENT_ID ?? '';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppInsightsContext.Provider value={reactPlugin}>
      <AuthKitProvider clientId={workosClientId}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </AuthKitProvider>
    </AppInsightsContext.Provider>
  </StrictMode>,
);
