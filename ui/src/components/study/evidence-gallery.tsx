"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { ExternalLink, ImageOff, X } from "lucide-react";
import type { StoredCrop } from "@/lib/study-types";
import { cn } from "@/lib/utils";
import { docLabel } from "./format";

const CROPS_PREFIX = "data/crops/";

/** `data/crops/x.png` → `/api/crops/x.png`; `null` outside data/crops. */
function cropUrl(path: string): string | null {
  if (!path.startsWith(CROPS_PREFIX)) return null;
  const rest = path.slice(CROPS_PREFIX.length).split("/");
  return `/api/crops/${rest.map(encodeURIComponent).join("/")}`;
}

const cropLabel = (crop: StoredCrop) =>
  `${docLabel(crop.region.doc)} · p. ${crop.region.page}`;

function CropImage({
  src,
  alt,
  className,
}: {
  src: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        role="img"
        aria-label={`${alt} (image unavailable)`}
        className={cn(
          "bg-muted text-muted-foreground flex items-center justify-center",
          className,
        )}
      >
        <ImageOff
          aria-hidden
          className="size-5"
        />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={className}
    />
  );
}

export function EvidenceGallery({ evidence }: { evidence: StoredCrop[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (evidence.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">No image evidence saved.</p>
    );
  }
  const current = open === null ? null : evidence[open];
  const currentUrl = current ? cropUrl(current.path) : null;

  return (
    <Dialog.Root
      open={open !== null}
      onOpenChange={(o) => !o && setOpen(null)}
    >
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {evidence.map((crop, i) => (
          <li key={crop.path}>
            <button
              type="button"
              onClick={() => setOpen(i)}
              className="group focus-visible:ring-ring/50 block w-full overflow-hidden rounded-lg border text-left outline-none focus-visible:ring-[3px]"
            >
              <CropImage
                src={cropUrl(crop.path)}
                alt={`Evidence from ${cropLabel(crop)}`}
                className="bg-muted aspect-[4/3] w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
              />
              <span className="block truncate border-t px-2 py-1 text-xs font-medium">
                {cropLabel(crop)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Dialog.Portal>
        <Dialog.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[min(92vw,64rem)] -translate-x-1/2 -translate-y-1/2 flex-col gap-3 rounded-xl border p-4 shadow-lg">
          {current && (
            <>
              <div className="flex items-center justify-between gap-3">
                <Dialog.Title className="text-sm font-semibold">
                  {cropLabel(current)}
                </Dialog.Title>
                <div className="flex items-center gap-1">
                  {currentUrl && (
                    <a
                      href={currentUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-muted-foreground hover:text-foreground hover:bg-accent inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs"
                    >
                      <ExternalLink
                        aria-hidden
                        className="size-3.5"
                      />
                      Full size
                    </a>
                  )}
                  <Dialog.Close
                    className="text-muted-foreground hover:text-foreground hover:bg-accent focus-visible:ring-ring/50 rounded-md p-1 outline-none focus-visible:ring-[3px]"
                    aria-label="Close"
                  >
                    <X
                      aria-hidden
                      className="size-4"
                    />
                  </Dialog.Close>
                </div>
              </div>
              <Dialog.Description className="sr-only">
                {`Image region saved as evidence from ${cropLabel(current)}.`}
              </Dialog.Description>
              <div className="bg-muted/40 min-h-0 flex-1 overflow-auto rounded-lg border">
                <CropImage
                  key={current.path}
                  src={currentUrl}
                  alt={`Evidence from ${cropLabel(current)}`}
                  className="mx-auto h-auto max-h-[75vh] w-auto max-w-full object-contain"
                />
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
