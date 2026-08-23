import { useEffect, useState } from "react";
import Landing from "./views/Landing.jsx";
import Review from "./views/Review.jsx";
import Verify from "./views/Verify.jsx";

// Hash routing rather than paths. The demo is served from our own process, but
// the Xano static host does not document a history fallback, and a refresh that
// 404s on stage is not a risk worth taking for tidier URLs.
const VIEWS = { "": Landing, "#/verify": Verify, "#/review": Review };

function useRoute() {
  const [route, setRoute] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export default function App() {
  const route = useRoute();
  const View = VIEWS[route] || Landing;

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [route]);

  return (
    <>
      <header className="wrap plate">
        <a className="plate__mark" href="#/">Signet</a>
        <span className="plate__gap" aria-hidden="true" />
        <nav className="plate__nav cap">
          <a href="#/verify" aria-current={route === "#/verify" ? "page" : undefined}>Examine</a>
          <a href="#/review" aria-current={route === "#/review" ? "page" : undefined}>Review</a>
        </nav>
      </header>

      <main className="wrap">
        <View />
      </main>

      <footer className="wrap foot">
        Signet publishes an issuer&rsquo;s signing key as a TXT record on the issuer&rsquo;s own
        domain, so verification needs no account and no trust in us.
      </footer>
    </>
  );
}
