// TACADA startsidan: banrundan (en påhittad bana ovanifrån, ett halvt varv, ner på tee på hål 7)
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

    // Påhittad bana (ingen riktig klubb). Terrängen och trädhöjderna är framräknade ur
    // banbilden med hemsida/verktyg/fiktiv_bana.py. Koordinater i meter från banbildens nedre vänstra hörn.
    var HAL = '7';
    var PINS = {1:[485.6,1349.6],2:[859.1,1256.3],3:[762.0,901.4],4:[373.5,1047.1],5:[97.1,938.8],6:[649.9,804.3],7:[179.3,569.0],8:[407.1,785.6],9:[810.6,733.3],10:[425.8,341.1],11:[545.4,438.2],12:[833.0,169.3],13:[216.6,131.9],14:[257.7,591.4],15:[859.1,542.8],16:[709.7,669.8],17:[582.7,606.3],18:[224.1,766.9]};
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
        var el = document.createElement('div'); el.className = 'nal' + (n === HAL ? ' fjorton' : ''); el.textContent = n; nalar.appendChild(el);
        var x = PINS[n][0] - cE, y = PINS[n][1] - cN;
        return { n: +n, el: el, p: new THREE.Vector3(x, y, mark(x, y) + 3) };
      });

      // Tee på hål 7 och siktet 150 m ut längs mittlinjen (hålet går rakt norrut).
      var tee56 = { x: 192.0 - cE, y: 217.9 - cN }, sikte = { x: 183.0 - cE, y: 367.9 - cN };
      var teeZ = mark(tee56.x, tee56.y) + 1.6, sikteZ = mark(sikte.x, sikte.y);
      var start = { d: 2600, tx: 0, ty: 0 }, N = [], W = 1, H = 1;

      function storlek() {
        W = steg.clientWidth; H = steg.clientHeight;
        renderer.setSize(W, H, false); cam.aspect = W / H; cam.updateProjectionMatrix();
        var tv = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
        if (W > 760) { var d = T.H * .6 / tv; start = { d: d, tx: -d * tv * cam.aspect * .32, ty: d * tv * .08 }; } // Banan lite mindre och lägre, så menyn får fri yta ovanför.
        else { var dm = T.H * 1.3 / tv, hv = dm * tv; start = { d: dm, tx: 0, ty: -(hv - T.H * .5 - hv * .19) }; } // Mobil: banan i övre halvan, texten under.
        var slutLut = THREE.MathUtils.radToDeg(Math.atan2(teeZ - sikteZ, 150));
        // Nyckelbilder: läge i scroll, vinkel runt banan, lutning, avstånd, siktpunkt.
        N = [
          { f: 0, th: 0, fi: 89, d: start.d, tx: start.tx, ty: start.ty },
          // Ett svep ut över sjön och tillbaka, inget helt varv. Hål 7 spelas norrut, så vi landar med vinkel 0.
          { f: .3, th: -55, fi: 50, d: start.d * .78, tx: -40, ty: 120 },
          { f: .6, th: -95, fi: 32, d: start.d * .5, tx: -120, ty: -220 },
          { f: .82, th: -22, fi: 18, d: 330, tx: sikte.x, ty: sikte.y },
          { f: .94, th: 0, fi: slutLut, d: 150, tx: sikte.x, ty: sikte.y },
          { f: 1, th: 0, fi: slutLut, d: 150, tx: sikte.x, ty: sikte.y }
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
          var syn = (p.n === +HAL ? Math.max(0, 1 - Math.max(0, f - .82) / .06) : nalSyn) * (v.z < 1 ? 1 : 0) * (tand ? 1 : 0);
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
  // ---------------- Slag för slag (hål 7) ----------------
  var slag = document.getElementById('slag');
  if (slag) {
    var fas = [].slice.call(slag.querySelectorAll('.fas'));
    var s1 = slag.querySelector('.s1'), s2 = slag.querySelector('.s2'), boll = slag.querySelector('.boll');
    var l1 = slag.querySelector('.l1'), flagga = slag.querySelector('.flagga');
    var a1 = slag.querySelector('.a1'), a2 = slag.querySelector('.a2'), skylt = slag.querySelector('.namnskylt');
    var L1 = s1.getTotalLength(), L2 = s2.getTotalLength();
    [[s1, L1], [s2, L2]].forEach(function (x) { x[0].style.strokeDasharray = x[1]; x[0].style.strokeDashoffset = x[1]; });
    var klamp = function (v) { return Math.max(0, Math.min(1, v)); };
    var ease = function (t) { return 1 - Math.pow(1 - t, 2.2); };
    function ritaSlag(f) {
      fas.forEach(function (k) { k.classList.toggle('pa', f >= +k.dataset.fran && f < +k.dataset.till); });
      // Utslaget ritas mellan 4 och 30 %, inspelet mellan 40 och 64 %.
      var t1 = ease(klamp((f - .04) / .26));
      var t2 = ease(klamp((f - .4) / .24));
      s1.style.strokeDashoffset = L1 * (1 - t1);
      s2.style.strokeDashoffset = L2 * (1 - t2);
      var pt = t2 > 0 ? s2.getPointAtLength(L2 * t2) : s1.getPointAtLength(L1 * t1);
      boll.setAttribute('cx', pt.x); boll.setAttribute('cy', pt.y);
      boll.setAttribute('r', 6 + 5 * Math.sin(Math.PI * (t2 > 0 ? t2 : t1))); // bollen "lyfter" mitt i flykten
      l1.style.opacity = t1 >= 1 ? 1 - klamp((f - .3) / .1) * .6 : 0;
      l1.setAttribute('r', 9 + 22 * klamp((f - .3) / .1));
      a1.classList.toggle('syns', t1 >= 1);
      a2.classList.toggle('syns', t2 >= 1);
      flagga.classList.toggle('upp', f > .34);
      skylt.classList.toggle('syns', f > .72);
    }
    // Eric 2026-11-05: spelas som en film när sektionen kommer i bild, scrollen styr inte.
    var LANGD = 9000, igen = slag.querySelector('.igen'), spelar = false;
    function spela() {
      if (spelar) return;
      spelar = true; igen.classList.remove('syns');
      if (stilla) { ritaSlag(1); spelar = false; igen.classList.add('syns'); return; }
      var t0 = performance.now();
      (function ruta(nu) {
        var f = Math.min(1, (nu - t0) / LANGD);
        ritaSlag(f);
        if (f < 1) requestAnimationFrame(ruta); else { spelar = false; igen.classList.add('syns'); }
      })(t0);
    }
    ritaSlag(0);
    igen.addEventListener('click', spela);
    if ('IntersectionObserver' in window) {
      var obs = new IntersectionObserver(function (p) { if (p[0].isIntersecting) { obs.disconnect(); spela(); } }, { threshold: .55 });
      obs.observe(slag);
    } else spela();
  }

  // ---------------- Skylten byggs ----------------
  var bygge = document.getElementById('skyltbygge');
  if (bygge) {
    var plattor = [].slice.call(bygge.querySelectorAll('.platta'));
    var rader = [].slice.call(bygge.querySelectorAll('li'));
    // Varje platta kommer från sitt håll och landar på stolparna.
    var fran = [{ x: 0, y: -70, r: -8 }, { x: 60, y: 0, r: 6 }, { x: 0, y: 70, r: 4 }];
    function bygg() {
      if (!synlig(bygge)) return;
      var f = framsteg(bygge);
      plattor.forEach(function (pl, i) {
        var t = Math.max(0, Math.min(1, (f - .06 - i * .27) / .2));
        if (stilla) t = t > 0 ? 1 : 0;
        var e = 1 - Math.pow(1 - t, 3), o = fran[i];
        pl.style.opacity = Math.min(1, t * 2.5);
        pl.style.transform = 'translate(' + (o.x * (1 - e)) + 'vw,' + (o.y * (1 - e)) + 'vh) rotate(' + (o.r * (1 - e)) + 'deg)';
      });
      var aktivRad = Math.max(0, Math.min(2, Math.floor((f - .06) / .27)));
      rader.forEach(function (r, i) { r.classList.toggle('pa', i <= aktivRad); });
    }
    addEventListener('scroll', bygg, { passive: true }); addEventListener('resize', bygg); bygg();
  }
})();
