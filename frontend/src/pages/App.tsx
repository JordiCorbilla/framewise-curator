import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Aperture,
  ArrowDownToLine,
  ArrowRight,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Folder,
  FolderOpen,
  Grid2X2,
  Library as LibraryIcon,
  Loader2,
  LockKeyhole,
  Plus,
  ScanLine,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { PhotoViewer } from "../components/PhotoViewer";
import { Progress, active } from "../components/Progress";
import { Budget, Gallery } from "../features/curation/Gallery";
import { ScanForm } from "./Scan";
import { Export } from "./Export";
import { Settings } from "./Settings";
import { api } from "../services/api";
import type { Job, Library, ModelStatus, Photo } from "../types";
type Page = "Library" | "Scan" | "Curate" | "Selected" | "Export" | "Settings";
const navigation = [
  { label: "Library", icon: LibraryIcon },
  { label: "Scan", icon: ScanLine },
  { label: "Curate", icon: Grid2X2 },
  { label: "Selected", icon: CheckCheck },
  { label: "Export", icon: ArrowDownToLine },
  { label: "Settings", icon: Settings2 },
] as const;

export function App() {
  const client = useQueryClient();
  const [page, setPage] = useState<Page>("Library");
  const [libraryId, setLibraryId] = useState("");
  const [error, setError] = useState("");
  const libraries = useQuery({
    queryKey: ["libraries"],
    queryFn: () => api<Library[]>("/libraries"),
    refetchInterval: (query) =>
      query.state.data?.some((l) => active(l.job)) ? 2500 : false,
  });
  const model = useQuery({
    queryKey: ["model"],
    queryFn: () => api<ModelStatus>("/models"),
    refetchInterval: 10000,
  });
  const library =
    libraries.data?.find((l) => l.id === libraryId) ?? libraries.data?.[0];
  const [viewer, setViewer] = useState<Photo | null>(null);
  const [galleryItems, setGalleryItems] = useState<Photo[]>([]);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["libraries"] });
    void client.invalidateQueries({ queryKey: ["photos"] });
    void client.invalidateQueries({ queryKey: ["photo"] });
    void client.invalidateQueries({ queryKey: ["related"] });
  };
  const change = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<Pick<Photo, "decision" | "stars">>;
    }) => api<Photo>(`/photos/${id}/decision`, "PATCH", data),
    onSuccess: (p) => {
      client.setQueryData(["photo", p.id], p);
      refresh();
    },
    onError: (e) => setError(e.message),
  });
  const decide = (
    id: string,
    data: Partial<Pick<Photo, "decision" | "stars">>,
  ) => change.mutate({ id, data });
  const scan = useMutation({
    mutationFn: (id: string) => api(`/libraries/${id}/scan`, "POST", {}),
    onSuccess: () => {
      refresh();
      setPage("Curate");
    },
    onError: (e) => setError(e.message),
  });
  const cancel = useMutation({
    mutationFn: (id: string) => api(`/jobs/${id}/cancel`, "POST", {}),
    onSuccess: refresh,
    onError: (e) => setError(e.message),
  });
  const jobId = library?.job?.id;
  const jobIsActive = active(library?.job);
  useEffect(() => {
    if (!jobId || !jobIsActive) return;
    const events = new EventSource(`/api/jobs/${jobId}/events`);
    let updated = 0;
    events.onmessage = (event) => {
      const job: Job = JSON.parse(event.data);
      client.setQueryData<Library[]>(["libraries"], (values) =>
        values?.map((l) => (l.job?.id === jobId ? { ...l, job } : l)),
      );
      if (Date.now() - updated > 2000 || !active(job)) {
        void client.invalidateQueries({ queryKey: ["photos"] });
        void client.invalidateQueries({ queryKey: ["libraries"] });
        updated = Date.now();
      }
      if (!active(job)) events.close();
    };
    return () => events.close();
  }, [jobId, jobIsActive, client]);
  const choose = (lib: Library) => {
    setLibraryId(lib.id);
    setPage("Curate");
    setViewer(null);
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          aria-label="Framewise library"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Library");
          }}
        >
          <Aperture size={27} strokeWidth={1.5} />
          <span>
            framewise<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="sidebar-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.label}
              aria-label={item.label}
              aria-current={page === item.label ? "page" : undefined}
              className={page === item.label ? "active" : ""}
              onClick={() => {
                setPage(item.label);
                setViewer(null);
              }}
            >
              <item.icon size={17} strokeWidth={1.6} />
              <span>{item.label}</span>
              {item.label === "Selected" && !!library?.selected && (
                <b>{library.selected}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-collections">
          <div className="sidebar-label">
            COLLECTIONS
            <button onClick={() => setPage("Scan")} aria-label="New collection">
              <Plus size={14} />
            </button>
          </div>
          {libraries.data?.map((lib) => (
            <button
              key={lib.id}
              className={lib.id === library?.id ? "current" : ""}
              onClick={() => choose(lib)}
            >
              <Folder size={14} />
              <span>{lib.name}</span>
              <small>{lib.total}</small>
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="local-badge">
            <span className="status-dot" />
            LOCAL WORKSPACE
          </div>
          <p>
            <LockKeyhole size={12} />
            Your photographs stay here.
          </p>
          <div className="model-small">
            <span
              className={`status-dot ${model.data?.status !== "ready" ? "muted" : ""}`}
            />
            {model.data?.status === "ready"
              ? "Aesthetic model ready · CPU"
              : model.data?.status === "loading"
                ? "Loading aesthetic model…"
                : "Classical analysis available"}
          </div>
          <span className="version">FRAMEWISE / 0.1</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <b>{page}</b>
            {library && page !== "Library" && (
              <>
                <ChevronRight size={13} />
                <span className="breadcrumb-name">{library.name}</span>
              </>
            )}
          </div>
          <span className="topbar-private">
            <ShieldCheck size={14} />
            Private by design
          </span>
        </header>
        {(error || libraries.error) && (
          <div className="error-banner" role="alert">
            <span>{error || libraries.error?.message}</span>
            <button
              onClick={() => {
                setError("");
                void libraries.refetch();
              }}
              aria-label="Dismiss error"
            >
              <X size={16} />
            </button>
          </div>
        )}
        <main>
          {page === "Library" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR PHOTOGRAPHIC WORKSPACE</div>
                  <h1>
                    Your best frames,
                    <br />
                    <em>discovered.</em>
                  </h1>
                  <p>A considered first pass. The final eye is yours.</p>
                </div>
                <Button onClick={() => setPage("Scan")}>
                  <Plus size={16} />
                  Scan a Folder
                </Button>
              </div>
              <div className="section-heading">
                <h2>
                  Your collections <span>{libraries.data?.length ?? 0}</span>
                </h2>
                <span>Originals always stay untouched</span>
              </div>
              {libraries.isPending ? (
                <div className="empty">
                  <Loader2 className="animate-spin" />
                  Opening your library…
                </div>
              ) : !libraries.data?.length ? (
                <section className="welcome-empty">
                  <div className="empty-frame">
                    <Aperture size={50} strokeWidth={1} />
                  </div>
                  <h2>Every trip has a few extraordinary frames.</h2>
                  <p>
                    Bring in a folder. Find the photographs you want to spend
                    time with.
                    <br />
                    NEF, JPEG and PNG · local analysis · no uploads
                  </p>
                  <Button onClick={() => setPage("Scan")}>
                    <FolderOpen size={16} />
                    Scan your first folder
                    <ArrowRight size={15} />
                  </Button>
                </section>
              ) : (
                <div className="collection-grid">
                  {libraries.data.map((lib) => (
                    <button
                      key={lib.id}
                      className="collection-card"
                      onClick={() => choose(lib)}
                    >
                      <div className="collection-cover">
                        {lib.cover ? (
                          <img
                            src={lib.cover}
                            alt={`Best-ranked frame in ${lib.name}`}
                          />
                        ) : (
                          <Aperture size={44} />
                        )}
                        <span className="collection-status">
                          {active(lib.job)
                            ? "Processing"
                            : lib.job?.status === "complete"
                              ? "Ready to curate"
                              : "Open collection"}
                        </span>
                      </div>
                      <div className="collection-info">
                        <div>
                          <h3>{lib.name}</h3>
                          <p>
                            {lib.total} photographs <span>·</span>{" "}
                            {lib.selected} selected
                          </p>
                        </div>
                        <ArrowRight size={18} />
                      </div>
                      <div className="collection-footer">
                        <span>
                          {new Date(lib.created).toLocaleDateString("en-GB", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </span>
                        <span>
                          {lib.config.recursive
                            ? "Recursive scan"
                            : "Single folder"}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              <div className="library-note">
                <ShieldCheck size={20} />
                <div>
                  <strong>A lighter way to get to the edit.</strong>
                  <p>
                    Read-only originals. Persistent decisions. A shortlist that
                    leaves room for your judgement.
                  </p>
                </div>
              </div>
            </>
          )}
          {page === "Scan" && (
            <ScanForm
              onCreated={(lib) => {
                setLibraryId(lib.id);
                refresh();
                scan.mutate(lib.id);
              }}
              onError={setError}
              scanning={scan.isPending}
            />
          )}
          {(page === "Curate" || page === "Selected") &&
            (library ? (
              <>
                <div className="page-heading gallery-heading">
                  <div>
                    <div className="eyebrow">
                      {page === "Selected"
                        ? "THE NEXT CHAPTER"
                        : "A FIRST PASS, THROUGH YOUR LENS"}
                    </div>
                    <h1>
                      {page === "Selected"
                        ? "Selected for editing"
                        : library.name}
                    </h1>
                    <p>
                      {library.total} photographs{" "}
                      <span className="dot-separator">/</span>{" "}
                      {library.selected} selected{" "}
                      <span className="dot-separator">/</span>{" "}
                      {Math.round(
                        (library.selected / Math.max(library.total, 1)) * 100,
                      )}
                      % of your collection
                    </p>
                  </div>
                  {page === "Selected" ? (
                    <Button onClick={() => setPage("Export")}>
                      <ArrowDownToLine size={15} />
                      Export selection
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      onClick={() => setPage("Selected")}
                    >
                      <CheckCheck size={16} />
                      Review selection
                      <ArrowRight size={14} />
                    </Button>
                  )}
                </div>
                {library.job && (active(library.job) || page === "Curate") && (
                  <Progress
                    job={library.job}
                    cancel={() => cancel.mutate(library.job!.id)}
                    resume={() => scan.mutate(library.id)}
                    pending={scan.isPending || cancel.isPending}
                  />
                )}
                {page === "Selected" && <SelectionSummary library={library} />}
                <Budget
                  key={library.id}
                  library={library}
                  onError={setError}
                  refresh={refresh}
                />
                {model.data?.status !== "ready" && (
                  <div className="notice">
                    <CircleHelp size={15} />
                    <span>
                      {model.data?.status === "loading"
                        ? "Loading the local aesthetic model."
                        : "Aesthetic model unavailable. Recommendations currently use measured sharpness and tonal quality."}{" "}
                      <button onClick={() => setPage("Settings")}>
                        Model settings
                      </button>
                    </span>
                  </div>
                )}
                <Gallery
                  key={`${library.id}-${page}`}
                  library={library}
                  selected={page === "Selected"}
                  decide={decide}
                  open={(p, items) => {
                    setViewer(p);
                    setGalleryItems(items);
                  }}
                />
              </>
            ) : (
              <NoCollection start={() => setPage("Scan")} />
            ))}
          {page === "Export" &&
            (library ? (
              <Export library={library} />
            ) : (
              <NoCollection start={() => setPage("Scan")} />
            ))}
          {page === "Settings" && (
            <Settings
              library={library}
              model={model.data}
              onError={setError}
              refresh={refresh}
            />
          )}
        </main>
        <footer className="workspace-footer">
          <span>YOUR BEST FRAMES, DISCOVERED.</span>
          <span>
            <LockKeyhole size={11} />
            Local-first. Always yours.
          </span>
        </footer>
      </div>
      {viewer && (
        <PhotoViewer
          photo={viewer}
          items={galleryItems}
          close={() => setViewer(null)}
          navigate={setViewer}
          decide={decide}
        />
      )}
    </div>
  );
}

function NoCollection({ start }: { start: () => void }) {
  return (
    <div className="empty">
      <FolderOpen size={40} />
      <h2>Your workspace starts with a folder.</h2>
      <Button onClick={start}>Scan a Folder</Button>
    </div>
  );
}

function SelectionSummary({ library }: { library: Library }) {
  return (
    <section
      className="selection-summary"
      aria-label="Selected photograph quality summary"
    >
      <div>
        <span>YOUR FINAL SHORTLIST</span>
        <strong>
          {library.selected}
          <small>frames</small>
        </strong>
      </div>
      {(["aesthetic", "sharpness", "exposure"] as const).map((key) => (
        <div key={key}>
          <span>
            {key === "aesthetic"
              ? "MEAN AESTHETIC"
              : key === "sharpness"
                ? "MEAN DETAIL"
                : "MEAN TONAL QUALITY"}
          </span>
          <strong>
            {library.summary?.[key]?.toFixed(1) ?? "—"}
            <small>{key === "aesthetic" ? "/ 10" : "/ 100"}</small>
          </strong>
        </div>
      ))}
      <p>
        Measured averages across the final combined selection. Artistic
        judgement stays with you.
      </p>
    </section>
  );
}
