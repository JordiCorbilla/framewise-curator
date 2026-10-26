import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUp, Folder, FolderOpen, Loader2 } from "lucide-react";
import { Modal } from "./Modal";
import { Button } from "./ui/button";
import { api } from "../services/api";

interface Folders {
  roots: { path: string; name: string }[];
  path: string | null;
  parent: string | null;
  items: { path: string; name: string }[];
  page: number;
  total: number;
  restricted: boolean;
}
export function FolderPicker({
  close,
  choose,
}: {
  close: () => void;
  choose: (path: string) => void;
}) {
  const [path, setPath] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const result = useQuery({
    queryKey: ["folders", path, page, filter],
    queryFn: () =>
      api<Folders>(
        `/folders?${new URLSearchParams({ ...(path ? { path } : {}), page: String(page), q: filter })}`,
      ),
  });
  const move = (next: string | null) => {
    setPath(next);
    setPage(1);
    setFilter("");
  };
  const folders = result.data;
  return (
    <Modal title="Choose a photographs folder" close={close}>
      <div className="folder-picker">
        <p>
          {folders?.restricted
            ? "Browse the photographs folder shared with Framewise. Originals are mounted read-only."
            : "Browse local folders. Framewise reads originals and stores previews separately."}{" "}
          No photographs are uploaded.
        </p>
        <div className="folder-navigation">
          <Button
            variant="outline"
            size="sm"
            disabled={!path}
            onClick={() => move(null)}
          >
            Locations
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!folders?.parent}
            onClick={() => move(folders?.parent ?? null)}
          >
            <ArrowUp size={14} />
            Up
          </Button>
        </div>
        <div className="folder-current" aria-label="Current folder">
          {path ?? "Choose a location"}
        </div>
        {path && (
          <input
            aria-label="Filter subfolders"
            placeholder="Filter subfolders…"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setPage(1);
            }}
          />
        )}
        <div className="folder-list" aria-busy={result.isFetching}>
          {result.isPending ? (
            <p>
              <Loader2 className="animate-spin" size={16} />
              Reading folders…
            </p>
          ) : result.error ? (
            <div className="error" role="alert">
              {result.error.message}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void result.refetch()}
              >
                Retry
              </Button>
            </div>
          ) : !folders?.items.length ? (
            <p>No subfolders here. You can select this folder.</p>
          ) : (
            folders.items.map((item) => (
              <button key={item.path} onClick={() => move(item.path)}>
                <Folder size={17} />
                <span>{item.name}</span>
                <span aria-hidden="true">›</span>
              </button>
            ))
          )}
        </div>
        {!!folders && folders.total > 100 && (
          <div className="form-actions">
            <Button
              size="sm"
              variant="outline"
              disabled={page === 1 || result.isFetching}
              onClick={() => setPage(page - 1)}
            >
              Previous folders
            </Button>
            <span>
              Page {page} of {Math.ceil(folders.total / 100)}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page * 100 >= folders.total || result.isFetching}
              onClick={() => setPage(page + 1)}
            >
              Next folders
            </Button>
          </div>
        )}
        <div className="form-actions">
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={!path || !folders || !!result.error || result.isFetching}
            onClick={() => choose(path!)}
          >
            <FolderOpen size={15} />
            Use this folder
          </Button>
        </div>
        {folders?.restricted && (
          <p className="footnote">
            To browse another drive or folder outside this location, stop
            Framewise and relaunch it with that parent folder selected.
          </p>
        )}
      </div>
    </Modal>
  );
}
