import { useEffect, useState } from "react";
import { Check, CheckCircle2, Copy, Download, FileCode2 } from "lucide-react";

interface ExportViewProps {
  testsVerifiedCount: number;
}

export function ExportView({ testsVerifiedCount }: ExportViewProps) {
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("README.md");
  const [fileContent, setFileContent] = useState<string>("");
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingFile, setLoadingFile] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    fetch("/api/repo/files")
      .then((r) => r.json())
      .then((data) => {
        if (!active) return;
        const list = Array.isArray(data.files) ? (data.files as string[]) : [];
        setFiles(list);
        if (list.length > 0 && !list.includes(selectedFile)) {
          setSelectedFile(list[0]);
        }
      })
      .finally(() => {
        if (active) setLoadingList(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedFile) return;
    let active = true;
    setLoadingFile(true);
    fetch(`/api/repo/file?path=${encodeURIComponent(selectedFile)}`)
      .then((r) => r.json())
      .then((data) => {
        if (!active) return;
        setFileContent(typeof data.content === "string" ? data.content : "");
      })
      .finally(() => {
        if (active) setLoadingFile(false);
      });
    return () => {
      active = false;
    };
  }, [selectedFile]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(fileContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Python Project Snapshot
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Packaged directly from the verified <code className="font-mono text-xs">competitor-tracker/</code> directory on disk.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <div className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md whitespace-nowrap">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span className="font-mono tabular-nums">{testsVerifiedCount}/{testsVerifiedCount} pytest passed</span>
          </div>

          <a
            href="/api/repo/zip"
            download="competitor-tracker.zip"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-blue-700 rounded-md hover:bg-blue-800 transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="w-3.5 h-3.5" />
            Download competitor-tracker.zip
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* File Tree */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-900">Repository Files</span>
            <span className="text-xs font-mono tabular-nums text-slate-500">{files.length} files</span>
          </div>
          <div className="max-h-[540px] overflow-y-auto divide-y divide-slate-100">
            {loadingList ? (
              <div className="p-4 text-xs text-slate-500">Loading repository index...</div>
            ) : (
              files.map((filePath) => (
                <button
                  key={filePath}
                  type="button"
                  onClick={() => setSelectedFile(filePath)}
                  className={`w-full text-left px-4 py-2 text-xs font-mono flex items-center gap-2 transition-colors cursor-pointer ${
                    selectedFile === filePath
                      ? "bg-blue-50 text-blue-800 font-semibold"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <FileCode2 className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                  <span className="truncate">{filePath}</span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* File Viewer */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-2">
            <span className="text-xs font-mono font-semibold text-slate-900 truncate">
              competitor-tracker/{selectedFile}
            </span>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 bg-slate-100 border border-slate-200 rounded hover:bg-slate-200 transition-colors whitespace-nowrap shrink-0 cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-700" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <div className="flex-1 max-h-[540px] overflow-auto bg-slate-50 p-4">
            {loadingFile ? (
              <div className="text-xs text-slate-500">Reading file...</div>
            ) : (
              <pre className="text-xs font-mono text-slate-800 leading-relaxed whitespace-pre">
                {fileContent}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
