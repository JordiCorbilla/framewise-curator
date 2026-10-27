import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCheck,
  FolderOpen,
  Image as ImageIcon,
  Layers,
  Loader2,
  ScanLine,
  SlidersHorizontal,
} from "lucide-react";
import type { Library } from "../types";
import { Button } from "../components/ui/button";
import { api } from "../services/api";
import { FolderPicker } from "../components/FolderPicker";
export function ScanForm({
  onCreated,
  onError,
  scanning,
}: {
  onCreated: (lib: Library) => void;
  onError: (message: string) => void;
  scanning: boolean;
}) {
  const [source, setSource] = useState("");
  const [choosing, setChoosing] = useState(false);
  const [name, setName] = useState("");
  const [recursive, setRecursive] = useState(true);
  const create = useMutation({
    mutationFn: () =>
      api<Library>("/libraries", "POST", { source, name, recursive }),
    onSuccess: onCreated,
    onError: (e) => onError(e.message),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">BRING HOME THE WHOLE STORY</div>
          <h1>A new collection.</h1>
          <p>Your originals stay exactly where they are.</p>
        </div>
      </div>
      <div className="scan-layout">
        <form
          className="scan-form"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <div className="scan-icon">
            <FolderOpen size={30} strokeWidth={1.3} />
          </div>
          <h2>Where are your photographs?</h2>
          <p>
            Choose a photographs folder. Framewise reads your files and stores
            previews in its own private cache.
          </p>
          <label htmlFor="folder-path">Source folder</label>
          <div className="source-folder-control">
            <input
              id="folder-path"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              required
              placeholder="Choose a folder or enter its path"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => setChoosing(true)}
            >
              <FolderOpen size={16} />
              Choose folder
            </Button>
          </div>
          <p className="field-hint">
            Browse folders without uploading photographs. Docker shows only your
            shared photo location.
          </p>
          <label htmlFor="collection-name">
            Collection name <span>(optional)</span>
          </label>
          <input
            id="collection-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Uses the folder name"
            maxLength={200}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => setRecursive(e.target.checked)}
            />
            Include subfolders
          </label>
          <Button
            type="submit"
            disabled={create.isPending || scanning || !source.trim()}
          >
            {create.isPending || scanning ? (
              <Loader2 className="animate-spin" size={16} />
            ) : (
              <ScanLine size={16} />
            )}
            Start local scan
            <ArrowRight size={15} />
          </Button>
        </form>
        <aside className="scan-explanation">
          <div className="eyebrow">FROM FOLDER TO FIRST PASS</div>
          {[
            {
              icon: ImageIcon,
              title: "See your frames as they arrive",
              text: "Embedded RAW previews first. No unnecessary full RAW development.",
            },
            {
              icon: SlidersHorizontal,
              title: "Measure, then recommend",
              text: "Local aesthetic inference when installed, plus measured detail and exposure.",
            },
            {
              icon: Layers,
              title: "Find the strongest in a sequence",
              text: "Conservative similarity groups keep alternatives within reach.",
            },
            {
              icon: CheckCheck,
              title: "You make the final call",
              text: "Keep, exclude and rate. Your decisions always take precedence.",
            },
          ].map((step, n) => (
            <div key={step.title}>
              <span className="step-number">0{n + 1}</span>
              <step.icon size={19} />
              <section>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </section>
            </div>
          ))}
          <p className="footnote">
            Supported: Nikon .NEF, .JPG, .JPEG, .PNG. CPU processing. No cloud
            connection required after setup.
          </p>
        </aside>
      </div>
      {choosing && (
        <FolderPicker
          close={() => setChoosing(false)}
          choose={(path) => {
            setSource(path);
            setChoosing(false);
          }}
        />
      )}
    </>
  );
}
