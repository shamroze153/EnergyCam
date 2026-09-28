/* Mimar AI — site interactions: navigation, reveal on scroll, contact form, copy buttons. */
(function () {
  'use strict';
  var WA = '923352634093';

  /* services mega menu: click to toggle, hover on devices that can hover */
  document.querySelectorAll('.nav-drop').forEach(function (drop) {
    var btn = drop.querySelector('button');
    var hoverTimer;
    function set(open) { drop.classList.toggle('open', open); btn.setAttribute('aria-expanded', String(open)); }
    btn.addEventListener('click', function (e) { e.stopPropagation(); set(!drop.classList.contains('open')); });
    if (window.matchMedia('(hover: hover)').matches) {
      drop.addEventListener('mouseenter', function () { clearTimeout(hoverTimer); set(true); });
      drop.addEventListener('mouseleave', function () { hoverTimer = setTimeout(function () { set(false); }, 180); });
    }
    document.addEventListener('click', function (e) { if (!drop.contains(e.target)) set(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && drop.classList.contains('open')) { set(false); btn.focus(); } });
  });

  /* mobile drawer */
  var drawer = document.getElementById('drawer');
  var burger = document.querySelector('.burger');
  if (drawer && burger) {
    var closeBtn = drawer.querySelector('.drawer-close');
    function openDrawer(open) {
      drawer.classList.toggle('open', open); burger.setAttribute('aria-expanded', String(open));
      document.documentElement.style.overflow = open ? 'hidden' : '';
      if (open && closeBtn) closeBtn.focus(); else burger.focus();
    }
    burger.addEventListener('click', function () { openDrawer(true); });
    if (closeBtn) closeBtn.addEventListener('click', function () { openDrawer(false); });
    drawer.addEventListener('keydown', function (e) { if (e.key === 'Escape') openDrawer(false); });
    drawer.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { openDrawer(false); }); });
  }

  /* reveal on scroll: only for elements that start below the first screen, so nothing visible at load is hidden */
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduce && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting || e.boundingClientRect.top < 0) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    /* safety net: never leave content hidden, even if an observer callback is missed */
    var maxSeen = window.scrollY + vh;
    function revealPassed() {
      maxSeen = Math.max(maxSeen, window.scrollY + window.innerHeight);
      document.querySelectorAll('.rv:not(.in)').forEach(function (el) { if (el.getBoundingClientRect().top + window.scrollY < maxSeen) el.classList.add('in'); });
    }
    window.addEventListener('scroll', function () { maxSeen = Math.max(maxSeen, window.scrollY + window.innerHeight); clearTimeout(window.__rvT); window.__rvT = setTimeout(revealPassed, 100); }, { passive: true });
    var vh = window.innerHeight;
    document.querySelectorAll('[data-reveal]').forEach(function (el, i) {
      if (el.getBoundingClientRect().top > vh * 0.9) {
        el.classList.add('rv'); el.style.transitionDelay = (Number(el.getAttribute('data-reveal')) || 0) * 80 + 'ms'; io.observe(el);
      }
    });
  }

  /* copy buttons */
  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      var text = b.getAttribute('data-copy'), label = b.textContent;
      function done(ok) { b.textContent = ok ? 'Copied' : 'Select and copy'; setTimeout(function () { b.textContent = label; }, 1600); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
      else done(false);
    });
  });

  /* contact form: composes a WhatsApp message or an email from the fields */
  var form = document.getElementById('contact-form');
  if (form) {
    var status = document.getElementById('form-status');
    function compose() {
      var f = new FormData(form);
      var svcs = f.getAll('services');
      var lines = [
        'Hi Mimar AI,',
        '',
        (f.get('message') || '').toString().trim() || 'I would like to talk about my building.',
        '',
        'Name: ' + (f.get('name') || ''),
        f.get('company') ? 'Company: ' + f.get('company') : '',
        f.get('building') ? 'Building type: ' + f.get('building') : '',
        svcs.length ? 'Interested in: ' + svcs.join(', ') : '',
        f.get('email') ? 'Email: ' + f.get('email') : '',
        f.get('phone') ? 'Phone: ' + f.get('phone') : ''
      ].filter(function (l, i) { return l !== '' || i === 1 || i === 3; });
      return { text: lines.join('\n'), name: (f.get('name') || '').toString() };
    }
    function check() {
      if (!form.reportValidity) return true;
      return form.reportValidity();
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!check()) return;
      var m = compose();
      var url = 'https://wa.me/' + WA + '?text=' + encodeURIComponent(m.text);
      window.open(url, '_blank', 'noopener');
      if (status) status.textContent = 'WhatsApp should open with your message ready. Press send there to reach us.';
    });
    var mailBtn = document.getElementById('send-email');
    if (mailBtn) mailBtn.addEventListener('click', function () {
      if (!check()) return;
      var m = compose();
      var subject = 'Enquiry from ' + (m.name || 'the Mimar AI website');
      window.location.href = 'mailto:shamroze341@gmail.com?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(m.text);
      if (status) status.textContent = 'Your email app should open with the message ready. Press send there to reach us.';
    });
  }

  /* year */
  document.querySelectorAll('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });
})();
