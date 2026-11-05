// TACADA – höjdkurvor (en kulle per yta) och sponsorkalkylatorn.
(function () {
  function ritaKurvor(c, del) {
    if (del === undefined) del = 1;
    var r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    if (!r.width || !r.height) return;
    c.width = r.width * d; c.height = r.height * d;
    var g = c.getContext('2d'); g.scale(d, d);
    var p = (c.dataset.kulle || '0.8,0.3').split(',').map(Number);
    var cx = p[0] * r.width, cy = p[1] * r.height;
    var max = Math.hypot(r.width, r.height) * 0.75, n = 22, fro = cx * 0.013 + cy * 0.007;
    for (var i = 1; i <= n; i++) {
      var rad = max * i / n;
      // del 0-1: varje kurva ritas runt, de inre först.
      var andel = Math.max(0, Math.min(1, del * 1.8 - (i - 1) / n * .8));
      if (andel <= 0) continue;
      g.beginPath();
      for (var a = 0; a <= (Math.PI * 2 + 0.01) * andel; a += 0.04) {
        var w = 1 + 0.09 * Math.sin(3 * a + fro + i * 0.15) + 0.05 * Math.sin(5 * a - fro * 1.7 + i * 0.1) + 0.03 * Math.sin(9 * a + i * 0.3);
        var x = cx + Math.cos(a) * rad * w * 1.25, y = cy + Math.sin(a) * rad * w * 0.8;
        if (a === 0) g.moveTo(x, y); else g.lineTo(x, y);
      }
      g.strokeStyle = 'rgba(243,237,226,' + (0.15 * (1 - i / (n + 4))) + ')';
      g.lineWidth = 0.9; g.stroke();
    }
  }
  function allaKurvor() { document.querySelectorAll('canvas.topo').forEach(function (c) { ritaKurvor(c); }); }
  var stilla = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // Höjdkurvorna ritas fram inifrån och ut första gången ytan syns.
  if (!stilla && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (poster) {
      poster.forEach(function (p) {
        if (!p.isIntersecting) return;
        io.unobserve(p.target);
        var c = p.target, t0 = performance.now();
        (function steg(nu) {
          var t = Math.min(1, (nu - t0) / 2200);
          ritaKurvor(c, t);
          if (t < 1) requestAnimationFrame(steg);
        })(t0);
      });
    }, { threshold: .15 });
    document.querySelectorAll('canvas.topo').forEach(function (c) { ritaKurvor(c, 0); io.observe(c); });
  } else allaKurvor();

  // Rubriker, kort och listor glider in när de kommer in i bild.
  if (!stilla && 'IntersectionObserver' in window) {
    document.documentElement.classList.add('js-rorelse');
    var sel = '.sek .rubrikgrupp, .sek .del, .sek .vinster li, .sek .stilar li, .band > div, .sek .panel, .sek .referens, .sek .lank-pil';
    var iSikt = new IntersectionObserver(function (poster) {
      poster.forEach(function (p) { if (p.isIntersecting) { p.target.classList.add("syns"); iSikt.unobserve(p.target); } });
    }, { threshold: .12, rootMargin: '0px 0px -6% 0px' });
    document.querySelectorAll(sel).forEach(function (el) {
      var syskon = [].indexOf.call(el.parentNode.children, el);
      el.classList.add('avsloj'); el.style.transitionDelay = Math.min(syskon, 5) * 90 + 'ms';
      iSikt.observe(el);
    });
  }
  var t; window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(allaKurvor, 150); });

  var hal = document.getElementById('kalk-hal'), pris = document.getElementById('kalk-pris');
  if (hal && pris) {
    var kr = function (v) { return v.toLocaleString('sv-SE').replace(/ /g, ' ') + ' kr'; };
    var visa = function () {
      document.getElementById('kalk-hal-ut').textContent = hal.value;
      document.getElementById('kalk-pris-ut').textContent = kr(+pris.value);
      document.getElementById('kalk-summa').textContent = kr(hal.value * pris.value);
    };
    hal.addEventListener('input', visa); pris.addEventListener('input', visa); visa();
  }
})();
