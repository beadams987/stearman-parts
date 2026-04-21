import { ApplicationInsights } from '@microsoft/applicationinsights-web';
import { ReactPlugin } from '@microsoft/applicationinsights-react-js';

const connectionString = import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING ?? '';

export const reactPlugin = new ReactPlugin();

export const appInsights = new ApplicationInsights({
  config: {
    connectionString,
    extensions: [reactPlugin],
    enableAutoRouteTracking: true,
    disableCookiesUsage: true,
    disableFetchTracking: false,
    enableCorsCorrelation: false,
    enableAjaxErrorStatusText: true,
    autoTrackPageVisitTime: false,
  },
});

let loaded = false;

export function loadAppInsights(): void {
  if (loaded) return;
  if (!connectionString) {
    if (import.meta.env.DEV) {
      console.warn('[appInsights] VITE_APPINSIGHTS_CONNECTION_STRING is empty — telemetry disabled');
    }
    return;
  }
  appInsights.loadAppInsights();
  loaded = true;
}

export function trackEvent(name: string, properties?: Record<string, unknown>): void {
  if (!loaded) return;
  appInsights.trackEvent({ name }, properties);
}
