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

  // Årstiden styr bilderna: kartan och hålbilderna visas som banan ser ut just nu.
  // Vår april–maj, sommar juni–augusti, höst september–oktober, vinter november–mars.
  // ?arstid=vinter (osv.) visar en annan årstid under besöket – för granskning.
  var arstid = ['vinter', 'vinter', 'vinter', 'var', 'var', 'sommar', 'sommar', 'sommar', 'host', 'host', 'vinter', 'vinter'][new Date().getMonth()];
  try {
    var vald = new URLSearchParams(location.search).get('arstid');
    if (/^(var|sommar|host|vinter)$/.test(vald || '')) sessionStorage.setItem('arstid', vald);
    arstid = sessionStorage.getItem('arstid') || arstid;
  } catch (e) { /* utan lagring: dagens årstid */ }
  document.documentElement.dataset.arstid = arstid;
  if (arstid !== 'sommar') {
    document.querySelectorAll('img[data-arstid-' + arstid + ']').forEach(function (img) {
      var s = img.getAttribute('data-arstid-' + arstid);
      if (img.hasAttribute('srcset')) img.srcset = s;
      img.src = s.split(' ')[0];
    });
    document.querySelectorAll('[data-arstid-text]').forEach(function (p) {
      var t = p.getAttribute('data-text-' + arstid);
      if (t) p.textContent = t;
    });
  }

  // Startsidan: avståndet till flaggan på hål 14 räknas ner medan man scrollar förbi toppbilden
  var scen = document.querySelector('[data-scen]');
  var tal = document.querySelector('[data-meter]');
  if (scen && tal && !lugn) {
    var fran = +tal.dataset.fran, text = document.querySelector('[data-meter-text]'), vantar = false;
    var rakna = function () {
      vantar = false;
      var del = Math.min(1, Math.max(0, window.scrollY / (scen.offsetHeight * 0.85)));
      var m = Math.round(fran * (1 - del));
      tal.textContent = m;
      text.textContent = m === fran ? 'från tee 56 till flaggan' : m > 0 ? 'kvar till flaggan' : 'i hål';
    };
    window.addEventListener('scroll', function () { if (!vantar) { vantar = true; requestAnimationFrame(rakna); } }, { passive: true });
    rakna();
  }

  // Startsidan: kartan visar årstidens bild (laddas bara den som behövs)
  var karta = document.querySelector('[data-karta]');
  if (karta) {
    karta.querySelectorAll('[data-lager]').forEach(function (img) {
      var ratt = img.dataset.lager === arstid;
      if (ratt && img.dataset.src) {
        img.srcset = img.dataset.srcset; img.src = img.dataset.src;
        delete img.dataset.src;
      }
      img.classList.toggle('aktiv', ratt);
    });
    // Siffrorna tänds en efter en, hål 1 till 18, första gången kartan syns
    if (!lugn && 'IntersectionObserver' in window) {
      var o = new IntersectionObserver(function (e) {
        if (e[0].isIntersecting) { karta.classList.add('runda'); o.disconnect(); }
      }, { threshold: 0.4 });
      o.observe(karta);
    }
    var ruta2 = document.querySelector('[data-karta-hal]');
    var sponsorruta = document.querySelector('[data-sponsorruta]');
    var sponsorsida = document.querySelector('a[href*="halsponsorer"]');
    var visa = function (pin) {
      karta.querySelectorAll('.pin.vald').forEach(function (p) { p.classList.remove('vald'); });
      pin.classList.add('vald');
      pin.visadTid = Date.now();
      var d = pin.dataset, bild = pin.getAttribute('data-bild-' + arstid) || d.bild;
      ruta2.innerHTML = '<div class="karta-kort">' + (bild ? '<img src="' + bild + '" alt="" width="96" height="120">' : '<span></span>') +
        '<div><p class="karta-kort-nr">' + d.nr + '</p><p class="karta-kort-fakta">Par ' + d.par + ' · ' + d.langd + ' m</p>' +
        (d.rubrik ? '<p class="karta-kort-rubrik">' + d.rubrik + '</p>' : '') +
        '<a class="pil" href="' + pin.getAttribute('href') + '">Gå till hål ' + d.nr + '</a></div></div>';
      // Rutan för hålsponsorn: loggan om den finns, annars namnet, annars en ledig plats
      if (sponsorruta) {
        var namn = d.sponsor, inne;
        if (namn) {
          inne = d.sponsorLogga ? '<img src="' + d.sponsorLogga + '" alt="' + namn + '">' : '<span class="sponsorruta-namn">' + namn + '</span>';
          if (d.sponsorUrl) inne = '<a href="' + d.sponsorUrl + '" rel="noopener" data-hal="h' + ('0' + d.nr).slice(-2) + '">' + inne + '</a>';
          sponsorruta.innerHTML = '<p class="sponsorruta-text">' + namn + '-hålet</p><div class="sponsorruta-logga">' + inne + '</div>';
        } else {
          sponsorruta.innerHTML = '<p class="sponsorruta-text">Hålsponsor</p><div class="sponsorruta-logga sponsorruta-ledig">' +
            '<a class="pil" href="' + (sponsorsida ? sponsorsida.getAttribute('href') : '/halsponsorer/') + '">Ge ert företag hål ' + d.nr + '</a></div>';
        }
        sponsorruta.hidden = false;
      }
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
