/**
 * @vitest-environment jsdom
 *
 * Tests for the CVUpload component.
 *
 * Regression-pin: CVUpload must call `get('/resumes/')` exactly once on
 * mount (not in a render loop, not zero times). We had a bug where a
 * missing dependency array caused this fetch to fire continuously.
 *
 * The API client is mocked so no real network traffic happens; we
 * assert the mock was invoked and that the drag-and-drop path triggers
 * the upload fetch.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  apiRequest: vi.fn(),
}));

import { get } from '../api/client';
import CVUpload from '../components/CVUpload';

describe('CVUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockResolvedValue([]);
  });

  it('fetches the resume list once on mount', async () => {
    render(<CVUpload />);

    await waitFor(() => {
      expect(get).toHaveBeenCalledTimes(1);
    });
    expect(get).toHaveBeenCalledWith('/resumes/', expect.any(Object));
  });

  it('renders the file picker UI and the drag-and-drop hint', async () => {
    render(<CVUpload />);

    expect(
      screen.getByText(/drop your resume here or click to browse/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/supports pdf and docx files up to 5mb/i)
    ).toBeInTheDocument();

    // Hidden file input is present for keyboard-accessible upload.
    // It's a sibling to the dropzone, type=file, accept=.pdf,.docx.
    const input = document.getElementById('file-input');
    expect(input).toBeTruthy();
    expect(input.getAttribute('type')).toBe('file');
    expect(input.getAttribute('accept')).toBe('.pdf,.docx');
  });

  it('triggers an upload fetch when a valid file is dropped', async () => {
    // Mock global fetch — CVUpload uses raw fetch() for /resumes/upload
    // because the request is multipart (the api client only does JSON).
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'r1' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    // Make the parsing-completion poll resolve immediately so we don't
    // wait the full 30s timeout for this test.
    get.mockResolvedValueOnce([]); // initial fetchResumes on mount
    get.mockResolvedValue({ id: 'r1', parsed_data: { skills: [] } });

    render(<CVUpload />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    const file = new File(['%PDF-1.4 test'], 'resume.pdf', {
      type: 'application/pdf',
    });

    // The dropzone is the parent of the hidden input. Find it via the
    // hint text and walk up.
    const hint = screen.getByText(/drop your resume here or click to browse/i);
    const dropzone = hint.closest('.card');
    expect(dropzone).toBeTruthy();

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/resumes/upload',
        expect.objectContaining({ method: 'POST' })
      );
    });

    vi.unstubAllGlobals();
  });
});
