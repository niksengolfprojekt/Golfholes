// Glasrikets GK – liten och fristående. Inga kakor.
(function () {
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
})();
