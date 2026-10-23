// A dead <script> tag is a no-op; a failed ESM import would break the dev graph.
if (import.meta.env.DEV) {
  const agent = document.createElement("script");
  agent.src = "http://localhost:8097";
  agent.async = true;
  agent.onerror = () => {};
  document.head.appendChild(agent);
}
