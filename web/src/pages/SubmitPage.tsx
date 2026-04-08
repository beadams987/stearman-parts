import { useState, useRef, useCallback } from 'react';
import { Upload, CheckCircle, AlertTriangle, FileText, Image as ImageIcon, Link, X } from 'lucide-react';
import { usePageMeta } from '../hooks/usePageMeta.ts';

const API_BASE = import.meta.env.VITE_API_URL || '';
const HCAPTCHA_SITE_KEY = import.meta.env.VITE_HCAPTCHA_SITE_KEY || '';
const MAX_FILE_SIZE_MB = 50;

const ACCEPTED_TYPES = '.jpg,.jpeg,.png,.tif,.tiff,.gif,.webp,.pdf';

type SubmitState = 'idle' | 'uploading' | 'success' | 'error';

export default function SubmitPage() {
  const [state, setState] = useState<SubmitState>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [description, setDescription] = useState('');
  const [resourceUrl, setResourceUrl] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const captchaRef = useRef<HTMLDivElement>(null);

  usePageMeta(
    'Submit a Resource',
    'Contribute Stearman drawings, manuals, photos, or links to the community archive.',
  );

  // Load hCaptcha script dynamically
  const loadCaptcha = useCallback(() => {
    if (!HCAPTCHA_SITE_KEY || document.getElementById('hcaptcha-script')) return;
    const script = document.createElement('script');
    script.id = 'hcaptcha-script';
    script.src = 'https://js.hcaptcha.com/1/api.js';
    script.async = true;
    document.head.appendChild(script);
  }, []);

  // Render captcha after script loads
  const renderCaptcha = useCallback(() => {
    if (!HCAPTCHA_SITE_KEY || !captchaRef.current) return;
    const w = window as any;
    if (w.hcaptcha && captchaRef.current.childElementCount === 0) {
      w.hcaptcha.render(captchaRef.current, {
        sitekey: HCAPTCHA_SITE_KEY,
        callback: (token: string) => setCaptchaToken(token),
        'expired-callback': () => setCaptchaToken(''),
      });
    }
  }, []);

  // Initialize captcha on first interaction
  const initCaptcha = useCallback(() => {
    loadCaptcha();
    setTimeout(renderCaptcha, 1000);
  }, [loadCaptcha, renderCaptcha]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
    initCaptcha();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
    initCaptcha();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!file && !resourceUrl) {
      setErrorMsg('Please upload a file or provide a URL.');
      return;
    }

    if (file && file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setErrorMsg(`File exceeds ${MAX_FILE_SIZE_MB} MB limit.`);
      return;
    }

    // Captcha required if configured
    if (HCAPTCHA_SITE_KEY && !captchaToken) {
      setErrorMsg('Please complete the captcha.');
      return;
    }

    setState('uploading');

    try {
      const formData = new FormData();
      if (file) formData.append('file', file);
      else {
        // Create a minimal placeholder file if only URL submitted
        const placeholder = new Blob(['url-only-submission'], { type: 'text/plain' });
        formData.append('file', placeholder, 'url_submission.pdf');
      }
      formData.append('submitter_name', name);
      formData.append('submitter_email', email);
      formData.append('description', description);
      formData.append('resource_url', resourceUrl);
      formData.append('captcha_token', captchaToken);

      const response = await fetch(`${API_BASE}/api/submissions`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || `Upload failed (${response.status})`);
      }

      setState('success');
    } catch (err: any) {
      setState('error');
      setErrorMsg(err.message || 'Something went wrong. Please try again.');
    }
  };

  const resetForm = () => {
    setState('idle');
    setFile(null);
    setName('');
    setEmail('');
    setDescription('');
    setResourceUrl('');
    setCaptchaToken('');
    setErrorMsg('');
  };

  if (state === 'success') {
    return (
      <div className="max-w-2xl mx-auto py-16 px-4 text-center space-y-6">
        <CheckCircle className="w-16 h-16 text-green-500 mx-auto" />
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
          Submission Received!
        </h1>
        <p className="text-slate-600 dark:text-slate-400">
          Thank you for contributing to the Stearman community archive.
          Your submission will be reviewed before being published.
        </p>
        <button
          onClick={resetForm}
          className="px-6 py-2.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 cursor-pointer"
        >
          Submit Another
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8 py-8 px-4">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-sm font-medium">
          <Upload className="w-4 h-4" />
          Community Contribution
        </div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-50">
          Submit a Resource
        </h1>
        <p className="text-lg text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Have a Stearman drawing, manual, photo, or helpful link?
          Share it with the community. All submissions are reviewed before publishing.
        </p>
      </div>

      {/* Accepted formats */}
      <div className="flex flex-wrap justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">JPEG</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">PNG</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">TIFF</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">GIF</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">WebP</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">PDF</span>
        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded">URL</span>
        <span className="text-slate-400 dark:text-slate-500">· Max {MAX_FILE_SIZE_MB} MB</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200
            ${dragActive
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
              : file
                ? 'border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/10'
                : 'border-slate-300 dark:border-slate-600 hover:border-blue-400 dark:hover:border-blue-500'
            }
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            onChange={handleFileChange}
            className="hidden"
          />
          {file ? (
            <div className="flex items-center justify-center gap-3">
              {file.type.startsWith('image/') ? (
                <ImageIcon className="w-8 h-8 text-green-500" />
              ) : (
                <FileText className="w-8 h-8 text-green-500" />
              )}
              <div className="text-left">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              </div>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 cursor-pointer"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>
          ) : (
            <>
              <Upload className="w-10 h-10 text-slate-400 mx-auto mb-3" />
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Drag & drop a file here, or <span className="text-blue-600 dark:text-blue-400 font-medium">browse</span>
              </p>
              <p className="text-xs text-slate-400 mt-1">Images and PDFs up to {MAX_FILE_SIZE_MB} MB</p>
            </>
          )}
        </div>

        {/* Or provide a URL */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
            <Link className="w-4 h-4 inline mr-1.5" />
            Or provide a URL (optional)
          </label>
          <input
            type="url"
            value={resourceUrl}
            onChange={(e) => { setResourceUrl(e.target.value); initCaptcha(); }}
            placeholder="https://example.com/stearman-drawing.pdf"
            className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700
              bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200
              focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
            Description *
          </label>
          <textarea
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onFocus={initCaptcha}
            rows={3}
            placeholder="What is this resource? Drawing number, part name, manual section, etc."
            className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700
              bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200
              focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-y"
          />
        </div>

        {/* Name / Email (optional) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Your Name (optional)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="For attribution"
              className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700
                bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200
                focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Email (optional)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="For follow-up questions"
              className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700
                bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200
                focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
        </div>

        {/* hCaptcha */}
        {HCAPTCHA_SITE_KEY && (
          <div className="flex justify-center">
            <div ref={captchaRef} />
          </div>
        )}

        {/* Error message */}
        {errorMsg && (
          <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg text-red-700 dark:text-red-300 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {errorMsg}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={state === 'uploading'}
          className={`
            w-full py-3 text-sm font-semibold rounded-lg transition-colors duration-150 cursor-pointer
            ${state === 'uploading'
              ? 'bg-slate-400 text-white cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
            }
          `}
        >
          {state === 'uploading' ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Uploading...
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <Upload className="w-4 h-4" />
              Submit Resource
            </span>
          )}
        </button>
      </form>

      {/* Trust note */}
      <div className="text-center text-xs text-slate-400 dark:text-slate-500 space-y-1 pb-4">
        <p>All submissions are reviewed before publishing. We don't share your email.</p>
        <p>Accepted formats: JPEG, PNG, TIFF, GIF, WebP, PDF — max {MAX_FILE_SIZE_MB} MB.</p>
      </div>
    </div>
  );
}
