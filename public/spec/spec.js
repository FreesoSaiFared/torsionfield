(() => {
  const root = document.documentElement;
  const search = document.querySelector('#spec-search');
  const tocLinks = [...document.querySelectorAll('.toc a[data-section]')];
  const sections = [...document.querySelectorAll('.spec-section')];
  const progress = document.querySelector('.reading-progress span');
  const modeButtons = [...document.querySelectorAll('[data-view-mode]')];
  const printButton = document.querySelector('[data-print]');

  const setMode = mode => {
    root.dataset.view = mode;
    modeButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.viewMode === mode)));
    try { localStorage.setItem('torsionfield-spec-view', mode); } catch {}
  };

  let savedMode = 'comfortable';
  try { savedMode = localStorage.getItem('torsionfield-spec-view') || savedMode; } catch {}
  if (!['comfortable', 'compact'].includes(savedMode)) savedMode = 'comfortable';
  setMode(savedMode);
  modeButtons.forEach(button => button.addEventListener('click', () => setMode(button.dataset.viewMode)));
  printButton?.addEventListener('click', () => window.print());
  const live = document.createElement('p');
  live.className = 'sr-only';
  live.setAttribute('aria-live', 'polite');
  search?.insertAdjacentElement('afterend', live);

  search?.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    sections.forEach(section => {
      const match = !query || section.textContent.toLowerCase().includes(query);
      section.classList.toggle('is-filtered', !match);
      const number = section.id.replace('section-', '');
      const link = document.querySelector(`.toc a[data-section="${number}"]`);
      link?.classList.toggle('is-hidden', !match);
      if (match) visible += 1;
    });
    document.querySelectorAll('.part-opener').forEach(part => {
      let next = part.nextElementSibling;
      let hasVisible = false;
      while (next && !next.classList.contains('part-opener')) {
        if (next.classList.contains('spec-section') && !next.classList.contains('is-filtered')) hasVisible = true;
        next = next.nextElementSibling;
      }
      part.classList.toggle('is-filtered', query && !hasVisible);
    });
    live.textContent = query ? `${visible} sections match “${search.value}”.` : 'All sections visible.';
  });

  const updateProgress = () => {
    if (!progress) return;
    const max = document.documentElement.scrollHeight - innerHeight;
    const value = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 0;
    progress.style.width = `${value * 100}%`;
  };
  addEventListener('scroll', updateProgress, { passive: true });
  addEventListener('resize', updateProgress, { passive: true });
  updateProgress();
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      const active = entries
        .filter(entry => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!active) return;
      tocLinks.forEach(link => link.removeAttribute('aria-current'));
      const number = active.target.id.replace('section-', '');
      document.querySelector(`.toc a[data-section="${number}"]`)?.setAttribute('aria-current', 'location');
    }, { rootMargin: '-15% 0px -70% 0px', threshold: [0, 0.01] });
    sections.forEach(section => observer.observe(section));
  }

  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      search?.focus();
    }
    if (event.key === 'Escape' && document.activeElement === search) {
      search.value = '';
      search.dispatchEvent(new Event('input'));
      search.blur();
    }
  });
})();
