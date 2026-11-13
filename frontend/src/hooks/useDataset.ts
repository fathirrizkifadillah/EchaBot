"use client";
import { useState, useCallback } from "react";
import { uploadFile, useSample, UploadResponse } from "@/lib/api";

export interface DatasetState {
  name: string;
  preview: Record<string, string>[];
  report: Record<string, unknown>;
}

export function useDataset() {
  const [dataset, setDataset] = useState<DatasetState | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleResult = useCallback((res: UploadResponse, name: string) => {
    if (res.ok) {
      setDataset({
        name,
        preview: res.preview || [],
        report: res.report || {},
      });
      setError(null);
    } else {
      setError(res.message);
    }
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      setError(null);
      try {
        const res = await uploadFile(file);
        handleResult(res, file.name);
        return res;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload gagal.";
        setError(msg);
        return { ok: false, message: msg } as UploadResponse;
      } finally {
        setUploading(false);
      }
    },
    [handleResult]
  );

  const loadSample = useCallback(async () => {
    setUploading(true);
    setError(null);
    try {
      const res = await useSample();
      handleResult(res, "Walmart_Sales.csv");
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Gagal load sample.";
      setError(msg);
      return { ok: false, message: msg } as UploadResponse;
    } finally {
      setUploading(false);
    }
  }, [handleResult]);

  const clear = useCallback(() => {
    setDataset(null);
    setError(null);
  }, []);

  return { dataset, uploading, error, upload, loadSample, clear };
}
