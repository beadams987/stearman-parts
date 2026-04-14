import { useEffect } from 'react';

const SITE_NAME = 'StearmanHQ';

/**
 * Set the document title and optionally the meta description for the current page.
 * Resets to default on unmount.
 */
export function usePageMeta(title?: string, description?: string) {
  useEffect(() => {
    const prevTitle = document.title;
    if (title) {
      document.title = `${title} — ${SITE_NAME}`;
    }

    const metaDesc = document.querySelector('meta[name="description"]');
    const prevDesc = metaDesc?.getAttribute('content') ?? '';
    if (description && metaDesc) {
      metaDesc.setAttribute('content', description);
    }

    return () => {
      document.title = prevTitle;
      if (metaDesc && prevDesc) {
        metaDesc.setAttribute('content', prevDesc);
      }
    };
  }, [title, description]);
}
