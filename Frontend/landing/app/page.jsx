import './globals.css'

export const metadata = {
  title: 'SignalMind — OutOfBlack',
  description:
    'SignalMind / OutOfBlack — aerial search, signal detection and approximate localization.',
}

export default function Home() {
  return (
    <main>
      <div className="noise" />
      <header className="nav">
        <a className="brand" href="#">
          <span className="mark">SM</span>
          <span>SignalMind</span>
        </a>
        <nav>
          <a href="#mission">Misja</a>
          <a href="#system">System</a>
          <a href="#contact">Kontakt</a>
        </nav>
        <a className="navCta" href="#contact">
          Poznaj projekt <span>↗</span>
        </a>
      </header>

      <section className="hero">
        <div className="copy">
          <div className="eyebrow">
            <i /> OUTOFBLACK / SEARCH & RESCUE
          </div>
          <h1>
            Znajdujemy
            <br />
            <em>sygnał.</em>
            <br />
            Odnajdujemy ludzi.
          </h1>
          <p>
            Autonomiczna sieć dronów do rozpoznania zniszczonej infrastruktury i
            przybliżonej lokalizacji osób na podstawie dostępnych sygnałów
            GSM/Wi‑Fi.
          </p>
          <div className="actions">
            <a className="primary" href="#system">
              Zobacz jak działa <span>→</span>
            </a>
            <a className="ghost" href="#mission">
              Nasza misja
            </a>
          </div>
          <div className="metrics">
            <div>
              <b>01</b>
              <span>Rozpoznanie</span>
            </div>
            <div>
              <b>02</b>
              <span>Detekcja sygnału</span>
            </div>
            <div>
              <b>03</b>
              <span>Lokalizacja</span>
            </div>
          </div>
        </div>

        <div className="radarWrap">
          <div className="radar">
            <div className="sweep" />
            <div className="ring r1" />
            <div className="ring r2" />
            <div className="ring r3" />
            <div className="line x" />
            <div className="line y" />
            <span className="point p1" />
            <span className="point p2" />
            <span className="point p3" />
            <span className="point p4" />
            <span className="drone d1">◆</span>
            <span className="drone d2">◆</span>
            <span className="drone d3">◆</span>
            <div className="target">+</div>
            <span className="label top">SIGNAL FIELD</span>
            <span className="label bottom">LIVE / 24.7 MHz</span>
          </div>
          <div className="hud cardA">
            <small>ACTIVE NODES</small>
            <b>07</b>
            <span>DRONES</span>
          </div>
          <div className="hud cardB">
            <small>LOC. CONFIDENCE</small>
            <b>86%</b>
            <span>ESTIMATED AREA</span>
          </div>
        </div>
      </section>
    </main>
  )
}
