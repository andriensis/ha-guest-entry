import { render } from "preact";
import { App } from "./app";
import "./style.css";

render(<App />, document.getElementById("app")!);

// Register service worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // SW registration is best-effort
    });
  });
}
