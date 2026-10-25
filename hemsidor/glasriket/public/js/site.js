// Glasrikets GK – liten och fristående. Inga kakor.
(function () {
  document.documentElement.classList.add('js');
  var lugn = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  // QR-koden på teeskylten pekar på /banan/hal-NN/?q=hNN. Med besöksräknaren påslagen
  // registreras ett "QR-besök" med egenskapen q = hNN, och ?q= tas bort ur adressfältet.
  // Klick på sponsorns länk blir "Sponsorklick" med egenskapen hal = hNN.
  // Samma namn som sponsorrapporten läser (golfholes/statistik.py).
  try {
    var q = new URLSearchParams(location.search).get('q');
    if (q && /^h(0[1-9]|1[0-8])$/.test(q) && typeof window.plausible === 'function') {
      window.plausible('QR-besök', { props: { q: q } });
      history.replaceState(null, '', location.pathname + location.hash);
    }
    document.addEventListener('click', function (h) {
      var a = h.target.closest && h.target.closest('a[data-hal]');
      if (a && typeof window.plausible === 'function') window.plausible('Sponsorklick', { props: { hal: a.dataset.hal } });
    });
  } catch (e) { /* äldre webbläsare: inget räknas, sidan fungerar ändå */ }

  // Mobilmenyn stängs när man väljer en länk eller trycker Esc
  var meny = document.querySelector('.mobilmeny');
  if (meny) {
    meny.addEventListener('click', function (h) { if (h.target.tagName === 'A') meny.open = false; });
    document.addEventListener('keydown', function (h) { if (h.key === 'Escape') meny.open = false; });
  }

  // Startsidan: flygningen över hål 14. Avståndet till flaggan följer filmen (ett värde per kvarts sekund).
  var film = document.querySelector('[data-film]');
  var snal = navigator.connection && navigator.connection.saveData;
  if (film && !lugn && !snal) {
    var tal = document.querySelector('[data-meter]');
    var text = document.querySelector('[data-meter-text]');
    var knapp = document.querySelector('[data-film-knapp]');
    var meter = null, pausad = false, ruta = 0;
    fetch(film.querySelector('source').getAttribute('src').replace('flygning.mp4', 'avstand.json')).then(function (r) { return r.json(); }).then(function (m) { meter = m; });
    film.preload = 'auto';
    var rita = function () {
      if (meter && tal) {
        var t = film.currentTime, i = Math.min(meter.length - 1, Math.floor(t * 4));
        tal.textContent = meter[i];
        text.textContent = meter[i] < meter[0] ? 'kvar till flaggan' : 'från tee 56 till flaggan';
        film.classList.toggle('tona', film.duration - t < 0.5);
      }
      if (!film.paused) ruta = requestAnimationFrame(rita);
    };
    film.addEventListener('play', function () { cancelAnimationFrame(ruta); ruta = requestAnimationFrame(rita); });
    if (knapp) {
      knapp.hidden = false;
      knapp.addEventListener('click', function () {
        pausad = !pausad;
        knapp.setAttribute('aria-pressed', pausad);
        knapp.setAttribute('aria-label', pausad ? 'Spela filmen' : 'Pausa filmen');
        if (pausad) film.pause(); else film.play();
      });
    }
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (e) {
        if (e[0].isIntersecting && !pausad) { var p = film.play(); if (p) p.catch(function () {}); }
        else film.pause();
      }, { threshold: 0.25 }).observe(film);
    } else { film.play(); }
  }

  // Startsidan: kartan i fyra årstider. Bilderna laddas först när någon väljer årstiden.
  var karta = document.querySelector('[data-karta]');
  if (karta) {
    document.querySelectorAll('[data-arstid]').forEach(function (b) {
      b.addEventListener('click', function () {
        var a = b.dataset.arstid;
        document.querySelectorAll('[data-arstid]').forEach(function (x) { x.setAttribute('aria-pressed', x === b); });
        karta.querySelectorAll('[data-lager]').forEach(function (img) {
          if (img.dataset.lager === a && img.dataset.src) {
            img.srcset = img.dataset.srcset; img.src = img.dataset.src;
            delete img.dataset.src;
          }
          img.classList.toggle('aktiv', img.dataset.lager === a);
        });
      });
    });
    // Siffrorna tänds en efter en, hål 1 till 18, första gången kartan syns
    if (!lugn && 'IntersectionObserver' in window) {
      var o = new IntersectionObserver(function (e) {
        if (e[0].isIntersecting) { karta.classList.add('runda'); o.disconnect(); }
      }, { threshold: 0.4 });
      o.observe(karta);
    }
    var ruta2 = document.querySelector('[data-karta-hal]');
    var visa = function (pin) {
      karta.querySelectorAll('.pin.vald').forEach(function (p) { p.classList.remove('vald'); });
      pin.classList.add('vald');
      pin.visadTid = Date.now();
      var d = pin.dataset;
      ruta2.innerHTML = '<div class="karta-kort">' + (d.bild ? '<img src="' + d.bild + '" alt="" width="96" height="120">' : '<span></span>') +
        '<div><p class="karta-kort-nr">' + d.nr + '</p><p class="karta-kort-fakta">Par ' + d.par + ' · ' + d.langd + ' m</p>' +
        (d.rubrik ? '<p class="karta-kort-rubrik">' + d.rubrik + '</p>' : '') +
        '<a class="pil" href="' + pin.getAttribute('href') + '">Gå till hål ' + d.nr + '</a></div></div>';
    };
    karta.querySelectorAll('.pin').forEach(function (pin) {
      pin.addEventListener('mouseenter', function () { if (matchMedia('(hover: hover)').matches) visa(pin); });
      pin.addEventListener('focus', function () { visa(pin); });
      pin.addEventListener('click', function (h) {
        // Första trycket visar hålet bredvid kartan, andra trycket går till hålets sida.
        // (Ett tryck på mobilen ger fokus och klick samtidigt – därför tidsgränsen.)
        if (!pin.classList.contains('vald') || Date.now() - pin.visadTid < 500) {
          h.preventDefault(); visa(pin);
          if (window.innerWidth < 900) ruta2.scrollIntoView({ behavior: lugn ? 'auto' : 'smooth', block: 'center' });
        }
      });
    });
  }

  // Delar som glider in när de kommer in i bild
  var delar = document.querySelectorAll('[data-visa]');
  if (!lugn && 'IntersectionObserver' in window) {
    var obs = new IntersectionObserver(function (e) {
      e.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('syns'); obs.unobserve(x.target); } });
    }, { rootMargin: '0px 0px -10% 0px' });
    delar.forEach(function (d) { obs.observe(d); });
  } else {
    delar.forEach(function (d) { d.classList.add('syns'); });
  }
})();
