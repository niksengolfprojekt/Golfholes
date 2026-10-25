// TACADA – höjdkurvor (en kulle per yta) och sponsorkalkylatorn.
(function () {
  function ritaKurvor(c) {
    var r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    if (!r.width || !r.height) return;
    c.width = r.width * d; c.height = r.height * d;
    var g = c.getContext('2d'); g.scale(d, d);
    var p = (c.dataset.kulle || '0.8,0.3').split(',').map(Number);
    var cx = p[0] * r.width, cy = p[1] * r.height;
    var max = Math.hypot(r.width, r.height) * 0.75, n = 22, fro = cx * 0.013 + cy * 0.007;
    for (var i = 1; i <= n; i++) {
      var rad = max * i / n;
      g.beginPath();
      for (var a = 0; a <= Math.PI * 2 + 0.01; a += 0.04) {
        var w = 1 + 0.09 * Math.sin(3 * a + fro + i * 0.15) + 0.05 * Math.sin(5 * a - fro * 1.7 + i * 0.1) + 0.03 * Math.sin(9 * a + i * 0.3);
        var x = cx + Math.cos(a) * rad * w * 1.25, y = cy + Math.sin(a) * rad * w * 0.8;
        if (a === 0) g.moveTo(x, y); else g.lineTo(x, y);
      }
      g.strokeStyle = 'rgba(243,237,226,' + (0.15 * (1 - i / (n + 4))) + ')';
      g.lineWidth = 0.9; g.stroke();
    }
  }
  function allaKurvor() { document.querySelectorAll('canvas.topo').forEach(ritaKurvor); }
  allaKurvor();
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
