// TACADA startsidan: banrundan (hela banan ovanifrån, ett halvt varv, ner på tee 14)
// och hålrullen (fyra hål, ett i taget). Båda styrs av scroll.
(function () {
  var stilla = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function framsteg(sek) {
    var r = sek.getBoundingClientRect(), langd = r.height - innerHeight;
    return langd > 0 ? Math.min(1, Math.max(0, -r.top / langd)) : 0;
  }
  function synlig(sek) {
    var r = sek.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight;
  }

  // ---------------- Banrundan ----------------
  var runda = document.getElementById('runda');
  if (runda) startaRunda(runda);

  function startaRunda(sek) {
    var steg = sek.querySelector('.scen'), canvas = sek.querySelector('.bana');
    var kort = [].slice.call(sek.querySelectorAll('.kort'));
    var tee = sek.querySelector('.tee'), hud = sek.querySelector('.hud'), nalar = sek.querySelector('.nalar');

    function bytKort(f) {
      kort.forEach(function (k) { k.classList.toggle('pa', f >= +k.dataset.fran && f < +k.dataset.till); });
      var fo = Math.max(0, Math.min(1, (f - .865) / .065));
      tee.style.opacity = fo; hud.style.opacity = fo;
      sek.classList.toggle('ute', fo > .5);
    }
    // Utan WebGL eller three.js: banbilden står still och texterna byts ändå.
    function reserv() {
      sek.classList.add('utan3d');
      var gaar = function () { bytKort(framsteg(sek)); };
      addEventListener('scroll', gaar, { passive: true }); gaar();
    }
    if (!window.THREE || !window.WebGLRenderingContext) return reserv();

    // Banbilden ligger på Lantmäteriets höjdmodell: 0,372 m per pixel, SWEREF 99 TM.
    // Trädkronorna är höjda till sin uppmätta höjd ur Laserdata Skog.
    var PINS = {1:[491711.0,6306516.8],2:[491588.3,6306140.3],3:[491538.8,6305904.5],4:[491735.1,6305612.3],5:[491755.2,6305433.5],6:[492000.4,6305517.4],7:[491820.7,6305799.4],8:[491955.1,6305757.7],9:[491827.9,6306003.0],10:[491888.4,6306368.7],11:[492047.3,6306044.3],12:[492126.9,6305610.2],13:[492180.1,6306122.8],14:[492311.8,6305911.1],15:[492092.0,6305560.4],16:[491783.1,6305799.4],17:[491733.3,6305972.3],18:[491733.3,6306104.6]};
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true }); } catch (e) { return reserv(); }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0xFCF2EB, 1);
    renderer.outputEncoding = THREE.sRGBEncoding;
    var scene = new THREE.Scene();
    // Dimman i samma papperston som banbildens kant, så att bildens ram inte syns.
    scene.fog = new THREE.Fog(new THREE.Color(0xFCF2EB).convertSRGBToLinear(), 2000, 5000);
    var cam = new THREE.PerspectiveCamera(36, 1, 1, 9000);
    cam.up.set(0, 0, 1);

    fetch('/img/banrunda/terrang.json').then(function (r) { return r.json(); }).then(function (T) {
      var raw = Uint8Array.from(atob(T.data), function (c) { return c.charCodeAt(0); });
      var hz = new Uint16Array(raw.buffer);
      var cE = T.E0 + T.B / 2, cN = T.N0 - T.H / 2;
      var geo = new THREE.PlaneGeometry(T.B, T.H, T.nx - 1, T.ny - 1), pa = geo.attributes.position;
      for (var i = 0; i < pa.count; i++) pa.setZ(i, hz[i] / 100);
      geo.computeVertexNormals();
      var tex = new THREE.TextureLoader().load('/img/banrunda/karta.webp');
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      tex.encoding = THREE.sRGBEncoding;
      scene.add(new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ map: tex })));
      scene.add(new THREE.AmbientLight(0xffffff, .74));
      var sol = new THREE.DirectionalLight(0xfff1dc, .5); sol.position.set(-1, -.35, .55); scene.add(sol);

      function mark(x, y) {
        var gx = (x + T.B / 2) / T.steg, gy = (T.H / 2 - y) / T.steg;
        var x0 = Math.max(0, Math.min(T.nx - 2, Math.floor(gx))), y0 = Math.max(0, Math.min(T.ny - 2, Math.floor(gy)));
        var fx = gx - x0, fy = gy - y0, h = function (a, b) { return hz[b * T.nx + a] / 100; };
        return h(x0, y0) * (1 - fx) * (1 - fy) + h(x0 + 1, y0) * fx * (1 - fy) + h(x0, y0 + 1) * (1 - fx) * fy + h(x0 + 1, y0 + 1) * fx * fy;
      }
      var nal = Object.keys(PINS).map(function (n) {
        var el = document.createElement('div'); el.className = 'nal' + (n === '14' ? ' fjorton' : ''); el.textContent = n; nalar.appendChild(el);
        var x = PINS[n][0] - cE, y = PINS[n][1] - cN;
        return { n: +n, el: el, p: new THREE.Vector3(x, y, mark(x, y) + 3) };
      });

      // Tee 56 på hål 14 och siktet 150 m ut längs mittlinjen.
      var tee56 = { x: 492313 - cE, y: 6305911 - cN }, sikte = { x: 492312.5 - cE, y: 6305761 - cN };
      var teeZ = mark(tee56.x, tee56.y) + 1.6, sikteZ = mark(sikte.x, sikte.y);
      var start = { d: 2600, tx: 0, ty: 0 }, N = [], W = 1, H = 1;

      function storlek() {
        W = steg.clientWidth; H = steg.clientHeight;
        renderer.setSize(W, H, false); cam.aspect = W / H; cam.updateProjectionMatrix();
        var tv = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
        if (W > 760) { var d = T.H * .53 / tv; start = { d: d, tx: -d * tv * cam.aspect * .32, ty: 0 }; }
        else { var dm = T.H * 1.3 / tv, hv = dm * tv; start = { d: dm, tx: 0, ty: -(hv - T.H * .5 - hv * .12) }; } // Mobil: banan i övre halvan, texten under.
        var slutLut = THREE.MathUtils.radToDeg(Math.atan2(teeZ - sikteZ, 150));
        // Nyckelbilder: läge i scroll, vinkel runt banan, lutning, avstånd, siktpunkt.
        N = [
          { f: 0, th: 0, fi: 89, d: start.d, tx: start.tx, ty: start.ty },
          { f: .3, th: 60, fi: 52, d: start.d * .78, tx: 0, ty: -40 },
          { f: .6, th: 125, fi: 34, d: start.d * .5, tx: 140, ty: -120 },
          { f: .82, th: 170, fi: 18, d: 330, tx: sikte.x, ty: sikte.y },
          { f: .94, th: 180, fi: slutLut, d: 150, tx: sikte.x, ty: sikte.y },
          { f: 1, th: 180, fi: slutLut, d: 150, tx: sikte.x, ty: sikte.y }
        ];
      }
      addEventListener('resize', storlek); storlek();

      var K = ['th', 'fi', 'd', 'tx', 'ty'], smooth = function (t) { return t * t * (3 - 2 * t); };
      function interp(f) {
        var i = 0; while (i < N.length - 2 && f > N[i + 1].f) i++;
        var a = N[Math.max(0, i - 1)], b = N[i], c = N[i + 1], d = N[Math.min(N.length - 1, i + 2)];
        var t = Math.min(1, Math.max(0, (f - b.f) / (c.f - b.f))), t2 = t * t, t3 = t2 * t, o = {};
        // Catmull-Rom ger jämn fart genom nyckelbilderna i stället för stopp vid varje.
        K.forEach(function (k) {
          o[k] = i === N.length - 2 ? b[k] + (c[k] - b[k]) * smooth(t)
            : .5 * ((2 * b[k]) + (-a[k] + c[k]) * t + (2 * a[k] - 5 * b[k] + 4 * c[k] - d[k]) * t2 + (-a[k] + 3 * b[k] - 3 * c[k] + d[k]) * t3);
        });
        return o;
      }
      var t0 = performance.now(), v = new THREE.Vector3();
      function ruta(nu) {
        requestAnimationFrame(ruta);
        if (!synlig(sek)) return;
        var f = framsteg(sek), tid = nu - t0, o = interp(f);
        // Något händer direkt: kameran sjunker in över banan och numren tänds ett i taget.
        if (!stilla) { var k = smooth(Math.min(1, tid / 2600)), m = Math.max(0, 1 - f / .1); o.d *= 1 + (1 - k) * .35 * m; o.th += (1 - k) * -14 * m; }
        var th = THREE.MathUtils.degToRad(o.th), fi = THREE.MathUtils.degToRad(o.fi);
        var slut = Math.max(0, Math.min(1, (f - .82) / .12)), tz = sikteZ * slut + (1 - slut) * 18;
        var pos = new THREE.Vector3(o.tx + o.d * Math.cos(fi) * Math.sin(th), o.ty - o.d * Math.cos(fi) * Math.cos(th), tz + o.d * Math.sin(fi));
        pos.z = Math.max(pos.z, mark(pos.x, pos.y) + 1.6);
        cam.position.copy(pos); cam.lookAt(o.tx, o.ty, tz);
        scene.fog.near = o.d * .9 + 200; scene.fog.far = o.d * 2.4 + 600;
        renderer.render(scene, cam);
        var nalSyn = f < .7 ? 1 : Math.max(0, 1 - (f - .7) / .1);
        nal.forEach(function (p, i) {
          v.copy(p.p).project(cam);
          var tand = stilla || tid > 500 + i * 90;
          var syn = (p.n === 14 ? Math.max(0, 1 - Math.max(0, f - .82) / .06) : nalSyn) * (v.z < 1 ? 1 : 0) * (tand ? 1 : 0);
          var sy = (1 - v.y) / 2 * H;
          if (W <= 760) syn *= Math.max(0, Math.min(1, (H * .52 - sy) / 40)); // Mobil: inga nummer över texten.
          p.el.style.opacity = syn; p.el.classList.toggle('syns', tand);
          p.el.style.left = ((v.x + 1) / 2 * W) + 'px'; p.el.style.top = ((1 - v.y) / 2 * H) + 'px';
        });
        bytKort(f);
      }
      requestAnimationFrame(ruta);
    }).catch(reserv);
  }

  // ---------------- Hålrullen ----------------
  var rulle = document.getElementById('halrulle');
  if (rulle) {
    var bilder = [].slice.call(rulle.querySelectorAll('.bilder img'));
    var hal = [].slice.call(rulle.querySelectorAll('.hal'));
    var prickar = [].slice.call(rulle.querySelectorAll('.prickar i'));
    var n = bilder.length, aktiv = 0;
    // Längden räknas upp när ett nytt hål tar över.
    function rakna(el) {
      var mal = +el.parentNode.parentNode.dataset.langd, t0 = performance.now();
      if (stilla) { el.textContent = mal; return; }
      (function steg(nu) {
        var t = Math.min(1, (nu - t0) / 700);
        el.textContent = Math.round(mal * (1 - Math.pow(1 - t, 3)));
        if (t < 1) requestAnimationFrame(steg);
      })(t0);
    }
    function uppdatera() {
      if (!synlig(rulle)) return;
      var f = framsteg(rulle) * n;
      bilder.forEach(function (img, i) {
        var t = f - i - .5;                          // -0,5 när hålet kommer in, 0,5 när det lämnar
        var op = Math.max(0, Math.min(1, 1.6 - Math.abs(t) * 2.4));
        if (i === 0 && t < 0) op = 1;
        if (i === n - 1 && t > 0) op = 1;
        var tt = Math.max(-.5, Math.min(.5, t));
        // Bilden glider uppåt och zoomar sakta mot greenen, som en kamera längs hålet.
        img.style.opacity = op;
        img.style.transform = stilla ? 'none' : 'translateY(' + (-tt * 6) + 'vh) scale(' + (1.04 + tt * .12) + ')';
      });
      var ny = Math.max(0, Math.min(n - 1, Math.floor(f)));
      if (ny !== aktiv) {
        aktiv = ny;
        hal.forEach(function (h, i) { h.classList.toggle('pa', i === ny); });
        prickar.forEach(function (p, i) { p.classList.toggle('pa', i === ny); });
        rakna(hal[ny].querySelector('i'));
      }
    }
    addEventListener('scroll', uppdatera, { passive: true }); addEventListener('resize', uppdatera); uppdatera();
  }
})();
