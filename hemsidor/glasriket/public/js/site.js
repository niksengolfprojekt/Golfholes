// Glasrikets GK – liten och fristående. Inga kakor.
(function () {
  // QR-koden på teeskylten pekar på /banan/hal-NN/?q=hNN. Med besöksräknaren påslagen
  // registreras ett "QR-besök" med hålets nummer, och ?q= tas bort ur adressfältet.
  try {
    var q = new URLSearchParams(location.search).get('q');
    if (q && /^h(0[1-9]|1[0-8])$/.test(q) && typeof window.plausible === 'function') {
      window.plausible('QR-besök', { props: { hal: q } });
      history.replaceState(null, '', location.pathname + location.hash);
    }
  } catch (e) { /* äldre webbläsare: inget räknas, sidan fungerar ändå */ }

  // Mobilmenyn stängs när man väljer en länk eller trycker Esc
  var meny = document.querySelector('.mobilmeny');
  if (meny) {
    meny.addEventListener('click', function (h) { if (h.target.tagName === 'A') meny.open = false; });
    document.addEventListener('keydown', function (h) { if (h.key === 'Escape') meny.open = false; });
  }
})();
