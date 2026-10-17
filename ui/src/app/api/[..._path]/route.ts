import { initApiPassthrough } from "langgraph-nextjs-api-passthrough";

// Proxies /api/* to the agent server, adding its API key server-side, for deployments where
// the browser must not talk to the agent server directly. Point NEXT_PUBLIC_API_URL at
// "<this site>/api" to use it.

export const { GET, POST, PUT, PATCH, DELETE, OPTIONS, runtime } =
  initApiPassthrough({
    apiUrl: process.env.AGENT_SERVER_URL ?? "remove-me",
    apiKey: process.env.AGENT_SERVER_API_KEY ?? "remove-me",
    runtime: "edge",
    disableWarningLog: true,
  });
