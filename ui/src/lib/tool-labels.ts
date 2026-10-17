import type { LucideIcon } from "lucide-react";
import {
  Archive,
  BookOpen,
  ClipboardCheck,
  Compass,
  FilePen,
  FilePlus,
  FileText,
  Files,
  Folder,
  Image,
  LandPlot,
  Library,
  ListTodo,
  ListTree,
  Map,
  MapPin,
  MessageCircleQuestionMark,
  Search,
  Send,
  TextSearch,
  Users,
  Wrench,
  ZoomIn,
} from "lucide-react";

type Args = Record<string, unknown>;

export type ToolLabel = {
  /** Short human label, e.g. "Read pages". */
  label: string;
  icon: LucideIcon;
  /** The key arguments in a few words, e.g. "plu p.320–332". */
  summary?: (args: Args) => string | undefined;
};

/** Sub-agent display names and icons, keyed by `subagent_type`. */
export const SUBAGENTS: Record<string, { name: string; icon: LucideIcon }> = {
  surveyor: { name: "Surveyor", icon: Compass },
  zoning_analyst: { name: "Zoning analyst", icon: Map },
  doc_analyst: { name: "Document analyst", icon: BookOpen },
};

const str = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim()
    ? value.trim()
    : typeof value === "number"
      ? String(value)
      : undefined;

const quoted = (value: unknown) => {
  const text = str(value);
  return text ? `“${text}”` : undefined;
};

const page = (args: Args) =>
  [str(args.doc), args.page != null ? `p.${args.page}` : undefined]
    .filter(Boolean)
    .join(" ");

const list = (value: unknown) =>
  Array.isArray(value) ? value.map(String).join(", ") : str(value);

const TOOLS: Record<string, ToolLabel> = {
  // Site
  geocode: {
    label: "Geocode address",
    icon: MapPin,
    summary: (a) => quoted(a.query),
  },
  find_parcels: {
    label: "Find parcels",
    icon: LandPlot,
    summary: (a) =>
      a.latitude != null && a.longitude != null
        ? `${a.latitude}, ${a.longitude}`
        : undefined,
  },
  describe_parcels: {
    label: "Describe parcels",
    icon: LandPlot,
    summary: (a) => list(a.ids),
  },
  site_view: {
    label: "View site map",
    icon: Map,
    summary: (a) =>
      [str(a.kind), str(a.scale), list(a.ids)].filter(Boolean).join(" · "),
  },
  // Documents
  list_documents: { label: "List documents", icon: Library },
  list_sections: {
    label: "List sections",
    icon: ListTree,
    summary: (a) => [str(a.doc), str(a.parent)].filter(Boolean).join(" › "),
  },
  read_section: {
    label: "Read section",
    icon: FileText,
    summary: (a) => str(a.section_id),
  },
  read_pages: {
    label: "Read pages",
    icon: FileText,
    summary: (a) =>
      [
        str(a.doc),
        a.start != null
          ? a.end != null && a.end !== a.start
            ? `p.${a.start}–${a.end}`
            : `p.${a.start}`
          : undefined,
      ]
        .filter(Boolean)
        .join(" "),
  },
  search: {
    label: "Search documents",
    icon: Search,
    summary: (a) =>
      [quoted(a.query), str(a.doc) ? `in ${str(a.doc)}` : undefined]
        .filter(Boolean)
        .join(" "),
  },
  view_image: { label: "View page", icon: Image, summary: page },
  zoom: { label: "Zoom into page", icon: ZoomIn, summary: page },
  // Orchestration
  load_playbook: {
    label: "Load playbook",
    icon: BookOpen,
    summary: (a) => str(a.name),
  },
  read_artifact: {
    label: "Read result",
    icon: Archive,
    summary: (a) => str(a.name),
  },
  ask_user: {
    label: "Ask you",
    icon: MessageCircleQuestionMark,
    summary: (a) =>
      Array.isArray(a.questions)
        ? `${a.questions.length} question${a.questions.length === 1 ? "" : "s"}`
        : undefined,
  },
  task: {
    label: "Delegate",
    icon: Users,
    summary: (a) => {
      const type = str(a.subagent_type);
      return type ? (SUBAGENTS[type]?.name ?? humanize(type)) : undefined;
    },
  },
  write_todos: {
    label: "Updated plan",
    icon: ListTodo,
    summary: (a) =>
      Array.isArray(a.todos)
        ? `${a.todos.length} item${a.todos.length === 1 ? "" : "s"}`
        : undefined,
  },
  // Submissions
  submit_parcel: { label: "Submit site", icon: Send },
  submit_zone: { label: "Submit zone", icon: Send },
  submit_notes: {
    label: "Submit notes",
    icon: Send,
    summary: (a) => str(a.label),
  },
  submit_study: { label: "Submit study", icon: ClipboardCheck },
  // Scratch filesystem
  ls: { label: "List files", icon: Folder, summary: (a) => str(a.path) },
  read_file: {
    label: "Read file",
    icon: FileText,
    summary: (a) => str(a.file_path),
  },
  write_file: {
    label: "Write file",
    icon: FilePlus,
    summary: (a) => str(a.file_path),
  },
  edit_file: {
    label: "Edit file",
    icon: FilePen,
    summary: (a) => str(a.file_path),
  },
  glob: { label: "Find files", icon: Files, summary: (a) => str(a.pattern) },
  grep: {
    label: "Search files",
    icon: TextSearch,
    summary: (a) => quoted(a.pattern),
  },
};

/** "find_parcels" -> "Find parcels". */
export function humanize(name: string): string {
  const words = name
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_\-.]+/g, " ")
    .trim()
    .toLowerCase();
  return words ? words[0].toUpperCase() + words.slice(1) : "Tool";
}

/** Label, icon and argument summary of a tool call. */
export function describeToolCall(
  name: string,
  args: Args,
): { label: string; icon: LucideIcon; summary?: string } {
  const known = TOOLS[name];
  if (known) {
    return {
      label: known.label,
      icon: known.icon,
      summary: known.summary?.(args),
    };
  }
  const firstText = Object.values(args).map(str).find(Boolean);
  return {
    label: humanize(name),
    icon: name.startsWith("submit_") ? Send : Wrench,
    summary: firstText,
  };
}

/** Display name and icon of a sub-agent type. */
export function describeSubagent(type: string | undefined): {
  name: string;
  icon: LucideIcon;
} {
  if (type && SUBAGENTS[type]) return SUBAGENTS[type];
  return { name: type ? humanize(type) : "Sub-agent", icon: Users };
}

/** Icon of the questions card. */
export const ASK_USER_ICON = MessageCircleQuestionMark;
