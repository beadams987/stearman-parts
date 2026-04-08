import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock pdfjs-dist before importing PdfViewer
const mockGetPage = vi.fn();
const mockDestroy = vi.fn();
const mockRender = vi.fn(() => ({
  promise: Promise.resolve(),
  cancel: vi.fn(),
}));

vi.mock('pdfjs-dist', () => ({
  getDocument: vi.fn(() => ({
    promise: Promise.resolve({
      numPages: 10,
      getPage: mockGetPage.mockResolvedValue({
        getViewport: () => ({ width: 612, height: 792 }),
        render: mockRender,
      }),
    }),
    onProgress: null,
    destroy: mockDestroy,
  })),
  GlobalWorkerOptions: { workerSrc: '' },
  version: '4.10.38',
}));

import PdfViewer from '../PdfViewer.tsx';

beforeEach(() => {
  vi.clearAllMocks();
  // Mock canvas getContext
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    scale: vi.fn(),
    clearRect: vi.fn(),
    fillRect: vi.fn(),
  })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
});

describe('PdfViewer', () => {
  it('renders without crashing', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const viewer = await screen.findByTestId('pdf-viewer');
    expect(viewer).toBeInTheDocument();
  });

  it('displays total page count after loading', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const pageDisplay = await screen.findByTestId('pdf-page-display');
    expect(pageDisplay).toHaveTextContent('/ 10');
  });

  it('renders page navigation buttons', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const prev = await screen.findByTestId('pdf-prev');
    const next = await screen.findByTestId('pdf-next');
    expect(prev).toBeInTheDocument();
    expect(next).toBeInTheDocument();
  });

  it('disables prev button on first page', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const prev = await screen.findByTestId('pdf-prev');
    expect(prev).toBeDisabled();
  });

  it('enables next button when there are more pages', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const next = await screen.findByTestId('pdf-next');
    expect(next).not.toBeDisabled();
  });

  it('navigates to next page on next button click', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const next = await screen.findByTestId('pdf-next');
    fireEvent.click(next);
    const input = screen.getByLabelText('Page number') as HTMLInputElement;
    expect(input.value).toBe('2');
  });

  it('renders zoom controls', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const zoomIn = await screen.findByTestId('pdf-zoom-in');
    const zoomOut = await screen.findByTestId('pdf-zoom-out');
    expect(zoomIn).toBeInTheDocument();
    expect(zoomOut).toBeInTheDocument();
  });

  it('has fit width and fit page buttons', async () => {
    render(<PdfViewer url="https://example.com/test.pdf" />);
    const fitWidth = await screen.findByLabelText('Fit width');
    const fitPage = await screen.findByLabelText('Fit page');
    expect(fitWidth).toBeInTheDocument();
    expect(fitPage).toBeInTheDocument();
  });
});
